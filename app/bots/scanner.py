"""
Scanner de acciones.

Filtra el universo de acciones por:
1. Liquidez (volumen, dollar volume, precio mínimo)
2. Fuerza institucional (RS vs SPY, tendencia EMAs, volume spike)
3. Genera un score compuesto para ranking
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockSnapshotRequest
from alpaca.data.timeframe import TimeFrame

from app.bots.config import LiquidityConfig, InstitutionalConfig, ScorerConfig

logger = logging.getLogger(__name__)


class ScanResult:
    """Resultado del scan para un símbolo."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.passes_liquidity = False
        self.passes_institutional = False
        self.relative_strength: float = 0.0
        self.volume_expansion: float = 0.0
        self.trend_quality: float = 0.0
        self.score: float = 0.0

    def __repr__(self):
        return f"ScanResult({self.symbol}, score={self.score:.3f})"


class Scanner:
    """Escanea acciones y genera candidatos rankeados."""

    def __init__(
        self,
        data_client: StockHistoricalDataClient,
        liquidity_config: LiquidityConfig,
        institutional_config: InstitutionalConfig,
        scorer_config: ScorerConfig,
    ):
        self.data_client = data_client
        self.liquidity = liquidity_config
        self.institutional = institutional_config
        self.scorer = scorer_config

    def scan(self, symbols: list[str]) -> list[ScanResult]:
        """Escanea una lista de símbolos y retorna candidatos válidos rankeados."""
        results = []
        spy_bars = self._get_daily_bars("SPY", days=60)
        spy_returns = self._calc_returns(spy_bars) if spy_bars else None

        for symbol in symbols:
            try:
                result = self._evaluate_symbol(symbol, spy_returns)
                if result and result.passes_liquidity and result.passes_institutional:
                    results.append(result)
            except Exception as e:
                logger.debug("Error escaneando %s: %s", symbol, e)

        # Ordenar por score descendente
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _evaluate_symbol(self, symbol: str, spy_returns: Optional[np.ndarray]) -> Optional[ScanResult]:
        """Evalúa un símbolo individual."""
        bars = self._get_daily_bars(symbol, days=220)
        if bars is None or len(bars) < 50:
            return None

        result = ScanResult(symbol)
        closes = np.array([float(bar.close) for bar in bars])
        volumes = np.array([float(bar.volume) for bar in bars])

        # ─── Filtro de liquidez ───
        avg_volume_20 = np.mean(volumes[-20:])
        current_price = closes[-1]
        dollar_volume = avg_volume_20 * current_price

        if avg_volume_20 < self.liquidity.min_avg_volume:
            return None
        if dollar_volume < self.liquidity.min_dollar_volume:
            return None
        if current_price < self.liquidity.min_price:
            return None

        result.passes_liquidity = True

        # ─── Filtro institucional ───
        # Relative Strength vs SPY
        if spy_returns is not None and len(closes) >= self.institutional.rs_lookback_days:
            stock_returns = self._calc_returns_from_closes(closes)
            if stock_returns is not None and len(stock_returns) >= self.institutional.rs_lookback_days:
                rs_stock = np.sum(stock_returns[-self.institutional.rs_lookback_days:])
                rs_spy = np.sum(spy_returns[-self.institutional.rs_lookback_days:]) if len(spy_returns) >= self.institutional.rs_lookback_days else 0
                result.relative_strength = rs_stock - rs_spy
                if result.relative_strength <= 0:
                    return None

        # Tendencia EMAs
        if len(closes) >= self.institutional.ema_long:
            ema_short = self._ema(closes, self.institutional.ema_short)
            ema_mid = self._ema(closes, self.institutional.ema_mid)
            ema_long = self._ema(closes, self.institutional.ema_long)

            if not (ema_short[-1] > ema_mid[-1] > ema_long[-1]):
                return None

            # Trend quality: distancia normalizada entre EMAs
            result.trend_quality = min(1.0, (ema_short[-1] - ema_long[-1]) / ema_long[-1] * 10)
        else:
            return None

        # Volume spike
        current_vol = volumes[-1]
        avg_vol_20 = np.mean(volumes[-20:])
        vol_ratio = current_vol / avg_vol_20 if avg_vol_20 > 0 else 0
        result.volume_expansion = min(1.0, (vol_ratio - 1.0) / (self.institutional.volume_spike_multiplier - 1.0))

        if vol_ratio < self.institutional.volume_spike_multiplier:
            # No descartamos, pero reduce el score
            result.volume_expansion = max(0.0, result.volume_expansion)

        result.passes_institutional = True

        # ─── Score compuesto ───
        result.score = (
            self.scorer.weight_relative_strength * min(1.0, result.relative_strength * 5) +
            self.scorer.weight_volume_expansion * max(0.0, result.volume_expansion) +
            self.scorer.weight_trend_quality * result.trend_quality +
            self.scorer.weight_squeeze_strength * 0.5 +  # Se actualizará en signal_generator
            self.scorer.weight_volatility_expansion * 0.5
        )

        return result

    def _get_daily_bars(self, symbol: str, days: int):
        """Obtiene barras diarias."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=int(days * 1.5))

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
        )
        try:
            bars_data = self.data_client.get_stock_bars(request)
            bars = bars_data[symbol] if symbol in bars_data else []
            return list(bars)
        except Exception:
            return None

    def _calc_returns(self, bars) -> Optional[np.ndarray]:
        """Calcula retornos diarios desde barras."""
        if not bars or len(bars) < 2:
            return None
        closes = np.array([float(bar.close) for bar in bars])
        return np.diff(closes) / closes[:-1]

    @staticmethod
    def _calc_returns_from_closes(closes: np.ndarray) -> Optional[np.ndarray]:
        """Calcula retornos diarios desde closes."""
        if len(closes) < 2:
            return None
        return np.diff(closes) / closes[:-1]

    @staticmethod
    def _ema(data: np.ndarray, period: int) -> np.ndarray:
        """Calcula EMA."""
        multiplier = 2.0 / (period + 1)
        ema = np.zeros_like(data)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = (data[i] - ema[i - 1]) * multiplier + ema[i - 1]
        return ema

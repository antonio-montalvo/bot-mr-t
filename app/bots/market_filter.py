"""
Filtro de Régimen de Mercado.

Condiciones para habilitar operaciones LONG:
- SPY > EMA50
- EMA21 > EMA50
- VIX < 25

Si no se cumplen → CASH_MODE (no operar).
"""

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from app.bots.config import MarketRegimeConfig

logger = logging.getLogger(__name__)


class MarketFilter:
    """Evalúa si el régimen de mercado permite operar."""

    def __init__(self, data_client: StockHistoricalDataClient, config: MarketRegimeConfig):
        self.data_client = data_client
        self.config = config

    def is_bullish(self) -> bool:
        """Retorna True si el mercado está en modo alcista (se puede operar)."""
        try:
            spy_bars = self._get_bars(self.config.spy_symbol, days=100)
            if spy_bars is None or len(spy_bars) < self.config.ema_slow:
                logger.warning("Datos insuficientes para SPY")
                return False

            closes = np.array([float(bar.close) for bar in spy_bars])

            ema_fast = self._ema(closes, self.config.ema_fast)
            ema_slow = self._ema(closes, self.config.ema_slow)

            current_price = closes[-1]
            spy_above_ema50 = current_price > ema_slow[-1]
            ema21_above_ema50 = ema_fast[-1] > ema_slow[-1]

            # VIX check (usando proxy ETF)
            vix_ok = self._check_vix()

            is_bull = spy_above_ema50 and ema21_above_ema50 and vix_ok

            logger.info(
                "Market Regime: SPY>EMA50=%s, EMA21>EMA50=%s, VIX_OK=%s → %s",
                spy_above_ema50, ema21_above_ema50, vix_ok,
                "BULLISH" if is_bull else "CASH_MODE"
            )

            return is_bull

        except Exception as e:
            logger.error("Error evaluando market regime: %s", e)
            return False

    def _check_vix(self) -> bool:
        """Verifica que VIX esté por debajo del umbral."""
        try:
            bars = self._get_bars(self.config.vix_symbol, days=5)
            if bars is None or len(bars) == 0:
                return True  # Si no podemos obtener VIX, asumimos OK
            current = float(bars[-1].close)
            return current < self.config.vix_max
        except Exception:
            return True

    def _get_bars(self, symbol: str, days: int):
        """Obtiene barras diarias históricas."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days * 2)  # Margen extra por fines de semana

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
        )
        bars_data = self.data_client.get_stock_bars(request)
        bars = bars_data[symbol] if symbol in bars_data else []
        return list(bars)[-days:] if bars else None

    @staticmethod
    def _ema(data: np.ndarray, period: int) -> np.ndarray:
        """Calcula EMA sobre un array."""
        multiplier = 2.0 / (period + 1)
        ema = np.zeros_like(data)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = (data[i] - ema[i - 1]) * multiplier + ema[i - 1]
        return ema

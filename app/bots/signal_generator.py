"""
Generador de señales de trading.

Detecta:
1. Squeeze (Bollinger Bands dentro de Keltner Channels)
2. Momentum positivo (histograma)
3. Breakout confirmado (volumen + cierre arriba de resistencia)
"""

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed

from app.bots.config import SqueezeConfig

logger = logging.getLogger(__name__)


class Signal:
    """Señal de trading generada."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.squeeze_on: bool = False
        self.squeeze_fired: bool = False
        self.momentum_positive: bool = False
        self.breakout_confirmed: bool = False
        self.entry_price: float = 0.0
        self.atr: float = 0.0
        self.is_valid: bool = False

    def __repr__(self):
        return (
            f"Signal({self.symbol}, valid={self.is_valid}, "
            f"squeeze_fired={self.squeeze_fired}, momentum={self.momentum_positive})"
        )


class SignalGenerator:
    """Genera señales basadas en squeeze y breakout."""

    def __init__(self, data_client: StockHistoricalDataClient, config: SqueezeConfig):
        self.data_client = data_client
        self.config = config

    def evaluate(self, symbol: str) -> Signal:
        """Evalúa un símbolo y genera una señal."""
        logger.info("SignalGenerator: Evaluando %s...", symbol)
        signal = Signal(symbol)

        bars = self._get_bars(symbol, days=100)
        min_bars = max(self.config.bb_length, self.config.kc_length, self.config.momentum_length) + 10
        if bars is None or len(bars) < min_bars:
            logger.warning("SignalGenerator: %s - Datos insuficientes (necesita %d barras)", symbol, min_bars)
            return signal

        closes = np.array([float(bar.close) for bar in bars])
        highs = np.array([float(bar.high) for bar in bars])
        lows = np.array([float(bar.low) for bar in bars])

        # ─── Bollinger Bands ───
        bb_upper, bb_lower = self._bollinger_bands(closes)

        # ─── Keltner Channels ───
        kc_upper, kc_lower = self._keltner_channels(closes, highs, lows)

        # ─── Squeeze detection ───
        # Squeeze ON: BB está dentro de KC
        squeeze_on_now = (bb_upper[-1] < kc_upper[-1]) and (bb_lower[-1] > kc_lower[-1])
        squeeze_on_prev = (bb_upper[-2] < kc_upper[-2]) and (bb_lower[-2] > kc_lower[-2])

        signal.squeeze_on = squeeze_on_now

        # Squeeze FIRED: estaba en squeeze y ahora no (expansión)
        signal.squeeze_fired = squeeze_on_prev and not squeeze_on_now

        # ─── Momentum ───
        momentum = self._momentum_histogram(closes)
        signal.momentum_positive = momentum[-1] > 0 and momentum[-1] > momentum[-2]

        # ─── Breakout confirmation ───
        # Cierre arriba de la banda superior de Bollinger con volumen
        volumes = np.array([float(bar.volume) for bar in bars])
        avg_vol = np.mean(volumes[-20:])
        current_vol = volumes[-1]
        vol_spike = current_vol > (avg_vol * 1.3)

        resistance = np.max(highs[-20:-1])
        breakout = closes[-1] > resistance and vol_spike

        signal.breakout_confirmed = breakout

        # ─── ATR para stops ───
        signal.atr = self._atr(highs, lows, closes, period=14)
        signal.entry_price = closes[-1]

        # ─── Señal válida ───
        signal.is_valid = (
            signal.squeeze_fired and
            signal.momentum_positive and
            signal.breakout_confirmed
        )

        logger.info("SignalGenerator: %s - Squeeze: %s, Momentum: %s, Breakout: %s → Valid: %s",
                   symbol, 
                   "FIRED ✓" if signal.squeeze_fired else "NO ✗",
                   "POS ✓" if signal.momentum_positive else "NEG ✗",
                   "YES ✓" if signal.breakout_confirmed else "NO ✗",
                   "YES" if signal.is_valid else "NO")

        if signal.is_valid:
            logger.info(
                "SignalGenerator: ✓ SIGNAL VALID: %s @ $%.2f | ATR=%.2f",
                symbol, signal.entry_price, signal.atr
            )

        return signal

    def _bollinger_bands(self, closes: np.ndarray):
        """Calcula Bollinger Bands."""
        length = self.config.bb_length
        sma = np.convolve(closes, np.ones(length) / length, mode='valid')
        # Pad to match array length
        pad = len(closes) - len(sma)
        sma = np.concatenate([np.full(pad, sma[0]), sma])

        std = np.array([
            np.std(closes[max(0, i - length + 1):i + 1])
            for i in range(len(closes))
        ])

        upper = sma + self.config.bb_std * std
        lower = sma - self.config.bb_std * std
        return upper, lower

    def _keltner_channels(self, closes: np.ndarray, highs: np.ndarray, lows: np.ndarray):
        """Calcula Keltner Channels."""
        length = self.config.kc_length
        ema = self._ema(closes, length)

        # ATR
        tr = np.maximum(
            highs - lows,
            np.maximum(
                np.abs(highs - np.roll(closes, 1)),
                np.abs(lows - np.roll(closes, 1))
            )
        )
        tr[0] = highs[0] - lows[0]
        atr = self._ema(tr, length)

        upper = ema + self.config.kc_atr_multiplier * atr
        lower = ema - self.config.kc_atr_multiplier * atr
        return upper, lower

    def _momentum_histogram(self, closes: np.ndarray) -> np.ndarray:
        """Calcula momentum como diferencia del precio vs regresión lineal."""
        length = self.config.momentum_length
        momentum = np.zeros(len(closes))

        for i in range(length, len(closes)):
            segment = closes[i - length:i + 1]
            x = np.arange(len(segment))
            slope, intercept = np.polyfit(x, segment, 1)
            regression_value = slope * length + intercept
            momentum[i] = closes[i] - regression_value

        return momentum

    def _atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        """Calcula ATR actual."""
        tr = np.maximum(
            highs - lows,
            np.maximum(
                np.abs(highs - np.roll(closes, 1)),
                np.abs(lows - np.roll(closes, 1))
            )
        )
        tr[0] = highs[0] - lows[0]
        atr_values = self._ema(tr, period)
        return float(atr_values[-1])

    def _get_bars(self, symbol: str, days: int):
        """Obtiene barras diarias."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=int(days * 1.5))

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed=DataFeed.IEX,
        )
        try:
            bars_data = self.data_client.get_stock_bars(request)
            bars = bars_data[symbol] if symbol in bars_data else []
            return list(bars)
        except Exception:
            return None

    @staticmethod
    def _ema(data: np.ndarray, period: int) -> np.ndarray:
        """Calcula EMA."""
        multiplier = 2.0 / (period + 1)
        ema = np.zeros_like(data, dtype=float)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = (data[i] - ema[i - 1]) * multiplier + ema[i - 1]
        return ema

"""
Parámetros de configuración para la estrategia híbrida de trading.

Basada en:
- Market Regime Filter (SPY/VIX)
- Liquidity Filter
- Institutional Strength (Relative Strength)
- Squeeze Detection (Bollinger/Keltner)
- Risk Management (ATR-based)
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MarketRegimeConfig:
    """Filtro de régimen de mercado."""
    spy_symbol: str = "SPY"
    qqq_symbol: str = "QQQ"
    vix_symbol: str = "VIXY"  # ETF proxy para VIX en Alpaca
    ema_fast: int = 21
    ema_slow: int = 50
    vix_max: float = 25.0


@dataclass
class LiquidityConfig:
    """Filtro de liquidez."""
    min_avg_volume: int = 2_000_000        # 2M shares
    min_dollar_volume: float = 20_000_000  # 20M USD/day
    max_spread_pct: float = 0.0015         # 0.15%
    min_price: float = 10.0                # USD


@dataclass
class InstitutionalConfig:
    """Filtro de fuerza institucional."""
    rs_lookback_days: int = 20
    ema_short: int = 20
    ema_mid: int = 50
    ema_long: int = 200
    volume_spike_multiplier: float = 1.5


@dataclass
class SqueezeConfig:
    """Detección de squeeze (Bollinger dentro de Keltner)."""
    bb_length: int = 20
    bb_std: float = 2.0
    kc_length: int = 20
    kc_atr_multiplier: float = 1.5
    momentum_length: int = 12


@dataclass
class RiskConfig:
    """Gestión de riesgo."""
    max_risk_per_trade_pct: float = 0.01   # 1% del capital
    atr_stop_multiplier: float = 1.5       # StopLoss = Entry - 1.5 * ATR14
    atr_length: int = 14
    take_profit_r_multiple: float = 2.0    # Take 50% at 2R
    trailing_ema: int = 9
    daily_loss_limit_pct: float = 0.03     # 3% daily loss → stop trading
    max_drawdown_pct: float = 0.10         # 10% drawdown → reduce size 50%
    max_open_positions: int = 5


@dataclass
class ScorerConfig:
    """Ranking de oportunidades."""
    weight_relative_strength: float = 0.30
    weight_volume_expansion: float = 0.25
    weight_squeeze_strength: float = 0.20
    weight_trend_quality: float = 0.15
    weight_volatility_expansion: float = 0.10
    min_score: float = 0.6  # Solo comprar si score > 0.6


@dataclass
class BotConfig:
    """Configuración completa del bot."""
    market_regime: MarketRegimeConfig = field(default_factory=MarketRegimeConfig)
    liquidity: LiquidityConfig = field(default_factory=LiquidityConfig)
    institutional: InstitutionalConfig = field(default_factory=InstitutionalConfig)
    squeeze: SqueezeConfig = field(default_factory=SqueezeConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    scorer: ScorerConfig = field(default_factory=ScorerConfig)

    # Timeframe y universo
    timeframe: str = "1Day"            # "1Day" para swing, "15Min" para intradía
    scan_interval_seconds: int = 60    # Intervalo entre ciclos del bot
    watchlist: list = field(default_factory=lambda: [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
        "AMD", "CRM", "NFLX", "ADBE", "AVGO", "COST", "PEP",
        "LLY", "UNH", "V", "MA", "JPM", "HD",
    ])

    @classmethod
    def from_database(cls, db, strategy_id: str) -> "BotConfig":
        """Carga la configuración desde strategy_parameters en la base de datos."""
        from app.bots.config_loader import load_strategy_parameters, apply_parameters_to_config
        
        # Crear configuración con valores por defecto
        config = cls()
        
        # Cargar parámetros de la DB
        params = load_strategy_parameters(db, strategy_id)
        
        if not params:
            logger.warning("No se encontraron parámetros para estrategia %s, usando defaults", strategy_id)
            return config
        
        # Aplicar parámetros a cada sección
        apply_parameters_to_config(config.market_regime, params, "market_regime.")
        apply_parameters_to_config(config.liquidity, params, "liquidity.")
        apply_parameters_to_config(config.institutional, params, "institutional.")
        apply_parameters_to_config(config.squeeze, params, "squeeze.")
        apply_parameters_to_config(config.risk, params, "risk.")
        apply_parameters_to_config(config.scorer, params, "scorer.")
        
        # Parámetros generales del bot
        if "timeframe" in params:
            config.timeframe = params["timeframe"]
        if "scan_interval_seconds" in params:
            config.scan_interval_seconds = params["scan_interval_seconds"]
        if "watchlist" in params:
            config.watchlist = params["watchlist"]
        
        logger.info("Configuración cargada desde DB para estrategia %s", strategy_id)
        return config

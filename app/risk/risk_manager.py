import logging

logger = logging.getLogger(__name__)


class RiskManager:
    """Gestión de riesgo para las operaciones de trading."""

    def __init__(self, max_position_size: float = 0.1, max_daily_loss: float = 0.02):
        self.max_position_size = max_position_size  # % del portafolio
        self.max_daily_loss = max_daily_loss  # % de pérdida diaria máxima
        self.daily_pnl = 0.0

    def validate(self, signal: dict) -> bool:
        """Valida si una señal cumple con las reglas de riesgo."""
        if self._exceeds_daily_loss():
            logger.warning("Pérdida diaria máxima alcanzada.")
            return False
        return True

    def _exceeds_daily_loss(self) -> bool:
        return self.daily_pnl <= -self.max_daily_loss

    def update_pnl(self, pnl: float):
        self.daily_pnl += pnl

    def reset_daily(self):
        self.daily_pnl = 0.0

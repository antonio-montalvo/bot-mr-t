"""
Gestión de Riesgo.

Controla:
1. Position sizing basado en ATR
2. Stop loss dinámico (ATR * multiplier)
3. Trailing stop (EMA9 o ATR trailing)
4. Parciales (50% at 2R, move stop to breakeven)
5. Capital protection (daily loss limit 3%, max drawdown 10%)
"""

import logging
from datetime import datetime, timezone

from app.bots.config import RiskConfig
from app.db import Database

logger = logging.getLogger(__name__)


class RiskManager:
    """Gestiona riesgo por operación y protección de capital."""

    def __init__(self, config: RiskConfig, db: Database, bot_id: str):
        self.config = config
        self.db = db
        self.bot_id = bot_id

    # ─── Position Sizing ─────────────────────────────────────────────────

    def calculate_position_size(self, equity: float, entry_price: float, atr: float) -> int:
        """
        PositionSize = RiskAmount / (Entry - StopLoss)
        StopLoss = Entry - (ATR * multiplier)
        """
        risk_amount = equity * self.config.max_risk_per_trade_pct
        stop_distance = atr * self.config.atr_stop_multiplier

        if stop_distance <= 0:
            return 0

        position_size = int(risk_amount / stop_distance)

        # Verificar que no exceda el buying power razonable
        max_position_value = equity * 0.20  # Max 20% del capital por posición
        max_shares = int(max_position_value / entry_price) if entry_price > 0 else 0

        final_size = min(position_size, max_shares)

        # Reducir si estamos en drawdown
        if self._is_in_drawdown():
            final_size = int(final_size * 0.5)
            logger.warning("Drawdown detectado: reduciendo position size 50%%")

        return max(0, final_size)

    def calculate_stop_loss(self, entry_price: float, atr: float) -> float:
        """StopLoss = Entry - (ATR * multiplier)"""
        return entry_price - (atr * self.config.atr_stop_multiplier)

    def calculate_take_profit(self, entry_price: float, stop_loss: float) -> float:
        """Take profit at 2R."""
        risk = entry_price - stop_loss
        return entry_price + (risk * self.config.take_profit_r_multiple)

    # ─── Capital Protection ──────────────────────────────────────────────

    def can_trade(self) -> bool:
        """Verifica si se puede operar (daily loss limit + max positions)."""
        if self._daily_loss_exceeded():
            logger.warning("CAPITAL GUARD: Daily loss limit alcanzado. No se puede operar.")
            return False

        if self._max_positions_reached():
            logger.info("Max posiciones abiertas alcanzado (%d)", self.config.max_open_positions)
            return False

        return True

    def _daily_loss_exceeded(self) -> bool:
        """IF DailyLoss > 3% → STOP TRADING TODAY."""
        try:
            cursor = self.db.conn.cursor()
            today = datetime.now(timezone.utc).date()

            # Sumar PnL realizado del día
            cursor.execute(
                """SELECT COALESCE(SUM(realized_pnl), 0)
                   FROM positions
                   WHERE bot_id = %s AND status = 'closed'
                     AND closed_at::date = %s""",
                (self.bot_id, today),
            )
            daily_realized = float(cursor.fetchone()[0])

            # Obtener equity actual
            cursor.execute(
                "SELECT equity FROM account_current_state WHERE bot_id = %s",
                (self.bot_id,),
            )
            row = cursor.fetchone()
            equity = float(row[0]) if row else 0

            if equity <= 0:
                return False

            daily_loss_pct = abs(daily_realized) / equity if daily_realized < 0 else 0
            return daily_loss_pct >= self.config.daily_loss_limit_pct

        except Exception as e:
            logger.error("Error verificando daily loss: %s", e)
            return False

    def _is_in_drawdown(self) -> bool:
        """IF Drawdown > 10% → reduce position size."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT equity FROM account_current_state WHERE bot_id = %s",
                (self.bot_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False

            current_equity = float(row[0])

            # Obtener máximo histórico de equity
            cursor.execute(
                "SELECT MAX(equity) FROM account_snapshots WHERE bot_id = %s",
                (self.bot_id,),
            )
            max_row = cursor.fetchone()
            if not max_row or max_row[0] is None:
                return False

            max_equity = float(max_row[0])
            if max_equity <= 0:
                return False

            drawdown = (max_equity - current_equity) / max_equity
            return drawdown >= self.config.max_drawdown_pct

        except Exception as e:
            logger.error("Error verificando drawdown: %s", e)
            return False

    def _max_positions_reached(self) -> bool:
        """Verifica si se alcanzó el máximo de posiciones abiertas."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM positions WHERE bot_id = %s AND status = 'open'",
                (self.bot_id,),
            )
            count = cursor.fetchone()[0]
            return count >= self.config.max_open_positions
        except Exception:
            return False

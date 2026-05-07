"""
Servicio de sincronización entre Alpaca y la base de datos.

Secuencia MVP:
  1. sync_account()    → account_current_state (upsert por bot_id)
  2. sync_positions()  → positions (upsert por bot_id + asset_id, cierra ausentes)
  3. sync_orders()     → orders + executions (upsert por broker_order_id)

Frecuencias:
  - account_current_state: cada 60s
  - positions:             cada 30s
  - open orders:           cada 30s
  - closed orders:         cada 5 min
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus

from app.db import Database
from app.api.crypto import decrypt

logger = logging.getLogger(__name__)


class SyncService:
    """Sincroniza datos de Alpaca con la base de datos para un bot específico."""

    def __init__(self, db: Database):
        self.db = db

    # ─── Público: ciclo completo ─────────────────────────────────────────

    def sync_all_bots_fast(self):
        """Ciclo rápido (30-60s): account + positions + open orders."""
        bots = self._get_enabled_bots()
        for bot in bots:
            try:
                client = self._get_client_for_bot(bot)
                if client is None:
                    continue
                self._log(bot["id"], "INFO", "sync", "Sync rápido iniciado")
                self.sync_account(bot, client)
                self.sync_positions(bot, client)
                self.sync_open_orders(bot, client)
                self._log(bot["id"], "INFO", "sync", "Sync rápido completado")
            except Exception as e:
                self._log(bot["id"], "ERROR", "sync", f"Error en sync rápido: {e}")
                logger.exception("Error sync rápido bot %s: %s", bot["id"], e)

    def sync_all_bots_slow(self):
        """Ciclo lento (5 min): closed/filled/canceled orders + executions."""
        bots = self._get_enabled_bots()
        for bot in bots:
            try:
                client = self._get_client_for_bot(bot)
                if client is None:
                    continue
                self._log(bot["id"], "INFO", "sync", "Sync lento iniciado")
                self.sync_closed_orders(bot, client)
                self._log(bot["id"], "INFO", "sync", "Sync lento completado")
            except Exception as e:
                self._log(bot["id"], "ERROR", "sync", f"Error en sync lento: {e}")
                logger.exception("Error sync lento bot %s: %s", bot["id"], e)

    # ─── sync_account ────────────────────────────────────────────────────

    def sync_account(self, bot: dict, client: TradingClient):
        """Sincroniza account_current_state (upsert por bot_id)."""
        try:
            account = client.get_account()
        except Exception as e:
            self._log(bot["id"], "ERROR", "sync_account", f"Alpaca error: {e}")
            return

        try:
            cursor = self.db.conn.cursor()
            now = datetime.now(timezone.utc)

            cursor.execute(
                "SELECT id FROM account_current_state WHERE bot_id = %s",
                (bot["id"],),
            )
            exists = cursor.fetchone()

            if exists:
                cursor.execute(
                    """UPDATE account_current_state
                       SET equity = %s,
                           cash = %s,
                           buying_power = %s,
                           portfolio_value = %s,
                           currency = %s,
                           account_id = %s,
                           trading_blocked = %s,
                           last_synced_at = %s,
                           updated_at = %s
                     WHERE bot_id = %s""",
                    (
                        float(account.equity),
                        float(account.cash),
                        float(account.buying_power),
                        float(account.portfolio_value),
                        account.currency or "USD",
                        str(account.id),
                        account.trading_blocked,
                        now,
                        now,
                        bot["id"],
                    ),
                )
            else:
                cursor.execute(
                    """INSERT INTO account_current_state
                       (bot_id, broker_name, environment, account_id,
                        equity, cash, buying_power, portfolio_value,
                        currency, trading_blocked, last_synced_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        bot["id"],
                        bot["broker_name"],
                        bot["environment"],
                        str(account.id),
                        float(account.equity),
                        float(account.cash),
                        float(account.buying_power),
                        float(account.portfolio_value),
                        account.currency or "USD",
                        account.trading_blocked,
                        now,
                    ),
                )

            self.db.conn.commit()
            self._log(bot["id"], "INFO", "sync_account", "Account sincronizado")
        except Exception as e:
            self.db.conn.rollback()
            self._log(bot["id"], "ERROR", "sync_account", f"DB error: {e}")
            logger.exception("Error sync_account bot %s", bot["id"])

    # ─── sync_positions ──────────────────────────────────────────────────

    def sync_positions(self, bot: dict, client: TradingClient):
        """Sincroniza positions (upsert por bot_id + asset_id). Cierra ausentes."""
        try:
            alpaca_positions = client.get_all_positions()
        except Exception as e:
            self._log(bot["id"], "ERROR", "sync_positions", f"Alpaca error: {e}")
            return

        try:
            cursor = self.db.conn.cursor()
            now = datetime.now(timezone.utc)

            synced_asset_ids = []

            for pos in alpaca_positions:
                asset_id = self._ensure_asset(pos.symbol, pos.asset_class or "us_equity")
                synced_asset_ids.append(asset_id)

                cursor.execute(
                    "SELECT id FROM positions WHERE bot_id = %s AND asset_id = %s AND status = 'open'",
                    (bot["id"], asset_id),
                )
                existing = cursor.fetchone()

                qty = float(pos.qty)
                avg_entry = float(pos.avg_entry_price)
                current_price = float(pos.current_price)
                unrealized_pnl = float(pos.unrealized_pl)
                side = pos.side.value if hasattr(pos.side, "value") else str(pos.side)

                if existing:
                    cursor.execute(
                        """UPDATE positions
                           SET quantity = %s,
                               average_entry_price = %s,
                               current_price = %s,
                               unrealized_pnl = %s,
                               updated_at = %s
                         WHERE id = %s""",
                        (qty, avg_entry, current_price, unrealized_pnl, now, existing[0]),
                    )
                else:
                    cursor.execute(
                        """INSERT INTO positions
                           (bot_id, asset_id, quantity, average_entry_price,
                            current_price, unrealized_pnl, status, opened_at)
                           VALUES (%s, %s, %s, %s, %s, %s, 'open', %s)""",
                        (bot["id"], asset_id, qty, avg_entry, current_price, unrealized_pnl, now),
                    )

            # Cerrar posiciones que Alpaca ya no reporta
            if synced_asset_ids:
                placeholders = ",".join(["%s"] * len(synced_asset_ids))
                cursor.execute(
                    f"""UPDATE positions
                        SET status = 'closed', quantity = 0, closed_at = %s, updated_at = %s
                      WHERE bot_id = %s AND status = 'open'
                        AND asset_id NOT IN ({placeholders})""",
                    [now, now, bot["id"]] + synced_asset_ids,
                )
            else:
                cursor.execute(
                    """UPDATE positions
                       SET status = 'closed', quantity = 0, closed_at = %s, updated_at = %s
                     WHERE bot_id = %s AND status = 'open'""",
                    (now, now, bot["id"]),
                )

            self.db.conn.commit()
            self._log(bot["id"], "INFO", "sync_positions", f"Positions sincronizadas: {len(alpaca_positions)} abiertas")
        except Exception as e:
            self.db.conn.rollback()
            self._log(bot["id"], "ERROR", "sync_positions", f"DB error: {e}")
            logger.exception("Error sync_positions bot %s", bot["id"])

    # ─── sync_open_orders ────────────────────────────────────────────────

    def sync_open_orders(self, bot: dict, client: TradingClient):
        """Sincroniza órdenes abiertas (upsert por broker_order_id)."""
        try:
            request = GetOrdersRequest(status=QueryOrderStatus.OPEN)
            orders = client.get_orders(filter=request)
        except Exception as e:
            self._log(bot["id"], "ERROR", "sync_open_orders", f"Alpaca error: {e}")
            return

        self._upsert_orders(bot, orders)
        self._log(bot["id"], "INFO", "sync_open_orders", f"Open orders sincronizadas: {len(orders)}")

    # ─── sync_closed_orders ──────────────────────────────────────────────

    def sync_closed_orders(self, bot: dict, client: TradingClient):
        """Sincroniza órdenes cerradas/filled/canceled recientes + executions."""
        try:
            request = GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=100)
            orders = client.get_orders(filter=request)
        except Exception as e:
            self._log(bot["id"], "ERROR", "sync_closed_orders", f"Alpaca error: {e}")
            return

        self._upsert_orders(bot, orders)

        # Sync executions para órdenes filled
        for order in orders:
            if order.status and order.status.value == "filled":
                self._sync_execution_for_order(bot, order)

        self._log(bot["id"], "INFO", "sync_closed_orders", f"Closed orders sincronizadas: {len(orders)}")

    # ─── Helpers privados ────────────────────────────────────────────────

    def _upsert_orders(self, bot: dict, orders):
        """Upsert órdenes en la tabla orders."""
        try:
            cursor = self.db.conn.cursor()
            now = datetime.now(timezone.utc)

            for order in orders:
                broker_order_id = str(order.id)
                symbol = order.symbol
                asset_id = self._ensure_asset(symbol, "us_equity")

                side = order.side.value if hasattr(order.side, "value") else str(order.side)
                order_type = order.type.value if hasattr(order.type, "value") else str(order.type)
                status = order.status.value if hasattr(order.status, "value") else str(order.status)
                qty = float(order.qty) if order.qty else 0
                limit_price = float(order.limit_price) if order.limit_price else None
                stop_price = float(order.stop_price) if order.stop_price else None

                cursor.execute(
                    "SELECT id FROM orders WHERE broker_order_id = %s AND bot_id = %s",
                    (broker_order_id, bot["id"]),
                )
                existing = cursor.fetchone()

                if existing:
                    cursor.execute(
                        """UPDATE orders
                           SET status = %s, updated_at = %s
                         WHERE id = %s""",
                        (status, now, existing[0]),
                    )
                else:
                    submitted_at = order.submitted_at or now
                    cursor.execute(
                        """INSERT INTO orders
                           (bot_id, asset_id, broker_order_id, side, order_type,
                            status, quantity, limit_price, stop_price, submitted_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            bot["id"], asset_id, broker_order_id, side, order_type,
                            status, qty, limit_price, stop_price, submitted_at,
                        ),
                    )

            self.db.conn.commit()
        except Exception as e:
            self.db.conn.rollback()
            logger.exception("Error upsert_orders bot %s: %s", bot["id"], e)

    def _sync_execution_for_order(self, bot: dict, order):
        """Inserta ejecución si no existe. Clave compuesta como broker_execution_id."""
        try:
            cursor = self.db.conn.cursor()

            filled_qty = float(order.filled_qty) if order.filled_qty else 0
            filled_avg_price = float(order.filled_avg_price) if order.filled_avg_price else 0
            filled_at = order.filled_at

            if filled_qty == 0:
                return

            # Clave compuesta: broker_order_id + filled_at + filled_qty + filled_avg_price
            broker_order_id = str(order.id)
            filled_at_str = str(filled_at) if filled_at else "none"
            broker_execution_id = f"{broker_order_id}_{filled_at_str}_{filled_qty}_{filled_avg_price}"

            # Buscar order_id interno
            cursor.execute(
                "SELECT id FROM orders WHERE broker_order_id = %s AND bot_id = %s",
                (broker_order_id, bot["id"]),
            )
            order_row = cursor.fetchone()
            if not order_row:
                return

            internal_order_id = order_row[0]

            # Verificar si ya existe
            cursor.execute(
                "SELECT id FROM executions WHERE broker_execution_id = %s AND order_id = %s",
                (broker_execution_id, internal_order_id),
            )
            if cursor.fetchone():
                return  # Ya existe, ignorar

            executed_at = filled_at or datetime.now(timezone.utc)

            cursor.execute(
                """INSERT INTO executions
                   (order_id, broker_execution_id, filled_quantity, filled_price, executed_at)
                   VALUES (%s, %s, %s, %s, %s)""",
                (internal_order_id, broker_execution_id, filled_qty, filled_avg_price, executed_at),
            )
            self.db.conn.commit()
        except Exception as e:
            self.db.conn.rollback()
            logger.debug("Error sync_execution: %s", e)

    def _ensure_asset(self, symbol: str, asset_type: str = "us_equity") -> str:
        """Asegura que el asset existe. Retorna asset_id."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT id FROM assets WHERE symbol = %s", (symbol,))
            row = cursor.fetchone()
            if row:
                return str(row[0])

            cursor.execute(
                "INSERT INTO assets (symbol, name, asset_type, is_active) VALUES (%s, %s, %s, TRUE) RETURNING id",
                (symbol, symbol, asset_type),
            )
            new_id = cursor.fetchone()[0]
            self.db.conn.commit()
            return str(new_id)
        except Exception as e:
            self.db.conn.rollback()
            logger.error("Error ensure_asset %s: %s", symbol, e)
            raise

    def _get_enabled_bots(self) -> list:
        """Obtiene bots habilitados con sus datos."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """SELECT bi.id, bi.user_id, bi.name, bi.broker_name, bi.environment
                   FROM bot_instances bi
                  WHERE bi.is_enabled = TRUE"""
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": str(row[0]),
                    "user_id": str(row[1]),
                    "name": row[2],
                    "broker_name": row[3],
                    "environment": row[4],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error("Error obteniendo bots habilitados: %s", e)
            self.db.conn.rollback()
            return []

    def _get_client_for_bot(self, bot: dict) -> Optional[TradingClient]:
        """Crea un TradingClient con las API keys del usuario del bot."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """SELECT api_key_encrypted, secret_key_encrypted
                   FROM api_keys
                  WHERE user_id = %s AND is_active = TRUE
                  ORDER BY created_at DESC LIMIT 1""",
                (bot["user_id"],),
            )
            row = cursor.fetchone()
            if not row:
                self._log(bot["id"], "ERROR", "sync", "No API keys encontradas para el usuario")
                return None
        except Exception as e:
            self.db.conn.rollback()
            logger.error("Error obteniendo API keys: %s", e)
            return None

        try:
            api_key = decrypt(row[0])
            secret_key = decrypt(row[1])
        except Exception as e:
            self._log(bot["id"], "ERROR", "sync", f"Error descifrando API keys: {e}")
            return None

        is_paper = bot["environment"].lower() in ("paper", "sandbox", "development")
        return TradingClient(api_key=api_key, secret_key=secret_key, paper=is_paper)

    def _log(self, bot_id: str, level: str, module: str, message: str):
        """Escribe un log en la tabla system_logs."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """INSERT INTO system_logs (bot_id, level, module, message)
                   VALUES (%s, %s, %s, %s)""",
                (bot_id, level, module, message),
            )
            self.db.conn.commit()
        except Exception:
            logger.exception("Error escribiendo log a DB para bot %s", bot_id)

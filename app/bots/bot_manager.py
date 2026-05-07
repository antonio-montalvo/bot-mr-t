"""
Gestor de múltiples instancias de bot.

Mantiene un registro en memoria de los bots activos y provee
métodos para iniciar, detener y consultar el estado de cada uno.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient

from app.db import Database
from app.api.crypto import decrypt
from app.bots.bot_engine import BotEngine
from app.bots.config import BotConfig

logger = logging.getLogger(__name__)


class BotManager:
    """Administra instancias activas de BotEngine."""

    def __init__(self, db: Database):
        self.db = db
        self._engines: dict[str, BotEngine] = {}

    def start_bot(self, bot_id: str) -> dict:
        """Inicia un bot por su ID."""
        if bot_id in self._engines and self._engines[bot_id].is_running:
            return {"status": "already_running", "bot_id": bot_id}

        # Obtener info del bot
        bot_info = self._get_bot_info(bot_id)
        if not bot_info:
            return {"status": "error", "detail": "Bot no encontrado"}

        # Obtener credenciales de Alpaca
        clients = self._create_clients(bot_info["user_id"], bot_info["environment"])
        if not clients:
            return {"status": "error", "detail": "No se pudieron obtener credenciales de Alpaca"}

        trading_client, data_client = clients

        # Crear y arrancar el engine
        config = BotConfig()
        engine = BotEngine(
            bot_id=bot_id,
            trading_client=trading_client,
            data_client=data_client,
            db=self.db,
            config=config,
        )
        engine.start()
        self._engines[bot_id] = engine

        return {"status": "started", "bot_id": bot_id}

    def stop_bot(self, bot_id: str) -> dict:
        """Detiene un bot por su ID."""
        engine = self._engines.get(bot_id)
        if not engine or not engine.is_running:
            # Actualizar estado en DB por si acaso
            self._force_stop_status(bot_id)
            return {"status": "not_running", "bot_id": bot_id}

        engine.stop()
        return {"status": "stopped", "bot_id": bot_id}

    def get_status(self, bot_id: str) -> dict:
        """Obtiene el estado de un bot."""
        engine = self._engines.get(bot_id)

        if engine and engine.is_running:
            uptime = None
            if engine.started_at:
                uptime = (datetime.now(timezone.utc) - engine.started_at).total_seconds()
            return {
                "bot_id": bot_id,
                "is_running": True,
                "started_at": engine.started_at,
                "uptime_seconds": uptime,
                "strategy": "hybrid_squeeze_momentum",
            }

        # Consultar DB para estado persistido
        bot_info = self._get_bot_info(bot_id)
        return {
            "bot_id": bot_id,
            "is_running": False,
            "started_at": None,
            "uptime_seconds": None,
            "strategy": None,
            "db_status": bot_info["status"] if bot_info else "unknown",
        }

    def stop_all(self):
        """Detiene todos los bots activos."""
        for bot_id in list(self._engines.keys()):
            self.stop_bot(bot_id)

    # ─── Helpers privados ────────────────────────────────────────────────

    def _get_bot_info(self, bot_id: str) -> Optional[dict]:
        """Obtiene info del bot desde la DB."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT id, user_id, name, broker_name, environment, status FROM bot_instances WHERE id = %s",
                (bot_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": str(row[0]),
                "user_id": str(row[1]),
                "name": row[2],
                "broker_name": row[3],
                "environment": row[4],
                "status": row[5],
            }
        except Exception as e:
            logger.error("Error obteniendo bot info: %s", e)
            return None

    def _create_clients(self, user_id: str, environment: str):
        """Crea TradingClient y DataClient para un usuario."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """SELECT api_key_encrypted, secret_key_encrypted
                   FROM api_keys
                   WHERE user_id = %s AND is_active = TRUE
                   ORDER BY created_at DESC LIMIT 1""",
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                logger.error("No API keys para user %s", user_id)
                return None

            api_key = decrypt(row[0])
            secret_key = decrypt(row[1])

            is_paper = environment.lower() in ("paper", "sandbox", "development")

            trading_client = TradingClient(
                api_key=api_key,
                secret_key=secret_key,
                paper=is_paper,
            )

            data_client = StockHistoricalDataClient(
                api_key=api_key,
                secret_key=secret_key,
            )

            return trading_client, data_client

        except Exception as e:
            logger.error("Error creando clients: %s", e)
            return None

    def _force_stop_status(self, bot_id: str):
        """Fuerza el estado a 'stopped' en DB."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "UPDATE bot_instances SET status = 'stopped', updated_at = %s WHERE id = %s",
                (datetime.now(timezone.utc), bot_id),
            )
            self.db.conn.commit()
        except Exception:
            pass

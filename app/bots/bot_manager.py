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
        logger.info("BotManager: Iniciando bot %s...", bot_id)
        
        if bot_id in self._engines and self._engines[bot_id].is_running:
            logger.warning("BotManager: Bot %s ya está corriendo", bot_id)
            return {"status": "already_running", "bot_id": bot_id}

        # Obtener info del bot
        logger.info("BotManager: Obteniendo información del bot %s...", bot_id)
        bot_info = self._get_bot_info(bot_id)
        if not bot_info:
            logger.error("BotManager: Bot %s no encontrado en DB", bot_id)
            return {"status": "error", "detail": "Bot no encontrado"}
        
        logger.info("BotManager: Bot %s - Name: %s, Env: %s", 
                   bot_id, bot_info["name"], bot_info["environment"])

        # Obtener credenciales de Alpaca
        logger.info("BotManager: Creando clientes Alpaca para bot %s...", bot_id)
        clients = self._create_clients(bot_info["user_id"], bot_info["environment"])
        if not clients:
            logger.error("BotManager: No se pudieron obtener credenciales de Alpaca para bot %s", bot_id)
            return {"status": "error", "detail": "No se pudieron obtener credenciales de Alpaca"}

        trading_client, data_client = clients
        logger.info("BotManager: ✓ Clientes Alpaca creados para bot %s", bot_id)

        # Cargar configuración desde la base de datos
        logger.info("BotManager: Cargando configuración para bot %s...", bot_id)
        strategy_id = bot_info.get("strategy_id")
        if strategy_id:
            logger.info("BotManager: Cargando parámetros desde DB para estrategia %s...", strategy_id)
            config = BotConfig.from_database(self.db, strategy_id)
        else:
            logger.warning("BotManager: Bot %s no tiene estrategia asociada, usando config por defecto", bot_id)
            config = BotConfig()
        
        # Crear y arrancar el engine
        logger.info("BotManager: Creando BotEngine para bot %s...", bot_id)
        engine = BotEngine(
            bot_id=bot_id,
            trading_client=trading_client,
            data_client=data_client,
            db=self.db,
            config=config,
        )
        
        logger.info("BotManager: Arrancando BotEngine para bot %s...", bot_id)
        engine.start()
        self._engines[bot_id] = engine

        logger.info("BotManager: ✓ Bot %s iniciado exitosamente", bot_id)
        return {"status": "started", "bot_id": bot_id}

    def stop_bot(self, bot_id: str) -> dict:
        """Detiene un bot por su ID."""
        logger.info("BotManager: Deteniendo bot %s...", bot_id)
        
        engine = self._engines.get(bot_id)
        if not engine or not engine.is_running:
            logger.warning("BotManager: Bot %s no está corriendo", bot_id)
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
        """Obtiene info del bot desde la DB, incluyendo strategy_id."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute(
                """SELECT bi.id, bi.user_id, bi.name, bi.broker_name, bi.environment, bi.status, s.id as strategy_id
                   FROM bot_instances bi
                   LEFT JOIN strategies s ON s.bot_id = bi.id AND s.is_active = TRUE
                   WHERE bi.id = %s
                   LIMIT 1""",
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
                "strategy_id": str(row[6]) if row[6] else None,
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
                raw_data=False,
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

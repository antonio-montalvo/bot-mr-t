"""
Scheduler para la sincronización periódica con Alpaca.

Frecuencias MVP:
  - account_current_state: cada 60 segundos
  - positions:             cada 30 segundos
  - open orders:           cada 30 segundos
  - closed orders:         cada 5 minutos
  - logs cleanup:          1 vez al día
"""

import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.db import Database
from app.sync.sync_service import SyncService

logger = logging.getLogger(__name__)


class SyncScheduler:
    """Gestiona los jobs de sincronización periódica."""

    def __init__(self, db: Database):
        self.db = db
        self.sync_service = SyncService(db)
        self.scheduler = BackgroundScheduler(
            job_defaults={"coalesce": True, "max_instances": 1}
        )

    def start(self):
        """Registra los jobs y arranca el scheduler."""

        # Ciclo rápido: account + positions + open orders (cada 30s)
        self.scheduler.add_job(
            self.sync_service.sync_all_bots_fast,
            trigger=IntervalTrigger(seconds=30),
            id="sync_fast",
            name="Sync rápido (account + positions + open orders)",
            replace_existing=True,
        )

        # Ciclo lento: closed orders + executions (cada 5 min)
        self.scheduler.add_job(
            self.sync_service.sync_all_bots_slow,
            trigger=IntervalTrigger(minutes=5),
            id="sync_slow",
            name="Sync lento (closed orders + executions)",
            replace_existing=True,
        )

        # Cleanup de logs antiguos (1 vez al día a las 03:00 UTC)
        self.scheduler.add_job(
            self._cleanup_old_logs,
            trigger=CronTrigger(hour=3, minute=0),
            id="logs_cleanup",
            name="Cleanup logs antiguos",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("SyncScheduler iniciado: fast=30s, slow=5min, cleanup=diario@03:00UTC")

    def stop(self):
        """Detiene el scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("SyncScheduler detenido")

    def _cleanup_old_logs(self):
        """Elimina logs de system_logs con más de 30 días."""
        try:
            cursor = self.db.conn.cursor()
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            cursor.execute(
                "DELETE FROM system_logs WHERE created_at < %s",
                (cutoff,),
            )
            deleted = cursor.rowcount
            self.db.conn.commit()
            logger.info("Logs cleanup: %d registros eliminados (>30 días)", deleted)
        except Exception as e:
            logger.exception("Error en cleanup de logs: %s", e)

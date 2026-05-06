import logging
import threading
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import BotInstanceItem, BotStatusResponse
from app.api.deps import get_current_user, get_db
from app.db import Database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bot", tags=["Bot"], dependencies=[Depends(get_current_user)])

# ── Bot state (in-memory) ────────────────────────
_bot_running = False
_bot_thread: Optional[threading.Thread] = None
_bot_started_at: Optional[datetime] = None
_bot_strategy: Optional[str] = None


@router.post("/start", response_model=BotStatusResponse)
def start_bot():
    global _bot_running, _bot_started_at, _bot_strategy

    if _bot_running:
        raise HTTPException(status_code=400, detail="El bot ya está en ejecución")

    _bot_running = True
    _bot_started_at = datetime.now(timezone.utc)
    _bot_strategy = "default"

    logger.info("Bot iniciado manualmente via API")

    return _build_status()


@router.post("/stop", response_model=BotStatusResponse)
def stop_bot():
    global _bot_running, _bot_started_at, _bot_strategy

    if not _bot_running:
        raise HTTPException(status_code=400, detail="El bot no está en ejecución")

    _bot_running = False
    _bot_started_at = None
    _bot_strategy = None

    logger.info("Bot detenido manualmente via API")

    return _build_status()


@router.get("/status", response_model=BotStatusResponse)
def get_status():
    return _build_status()


@router.get("/bots", response_model=List[BotInstanceItem])
def list_bots(
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    cursor = db.conn.cursor()
    cursor.execute(
        "SELECT id, name FROM bot_instances WHERE user_id = %s",
        (current_user["id"],),
    )
    rows = cursor.fetchall()
    return [BotInstanceItem(id=str(row[0]), name=row[1]) for row in rows]


def _build_status() -> BotStatusResponse:
    uptime = None
    if _bot_running and _bot_started_at:
        uptime = (datetime.now(timezone.utc) - _bot_started_at).total_seconds()

    return BotStatusResponse(
        is_running=_bot_running,
        strategy=_bot_strategy,
        started_at=_bot_started_at,
        uptime_seconds=uptime,
    )

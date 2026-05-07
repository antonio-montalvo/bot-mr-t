import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.schemas import BotInstanceItem, BotStatusResponse, BotCreateRequest, BotCreateResponse
from app.api.deps import get_current_user, get_db
from app.db import Database
from app.bots import BotManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bot", tags=["Bot"], dependencies=[Depends(get_current_user)])

# ── Bot Manager (singleton) ──────────────────────
_bot_manager: BotManager = None


def _get_bot_manager(db: Database = Depends(get_db)) -> BotManager:
    global _bot_manager
    if _bot_manager is None:
        _bot_manager = BotManager(db)
    return _bot_manager


@router.post("/start", response_model=BotStatusResponse)
def start_bot(
    bot_id: str = Query(..., description="ID del bot a iniciar"),
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    manager: BotManager = Depends(_get_bot_manager),
):
    # Verificar que el bot pertenece al usuario
    _verify_bot_ownership(db, bot_id, current_user["id"])

    result = manager.start_bot(bot_id)

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result.get("detail", "Error iniciando bot"))

    status = manager.get_status(bot_id)
    return BotStatusResponse(
        is_running=status["is_running"],
        strategy=status.get("strategy"),
        started_at=status.get("started_at"),
        uptime_seconds=status.get("uptime_seconds"),
    )


@router.post("/stop", response_model=BotStatusResponse)
def stop_bot(
    bot_id: str = Query(..., description="ID del bot a detener"),
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    manager: BotManager = Depends(_get_bot_manager),
):
    _verify_bot_ownership(db, bot_id, current_user["id"])

    manager.stop_bot(bot_id)

    status = manager.get_status(bot_id)
    return BotStatusResponse(
        is_running=status["is_running"],
        strategy=status.get("strategy"),
        started_at=status.get("started_at"),
        uptime_seconds=status.get("uptime_seconds"),
    )


@router.get("/status", response_model=BotStatusResponse)
def get_status(
    bot_id: str = Query(..., description="ID del bot"),
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    manager: BotManager = Depends(_get_bot_manager),
):
    _verify_bot_ownership(db, bot_id, current_user["id"])

    status = manager.get_status(bot_id)
    return BotStatusResponse(
        is_running=status["is_running"],
        strategy=status.get("strategy"),
        started_at=status.get("started_at"),
        uptime_seconds=status.get("uptime_seconds"),
    )


@router.post("/create", response_model=BotCreateResponse)
def create_bot(
    body: BotCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Crea una nueva instancia de bot con su estrategia asociada."""
    cursor = db.conn.cursor()

    # Crear bot_instance
    cursor.execute(
        """INSERT INTO bot_instances (user_id, name, broker_name, environment, status, is_enabled)
           VALUES (%s, %s, %s, %s, 'stopped', TRUE)
           RETURNING id""",
        (current_user["id"], body.name, body.broker_name, body.environment),
    )
    bot_id = str(cursor.fetchone()[0])

    # Crear estrategia asociada (hybrid_squeeze_momentum)
    cursor.execute(
        """INSERT INTO strategies (bot_id, name, type, description, is_active)
           VALUES (%s, %s, %s, %s, TRUE)
           RETURNING id""",
        (
            bot_id,
            "Hybrid Squeeze Momentum",
            "hybrid_squeeze_momentum",
            "Estrategia híbrida: Market Regime + Liquidity + Squeeze + Breakout + Risk Management",
        ),
    )
    strategy_id = str(cursor.fetchone()[0])

    db.conn.commit()

    return BotCreateResponse(
        id=bot_id,
        name=body.name,
        broker_name=body.broker_name,
        environment=body.environment,
        status="stopped",
        strategy_id=strategy_id,
    )


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


@router.delete("/{bot_id}")
def delete_bot(
    bot_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    manager: BotManager = Depends(_get_bot_manager),
):
    """Elimina un bot y todos sus datos asociados."""
    logger.info("Eliminando bot %s para usuario %s", bot_id, current_user["id"])
    
    # Verificar ownership
    _verify_bot_ownership(db, bot_id, current_user["id"])
    
    # Detener el bot si está corriendo
    try:
        manager.stop_bot(bot_id)
        logger.info("Bot %s detenido antes de eliminar", bot_id)
    except Exception as e:
        logger.warning("Error deteniendo bot %s: %s", bot_id, e)
    
    cursor = db.conn.cursor()
    
    try:
        # Eliminar bot_instance (las foreign keys con ON DELETE CASCADE
        # eliminarán automáticamente strategies, orders, executions, etc.)
        cursor.execute("DELETE FROM bot_instances WHERE id = %s", (bot_id,))
        
        db.conn.commit()
        
        logger.info("Bot %s eliminado exitosamente (CASCADE eliminó datos relacionados)", bot_id)
        
        return {
            "status": "deleted",
            "bot_id": bot_id,
            "message": "Bot eliminado exitosamente"
        }
        
    except Exception as e:
        db.conn.rollback()
        logger.error("Error eliminando bot %s: %s", bot_id, e)
        raise HTTPException(status_code=500, detail=f"Error eliminando bot: {str(e)}")


def _verify_bot_ownership(db: Database, bot_id: str, user_id: str):
    """Verifica que el bot pertenece al usuario autenticado."""
    cursor = db.conn.cursor()
    cursor.execute(
        "SELECT id FROM bot_instances WHERE id = %s AND user_id = %s",
        (bot_id, user_id),
    )
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Bot no encontrado")

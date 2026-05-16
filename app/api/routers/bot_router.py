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


@router.post(
    "/start",
    response_model=BotStatusResponse,
    summary="Iniciar bot",
    description="Inicia la ejecución de un bot de trading. El bot comenzará a ejecutar su estrategia configurada.",
    responses={
        200: {"description": "Bot iniciado exitosamente"},
        400: {"description": "Error al iniciar el bot"},
        401: {"description": "No autenticado"},
        404: {"description": "Bot no encontrado"}
    }
)
def start_bot(
    bot_id: str = Query(..., description="ID del bot a iniciar"),
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    manager: BotManager = Depends(_get_bot_manager),
):
    """Inicia un bot de trading que ejecutará su estrategia configurada."""
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


@router.post(
    "/stop",
    response_model=BotStatusResponse,
    summary="Detener bot",
    description="Detiene la ejecución de un bot de trading activo.",
    responses={
        200: {"description": "Bot detenido exitosamente"},
        401: {"description": "No autenticado"},
        404: {"description": "Bot no encontrado"}
    }
)
def stop_bot(
    bot_id: str = Query(..., description="ID del bot a detener"),
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    manager: BotManager = Depends(_get_bot_manager),
):
    """Detiene un bot de trading que está en ejecución."""
    _verify_bot_ownership(db, bot_id, current_user["id"])

    manager.stop_bot(bot_id)

    status = manager.get_status(bot_id)
    return BotStatusResponse(
        is_running=status["is_running"],
        strategy=status.get("strategy"),
        started_at=status.get("started_at"),
        uptime_seconds=status.get("uptime_seconds"),
    )


@router.get(
    "/status",
    response_model=BotStatusResponse,
    summary="Obtener estado del bot",
    description="Consulta el estado actual de un bot.",
    responses={
        200: {"description": "Estado obtenido exitosamente"},
        401: {"description": "No autenticado"},
        404: {"description": "Bot no encontrado"}
    }
)
def get_status(
    bot_id: str = Query(..., description="ID del bot"),
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    manager: BotManager = Depends(_get_bot_manager),
):
    """Obtiene el estado actual de un bot de trading."""
    _verify_bot_ownership(db, bot_id, current_user["id"])

    status = manager.get_status(bot_id)
    return BotStatusResponse(
        is_running=status["is_running"],
        strategy=status.get("strategy"),
        started_at=status.get("started_at"),
        uptime_seconds=status.get("uptime_seconds"),
    )


@router.post(
    "/create",
    response_model=BotCreateResponse,
    status_code=201,
    summary="Crear nuevo bot",
    description="Crea una nueva instancia de bot de trading con su estrategia.",
    responses={
        201: {"description": "Bot creado exitosamente"},
        400: {"description": "Datos inválidos"},
        401: {"description": "No autenticado"}
    }
)
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

    # Insertar parámetros por defecto de la estrategia
    _insert_default_strategy_parameters(cursor, strategy_id)

    db.conn.commit()

    return BotCreateResponse(
        id=bot_id,
        name=body.name,
        broker_name=body.broker_name,
        environment=body.environment,
        status="stopped",
        strategy_id=strategy_id,
    )


@router.get(
    "/bots",
    response_model=List[BotInstanceItem],
    summary="Listar bots del usuario",
    description="Obtiene la lista de todos los bots del usuario autenticado.",
    responses={
        200: {"description": "Lista de bots obtenida exitosamente"},
        401: {"description": "No autenticado"}
    }
)
def list_bots(
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Lista todos los bots de trading del usuario actual."""
    cursor = db.conn.cursor()
    cursor.execute(
        "SELECT id, name FROM bot_instances WHERE user_id = %s",
        (current_user["id"],),
    )
    rows = cursor.fetchall()
    return [BotInstanceItem(id=str(row[0]), name=row[1]) for row in rows]


@router.delete(
    "/{bot_id}",
    summary="Eliminar bot",
    description="Elimina un bot de trading y todos sus datos asociados. Si el bot está corriendo, se detiene automáticamente.",
    responses={
        200: {"description": "Bot eliminado exitosamente"},
        401: {"description": "No autenticado"},
        404: {"description": "Bot no encontrado"},
        500: {"description": "Error al eliminar el bot"}
    }
)
def delete_bot(
    bot_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    manager: BotManager = Depends(_get_bot_manager),
):
    """Elimina un bot y todos sus datos relacionados. Detiene el bot si está corriendo."""
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


def _insert_default_strategy_parameters(cursor, strategy_id: str):
    """Inserta los parámetros por defecto de la estrategia en la base de datos."""
    params = [
        # Market Regime
        ('market_regime.spy_symbol', 'SPY', 'str'),
        ('market_regime.qqq_symbol', 'QQQ', 'str'),
        ('market_regime.vix_symbol', 'VIXY', 'str'),
        ('market_regime.ema_fast', '21', 'int'),
        ('market_regime.ema_slow', '50', 'int'),
        ('market_regime.vix_max', '25.0', 'float'),
        # Liquidity
        ('liquidity.min_avg_volume', '2000000', 'int'),
        ('liquidity.min_dollar_volume', '20000000.0', 'float'),
        ('liquidity.max_spread_pct', '0.0015', 'float'),
        ('liquidity.min_price', '10.0', 'float'),
        # Institutional
        ('institutional.rs_lookback_days', '20', 'int'),
        ('institutional.ema_short', '20', 'int'),
        ('institutional.ema_mid', '50', 'int'),
        ('institutional.ema_long', '200', 'int'),
        ('institutional.volume_spike_multiplier', '1.5', 'float'),
        # Squeeze
        ('squeeze.bb_length', '20', 'int'),
        ('squeeze.bb_std', '2.0', 'float'),
        ('squeeze.kc_length', '20', 'int'),
        ('squeeze.kc_atr_multiplier', '1.5', 'float'),
        ('squeeze.momentum_length', '12', 'int'),
        # Risk
        ('risk.max_risk_per_trade_pct', '0.01', 'float'),
        ('risk.atr_stop_multiplier', '1.5', 'float'),
        ('risk.atr_length', '14', 'int'),
        ('risk.take_profit_r_multiple', '2.0', 'float'),
        ('risk.trailing_ema', '9', 'int'),
        ('risk.daily_loss_limit_pct', '0.03', 'float'),
        ('risk.max_drawdown_pct', '0.10', 'float'),
        ('risk.max_open_positions', '5', 'int'),
        # Scorer
        ('scorer.weight_relative_strength', '0.30', 'float'),
        ('scorer.weight_volume_expansion', '0.25', 'float'),
        ('scorer.weight_squeeze_strength', '0.20', 'float'),
        ('scorer.weight_trend_quality', '0.15', 'float'),
        ('scorer.weight_volatility_expansion', '0.10', 'float'),
        ('scorer.min_score', '0.6', 'float'),
        # General
        ('timeframe', '1Day', 'str'),
        ('scan_interval_seconds', '60', 'int'),
        ('watchlist', 'AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,AMD,CRM,NFLX,ADBE,AVGO,COST,PEP,LLY,UNH,V,MA,JPM,HD', 'list'),
    ]
    
    for param_key, param_value, data_type in params:
        cursor.execute(
            """INSERT INTO strategy_parameters (strategy_id, param_key, param_value, data_type)
               VALUES (%s, %s, %s, %s)""",
            (strategy_id, param_key, param_value, data_type)
        )
    
    logger.info("Insertados %d parámetros por defecto para estrategia %s", len(params), strategy_id)


def _verify_bot_ownership(db: Database, bot_id: str, user_id: str):
    """Verifica que el bot pertenece al usuario autenticado."""
    cursor = db.conn.cursor()
    cursor.execute(
        "SELECT id FROM bot_instances WHERE id = %s AND user_id = %s",
        (bot_id, user_id),
    )
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Bot no encontrado")

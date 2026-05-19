import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import (
    StrategyCreateRequest,
    StrategyUpdateRequest,
    StrategyResponse,
    StrategyWithParametersResponse,
    StrategyParameterResponse,
    StrategyParameterCreateRequest,
    StrategyParameterUpdateRequest,
)
from app.api.deps import get_current_user, get_db
from app.db import Database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategy", tags=["Strategy"], dependencies=[Depends(get_current_user)])


@router.get(
    "/strategies",
    response_model=List[StrategyResponse],
    summary="Listar estrategias",
    description="Obtiene todas las estrategias de trading disponibles."
)
def list_strategies(db: Database = Depends(get_db)):
    """Lista todas las estrategias registradas en el sistema."""
    try:
        cursor = db.conn.cursor()
        cursor.execute(
            """SELECT id, bot_id, name, type, description, is_active, created_at
               FROM strategies
               ORDER BY created_at DESC"""
        )
        rows = cursor.fetchall()
        return [
            StrategyResponse(
                id=str(row[0]),
                bot_id=str(row[1]),
                name=row[2],
                type=row[3],
                description=row[4],
                is_active=row[5],
                created_at=row[6],
            )
            for row in rows
        ]
    except Exception as e:
        logger.error("Error al listar estrategias: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/create",
    response_model=StrategyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear estrategia",
    description="Crea una nueva estrategia de trading asociada a un bot."
)
def create_strategy(
    body: StrategyCreateRequest,
    db: Database = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Crea una nueva estrategia y automáticamente inserta los parámetros por defecto."""
    try:
        cursor = db.conn.cursor()

        # Verificar que el bot existe y pertenece al usuario
        cursor.execute(
            "SELECT id FROM bot_instances WHERE id = %s AND user_id = %s",
            (body.bot_id, current_user["id"]),
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail="Bot no encontrado o no pertenece al usuario"
            )

        # Crear estrategia
        cursor.execute(
            """INSERT INTO strategies (bot_id, name, type, description, is_active)
               VALUES (%s, %s, %s, %s, FALSE)
               RETURNING id""",
            (body.bot_id, body.name, body.type, body.description),
        )
        strategy_id = str(cursor.fetchone()[0])

        # Insertar parámetros por defecto
        _insert_default_strategy_parameters(cursor, strategy_id)

        db.conn.commit()

        # Obtener estrategia creada
        cursor.execute(
            """SELECT id, bot_id, name, type, description, is_active, created_at
               FROM strategies WHERE id = %s""",
            (strategy_id,),
        )
        row = cursor.fetchone()

        return StrategyResponse(
            id=str(row[0]),
            bot_id=str(row[1]),
            name=row[2],
            type=row[3],
            description=row[4],
            is_active=row[5],
            created_at=row[6],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al crear estrategia: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{strategy_id}",
    response_model=StrategyWithParametersResponse,
    summary="Obtener estrategia",
    description="Obtiene una estrategia específica con todos sus parámetros."
)
def get_strategy(strategy_id: str, db: Database = Depends(get_db)):
    """Obtiene los detalles completos de una estrategia incluyendo sus parámetros."""
    try:
        cursor = db.conn.cursor()

        # Obtener estrategia
        cursor.execute(
            """SELECT id, bot_id, name, type, description, is_active, created_at
               FROM strategies WHERE id = %s""",
            (strategy_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada")

        # Obtener parámetros
        cursor.execute(
            """SELECT id, strategy_id, param_key, param_value, data_type, created_at
               FROM strategy_parameters
               WHERE strategy_id = %s
               ORDER BY param_key""",
            (strategy_id,),
        )
        param_rows = cursor.fetchall()

        parameters = [
            StrategyParameterResponse(
                id=str(p[0]),
                strategy_id=str(p[1]),
                param_key=p[2],
                param_value=p[3],
                data_type=p[4],
                created_at=p[5],
            )
            for p in param_rows
        ]

        return StrategyWithParametersResponse(
            id=str(row[0]),
            bot_id=str(row[1]),
            name=row[2],
            type=row[3],
            description=row[4],
            is_active=row[5],
            created_at=row[6],
            parameters=parameters,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al obtener estrategia: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/{strategy_id}",
    response_model=StrategyResponse,
    summary="Actualizar estrategia",
    description="Actualiza la información básica de una estrategia."
)
def update_strategy(
    strategy_id: str,
    body: StrategyUpdateRequest,
    db: Database = Depends(get_db),
):
    """Actualiza nombre, descripción o tipo de una estrategia."""
    try:
        cursor = db.conn.cursor()

        # Verificar que existe
        cursor.execute("SELECT id FROM strategies WHERE id = %s", (strategy_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Estrategia no encontrada")

        # Construir UPDATE dinámico
        updates = []
        values = []
        if body.name is not None:
            updates.append("name = %s")
            values.append(body.name)
        if body.description is not None:
            updates.append("description = %s")
            values.append(body.description)
        if body.type is not None:
            updates.append("type = %s")
            values.append(body.type)

        if not updates:
            # No hay cambios, retornar estrategia actual
            cursor.execute(
                """SELECT id, bot_id, name, type, description, is_active, created_at
                   FROM strategies WHERE id = %s""",
                (strategy_id,),
            )
            row = cursor.fetchone()
            return StrategyResponse(
                id=str(row[0]),
                bot_id=str(row[1]),
                name=row[2],
                type=row[3],
                description=row[4],
                is_active=row[5],
                created_at=row[6],
            )

        values.append(strategy_id)
        query = f"UPDATE strategies SET {', '.join(updates)} WHERE id = %s"
        cursor.execute(query, values)
        db.conn.commit()

        # Retornar estrategia actualizada
        cursor.execute(
            """SELECT id, bot_id, name, type, description, is_active, created_at
               FROM strategies WHERE id = %s""",
            (strategy_id,),
        )
        row = cursor.fetchone()

        return StrategyResponse(
            id=str(row[0]),
            bot_id=str(row[1]),
            name=row[2],
            type=row[3],
            description=row[4],
            is_active=row[5],
            created_at=row[6],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al actualizar estrategia: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{strategy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar estrategia",
    description="Elimina una estrategia y todos sus parámetros asociados."
)
def delete_strategy(strategy_id: str, db: Database = Depends(get_db)):
    """Elimina una estrategia. Los parámetros se eliminan automáticamente por CASCADE."""
    try:
        cursor = db.conn.cursor()
        cursor.execute("DELETE FROM strategies WHERE id = %s", (strategy_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada")
        db.conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al eliminar estrategia: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{strategy_id}/activate",
    response_model=StrategyResponse,
    summary="Activar estrategia",
    description="Activa una estrategia y desactiva las demás del mismo bot."
)
def activate_strategy(strategy_id: str, db: Database = Depends(get_db)):
    """Activa una estrategia específica."""
    try:
        cursor = db.conn.cursor()

        # Verificar que existe
        cursor.execute(
            "SELECT bot_id FROM strategies WHERE id = %s",
            (strategy_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Estrategia no encontrada")

        bot_id = row[0]

        # Desactivar otras estrategias del mismo bot
        cursor.execute(
            "UPDATE strategies SET is_active = FALSE WHERE bot_id = %s",
            (bot_id,)
        )

        # Activar esta estrategia
        cursor.execute(
            "UPDATE strategies SET is_active = TRUE WHERE id = %s",
            (strategy_id,)
        )
        db.conn.commit()

        # Retornar estrategia actualizada
        cursor.execute(
            """SELECT id, bot_id, name, type, description, is_active, created_at
               FROM strategies WHERE id = %s""",
            (strategy_id,),
        )
        row = cursor.fetchone()

        return StrategyResponse(
            id=str(row[0]),
            bot_id=str(row[1]),
            name=row[2],
            type=row[3],
            description=row[4],
            is_active=row[5],
            created_at=row[6],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al activar estrategia: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{strategy_id}/deactivate",
    response_model=StrategyResponse,
    summary="Desactivar estrategia",
    description="Desactiva una estrategia."
)
def deactivate_strategy(strategy_id: str, db: Database = Depends(get_db)):
    """Desactiva una estrategia específica."""
    try:
        cursor = db.conn.cursor()

        # Verificar que existe
        cursor.execute("SELECT id FROM strategies WHERE id = %s", (strategy_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Estrategia no encontrada")

        cursor.execute(
            "UPDATE strategies SET is_active = FALSE WHERE id = %s",
            (strategy_id,)
        )
        db.conn.commit()

        # Retornar estrategia actualizada
        cursor.execute(
            """SELECT id, bot_id, name, type, description, is_active, created_at
               FROM strategies WHERE id = %s""",
            (strategy_id,),
        )
        row = cursor.fetchone()

        return StrategyResponse(
            id=str(row[0]),
            bot_id=str(row[1]),
            name=row[2],
            type=row[3],
            description=row[4],
            is_active=row[5],
            created_at=row[6],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al desactivar estrategia: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════
# STRATEGY PARAMETERS ENDPOINTS
# ══════════════════════════════════════════════════════════════

@router.get(
    "/{strategy_id}/parameters",
    response_model=List[StrategyParameterResponse],
    summary="Listar parámetros",
    description="Obtiene todos los parámetros de una estrategia."
)
def list_parameters(strategy_id: str, db: Database = Depends(get_db)):
    """Lista todos los parámetros de una estrategia."""
    try:
        cursor = db.conn.cursor()
        cursor.execute(
            """SELECT id, strategy_id, param_key, param_value, data_type, created_at
               FROM strategy_parameters
               WHERE strategy_id = %s
               ORDER BY param_key""",
            (strategy_id,),
        )
        rows = cursor.fetchall()

        return [
            StrategyParameterResponse(
                id=str(row[0]),
                strategy_id=str(row[1]),
                param_key=row[2],
                param_value=row[3],
                data_type=row[4],
                created_at=row[5],
            )
            for row in rows
        ]
    except Exception as e:
        logger.error("Error al listar parámetros: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{strategy_id}/parameters",
    response_model=StrategyParameterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear parámetro",
    description="Crea un nuevo parámetro para una estrategia."
)
def create_parameter(
    strategy_id: str,
    body: StrategyParameterCreateRequest,
    db: Database = Depends(get_db),
):
    """Crea un nuevo parámetro de estrategia."""
    try:
        cursor = db.conn.cursor()

        # Verificar que la estrategia existe
        cursor.execute("SELECT id FROM strategies WHERE id = %s", (strategy_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Estrategia no encontrada")

        cursor.execute(
            """INSERT INTO strategy_parameters (strategy_id, param_key, param_value, data_type)
               VALUES (%s, %s, %s, %s)
               RETURNING id, created_at""",
            (strategy_id, body.param_key, body.param_value, body.data_type),
        )
        row = cursor.fetchone()
        db.conn.commit()

        return StrategyParameterResponse(
            id=str(row[0]),
            strategy_id=strategy_id,
            param_key=body.param_key,
            param_value=body.param_value,
            data_type=body.data_type,
            created_at=row[1],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al crear parámetro: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/{strategy_id}/parameters/{parameter_id}",
    response_model=StrategyParameterResponse,
    summary="Actualizar parámetro",
    description="Actualiza el valor de un parámetro."
)
def update_parameter(
    strategy_id: str,
    parameter_id: str,
    body: StrategyParameterUpdateRequest,
    db: Database = Depends(get_db),
):
    """Actualiza el valor de un parámetro de estrategia."""
    try:
        cursor = db.conn.cursor()

        cursor.execute(
            """UPDATE strategy_parameters
               SET param_value = %s
               WHERE id = %s AND strategy_id = %s""",
            (body.param_value, parameter_id, strategy_id),
        )

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Parámetro no encontrado")

        db.conn.commit()

        # Retornar parámetro actualizado
        cursor.execute(
            """SELECT id, strategy_id, param_key, param_value, data_type, created_at
               FROM strategy_parameters
               WHERE id = %s""",
            (parameter_id,),
        )
        row = cursor.fetchone()

        return StrategyParameterResponse(
            id=str(row[0]),
            strategy_id=str(row[1]),
            param_key=row[2],
            param_value=row[3],
            data_type=row[4],
            created_at=row[5],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al actualizar parámetro: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{strategy_id}/parameters/{parameter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar parámetro",
    description="Elimina un parámetro de una estrategia."
)
def delete_parameter(
    strategy_id: str,
    parameter_id: str,
    db: Database = Depends(get_db),
):
    """Elimina un parámetro de estrategia."""
    try:
        cursor = db.conn.cursor()
        cursor.execute(
            "DELETE FROM strategy_parameters WHERE id = %s AND strategy_id = %s",
            (parameter_id, strategy_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Parámetro no encontrado")
        db.conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al eliminar parámetro: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════

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

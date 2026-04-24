import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import StrategyCreate, StrategyUpdate, StrategyResponse
from app.api.deps import get_current_user, get_db
from app.db import Database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategies", tags=["Strategy"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[StrategyResponse])
def list_strategies(db: Database = Depends(get_db)):
    try:
        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM strategies ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [_row_to_strategy(row, db._is_postgres) for row in rows]
    except Exception as e:
        logger.error("Error al listar estrategias: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
def create_strategy(body: StrategyCreate, db: Database = Depends(get_db)):
    try:
        cursor = db.conn.cursor()
        params_json = json.dumps(body.parameters) if body.parameters else None
        now = datetime.now(timezone.utc)
        p = "%s" if db._is_postgres else "?"

        if db._is_postgres:
            cursor.execute(
                f"INSERT INTO strategies (name, description, type, parameters, is_active, created_at, updated_at) "
                f"VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}) RETURNING id",
                (body.name, body.description, body.type, params_json, False, now, now),
            )
            strategy_id = cursor.fetchone()[0]
        else:
            cursor.execute(
                f"INSERT INTO strategies (name, description, type, parameters, is_active, created_at, updated_at) "
                f"VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})",
                (body.name, body.description, body.type, params_json, False, now.isoformat(), now.isoformat()),
            )
            strategy_id = cursor.lastrowid
        db.conn.commit()

        return StrategyResponse(
            id=strategy_id,
            name=body.name,
            description=body.description,
            type=body.type,
            parameters=body.parameters,
            is_active=False,
            created_at=now,
            updated_at=now,
        )
    except Exception as e:
        logger.error("Error al crear estrategia: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{strategy_id}", response_model=StrategyResponse)
def update_strategy(strategy_id: int, body: StrategyUpdate, db: Database = Depends(get_db)):
    existing = _get_strategy_or_404(strategy_id, db)

    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.description is not None:
        updates["description"] = body.description
    if body.type is not None:
        updates["type"] = body.type
    if body.parameters is not None:
        updates["parameters"] = json.dumps(body.parameters)

    if not updates:
        return existing

    now = datetime.now(timezone.utc)
    updates["updated_at"] = now if db._is_postgres else now.isoformat()

    try:
        cursor = db.conn.cursor()
        p = "%s" if db._is_postgres else "?"
        set_clause = ", ".join(f"{k} = {p}" for k in updates)
        values = list(updates.values()) + [strategy_id]
        cursor.execute(f"UPDATE strategies SET {set_clause} WHERE id = {p}", values)
        db.conn.commit()

        return _get_strategy_or_404(strategy_id, db)
    except Exception as e:
        logger.error("Error al actualizar estrategia: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{strategy_id}/activate", response_model=StrategyResponse)
def activate_strategy(strategy_id: int, db: Database = Depends(get_db)):
    _get_strategy_or_404(strategy_id, db)
    try:
        cursor = db.conn.cursor()
        p = "%s" if db._is_postgres else "?"
        now = datetime.now(timezone.utc)
        ts = now if db._is_postgres else now.isoformat()

        cursor.execute(f"UPDATE strategies SET is_active = false, updated_at = {p} WHERE is_active = true", (ts,))
        cursor.execute(f"UPDATE strategies SET is_active = true, updated_at = {p} WHERE id = {p}", (ts, strategy_id))
        db.conn.commit()

        return _get_strategy_or_404(strategy_id, db)
    except Exception as e:
        logger.error("Error al activar estrategia: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{strategy_id}/deactivate", response_model=StrategyResponse)
def deactivate_strategy(strategy_id: int, db: Database = Depends(get_db)):
    _get_strategy_or_404(strategy_id, db)
    try:
        cursor = db.conn.cursor()
        p = "%s" if db._is_postgres else "?"
        now = datetime.now(timezone.utc)
        ts = now if db._is_postgres else now.isoformat()
        cursor.execute(f"UPDATE strategies SET is_active = false, updated_at = {p} WHERE id = {p}", (ts, strategy_id))
        db.conn.commit()

        return _get_strategy_or_404(strategy_id, db)
    except Exception as e:
        logger.error("Error al desactivar estrategia: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Helpers ──────────────────────────────────────
def _get_strategy_or_404(strategy_id: int, db: Database) -> StrategyResponse:
    cursor = db.conn.cursor()
    p = "%s" if db._is_postgres else "?"
    cursor.execute(f"SELECT * FROM strategies WHERE id = {p}", (strategy_id,))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Estrategia no encontrada")
    return _row_to_strategy(row, db._is_postgres)


def _row_to_strategy(row, is_postgres: bool) -> StrategyResponse:
    if is_postgres:
        return StrategyResponse(
            id=row[0], name=row[1], description=row[2], type=row[3],
            parameters=json.loads(row[4]) if row[4] else None,
            is_active=row[5], created_at=row[6], updated_at=row[7],
        )
    else:
        return StrategyResponse(
            id=row[0], name=row[1], description=row[2], type=row[3],
            parameters=json.loads(row[4]) if row[4] else None,
            is_active=bool(row[5]), created_at=row[6], updated_at=row[7],
        )

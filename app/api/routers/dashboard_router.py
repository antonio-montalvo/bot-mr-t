import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.schemas import (
    DashboardSummaryResponse,
    DashboardBotSummary,
    DashboardAccountSummary,
    DashboardPerformance,
    DashboardPosition,
    DashboardOrder,
    DashboardLog,
)
from app.api.deps import get_current_user, get_db
from app.db import Database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"], dependencies=[Depends(get_current_user)])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    bot_id: str = Query(..., description="UUID del bot"),
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    cursor = db.conn.cursor()

    # ── Bot instance ─────────────────────────────────
    cursor.execute(
        "SELECT id, name, status, environment, updated_at "
        "FROM bot_instances WHERE id = %s AND user_id = %s",
        (bot_id, current_user["id"]),
    )
    bot_row = cursor.fetchone()
    if bot_row is None:
        raise HTTPException(status_code=404, detail="Bot no encontrado")

    # last_run_at from bot_runs
    cursor.execute(
        "SELECT started_at FROM bot_runs WHERE bot_id = %s ORDER BY started_at DESC LIMIT 1",
        (bot_id,),
    )
    last_run_row = cursor.fetchone()
    last_run_at = last_run_row[0] if last_run_row else None

    bot_summary = DashboardBotSummary(
        id=str(bot_row[0]),
        name=bot_row[1],
        status=bot_row[2],
        environment=bot_row[3],
        last_run_at=last_run_at,
    )

    # ── Account current state ────────────────────────
    cursor.execute(
        "SELECT equity, cash, buying_power, currency FROM account_current_state "
        "WHERE bot_id = %s",
        (bot_id,),
    )
    acc_row = cursor.fetchone()
    if acc_row:
        account = DashboardAccountSummary(
            equity=float(acc_row[0]),
            cash=float(acc_row[1]) if acc_row[1] else 0,
            buying_power=float(acc_row[2]) if acc_row[2] else 0,
            currency=acc_row[3] or "USD",
        )
    else:
        account = DashboardAccountSummary(equity=0, cash=0, buying_power=0)

    # ── Performance ──────────────────────────────────
    # Open positions count
    cursor.execute(
        "SELECT COUNT(*) FROM positions WHERE bot_id = %s AND status = 'open'",
        (bot_id,),
    )
    open_positions = cursor.fetchone()[0]

    # Orders today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cursor.execute(
        "SELECT COUNT(*) FROM orders WHERE bot_id = %s AND submitted_at >= %s",
        (bot_id, today_start),
    )
    orders_today = cursor.fetchone()[0]

    # PnL: total unrealized from open positions
    cursor.execute(
        "SELECT COALESCE(SUM(unrealized_pnl), 0) FROM positions WHERE bot_id = %s AND status = 'open'",
        (bot_id,),
    )
    total_pnl = float(cursor.fetchone()[0])

    # Daily PnL: sum of realized + unrealized from today's positions
    cursor.execute(
        "SELECT COALESCE(SUM(unrealized_pnl + realized_pnl), 0) "
        "FROM positions WHERE bot_id = %s AND updated_at >= %s",
        (bot_id, today_start),
    )
    daily_pnl = float(cursor.fetchone()[0])

    performance = DashboardPerformance(
        daily_pnl=daily_pnl,
        total_pnl=total_pnl,
        open_positions=open_positions,
        orders_today=orders_today,
    )

    # ── Positions (open, with symbol from assets) ────
    cursor.execute(
        "SELECT a.symbol, p.quantity, p.average_entry_price, p.current_price, p.unrealized_pnl "
        "FROM positions p JOIN assets a ON p.asset_id = a.id "
        "WHERE p.bot_id = %s AND p.status = 'open' "
        "ORDER BY p.opened_at DESC LIMIT 10",
        (bot_id,),
    )
    positions = [
        DashboardPosition(
            symbol=row[0],
            qty=float(row[1]),
            avg_price=float(row[2]) if row[2] else 0,
            current_price=float(row[3]) if row[3] else 0,
            unrealized_pnl=float(row[4]) if row[4] else 0,
        )
        for row in cursor.fetchall()
    ]

    # ── Recent orders (with symbol from assets) ──────
    cursor.execute(
        "SELECT a.symbol, o.side, o.quantity, o.status, o.submitted_at "
        "FROM orders o JOIN assets a ON o.asset_id = a.id "
        "WHERE o.bot_id = %s ORDER BY o.submitted_at DESC LIMIT 10",
        (bot_id,),
    )
    recent_orders = [
        DashboardOrder(
            symbol=row[0],
            side=row[1],
            qty=float(row[2]),
            status=row[3],
            submitted_at=row[4],
        )
        for row in cursor.fetchall()
    ]

    # ── Recent logs ──────────────────────────────────
    cursor.execute(
        "SELECT level, message, created_at FROM system_logs "
        "WHERE bot_id = %s ORDER BY created_at DESC LIMIT 10",
        (bot_id,),
    )
    recent_logs = [
        DashboardLog(level=row[0], message=row[1], created_at=row[2])
        for row in cursor.fetchall()
    ]

    return DashboardSummaryResponse(
        bot=bot_summary,
        account=account,
        performance=performance,
        positions=positions,
        recent_orders=recent_orders,
        recent_logs=recent_logs,
    )

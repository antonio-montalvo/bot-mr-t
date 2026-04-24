import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import PnLResponse, PerformanceResponse
from app.api.deps import get_current_user, get_broker, get_position_manager, get_db
from app.broker import AlpacaBroker
from app.positions import PositionManager
from app.db import Database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["Metrics"], dependencies=[Depends(get_current_user)])


@router.get("/pnl", response_model=PnLResponse)
def get_pnl(
    broker: AlpacaBroker = Depends(get_broker),
    pm: PositionManager = Depends(get_position_manager),
):
    try:
        account = broker.get_account()
        positions = pm.get_all()

        unrealized = sum(float(p.unrealized_pl) for p in positions)
        equity = float(account.equity)
        last_equity = float(account.last_equity) if hasattr(account, "last_equity") and account.last_equity else equity
        daily_pnl = equity - last_equity

        return PnLResponse(
            total_pnl=equity - float(account.cash) + unrealized,
            daily_pnl=daily_pnl,
            unrealized_pnl=unrealized,
            realized_pnl=daily_pnl - unrealized,
        )
    except Exception as e:
        logger.error("Error al calcular PnL: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance", response_model=PerformanceResponse)
def get_performance(db: Database = Depends(get_db)):
    try:
        cursor = db.conn.cursor()
        cursor.execute("SELECT price, side FROM trades WHERE price IS NOT NULL")
        trades = cursor.fetchall()

        total = len(trades)
        if total == 0:
            return PerformanceResponse(
                total_trades=0, winning_trades=0, losing_trades=0,
                win_rate=0.0, avg_profit=0.0, avg_loss=0.0,
            )

        profits = []
        losses = []
        for t in trades:
            price = float(t[0]) if t[0] else 0
            if price > 0:
                profits.append(price)
            elif price < 0:
                losses.append(price)

        winning = len(profits)
        losing = len(losses)

        return PerformanceResponse(
            total_trades=total,
            winning_trades=winning,
            losing_trades=losing,
            win_rate=(winning / total * 100) if total > 0 else 0.0,
            avg_profit=(sum(profits) / winning) if winning > 0 else 0.0,
            avg_loss=(sum(losses) / losing) if losing > 0 else 0.0,
        )
    except Exception as e:
        logger.error("Error al calcular métricas: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

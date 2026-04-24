import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import AccountResponse, PositionResponse, OrderRequest, OrderResponse
from app.api.deps import get_current_user, get_broker, get_order_manager, get_position_manager
from app.broker import AlpacaBroker
from app.orders import OrderManager
from app.positions import PositionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/broker", tags=["Broker"], dependencies=[Depends(get_current_user)])


@router.get("/account", response_model=AccountResponse)
def get_account(broker: AlpacaBroker = Depends(get_broker)):
    try:
        account = broker.get_account()
        return AccountResponse(
            id=str(account.id),
            equity=str(account.equity),
            cash=str(account.cash),
            buying_power=str(account.buying_power),
            portfolio_value=str(account.portfolio_value),
            currency=str(account.currency),
            status=str(account.status),
        )
    except Exception as e:
        logger.error("Error al obtener cuenta: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions", response_model=list[PositionResponse])
def get_positions(pm: PositionManager = Depends(get_position_manager)):
    try:
        positions = pm.get_all()
        return [
            PositionResponse(
                symbol=str(p.symbol),
                qty=str(p.qty),
                side=str(p.side),
                avg_entry_price=str(p.avg_entry_price),
                current_price=str(p.current_price),
                unrealized_pl=str(p.unrealized_pl),
                unrealized_plpc=str(p.unrealized_plpc),
            )
            for p in positions
        ]
    except Exception as e:
        logger.error("Error al obtener posiciones: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders", response_model=list[OrderResponse])
def get_orders(om: OrderManager = Depends(get_order_manager)):
    try:
        orders = om.get_open_orders()
        return [
            OrderResponse(
                id=str(o.id),
                symbol=str(o.symbol),
                qty=str(o.qty),
                side=str(o.side),
                status=str(o.status),
                submitted_at=str(o.submitted_at) if o.submitted_at else None,
            )
            for o in orders
        ]
    except Exception as e:
        logger.error("Error al obtener órdenes: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders", response_model=OrderResponse)
def create_order(body: OrderRequest, om: OrderManager = Depends(get_order_manager)):
    try:
        signal = {"action": body.side, "symbol": body.symbol, "qty": body.qty}
        order = om.submit(signal)
        if order is None:
            raise HTTPException(status_code=400, detail="No se pudo enviar la orden")
        return OrderResponse(
            id=str(order.id),
            symbol=str(order.symbol),
            qty=str(order.qty),
            side=str(order.side),
            status=str(order.status),
            submitted_at=str(order.submitted_at) if order.submitted_at else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error al crear orden: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

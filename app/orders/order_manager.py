import logging

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

logger = logging.getLogger(__name__)


class OrderManager:
    """Gestiona el envío y seguimiento de órdenes."""

    def __init__(self, trading_client: TradingClient):
        self.trading_client = trading_client

    def submit(self, signal: dict):
        """Envía una orden al broker basándose en la señal recibida."""
        side = OrderSide.BUY if signal["action"] == "buy" else OrderSide.SELL

        order_request = MarketOrderRequest(
            symbol=signal["symbol"],
            qty=signal["qty"],
            side=side,
            time_in_force=TimeInForce.DAY,
        )

        try:
            order = self.trading_client.submit_order(order_request)
            logger.info("Orden enviada: %s %s x%s | ID: %s", side, signal["symbol"], signal["qty"], order.id)
            return order
        except Exception as e:
            logger.error("Error al enviar orden: %s", e, exc_info=True)
            return None

    def cancel(self, order_id: str):
        try:
            self.trading_client.cancel_order_by_id(order_id)
            logger.info("Orden cancelada: %s", order_id)
        except Exception as e:
            logger.error("Error al cancelar orden %s: %s", order_id, e)

    def get_open_orders(self):
        return self.trading_client.get_orders()

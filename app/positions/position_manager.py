import logging

from alpaca.trading.client import TradingClient

logger = logging.getLogger(__name__)


class PositionManager:
    """Gestiona las posiciones abiertas."""

    def __init__(self, trading_client: TradingClient):
        self.trading_client = trading_client

    def get_all(self):
        return self.trading_client.get_all_positions()

    def get_by_symbol(self, symbol: str):
        try:
            return self.trading_client.get_open_position(symbol)
        except Exception:
            return None

    def close(self, symbol: str):
        try:
            self.trading_client.close_position(symbol)
            logger.info("Posición cerrada: %s", symbol)
        except Exception as e:
            logger.error("Error al cerrar posición %s: %s", symbol, e)

    def close_all(self):
        try:
            self.trading_client.close_all_positions(cancel_orders=True)
            logger.info("Todas las posiciones cerradas.")
        except Exception as e:
            logger.error("Error al cerrar todas las posiciones: %s", e)

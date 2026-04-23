import logging

from app.broker import AlpacaBroker
from app.strategy import BaseStrategy
from app.orders import OrderManager
from app.risk import RiskManager
from app.positions import PositionManager

logger = logging.getLogger(__name__)


class TradingEngine:
    """Motor principal que coordina la ejecución del bot de trading."""

    def __init__(
        self,
        broker: AlpacaBroker,
        strategy: BaseStrategy,
        order_manager: OrderManager,
        risk_manager: RiskManager,
        position_manager: PositionManager,
    ):
        self.broker = broker
        self.strategy = strategy
        self.order_manager = order_manager
        self.risk_manager = risk_manager
        self.position_manager = position_manager
        self.is_running = False

    def start(self):
        logger.info("Iniciando motor de trading con estrategia: %s", self.strategy.name)
        self.is_running = True
        self.run()

    def stop(self):
        logger.info("Deteniendo motor de trading.")
        self.is_running = False

    def run(self):
        while self.is_running:
            if not self.broker.is_market_open():
                logger.info("Mercado cerrado. Esperando...")
                continue

            self._tick()

    def _tick(self):
        """Ejecuta un ciclo de evaluación de la estrategia."""
        try:
            signal = self.strategy.evaluate(None)
            if signal["action"] == "hold":
                return

            if not self.risk_manager.validate(signal):
                logger.warning("Señal rechazada por gestión de riesgo: %s", signal)
                return

            self.order_manager.submit(signal)
        except Exception as e:
            logger.error("Error en tick de trading: %s", e, exc_info=True)

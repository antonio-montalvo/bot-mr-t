from dotenv import load_dotenv

load_dotenv()

from app.auth import AlpacaAuth
from app.broker import AlpacaBroker
from app.orders import OrderManager
from app.positions import PositionManager
from app.risk import RiskManager
from app.db import Database
from app.logs import setup_logger


def main():
    logger = setup_logger()
    logger.info("=== Bot Mr T - Iniciando ===")

    # Autenticación
    auth = AlpacaAuth()
    broker = AlpacaBroker(auth)

    # Verificar conexión
    account = broker.get_account()
    logger.info("Cuenta: %s | Equity: %s | Cash: %s", account.id, account.equity, account.cash)

    # Componentes
    order_manager = OrderManager(auth.client)
    position_manager = PositionManager(auth.client)
    risk_manager = RiskManager()

    # Base de datos
    db = Database()
    db.connect()

    logger.info("Bot Mr T listo. Todos los componentes inicializados.")

    # TODO: Implementar estrategia concreta y conectar con TradingEngine
    # from app.trading import TradingEngine
    # engine = TradingEngine(broker, strategy, order_manager, risk_manager, position_manager)
    # engine.start()

    db.close()
    logger.info("=== Bot Mr T - Finalizado ===")


if __name__ == "__main__":
    main()

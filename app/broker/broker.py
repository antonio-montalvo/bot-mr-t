from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from app.auth import AlpacaAuth


class AlpacaBroker:
    """Interfaz con el broker Alpaca para obtener datos de mercado y cuenta."""

    def __init__(self, auth: AlpacaAuth):
        self.trading_client: TradingClient = auth.client
        self.data_client = StockHistoricalDataClient(
            api_key=auth.api_key,
            secret_key=auth.api_secret,
        )

    def get_account(self):
        return self.trading_client.get_account()

    def get_bars(self, symbol: str, timeframe: TimeFrame, start: str, end: str):
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
        )
        return self.data_client.get_stock_bars(request)

    def is_market_open(self) -> bool:
        clock = self.trading_client.get_clock()
        return clock.is_open

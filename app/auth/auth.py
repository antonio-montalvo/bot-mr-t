import os
from alpaca.trading.client import TradingClient


class AlpacaAuth:
    """Gestiona la autenticación con la API de Alpaca."""

    def __init__(self):
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.api_secret = os.getenv("ALPACA_SECRET_KEY")
        self.base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        self._client = None

    @property
    def client(self) -> TradingClient:
        if self._client is None:
            if not self.api_key or not self.api_secret:
                raise ValueError(
                    "ALPACA_API_KEY y ALPACA_SECRET_KEY deben estar configuradas como variables de entorno."
                )
            self._client = TradingClient(
                api_key=self.api_key,
                secret_key=self.api_secret,
                paper=True,
            )
        return self._client

from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """Clase base abstracta para todas las estrategias de trading."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def evaluate(self, market_data) -> dict:
        """Evalúa los datos de mercado y retorna una señal de trading.

        Returns:
            dict con claves: action ('buy', 'sell', 'hold'), symbol, qty, reason
        """
        pass

    @abstractmethod
    def should_enter(self, market_data) -> bool:
        """Determina si se debe abrir una posición."""
        pass

    @abstractmethod
    def should_exit(self, market_data) -> bool:
        """Determina si se debe cerrar una posición."""
        pass

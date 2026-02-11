# AlphaWheel Pro - Base para proveedores (provider agnostic)
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderStatus:
    """Estado de conexión del proveedor: Online / Offline."""
    online: bool
    message: str = ""


class BaseProvider(ABC):
    """Interfaz común para brokers (Tradier, futuro otro)."""

    @abstractmethod
    def validate_connection(self) -> ProviderStatus:
        """Valida la conexión y devuelve estado Online/Offline."""
        pass

    @abstractmethod
    def get_quote(self, symbol: str) -> Optional[float]:
        """Obtiene el precio actual del símbolo. None o error si falla."""
        pass

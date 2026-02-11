# AlphaWheel Pro - Integración Tradier (modular; tokens desde panel de configuración)
import requests
from typing import Optional

from engine.calculations import round2
from .base import BaseProvider, ProviderStatus


class TradierProvider(BaseProvider):
    """Proveedor Tradier. Token y entorno se configuran desde la app (panel de configuración)."""

    def __init__(self, access_token: str, environment: str = "sandbox"):
        self.token = (access_token or "").strip()
        if environment == "prod":
            self.base_url = "https://api.tradier.com/v1/"
        else:
            self.base_url = "https://sandbox.tradier.com/v1/"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

    def validate_connection(self) -> ProviderStatus:
        """Verifica si el token es válido. Muestra estado Online/Offline."""
        if not self.token:
            return ProviderStatus(online=False, message="Token no configurado")
        try:
            url = f"{self.base_url}user/profile"
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return ProviderStatus(online=True, message="Conectado")
            return ProviderStatus(online=False, message=f"API: {response.status_code}")
        except Exception as e:
            return ProviderStatus(online=False, message=f"Conexión: {str(e)}")

    def get_quote(self, symbol: str) -> Optional[float]:
        """Precio actual del ticker. Devuelve None si hay error (evita usar string en cálculos)."""
        if not self.token or not symbol:
            return None
        url = f"{self.base_url}markets/quotes"
        params = {"symbols": symbol.upper()}
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            if response.status_code != 200:
                return None
            data = response.json()
            quote = data.get("quotes", {}).get("quote")
            if not quote:
                return None
            last_price = float(quote.get("last", 0))
            return round2(last_price)
        except Exception:
            return None


# Compatibilidad con código que importa TradierClient desde tradier_engine
def TradierClient(token: str, environment: str = "sandbox"):
    return TradierProvider(token, environment)

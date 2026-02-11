import requests

class TradierClient:
    def __init__(self, token, environment="sandbox"):
        """
        Si tu cuenta es real, cambia environment a 'prod'.
        Si es de prueba, déjalo en 'sandbox'.
        """
        self.token = token
        if environment == "prod":
            self.base_url = "https://api.tradier.com/v1/"
        else:
            self.base_url = "https://sandbox.tradier.com/v1/"
            
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }

    def validate_token(self):
        """Verifica si el token es válido consultando el perfil del usuario."""
        url = f"{self.base_url}user/profile"
        response = requests.get(url, headers=self.headers)
        return response.status_code == 200

    def get_quote(self, symbol):
        """Obtiene el precio actual de un ticker redondeado a 2 decimales."""
        url = f"{self.base_url}markets/quotes"
        params = {'symbols': symbol.upper()}
        
        try:
            response = requests.get(url, params=params, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                # Tradier devuelve los datos dentro de 'quotes' -> 'quote'
                quote = data['quotes']['quote']
                last_price = float(quote['last'])
                return round(last_price, 2)
            else:
                return f"Error: {response.status_code}"
        except Exception as e:
            return f"Error de conexión: {str(e)}"

# --- PEQUEÑA PRUEBA DE CONEXIÓN ---
if __name__ == "__main__":
    # Sustituye 'TU_TOKEN_AQUI' por tu token real de Tradier para probar
    MI_TOKEN = "TU_TOKEN_AQUI" 
    client = TradierClient(MI_TOKEN, environment="sandbox")
    
    if client.validate_token():
        print("✅ Token Válido. Conexión exitosa.")
        precio = client.get_quote("SPY")
        print(f"📈 El precio actual de SPY es: {precio}")
    else:
        print("❌ Error: El Token no es válido o ha expirado.")
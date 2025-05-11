import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Configurações do mercado da Steam
STEAM_MARKET_CURRENCY = int(os.getenv('STEAM_MARKET_CURRENCY', '7'))  # 7 = BRL (Real Brasileiro)
STEAM_APPID = int(os.getenv('STEAM_APPID', '730'))  # 730 = CS2
STEAM_REQUEST_DELAY = float(os.getenv('STEAM_REQUEST_DELAY', '1.0'))  # 1 segundo


def get_api_config() -> dict:
    """Retorna um dicionário com as configurações atuais da API."""
    return {
        "currency": STEAM_MARKET_CURRENCY,
        "currency_name": "BRL" if STEAM_MARKET_CURRENCY == 7 else "Desconhecida",
        "appid": STEAM_APPID,
        "app_name": "Counter-Strike 2" if STEAM_APPID == 730 else "Desconhecido",
        "request_delay": STEAM_REQUEST_DELAY
    }

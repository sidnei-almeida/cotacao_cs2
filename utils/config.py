import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Configurações do mercado da Steam
STEAM_API_KEY = os.getenv('STEAM_API_KEY', '56C6D1730D781A4FE3A05830CDF23E8A')  # Chave API da Steam
STEAM_MARKET_CURRENCY = int(os.getenv('STEAM_MARKET_CURRENCY', '1'))  # 1 = USD (Dólar Americano)
STEAM_APPID = int(os.getenv('STEAM_APPID', '730'))  # 730 = CS2

# Configurações de rate limit
# Limite oficial da Steam: 200 requisições a cada 5 minutos (= 1 requisição a cada 1.5 segundos em média)
STEAM_REQUEST_DELAY = float(os.getenv('STEAM_REQUEST_DELAY', '1.8'))  # 1.8 segundos entre requisições (margem de segurança)
STEAM_MAX_RETRIES = int(os.getenv('STEAM_MAX_RETRIES', '3'))  # Número máximo de tentativas
STEAM_MAX_DELAY = float(os.getenv('STEAM_MAX_DELAY', '15.0'))  # Delay máximo em segundos

# Limite diário (100.000 requisições por dia)
STEAM_DAILY_LIMIT = int(os.getenv('STEAM_DAILY_LIMIT', '100000'))


def get_api_config() -> dict:
    """Retorna um dicionário com as configurações atuais da API."""
    return {
        "steam_api_key": STEAM_API_KEY[:5] + "..." if STEAM_API_KEY else "Não configurada",
        "currency": STEAM_MARKET_CURRENCY,
        "currency_name": "USD" if STEAM_MARKET_CURRENCY == 1 else "BRL" if STEAM_MARKET_CURRENCY == 7 else "Desconhecida",
        "appid": STEAM_APPID,
        "app_name": "Counter-Strike 2" if STEAM_APPID == 730 else "Desconhecido",
        "rate_limit": {
            "request_delay": STEAM_REQUEST_DELAY,
            "max_retries": STEAM_MAX_RETRIES,
            "max_delay": STEAM_MAX_DELAY,
            "requests_per_5min": int(300 / STEAM_REQUEST_DELAY),  # Estimativa baseada no delay
            "daily_limit": STEAM_DAILY_LIMIT
        }
    }

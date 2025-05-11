import requests
import json
import time
from typing import Dict, List, Any, Optional
from cachetools import TTLCache
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente (se existir um arquivo .env)
load_dotenv()

# Configurações
STEAM_MARKET_CURRENCY = int(os.getenv('STEAM_MARKET_CURRENCY', '7'))  # 7 = BRL
STEAM_APPID = int(os.getenv('STEAM_APPID', '730'))  # CS2
STEAM_REQUEST_DELAY = float(os.getenv('STEAM_REQUEST_DELAY', '1.0'))

# Cache para armazenar preços temporariamente (10 minutos de TTL)
price_cache = TTLCache(maxsize=1000, ttl=600)

# URL do endpoint não oficial de preços do mercado da Steam
STEAM_MARKET_URL = "https://steamcommunity.com/market/priceoverview"


def get_item_price(market_hash_name: str, currency: int = None, appid: int = None) -> float:
    """
    Obtém o preço atual de um item no mercado da Steam usando o endpoint não oficial.
    
    Args:
        market_hash_name: Nome do item formatado para o mercado
        currency: Código da moeda (7 = Real Brasileiro). Se None, usa o valor de configuração
        appid: ID da aplicação na Steam (730 = CS2). Se None, usa o valor de configuração
        
    Returns:
        Preço médio do item em BRL
    """
    # Usa valores de configuração se não especificados
    if currency is None:
        currency = STEAM_MARKET_CURRENCY
        
    if appid is None:
        appid = STEAM_APPID
        
    # Verifica se o preço está em cache
    cache_key = f"{market_hash_name}_{currency}_{appid}"
    if cache_key in price_cache:
        return price_cache[cache_key]
    
    # Tenta obter o preço real do mercado da Steam
    price = get_market_price(market_hash_name, currency, appid)
    if price is not None:
        price_cache[cache_key] = price
        return price
    
    # Se não conseguir obter o preço real, usar dados mockados
    # Simulação de preços para fins de desenvolvimento
    mock_prices = {
        "Operation Broken Fang Case": 3.50,
        "Prisma Case": 15.75,
        "Clutch Case": 5.20,
        "Snakebite Case": 2.85,
        "AWP | Asiimov (Field-Tested)": 350.0,
        "AK-47 | Redline (Field-Tested)": 120.0,
        "★ Karambit | Doppler (Factory New)": 3500.0,
        "M4A4 | The Emperor (Minimal Wear)": 85.0,
        "USP-S | Kill Confirmed (Well-Worn)": 155.0,
    }
    
    # Retornar um preço mockado ou um valor padrão
    price = mock_prices.get(market_hash_name, 10.0)
    
    # Armazena em cache
    price_cache[cache_key] = price
    
    return price


def get_market_price(market_hash_name: str, currency: int, appid: int) -> Optional[float]:
    """
    Obtém o preço real de um item do mercado da Steam usando o endpoint não oficial.
    
    Args:
        market_hash_name: Nome do item formatado para o mercado
        currency: Código da moeda (7 = Real Brasileiro)
        appid: ID da aplicação na Steam (730 = CS2)
        
    Returns:
        Preço médio do item ou None se falhar
    """
    params = {
        "currency": currency,
        "appid": appid,
        "market_hash_name": market_hash_name
    }
    
    try:
        response = requests.get(STEAM_MARKET_URL, params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            # A resposta da Steam contém 'lowest_price' e possivelmente 'median_price'
            if "median_price" in data:
                # Remover símbolo de moeda e converter para float
                price_str = data["median_price"].replace("R$", "").replace(",", ".").strip()
                return float(price_str)
            elif "lowest_price" in data:
                price_str = data["lowest_price"].replace("R$", "").replace(",", ".").strip()
                return float(price_str)
        
        # Se recebeu erro 429 (Too Many Requests) ou outro erro
        elif response.status_code == 429:
            print(f"Rate limit excedido na API do mercado da Steam. Aguardando {STEAM_REQUEST_DELAY} segundos.")
            time.sleep(STEAM_REQUEST_DELAY * 2)  # Espera mais tempo em caso de limite de taxa
            
        else:
            print(f"Erro ao acessar API do mercado: Status {response.status_code}")
            
    except Exception as e:
        print(f"Erro ao obter preço via mercado para {market_hash_name}: {e}")
    
    # Respeitar limite de requisições independente do resultado
    time.sleep(STEAM_REQUEST_DELAY)
    
    return None


def get_item_listings_page(market_hash_name: str, appid: int = None) -> Optional[str]:
    """
    Obtém a página HTML de listagens do mercado para um item específico.
    Essa função pode ser usada para scraping de informações adicionais.
    
    Args:
        market_hash_name: Nome do item formatado para o mercado
        appid: ID da aplicação na Steam (730 = CS2). Se None, usa configuração
        
    Returns:
        HTML da página ou None se falhar
    """
    if appid is None:
        appid = STEAM_APPID
        
    # URL da página de listagens do mercado
    url = f"https://steamcommunity.com/market/listings/{appid}/{market_hash_name}"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.text
        else:
            print(f"Erro ao acessar página do mercado: Status {response.status_code}")
            
        # Respeitar limite de requisições
        time.sleep(STEAM_REQUEST_DELAY)
        
    except Exception as e:
        print(f"Erro ao obter página de listagens para {market_hash_name}: {e}")
    
    return None


def get_api_status() -> Dict[str, Any]:
    """
    Verifica o status da API do mercado da Steam e faz um teste de conexão.
    
    Returns:
        Dicionário com informações sobre o status da API
    """
    result = {
        "market_api_reachable": False,
        "currency": STEAM_MARKET_CURRENCY,
        "appid": STEAM_APPID
    }
    
    # Testar conexão com API do mercado (não requer chave)
    try:
        test_item = "Operation Broken Fang Case"
        params = {
            "currency": STEAM_MARKET_CURRENCY,
            "appid": STEAM_APPID,
            "market_hash_name": test_item
        }
        
        response = requests.get(STEAM_MARKET_URL, params=params)
        result["market_api_reachable"] = response.status_code == 200
        
        if response.status_code == 200:
            data = response.json()
            result["test_response"] = data
        
    except Exception as e:
        print(f"Erro ao testar API do mercado: {e}")
        result["error"] = str(e)
    
    return result
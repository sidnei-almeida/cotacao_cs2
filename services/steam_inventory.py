import requests
import json
import time
from typing import Dict, List, Any, Optional
from services.steam_market import get_item_price
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente (se existir um arquivo .env)
load_dotenv()

# Configurações
STEAM_MARKET_CURRENCY = int(os.getenv('STEAM_MARKET_CURRENCY', '7'))  # 7 = BRL
STEAM_APPID = int(os.getenv('STEAM_APPID', '730'))  # CS2
STEAM_REQUEST_DELAY = float(os.getenv('STEAM_REQUEST_DELAY', '1.0'))

# URL base da API de inventário da Steam
STEAM_INVENTORY_URL = "https://steamcommunity.com/inventory/{steamid}/730/2"


def get_inventory_value(steamid: str) -> Dict[str, Any]:
    """
    Obtém o valor do inventário de CS2 de um usuário.
    
    Args:
        steamid: ID da Steam do usuário
        
    Returns:
        Dicionário com informações do inventário e valor total
    """
    # Neste momento, como não temos acesso à API da Steam, vamos criar uma simulação
    # Quando tivermos acesso à API, esta função será substituída pela implementação real
    
    # Exemplo de inventário mockado para fins de desenvolvimento
    mock_inventory = [
        {
            "name": "AWP | Asiimov (Field-Tested)",
            "market_hash_name": "AWP | Asiimov (Field-Tested)",
            "quantity": 1,
            "category": "Sniper Rifle",
            "rarity": "Covert",
            "exterior": "Field-Tested",
            "tradable": True,
            "image": "https://csgostash.com/img/skins/AWP+Asiimov+Field-Tested.png"
        },
        {
            "name": "AK-47 | Redline (Field-Tested)",
            "market_hash_name": "AK-47 | Redline (Field-Tested)",
            "quantity": 1,
            "category": "Rifle",
            "rarity": "Classified",
            "exterior": "Field-Tested",
            "tradable": True,
            "image": "https://csgostash.com/img/skins/AK-47+Redline+Field-Tested.png"
        },
        {
            "name": "Operation Broken Fang Case",
            "market_hash_name": "Operation Broken Fang Case",
            "quantity": 5,
            "category": "Container",
            "rarity": "Base Grade",
            "exterior": "Not Painted",
            "tradable": True,
            "image": "https://csgostash.com/img/containers/Operation+Broken+Fang+Case.png"
        },
        {
            "name": "Prisma Case",
            "market_hash_name": "Prisma Case",
            "quantity": 3,
            "category": "Container",
            "rarity": "Base Grade",
            "exterior": "Not Painted",
            "tradable": True,
            "image": "https://csgostash.com/img/containers/Prisma+Case.png"
        }
    ]
    
    # Calcular o valor dos itens e adicionar ao resultado
    total_value = 0.0
    items_with_price = []
    
    for item in mock_inventory:
        item_name = item.get("market_hash_name", "")
        item_quantity = item.get("quantity", 1)
        price = get_item_price(item_name)
        item_total = price * item_quantity
        
        # Adicionar o preço ao item
        item_with_price = item.copy()
        item_with_price["price"] = price
        item_with_price["total"] = item_total
        items_with_price.append(item_with_price)
        
        # Adicionar ao valor total
        total_value += item_total
    
    # Retornar o resultado
    return {
        "steamid": steamid,
        "total_items": sum(item.get("quantity", 1) for item in mock_inventory),
        "total_value": total_value,
        "currency": "BRL",
        "items": items_with_price
    }


def get_real_inventory(steamid: str, appid: int = None) -> Optional[Dict[str, Any]]:
    """
    Obtém o inventário real de um usuário da Steam.
    
    Args:
        steamid: ID da Steam do usuário
        appid: ID da aplicação na Steam. Se None, usa o valor de configuração
        
    Returns:
        Dicionário com informações do inventário ou None se falhar
    """
    if appid is None:
        appid = STEAM_APPID
        
    # Obter o inventário via endpoint público
    url = STEAM_INVENTORY_URL.format(steamid=steamid)
    
    try:
        # Adicionar user-agent para evitar bloqueios
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            inventory_data = response.json()
            
            # Processar os dados do inventário
            processed_inventory = process_inventory_data(inventory_data, steamid)
            return processed_inventory
        elif response.status_code == 403:
            print(f"Inventário privado ou não acessível para o usuário {steamid}")
        else:
            print(f"Erro ao acessar inventário: Status {response.status_code}")
            
    except Exception as e:
        print(f"Erro ao obter inventário para {steamid}: {e}")
    
    # Respeitar limite de requisições
    time.sleep(STEAM_REQUEST_DELAY)
    
    return None


def process_inventory_data(inventory_data: Dict[str, Any], steamid: str) -> Dict[str, Any]:
    """
    Processa os dados brutos do inventário da Steam.
    
    Args:
        inventory_data: Dados brutos do inventário
        steamid: ID da Steam do usuário
        
    Returns:
        Dicionário processado com itens do inventário
    """
    result = {
        "steamid": steamid,
        "total_items": 0,
        "total_value": 0.0,
        "currency": "BRL",
        "items": []
    }
    
    try:
        # Verifica se temos as informações necessárias
        if "assets" not in inventory_data or "descriptions" not in inventory_data:
            print("Formato de inventário inválido ou inventário vazio")
            return result
            
        # Mapear 'descriptions' pelo classid para acesso rápido
        descriptions = {}
        for desc in inventory_data["descriptions"]:
            key = f"{desc.get('classid')}_{desc.get('instanceid')}"
            descriptions[key] = desc
            
        # Processar cada item do inventário
        processed_items = []
        total_value = 0.0
        
        for asset in inventory_data["assets"]:
            asset_id = asset.get("assetid")
            classid = asset.get("classid")
            instanceid = asset.get("instanceid")
            amount = int(asset.get("amount", 1))
            
            # Encontrar a descrição do item
            desc_key = f"{classid}_{instanceid}"
            if desc_key in descriptions:
                desc = descriptions[desc_key]
                
                # Extrair informações relevantes
                market_hash_name = desc.get("market_hash_name", "")
                name = desc.get("name", "")
                type_info = desc.get("type", "")
                tradable = desc.get("tradable", 0) == 1
                
                # Obter preço do item
                price = get_item_price(market_hash_name) if tradable else 0.0
                item_total = price * amount
                
                # Determinar categoria e raridade com base no tipo_info
                category, rarity, exterior = parse_item_type(type_info, desc)
                
                # Obter URL da imagem
                image_url = desc.get("icon_url", "")
                if image_url and not image_url.startswith("http"):
                    image_url = f"https://community.akamai.steamstatic.com/economy/image/{image_url}"
                    
                # Adicionar item processado à lista
                processed_item = {
                    "assetid": asset_id,
                    "name": name,
                    "market_hash_name": market_hash_name,
                    "quantity": amount,
                    "category": category,
                    "rarity": rarity,
                    "exterior": exterior,
                    "tradable": tradable,
                    "price": price,
                    "total": item_total,
                    "image": image_url
                }
                
                processed_items.append(processed_item)
                total_value += item_total
                
        # Atualizar o resultado final
        result["items"] = processed_items
        result["total_items"] = len(processed_items)
        result["total_value"] = total_value
            
    except Exception as e:
        print(f"Erro ao processar dados do inventário: {e}")
        
    return result


def process_api_inventory_data(api_data: Dict[str, Any], steamid: str) -> Dict[str, Any]:
    """
    Processa os dados brutos do inventário obtidos via API oficial.
    
    Args:
        api_data: Dados brutos do inventário da API
        steamid: ID da Steam do usuário
        
    Returns:
        Dicionário processado com itens do inventário
    """
    # Nota: Esta função seria implementada quando tivermos acesso à API oficial
    # Por enquanto, retornamos um resultado vazio para simular
    return {
        "steamid": steamid,
        "total_items": 0,
        "total_value": 0.0,
        "currency": "BRL",
        "items": [],
        "api_used": True  # Indica que usamos a API oficial
    }


def parse_item_type(type_info: str, desc: Dict[str, Any]) -> tuple:
    """
    Analisa o tipo do item para extrair categoria, raridade e exterior.
    
    Args:
        type_info: String de tipo do item da Steam
        desc: Dicionário de descrição do item
        
    Returns:
        Tupla com (categoria, raridade, exterior)
    """
    # Valores padrão
    category = "Other"
    rarity = "Base Grade"
    exterior = "Not Painted"
    
    # Determinar categoria
    if "Rifle" in type_info:
        category = "Rifle"
    elif "Pistol" in type_info:
        category = "Pistol"
    elif "Sniper Rifle" in type_info:
        category = "Sniper Rifle"
    elif "SMG" in type_info:
        category = "SMG"
    elif "Shotgun" in type_info:
        category = "Shotgun"
    elif "Container" in type_info or "Case" in type_info:
        category = "Container"
    elif "Key" in type_info:
        category = "Key"
    elif "Knife" in type_info:
        category = "Knife"
    elif "Gloves" in type_info:
        category = "Gloves"
    
    # Determinar raridade com base nas tags
    if "tags" in desc:
        for tag in desc["tags"]:
            # Verificar categoria de raridade
            if tag.get("category") == "Rarity":
                rarity = tag.get("name", rarity)
                
            # Verificar exterior
            if tag.get("category") == "Exterior":
                exterior = tag.get("name", exterior)
                
    return category, rarity, exterior
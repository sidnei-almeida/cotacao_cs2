import requests
import json
import time
from typing import Dict, List, Any, Optional
from services.steam_market import get_item_price, get_steam_api_data
from utils.config import STEAM_API_KEY, STEAM_MARKET_CURRENCY, STEAM_APPID, STEAM_REQUEST_DELAY
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente (se existir um arquivo .env)
load_dotenv()

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
    print(f"Iniciando obtenção do inventário para SteamID: {steamid}")
    
    # Limpar o ID Steam de caracteres indesejados ou codificação URL
    # Remover chaves {} e qualquer codificação URL (%7B = { e %7D = })
    steamid = steamid.replace("{", "").replace("}", "").replace("%7B", "").replace("%7D", "")
    print(f"ID Steam normalizado: {steamid}")
    
    # Primeiro tentar obter o inventário usando o endpoint público
    print("Tentando obter inventário via endpoint público...")
    real_inventory = get_real_inventory(steamid)
    if real_inventory:
        print(f"Inventário completo obtido via endpoint público: {len(real_inventory.get('items', []))} itens encontrados")
        return real_inventory
    
    # Se falhar, tentar com a API oficial (se configurada)
    if STEAM_API_KEY:
        print(f"Endpoint público falhou, tentando API oficial...")
        api_inventory = get_api_inventory(steamid)
        if api_inventory:
            print(f"Inventário completo obtido via API oficial: {len(api_inventory.get('items', []))} itens encontrados")
            return api_inventory
        print("Falha ao obter inventário via API oficial.")
    else:
        print("Chave API não configurada e endpoint público falhou.")
    
    # Retornar inventário vazio em vez de dados mockados
    print(f"Não foi possível obter inventário para {steamid} ou o inventário está vazio")
    
    # Criar um inventário vazio válido
    return {
        "steamid": steamid,
        "total_items": 0,
        "total_value": 0.0,
        "currency": "BRL",
        "items": [],
        "most_valuable_item": None,
        "storage_units": [],
        "market_items": [],
        "storage_units_count": 0,
        "market_items_count": 0,
        "average_item_value": 0.0,
        "note": "Inventário vazio ou não acessível"
    }


def get_api_inventory(steamid: str) -> Optional[Dict[str, Any]]:
    """
    Obtém o inventário de um usuário da Steam usando a API oficial.
    
    Args:
        steamid: ID da Steam do usuário
        
    Returns:
        Dicionário com informações do inventário ou None se falhar
    """
    print(f"Tentando obter inventário via API oficial para {steamid}...")
    
    # Usar a API oficial para obter o inventário
    # A API oficial IEconItems_730 já retorna todos os itens de uma vez
    # sem necessidade de paginação na maioria dos casos
    inventory_data = get_steam_api_data(
        "IEconItems_730",  # Interface para CS2
        "GetPlayerItems",  # Método
        "v1",              # Versão
        {"steamid": steamid}
    )
    
    if inventory_data:
        print(f"Inventário obtido com sucesso via API oficial para {steamid}")
        # Processar os dados da API oficial
        return process_api_inventory_data(inventory_data, steamid)
    else:
        print(f"Falha ao obter inventário via API oficial para {steamid}")
        
    return None


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
        
    # Obter o inventário completo via endpoint público com suporte a paginação
    all_assets = []
    all_descriptions = []
    
    # URL base da API de inventário
    base_url = STEAM_INVENTORY_URL.format(steamid=steamid)
    
    # Iniciar com a primeira página
    url = base_url
    count = 0
    max_tries = 30  # Aumentando o limite para mais páginas (era 10)
    
    try:
        # Adicionar user-agent para evitar bloqueios
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Loop para obter todas as páginas do inventário
        while url and count < max_tries:
            print(f"Buscando página {count+1} do inventário para {steamid}...")
            
            response = requests.get(url, headers=headers, timeout=15)  # Adicionado timeout
            
            if response.status_code == 200:
                inventory_data = response.json()
                
                # Verificar se há dados válidos
                if "assets" not in inventory_data or "descriptions" not in inventory_data:
                    print(f"Formato de inventário inválido na página {count+1}")
                    break
                
                # Adicionar assets e descriptions desta página
                all_assets.extend(inventory_data.get("assets", []))
                all_descriptions.extend(inventory_data.get("descriptions", []))
                
                # Verificar se há mais páginas
                if "more_items" in inventory_data and inventory_data["more_items"] == 1:
                    # Obter o último assetid para a próxima página
                    last_assetid = inventory_data.get("last_assetid")
                    if last_assetid:
                        # Construir URL para a próxima página
                        url = f"{base_url}?start_assetid={last_assetid}"
                        
                        # Aguardar antes da próxima requisição para evitar limite de taxa
                        time.sleep(STEAM_REQUEST_DELAY * 1.5)
                    else:
                        print("Não foi possível obter o ID do último item para paginação")
                        break
                else:
                    # Não há mais páginas
                    break
                    
                count += 1
                print(f"Processada página {count} com {len(inventory_data.get('assets', []))} itens")
            elif response.status_code == 403:
                print(f"Inventário privado ou não acessível para o usuário {steamid}")
                return None
            else:
                print(f"Erro ao acessar inventário: Status {response.status_code}")
                return None
                
            # Respeitar limite de requisições
            time.sleep(STEAM_REQUEST_DELAY)
            
        # Combinar todas as páginas em um único objeto de inventário
        combined_inventory = {
            "assets": all_assets,
            "descriptions": all_descriptions,
            "total_inventory_count": len(all_assets)
        }
        
        # Processar os dados do inventário combinado
        if all_assets:
            processed_inventory = process_inventory_data(combined_inventory, steamid)
            print(f"Total de itens processados: {len(all_assets)} em {count} páginas")
            return processed_inventory
        else:
            print(f"Nenhum item encontrado no inventário de {steamid}")
            
    except Exception as e:
        print(f"Erro ao obter inventário para {steamid}: {e}")
        import traceback
        traceback.print_exc()
    
    return None


def process_inventory_data(inventory_data: Dict[str, Any], steamid: str) -> Dict[str, Any]:
    """
    Processa os dados brutos do inventário da Steam.
    Distingue entre itens de Unidades de Armazenamento e itens de mercado.
    
    Args:
        inventory_data: Dados brutos do inventário
        steamid: ID da Steam do usuário
        
    Returns:
        Dicionário processado com itens do inventário categorizados
    """
    result = {
        "steamid": steamid,
        "total_items": 0,
        "total_value": 0.0,
        "average_item_value": 0.0,
        "currency": "BRL",
        "items": [],
        "most_valuable_item": None,
        "storage_units": [],  # Lista de Unidades de Armazenamento
        "market_items": []    # Lista de itens do mercado
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
        storage_units = []
        market_items = []
        
        total_value = 0.0
        most_valuable_item = None
        highest_value = 0.0
        items_with_value = 0  # Para calcular a média corretamente
        
        # Contadores para estatísticas
        processed_count = 0
        valuable_count = 0
        sticker_count = 0
        
        for asset in inventory_data["assets"]:
            asset_id = asset.get("assetid")
            classid = asset.get("classid")
            instanceid = asset.get("instanceid")
            amount = int(asset.get("amount", 1))
            
            # Encontrar a descrição do item
            desc_key = f"{classid}_{instanceid}"
            if desc_key in descriptions:
                processed_count += 1
                desc = descriptions[desc_key]
                
                # Extrair informações relevantes
                market_hash_name = desc.get("market_hash_name", "")
                name = desc.get("name", "")
                type_info = desc.get("type", "")
                tradable = desc.get("tradable", 0) == 1
                
                # Verificar se é uma Unidade de Armazenamento
                is_storage_unit = "Storage Unit" in name or "Unidade de Armazenamento" in name
                
                # Verificar se é um adesivo
                is_sticker = "Sticker" in name or "Adesivo" in name
                if is_sticker:
                    sticker_count += 1
                    
                # Item especial (StatTrak, Souvenir)
                is_special = "StatTrak™" in name or "Souvenir" in name
                
                # Obter preço do item
                price = 0.0
                if tradable:
                    try:
                        price = get_item_price(market_hash_name)
                        if price > 0:
                            valuable_count += 1
                    except Exception as e:
                        print(f"Erro ao obter preço para {market_hash_name}: {e}")
                
                item_total = price * amount
                
                # Extrair categoria e tipo
                category, item_type = parse_item_type(type_info, desc)
                
                # Verificar se o item tem tags que indicam qualidade/raridade 
                tags = desc.get("tags", [])
                rarity = next((tag.get("name", "") for tag in tags if tag.get("category") == "Rarity"), "Normal")
                exterior = next((tag.get("name", "") for tag in tags if tag.get("category") == "Exterior"), "Not Painted")
                
                # Criar objeto item
                item = {
                    "assetid": asset_id,
                    "name": name,
                    "market_hash_name": market_hash_name,
                    "quantity": amount,
                    "price": price,
                    "total": item_total,
                    "tradable": tradable,
                    "category": category,
                    "type": item_type,
                    "rarity": rarity,
                    "exterior": exterior,
                    "stattrak": "StatTrak™" in name,
                    "souvenir": "Souvenir" in name,
                    "is_sticker": is_sticker,
                    "image": get_item_image(desc),
                    "source": "storage_unit" if is_storage_unit else "market"
                }
                
                # Adicionar à categoria apropriada
                if is_storage_unit:
                    storage_units.append(item)
                else:
                    market_items.append(item)
                
                # Adicionar à lista geral de itens
                processed_items.append(item)
                
                # Atualizar item mais valioso
                if price > highest_value:
                    highest_value = price
                    most_valuable_item = {
                        "name": name,
                        "market_hash_name": market_hash_name,
                        "price": price,
                        "rarity": rarity,
                        "category": category,
                        "source": "storage_unit" if is_storage_unit else "market"
                    }
                    print(f"Novo item mais valioso encontrado: {name} - R$ {price:.2f}")
                
                # Atualizar valor total
                total_value += item_total
                
                # Contar apenas itens com valor na média
                if price > 0:
                    items_with_value += amount
                
        # Atualizar resultados
        result["items"] = processed_items
        result["storage_units"] = storage_units
        result["market_items"] = market_items
        result["total_items"] = sum(item.get("quantity", 1) for item in processed_items)
        result["total_value"] = total_value
            
        # Calcular valor médio (apenas para itens com valor)
        result["average_item_value"] = total_value / items_with_value if items_with_value > 0 else 0
        
        # Atualizar item mais valioso
        result["most_valuable_item"] = most_valuable_item
        
        # Adicionar contagens por categoria
        result["storage_units_count"] = len(storage_units)
        result["market_items_count"] = len(market_items)
        
        # Adicionar estatísticas detalhadas
        result["stats"] = {
            "processed_count": processed_count,
            "valuable_items_count": valuable_count,
            "sticker_count": sticker_count,
            "total_pages_processed": inventory_data.get("total_pages", 1)
        }
        
        print(f"Processados {processed_count} itens, totalizando {result['total_items']} unidades, no valor de R$ {total_value:.2f}")
        print(f"Itens valiosos: {valuable_count}, Adesivos: {sticker_count}")
        
    except Exception as e:
        print(f"Erro ao processar inventário: {e}")
        import traceback
        traceback.print_exc()
        
    return result


def process_api_inventory_data(api_data: Dict[str, Any], steamid: str) -> Dict[str, Any]:
    """
    Processa os dados obtidos pela API oficial da Steam.
    
    Args:
        api_data: Dados brutos da API oficial
        steamid: ID da Steam do usuário
        
    Returns:
        Dicionário processado com itens do inventário
    """
    result = {
        "steamid": steamid,
        "total_items": 0,
        "total_value": 0.0,
        "average_item_value": 0.0,
        "currency": "BRL",
        "items": [],
        "most_valuable_item": None
    }
    
    try:
        # Verifica se temos as informações necessárias
        if "result" not in api_data or "status" not in api_data["result"] or api_data["result"]["status"] != 1:
            print("Erro ao obter inventário ou inventário vazio")
            return result
            
        if "items" not in api_data["result"]:
            print("Nenhum item encontrado no inventário")
            return result
            
        # Processar cada item do inventário
        items_data = api_data["result"]["items"]
        processed_items = []
        total_value = 0.0
        most_valuable_item = None
        highest_value = 0.0
        items_with_value = 0  # Para calcular a média corretamente
        
        # Debug: Contar itens processados
        processed_count = 0
        
        for item in items_data:
            processed_count += 1
            # Extrair informações relevantes do item
            item_name = item.get("name", "")
            market_hash_name = item.get("market_hash_name", item_name)
            
            # Debug para itens de alto valor
            if "Knife" in item_name or "★" in item_name or "Gloves" in item_name:
                print(f"Item potencialmente valioso encontrado: {item_name} ({market_hash_name})")
            
            # Obter categoria, raridade, exterior
            item_tags = item.get("tags", [])
            category = next((tag.get("localized_tag_name") for tag in item_tags if tag.get("category") == "Type"), "Other")
            rarity = next((tag.get("localized_tag_name") for tag in item_tags if tag.get("category") == "Rarity"), "Normal")
            exterior = next((tag.get("localized_tag_name") for tag in item_tags if tag.get("category") == "Exterior"), "Not Painted")
            
            # Verificar se é negociável
            tradable = item.get("tradable", 0) == 1
            
            # Verificar se o item é especial (Stattrak, Souvenir, etc)
            is_stattrak = "StatTrak™" in item_name
            is_souvenir = "Souvenir" in item_name
            
            # Obter preço do mercado
            price = get_item_price(market_hash_name) if tradable else 0.0
            
            # Atualizar item mais valioso
            if price > highest_value:
                highest_value = price
                most_valuable_item = {
                    "name": item_name,
                    "market_hash_name": market_hash_name,
                    "price": price
                }
                print(f"Novo item mais valioso encontrado: {item_name} - R$ {price:.2f}")
            
            # Contar para média apenas se tiver valor
            if price > 0:
                total_value += price
                items_with_value += 1
            
            # Criar objeto do item processado
            processed_item = {
                "name": item_name,
                "market_hash_name": market_hash_name,
                "category": category,
                "rarity": rarity,
                "exterior": exterior,
                "tradable": tradable,
                "stattrak": is_stattrak,
                "souvenir": is_souvenir,
                "price": price,
                "total": price,  # Quantidade é sempre 1 para itens da API oficial
                "quantity": 1,
                "image": f"https://community.cloudflare.steamstatic.com/economy/image/{item.get('icon_url', '')}"
            }
            
            processed_items.append(processed_item)
        
        print(f"Total de itens processados via API oficial: {processed_count} de {len(items_data)}")
        print(f"Total de itens com valor: {items_with_value}")
        print(f"Valor total do inventário: R$ {total_value:.2f}")
        
        # Calcular valor médio por item (apenas para itens com valor)
        average_value = total_value / items_with_value if items_with_value > 0 else 0
        print(f"Valor médio por item: R$ {average_value:.2f}")
        
        # Ordenar itens por valor (mais valiosos primeiro)
        processed_items.sort(key=lambda x: x.get("price", 0), reverse=True)
        
        # Atualizar resultado
        result["items"] = processed_items
        result["total_value"] = total_value
        result["total_items"] = len(processed_items)
        result["average_item_value"] = average_value
        result["most_valuable_item"] = most_valuable_item
        
        if most_valuable_item:
            print(f"Item mais valioso no resultado final: {most_valuable_item['name']} - R$ {most_valuable_item['price']:.2f}")
        else:
            print("AVISO: Nenhum item valioso encontrado no inventário!")
        
    except Exception as e:
        print(f"Erro ao processar dados da API oficial: {e}")
        import traceback
        traceback.print_exc()
    
    return result


def parse_item_type(type_info: str, desc: Dict[str, Any]) -> tuple:
    """
    Analisa o tipo do item para extrair categoria, raridade e exterior.
    
    Args:
        type_info: String de tipo do item da Steam
        desc: Dicionário de descrição do item
        
    Returns:
        Tupla com (categoria, item_type)
    """
    # Valores padrão
    category = "Other"
    item_type = "Normal"
    
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
                item_type = tag.get("name", item_type)
                
    return category, item_type


def get_item_image(desc: Dict[str, Any]) -> str:
    """
    Extrai a URL da imagem a partir da descrição do item.
    
    Args:
        desc: Dicionário com descrição do item
        
    Returns:
        URL da imagem do item
    """
    image_url = desc.get("icon_url", "")
    if image_url and not image_url.startswith("http"):
        image_url = f"https://community.akamai.steamstatic.com/economy/image/{image_url}"
    return image_url


def get_storage_unit_contents(storage_unit_id: str, steam_id: str, session_id: str, token: str) -> Dict[str, Any]:
    """
    Obtém os itens dentro de uma Unidade de Armazenamento.
    Requer que o usuário esteja autenticado com a Steam.
    
    Args:
        storage_unit_id: ID da Unidade de Armazenamento
        steam_id: SteamID do usuário
        session_id: ID da sessão Steam
        token: Token de autenticação Steam
        
    Returns:
        Dicionário com itens dentro da Unidade de Armazenamento
    """
    url = "https://steamcommunity.com/inventory/ajaxviewstorageunit/"
    
    cookies = {
        'sessionid': session_id,
        'steamLoginSecure': token
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': f'https://steamcommunity.com/profiles/{steam_id}/inventory/',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    data = {
        'casket_item_id': storage_unit_id,
        'sessionid': session_id
    }
    
    try:
        response = requests.post(url, cookies=cookies, headers=headers, data=data)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                # Processar os itens do resultado
                items = []
                for item_id, item_data in result.get('items', {}).items():
                    # Processar cada item na unidade de armazenamento
                    market_hash_name = item_data.get('market_hash_name', '')
                    quantity = item_data.get('amount', 1)
                    name = item_data.get('name', '')
                    
                    # Obter preço do item
                    price = get_item_price(market_hash_name)
                    
                    items.append({
                        'name': name,
                        'market_hash_name': market_hash_name,
                        'quantity': quantity,
                        'price': price,
                        'total': price * quantity,
                        'image': item_data.get('icon_url', ''),
                        'source': 'storage_unit_content'
                    })
                
                return {
                    'storage_unit_id': storage_unit_id,
                    'total_items': len(items),
                    'items': items,
                    'total_value': sum(item['total'] for item in items)
                }
            else:
                print(f"Erro ao acessar unidade: {result.get('error', 'Desconhecido')}")
        else:
            print(f"Erro HTTP ao acessar unidade: {response.status_code}")
    
    except Exception as e:
        print(f"Erro ao obter conteúdo da unidade de armazenamento: {e}")
        import traceback
        traceback.print_exc()
    
    return {
        'storage_unit_id': storage_unit_id,
        'error': 'Não foi possível acessar o conteúdo desta unidade de armazenamento',
        'items': [],
        'total_items': 0,
        'total_value': 0
    }
import json
import os
from typing import Dict, List, Any, Optional
from services.steam_market import get_item_price

# Caminhos dos arquivos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_FILE = os.path.join(BASE_DIR, 'data', 'cases.json')


def load_cases_data() -> Dict[str, Any]:
    """
    Carrega os dados das caixas do arquivo JSON.
    Se o arquivo não existir ou estiver vazio, retorna um dicionário padrão.
    """
    if os.path.exists(CASES_FILE) and os.path.getsize(CASES_FILE) > 0:
        with open(CASES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # Dados mockados para iniciar o desenvolvimento
        return {
            "cases": {
                "operation_broken_fang_case": {
                    "name": "Operation Broken Fang Case",
                    "image": "https://csgostash.com/img/containers/Operation+Broken+Fang+Case.png",
                    "items": [
                        {
                            "name": "Glock-18 | Neo-Noir",
                            "rarity": "Covert",
                            "probability": 0.0025
                        },
                        {
                            "name": "M4A1-S | Printstream",
                            "rarity": "Covert",
                            "probability": 0.0025
                        },
                        {
                            "name": "USP-S | Monster Mashup",
                            "rarity": "Classified",
                            "probability": 0.0125
                        },
                        {
                            "name": "AWP | Exoskeleton",
                            "rarity": "Classified",
                            "probability": 0.0125
                        },
                        {
                            "name": "M4A4 | Cyber Security",
                            "rarity": "Restricted",
                            "probability": 0.03
                        }
                    ]
                },
                "prisma_case": {
                    "name": "Prisma Case",
                    "image": "https://csgostash.com/img/containers/Prisma+Case.png",
                    "items": [
                        {
                            "name": "AK-47 | Asiimov",
                            "rarity": "Covert",
                            "probability": 0.0025
                        },
                        {
                            "name": "Desert Eagle | Lightbringer",
                            "rarity": "Covert",
                            "probability": 0.0025
                        },
                        {
                            "name": "AWP | Atheris",
                            "rarity": "Classified",
                            "probability": 0.0125
                        },
                        {
                            "name": "UMP-45 | Momentum",
                            "rarity": "Restricted",
                            "probability": 0.03
                        }
                    ]
                }
            }
        }


def save_cases_data(data: Dict[str, Any]) -> None:
    """Salva os dados das caixas no arquivo JSON."""
    os.makedirs(os.path.dirname(CASES_FILE), exist_ok=True)
    with open(CASES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def list_cases() -> List[Dict[str, str]]:
    """
    Lista todas as caixas suportadas pela API.
    
    Returns:
        Lista de dicionários com informações básicas de cada caixa
    """
    cases_data = load_cases_data()
    result = []
    
    for case_id, case_info in cases_data.get("cases", {}).items():
        result.append({
            "id": case_id,
            "name": case_info.get("name", "Unknown"),
            "image": case_info.get("image", "")
        })
    
    return result


def get_case_details(case_name: str) -> Dict[str, Any]:
    """
    Obtém detalhes sobre uma caixa específica, incluindo itens possíveis e valor esperado.
    
    Args:
        case_name: Nome ou ID da caixa
        
    Returns:
        Dicionário com detalhes da caixa, itens e valor esperado
    
    Raises:
        Exception: Se a caixa não for encontrada
    """
    cases_data = load_cases_data()
    
    # Normaliza o nome da caixa para busca (remove espaços e converte para minúsculas)
    case_name_normalized = case_name.lower().replace(' ', '_').replace('-', '_')
    
    # Procura pelo ID normalizado ou pelo nome exato
    case_info = None
    for case_id, info in cases_data.get("cases", {}).items():
        if case_id == case_name_normalized or info.get("name", "").lower() == case_name.lower():
            case_info = info
            break
    
    if not case_info:
        raise Exception(f"Caixa '{case_name}' não encontrada")
    
    # Obter o preço atual da caixa
    case_price = get_item_price(case_info.get("name", ""))
    
    # Calcular o valor esperado dos itens da caixa
    items_with_prices = []
    total_expected_value = 0.0
    
    for item in case_info.get("items", []):
        item_name = item.get("name", "")
        item_probability = item.get("probability", 0)
        item_price = get_item_price(item_name)
        
        # Adiciona o item com seu preço à lista
        items_with_prices.append({
            "name": item_name,
            "rarity": item.get("rarity", ""),
            "probability": item_probability,
            "price": item_price
        })
        
        # Adiciona ao valor esperado total (preço * probabilidade)
        total_expected_value += item_price * item_probability
    
    # Probabilidade de faca/luva (estimada)
    knife_probability = 0.0025  # 0.25%
    avg_knife_price = 1500.0  # Preço médio estimado de facas
    
    # Adiciona o valor esperado de facas/luvas
    knife_expected_value = knife_probability * avg_knife_price
    total_expected_value += knife_expected_value
    
    # Calcular o EV com fator de chave (se aplicável)
    requires_key = True  # A maioria das caixas requer chave
    key_price = 6.50 if requires_key else 0  # Preço estimado da chave
    
    # Cálculo do valor esperado final
    net_expected_value = total_expected_value - case_price - key_price
    roi_percentage = (total_expected_value / (case_price + key_price) - 1) * 100 if (case_price + key_price) > 0 else 0
    
    return {
        "name": case_info.get("name", ""),
        "image": case_info.get("image", ""),
        "price": case_price,
        "requires_key": requires_key,
        "key_price": key_price if requires_key else 0,
        "items": items_with_prices,
        "expected_value": total_expected_value,
        "net_expected_value": net_expected_value,
        "roi_percentage": roi_percentage,
        "knife_probability": knife_probability,
        "avg_knife_value": avg_knife_price
    }
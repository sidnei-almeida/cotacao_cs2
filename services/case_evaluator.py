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


def list_cases() -> List[str]:
    """
    Lista todas as caixas suportadas pela API.
    
    Returns:
        Lista com os nomes das caixas disponíveis
    """
    try:
        cases_data = load_cases_data()
        
        # Verificar se o formato do arquivo é válido
        if not isinstance(cases_data, dict) or "cases" not in cases_data:
            print("Erro: Formato inválido no arquivo de caixas")
            return []
            
        # Retornar apenas os nomes das caixas para maior compatibilidade com o frontend
        result = []
        
        for case_id, case_info in cases_data.get("cases", {}).items():
            case_name = case_info.get("name", "")
            if case_name:  # Adiciona apenas se o nome não estiver vazio
                result.append(case_name)
                
        # Verificar se encontrou alguma caixa
        if not result:
            print("Aviso: Nenhuma caixa encontrada no arquivo")
            
        print(f"Total de caixas encontradas: {len(result)}")
        print(f"Caixas: {', '.join(result)}")
        
        return result
    except Exception as e:
        import traceback
        print(f"Erro ao listar caixas: {e}")
        traceback.print_exc()
        # Em caso de erro, retornar uma lista vazia em vez de propagar o erro
        return []


def get_case_details(case_name: str) -> Dict[str, Any]:
    """
    Obtém detalhes sobre uma caixa específica, incluindo apenas seu preço de mercado.
    Não analisa mais o conteúdo interno das caixas (itens possíveis).
    
    Args:
        case_name: Nome ou ID da caixa
        
    Returns:
        Dicionário com detalhes básicos da caixa (nome, imagem, preço)
    
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
    
    # Obter apenas o preço atual da caixa no mercado
    case_price = get_item_price(case_info.get("name", ""))
    
    # Retornar informações básicas sem análise de conteúdo interno
    return {
        "name": case_info.get("name", ""),
        "image": case_info.get("image", ""),
        "price": case_price,
        "item_type": "premium_case",  # Adicionar tipo para identificação
        "source": "market",  # Indicar que é um item do mercado
        "requires_key": True  # A maioria das caixas requer chave
    }
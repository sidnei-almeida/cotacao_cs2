import json
import os
from typing import Dict, List, Any, Optional
from services.steam_market import get_item_price
from utils.database import get_case_price, get_all_cases
import logging

# Caminhos dos arquivos (mantidos para compatibilidade)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_FILE = os.path.join(BASE_DIR, 'data', 'cases.json')

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_cases_data() -> Dict[str, Any]:
    """
    Carrega os dados das caixas do arquivo JSON.
    Mantido para compatibilidade com código existente.
    """
    if os.path.exists(CASES_FILE) and os.path.getsize(CASES_FILE) > 0:
        with open(CASES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # Retornar estrutura vazia em vez de dados mockados
        logger.warning("Arquivo de caixas não encontrado ou vazio. Retornando estrutura vazia.")
        return {
            "cases": {}
        }


def save_cases_data(data: Dict[str, Any]) -> None:
    """
    Salva os dados das caixas no arquivo JSON.
    Mantido para compatibilidade com código existente.
    """
    os.makedirs(os.path.dirname(CASES_FILE), exist_ok=True)
    with open(CASES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def list_cases() -> List[str]:
    """
    Lista todas as caixas disponíveis no banco de dados.
    
    Returns:
        Lista com os nomes das caixas disponíveis
    """
    try:
        # Primeiro tentar buscar do banco de dados
        cases_from_db = get_all_cases(limit=200)
        
        if cases_from_db:
            # Se encontrou no banco, usar esses dados
            result = [case['case_name'] for case in cases_from_db if case.get('case_name')]
            logger.info(f"Total de caixas encontradas no banco: {len(result)}")
            return result
        
        # Se não encontrou no banco, tentar usar o arquivo JSON (compatibilidade)
        logger.warning("Nenhuma caixa encontrada no banco, tentando usar arquivo JSON")
        cases_data = load_cases_data()
        
        # Verificar se o formato do arquivo é válido
        if not isinstance(cases_data, dict) or "cases" not in cases_data:
            logger.error("Erro: Formato inválido no arquivo de caixas")
            return []
            
        # Retornar apenas os nomes das caixas para maior compatibilidade com o frontend
        result = []
        
        for case_id, case_info in cases_data.get("cases", {}).items():
            case_name = case_info.get("name", "")
            if case_name:  # Adiciona apenas se o nome não estiver vazio
                result.append(case_name)
                
        # Verificar se encontrou alguma caixa
        if not result:
            logger.warning("Aviso: Nenhuma caixa encontrada no arquivo JSON")
            
        logger.info(f"Total de caixas encontradas no arquivo: {len(result)}")
        
        return result
    except Exception as e:
        import traceback
        logger.error(f"Erro ao listar caixas: {e}")
        traceback.print_exc()
        # Em caso de erro, retornar uma lista vazia em vez de propagar o erro
        return []


def get_case_details(case_name: str) -> Dict[str, Any]:
    """
    Obtém detalhes sobre uma caixa específica, incluindo seu preço e itens contidos.
    
    Args:
        case_name: Nome da caixa
        
    Returns:
        Dicionário com detalhes da caixa (nome, imagem, preço, itens)
    
    Raises:
        Exception: Se a caixa não for encontrada
    """
    try:
        # Tentar obter do banco de dados primeiro
        case_info = get_case_price(case_name=case_name)
        
        if case_info:
            logger.info(f"Detalhes da caixa '{case_name}' encontrados no banco de dados")
            
            # Formatar o retorno para o formato esperado pela API
            result = {
                "name": case_info.get("case_name", ""),
                "market_hash_name": case_info.get("market_hash_name", ""),
                "image": case_info.get("image_url", ""),
                "price": case_info.get("price", 0.0),
                "items": case_info.get("items", []),
                "source": "database",
                "requires_key": True,  # A maioria das caixas requer chave
                "id": case_info.get("id")
            }
            
            return result
            
    except Exception as e:
        logger.error(f"Erro ao buscar caixa no banco: {e}")
    
    # Se chegou aqui, não encontrou no banco ou ocorreu erro
    # Tenta buscar da forma antiga para manter compatibilidade
    logger.warning(f"Caixa '{case_name}' não encontrada no banco, tentando formato antigo")
    
    try:
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
        try:
            case_price = get_item_price(case_info.get("name", ""))
        except Exception as e:
            logger.error(f"Erro ao obter preço da caixa: {e}")
            case_price = 0.0
        
        # Retornar informações básicas sem análise de conteúdo interno
        return {
            "name": case_info.get("name", ""),
            "image": case_info.get("image", ""),
            "price": case_price,
            "item_type": "premium_case",  # Adicionar tipo para identificação
            "source": "legacy_file",  # Indicar que é um item do arquivo JSON
            "requires_key": True  # A maioria das caixas requer chave
        }
    except Exception as e:
        logger.error(f"Erro ao buscar caixa: {e}")
        raise Exception(f"Caixa '{case_name}' não encontrada: {str(e)}")
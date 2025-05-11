import requests
from selectolax.parser import HTMLParser
from typing import Dict, List, Any, Optional
import time
import re

# URL base para buscar informações de caixas e itens
CSGOSTASH_URL = "https://csgostash.com"


def get_case_info(case_name: str) -> Optional[Dict[str, Any]]:
    """
    Obtém informações detalhadas de uma caixa específica do CS2.
    
    Args:
        case_name: Nome ou identificador da caixa
        
    Returns:
        Dicionário com informações sobre a caixa e seus itens, ou None se não encontrado
    """
    # Normalizamos o nome da caixa para a URL (substituímos espaços por hífens, etc.)
    normalized_name = case_name.lower().replace(' ', '-').replace('_', '-')
    url = f"{CSGOSTASH_URL}/crates/{normalized_name}"
    
    try:
        # Em um cenário real, faríamos o scraping aqui
        # Mas como não estamos fazendo requisições reais, vamos retornar dados mockados
        
        # Mockando as raridades e probabilidades
        rarities = {
            "Covert": 0.0025,  # 0.25%
            "Classified": 0.0125,  # 1.25%
            "Restricted": 0.03,  # 3%
            "Mil-Spec": 0.15,  # 15%
            "Consumer": 0.80,  # 80%
            "Knife": 0.0025  # 0.25%
        }
        
        # Aqui simularemos o que seria o resultado do scraping
        # Em um cenário real, precisaríamos fazer o parsing do HTML da página
        return {
            "rarities": rarities,
            "requires_key": True,
            "key_price": 6.50
        }
        
    except Exception as e:
        print(f"Erro ao obter informações da caixa {case_name}: {e}")
        return None


def get_all_cases() -> List[Dict[str, Any]]:
    """
    Obtém informações básicas de todas as caixas disponíveis no CS2.
    
    Returns:
        Lista de dicionários com informações básicas de cada caixa
    """
    url = f"{CSGOSTASH_URL}/crates"
    
    try:
        # Em um cenário real, faríamos o scraping aqui
        # Mas como não estamos fazendo requisições reais, vamos retornar dados mockados
        
        # Mockando uma lista de caixas
        return [
            {
                "id": "operation_broken_fang_case",
                "name": "Operation Broken Fang Case",
                "image": "https://steamcommunity-a.akamaihd.net/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZLQHTxDZ7I56KU0Zwwo4NUX4oFJZEHLbXU5A1PIYQNqhpOSV-fRPasw8rsUFJ5KBFZv668FFUuh6qZJmlD7tiyl4OIlaGhYuLTzjhVupJ12urH89ii3lHlqEdoMDr2I5jVLFFridDMWO_f"
            },
            {
                "id": "prisma_case",
                "name": "Prisma Case",
                "image": "https://steamcommunity-a.akamaihd.net/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZLQHTxDZ7I56KU0Zwwo4NUX4oFJZEHLbXU5A1PIYQNqhpOSV-fRPasw8rsUFJ5KBFZv668FFQwnfCcJmxDv9rhwILdx6L1ZuuAzzoF7sEmiLyQot-sigXk-EY9Mjr3JJjVLFHILUU"
            },
            {
                "id": "clutch_case",
                "name": "Clutch Case",
                "image": "https://steamcommunity-a.akamaihd.net/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZLQHTxDZ7I56KU0Zwwo4NUX4oFJZEHLbXU5A1PIYQNqhpOSV-fRPasw8rsUFJ5KBFZv668FFUwnaLJJWtE4N65kIWZg8j3KqnUhFRd4cJ5nqeTpt2siVHlqEFuMGz2I4LAJwdqNwnVqwK6ye67hce4vJnPynUysylwsS3UyhfkiBtOcKUx0v3EV41s"
            },
            {
                "id": "snakebite_case",
                "name": "Snakebite Case",
                "image": "https://steamcommunity-a.akamaihd.net/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZLQHTxDZ7I56KU0Zwwo4NUX4oFJZEHLbXU5A1PIYQNqhpOSV-fRPasw8rsUFJ5KBFZv668FFUznaCaJWVDvozlzdONwvKjYL6Bzm4A65V12u2TpNn321Hk-UdpZGv7JYHEJAVsZw2F_FC8kL3tm9bi60IYvmR3"
            }
        ]
        
    except Exception as e:
        print(f"Erro ao obter lista de caixas: {e}")
        return []


def parse_case_page(html_content: str) -> Dict[str, Any]:
    """
    Processa o HTML de uma página de caixa para extrair informações dos itens.
    
    Args:
        html_content: Conteúdo HTML da página
        
    Returns:
        Dicionário com informações sobre os itens da caixa
    """
    # Nota: Esta função seria usada em um cenário real para fazer o parsing do HTML
    # Como estamos trabalhando com dados mockados, esta função é apenas um esboço
    
    parser = HTMLParser(html_content)
    
    items = []
    
    # Exemplo de como seria a implementação real:
    # Selecionar os elementos HTML que contêm informações dos itens
    # item_elements = parser.css('div.item-container')
    # 
    # for item_el in item_elements:
    #     name_el = item_el.css_first('div.item-name')
    #     rarity_el = item_el.css_first('div.item-rarity')
    #     
    #     if name_el and rarity_el:
    #         items.append({
    #             "name": name_el.text().strip(),
    #             "rarity": rarity_el.text().strip(),
    #             "probability": get_probability_by_rarity(rarity_el.text().strip())
    #         })
    
    return {
        "items": items
    }


def get_probability_by_rarity(rarity: str) -> float:
    """
    Retorna a probabilidade estimada com base na raridade do item.
    
    Args:
        rarity: Nome da raridade do item
        
    Returns:
        Probabilidade estimada
    """
    rarities = {
        "Covert": 0.0025,  # 0.25%
        "Classified": 0.0125,  # 1.25%
        "Restricted": 0.03,  # 3%
        "Mil-Spec": 0.15,  # 15%
        "Consumer": 0.80,  # 80%
        "Knife": 0.0025  # 0.25%
    }
    
    return rarities.get(rarity, 0.0)

"""
Módulo específico para scraping de caixas do CS2 do site stash.clash.gg
"""
import requests
import json
import time
import re
from datetime import datetime
from typing import List, Dict, Optional, Any
from selectolax.parser import HTMLParser

# URL base do stash.clash.gg
CLASH_URL = "https://stash.clash.gg"

# Delay entre requisições para evitar bloqueios
CLASH_REQUEST_DELAY = 2  # segundos

def sleep_between_requests(min_delay=CLASH_REQUEST_DELAY):
    """Aguarda um tempo mínimo entre requisições para evitar bloqueios."""
    time.sleep(min_delay)


def get_all_cases_from_clash() -> List[Dict[str, Any]]:
    """
    Obtém a lista de todas as caixas disponíveis no stash.clash.gg
    
    Returns:
        Lista de dicionários com informações básicas de cada caixa
    """
    url = f"{CLASH_URL}/containers/skin-cases"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Cache-Control': 'no-cache',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        print(f"Obtendo lista de caixas de {url}")
        sleep_between_requests()
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"Erro ao acessar {url}: Status {response.status_code}")
            return []
        
        # Parsear o HTML
        parser = HTMLParser(response.text)
        
        # Encontrar todos os elementos de caixa
        # Nota: Adaptar os seletores CSS conforme a estrutura real do site
        case_elements = parser.css('div.grid-item')
        
        cases = []
        for case_el in case_elements:
            # Pegar link, nome e imagem
            link_el = case_el.css_first('a')
            img_el = case_el.css_first('img')
            name_el = case_el.css_first('h2.name')
            
            if link_el and img_el and name_el:
                case_link = link_el.attributes.get('href', '')
                case_url = f"{CLASH_URL}{case_link}" if case_link else None
                
                # Extrair nome da caixa
                case_name = name_el.text().strip()
                
                # Obter URL da imagem
                image_url = img_el.attributes.get('src', '')
                if image_url and not image_url.startswith('http'):
                    image_url = f"{CLASH_URL}{image_url}"
                
                if case_url and case_name:
                    cases.append({
                        'name': case_name,
                        'url': case_url,
                        'image_url': image_url
                    })
        
        print(f"Encontradas {len(cases)} caixas")
        return cases
        
    except Exception as e:
        print(f"Erro ao obter lista de caixas: {e}")
        return []


def get_case_details_from_clash(case_url: str) -> Optional[Dict[str, Any]]:
    """
    Obtém detalhes completos de uma caixa específica no stash.clash.gg
    
    Args:
        case_url: URL da página da caixa
        
    Returns:
        Dicionário com detalhes da caixa (nome, preço, imagem, itens)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Cache-Control': 'no-cache',
        'Referer': CLASH_URL
    }
    
    try:
        print(f"Obtendo detalhes da caixa: {case_url}")
        sleep_between_requests()
        
        response = requests.get(case_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"Erro ao acessar {case_url}: Status {response.status_code}")
            return None
        
        # Parsear o HTML
        parser = HTMLParser(response.text)
        
        # Extrair informações básicas da caixa
        case_name_el = parser.css_first('h1.item-name')
        case_name = case_name_el.text().strip() if case_name_el else "Caixa desconhecida"
        
        # Extrair nome formado para mercado
        # No formato que Steam usa (para usar com get_item_price)
        market_hash_name = case_name
        
        # Extrair preço (se disponível na página)
        price_el = parser.css_first('div.price')
        price_text = price_el.text().strip() if price_el else None
        price = 0.0
        
        if price_text:
            # Tentar extrair o valor numérico
            price_match = re.search(r'(\$|R\$|€|£|¥)\s*([0-9.,]+)', price_text)
            if price_match:
                symbol, price_val = price_match.groups()
                
                # Converter para float (considerando formato brasileiro)
                if symbol == 'R$':
                    price = float(price_val.replace('.', '').replace(',', '.'))
                else:
                    price = float(price_val.replace(',', ''))
        
        # Extrair URL da imagem
        img_el = parser.css_first('img.item-image')
        image_url = img_el.attributes.get('src', '') if img_el else None
        
        if image_url and not image_url.startswith('http'):
            image_url = f"{CLASH_URL}{image_url}"
        
        # Extrair os itens da caixa
        items = []
        
        # Adaptar os seletores conforme a estrutura real do site
        item_elements = parser.css('div.item-card')
        
        for item_el in item_elements:
            name_el = item_el.css_first('div.item-name')
            rarity_el = item_el.css_first('div.rarity-tag')
            
            if name_el and rarity_el:
                item_name = name_el.text().strip()
                item_rarity = rarity_el.text().strip()
                
                # Probabilidade aproximada
                probability = get_probability_by_rarity(item_rarity)
                
                items.append({
                    "name": item_name,
                    "rarity": item_rarity,
                    "probability": probability
                })
        
        # Criar o dicionário de retorno
        case_details = {
            "name": case_name,
            "market_hash_name": market_hash_name,
            "image": image_url,
            "price": price,
            "items": items,
            "source": "stash.clash.gg"
        }
        
        return case_details
        
    except Exception as e:
        print(f"Erro ao obter detalhes da caixa: {e}")
        return None


def get_probability_by_rarity(rarity: str) -> float:
    """Retorna a probabilidade aproximada com base na raridade do item."""
    # Reuso da função existente
    estimated_probabilities = {
        "Covert": 0.0025,  # Aproximadamente 0.25%
        "Classified": 0.0125,  # Aproximadamente 1.25%
        "Restricted": 0.03,  # Aproximadamente 3%
        "Mil-Spec Grade": 0.15,  # Aproximadamente 15%
        "Industrial Grade": 0.30,  # Aproximadamente 30%
        "Consumer Grade": 0.45,  # Aproximadamente 45%
        "Knife": 0.0025,  # Aproximadamente 0.25%
        "Extraordinary": 0.0025  # Aproximadamente 0.25%
    }
    
    # Normalizar nome da raridade
    normalized_rarity = rarity.strip()
    
    # Correspondências aproximadas
    if "Covert" in normalized_rarity or "Red" in normalized_rarity:
        return estimated_probabilities["Covert"]
    elif "Classified" in normalized_rarity or "Pink" in normalized_rarity:
        return estimated_probabilities["Classified"]
    elif "Restricted" in normalized_rarity or "Purple" in normalized_rarity:
        return estimated_probabilities["Restricted"]
    elif "Mil-Spec" in normalized_rarity or "Blue" in normalized_rarity:
        return estimated_probabilities["Mil-Spec Grade"]
    elif "Industrial" in normalized_rarity or "Light Blue" in normalized_rarity:
        return estimated_probabilities["Industrial Grade"]
    elif "Consumer" in normalized_rarity or "White" in normalized_rarity:
        return estimated_probabilities["Consumer Grade"]
    elif "Knife" in normalized_rarity or "Yellow" in normalized_rarity or "Gold" in normalized_rarity:
        return estimated_probabilities["Knife"]
    
    return estimated_probabilities.get(normalized_rarity, 0.01)


def update_cases_database():
    """
    Atualiza o banco de dados com as informações de todas as caixas.
    Este é o ponto de entrada principal que deve ser chamado pelo agendador.
    
    Returns:
        Dicionário com estatísticas da atualização
    """
    from utils.database import save_case_price
    
    print("Iniciando atualização do banco de dados de caixas...")
    
    # Estatísticas da atualização
    stats = {
        'start_time': datetime.now().isoformat(),
        'total_cases': 0,
        'updated_cases': 0,
        'failed_cases': 0,
        'end_time': None
    }
    
    try:
        # Obter lista de todas as caixas
        cases = get_all_cases_from_clash()
        stats['total_cases'] = len(cases)
        
        for i, case in enumerate(cases):
            try:
                print(f"[{i+1}/{len(cases)}] Processando {case['name']}...")
                
                # Obter detalhes da caixa
                case_details = get_case_details_from_clash(case['url'])
                
                if case_details:
                    # Converter a lista de itens para JSON
                    items_json = json.dumps(case_details['items'], ensure_ascii=False)
                    
                    # Salvar no banco de dados
                    save_case_price(
                        case_name=case_details['name'],
                        market_hash_name=case_details['market_hash_name'],
                        price=case_details['price'],
                        image_url=case_details['image'],
                        items_json=items_json
                    )
                    
                    stats['updated_cases'] += 1
                    print(f"  ✓ Caixa {case['name']} atualizada com sucesso")
                else:
                    stats['failed_cases'] += 1
                    print(f"  ✗ Falha ao obter detalhes da caixa {case['name']}")
                
                # Breve pausa entre requisições
                sleep_between_requests()
                
            except Exception as e:
                stats['failed_cases'] += 1
                print(f"  ✗ Erro ao processar caixa {case['name']}: {e}")
        
        stats['end_time'] = datetime.now().isoformat()
        print(f"Atualização concluída: {stats['updated_cases']} caixas atualizadas, {stats['failed_cases']} falhas")
        return stats
        
    except Exception as e:
        print(f"Erro durante a atualização do banco de caixas: {e}")
        stats['end_time'] = datetime.now().isoformat()
        return stats 
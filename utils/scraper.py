import requests
from selectolax.parser import HTMLParser
from typing import Dict, List, Any, Optional, Tuple
import time
import re
import numpy as np
from datetime import datetime, timedelta

# URL base para buscar informações de caixas e itens
CSGOSTASH_URL = "https://csgostash.com"


# Nova classe para armazenar e processar dados históricos de preços
class PriceHistoryManager:
    """
    Classe para gerenciar dados históricos de preços e aplicar filtragem estatística
    para obter valores mais precisos.
    """
    def __init__(self):
        # Estrutura: {market_hash_name: [(price, timestamp), ...]}
        self.price_history = {}
        # Máximo de dias para considerar dados históricos
        self.max_age_days = 30
        # Máximo de entradas para cada item
        self.max_entries_per_item = 100
    
    def add_price(self, market_hash_name: str, price: float, timestamp: Optional[datetime] = None):
        """
        Adiciona um novo preço ao histórico
        
        Args:
            market_hash_name: Nome do item no formato do mercado
            price: Preço coletado
            timestamp: Data/hora da coleta (usa hora atual se None)
        """
        if price <= 0:
            return
            
        if timestamp is None:
            timestamp = datetime.now()
            
        if market_hash_name not in self.price_history:
            self.price_history[market_hash_name] = []
        
        # Adicionar novo preço
        self.price_history[market_hash_name].append((price, timestamp))
        
        # Manter apenas as entradas mais recentes
        if len(self.price_history[market_hash_name]) > self.max_entries_per_item:
            self.price_history[market_hash_name] = sorted(
                self.price_history[market_hash_name],
                key=lambda x: x[1],  # Ordenar por timestamp
                reverse=True
            )[:self.max_entries_per_item]
    
    def clean_old_data(self):
        """Remove entradas mais antigas que max_age_days"""
        cutoff_date = datetime.now() - timedelta(days=self.max_age_days)
        
        for market_hash_name in self.price_history:
            self.price_history[market_hash_name] = [
                (price, timestamp) for price, timestamp in self.price_history[market_hash_name]
                if timestamp >= cutoff_date
            ]
    
    def get_clean_price(self, market_hash_name: str) -> Optional[float]:
        """
        Retorna um preço limpo e filtrado para o item, aplicando:
        1. Filtragem IQR para remover outliers
        2. Pesos temporais (preços mais recentes têm mais peso)
        3. Tendência (se detectada)
        
        Args:
            market_hash_name: Nome do item no formato do mercado
            
        Returns:
            Preço filtrado ou None se não houver dados suficientes
        """
        if market_hash_name not in self.price_history or not self.price_history[market_hash_name]:
            return None
            
        # Se só temos uma entrada, retornar ela diretamente
        if len(self.price_history[market_hash_name]) == 1:
            return self.price_history[market_hash_name][0][0]
        
        # Se temos poucas entradas (2-4), usar a mediana simples
        if len(self.price_history[market_hash_name]) < 5:
            prices = [p[0] for p in self.price_history[market_hash_name]]
            return np.median(prices)
        
        # Para 5+ entradas, aplicar o algorítmo completo
        return self._apply_weighted_iqr_filter(market_hash_name)
    
    def _apply_weighted_iqr_filter(self, market_hash_name: str) -> float:
        """
        Aplica filtragem IQR com pesos temporais
        
        Args:
            market_hash_name: Nome do item no formato do mercado
            
        Returns:
            Preço filtrado
        """
        # Obter dados históricos
        price_data = self.price_history[market_hash_name]
        
        # Ordenar por timestamp (mais recente primeiro)
        sorted_data = sorted(price_data, key=lambda x: x[1], reverse=True)
        
        # Calcular pesos temporais
        now = datetime.now()
        max_age = timedelta(days=self.max_age_days)
        
        weighted_prices = []
        
        for price, timestamp in sorted_data:
            age = now - timestamp
            
            # Calcular peso - preços mais recentes têm maior peso
            # Preços de hoje = peso 1.0, preços de max_age atrás = peso 0.2
            weight = max(0.2, 1.0 - (age / max_age) * 0.8) if age < max_age else 0.2
            
            # Adicionar o preço múltiplas vezes com base no peso
            # Por exemplo, um peso de 1.0 adiciona o preço 5 vezes, peso 0.2 adiciona 1 vez
            repeats = int(weight * 5)
            weighted_prices.extend([price] * repeats)
        
        # Aplicar IQR nos preços ponderados
        try:
            q1 = np.percentile(weighted_prices, 25)
            q3 = np.percentile(weighted_prices, 75)
            iqr = q3 - q1
            
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            # Filtrar outliers dos preços originais
            filtered_data = [(price, ts) for price, ts in sorted_data 
                           if lower_bound <= price <= upper_bound]
            
            if not filtered_data:
                # Se filtragem foi muito agressiva, usa original mas prioriza recentes
                filtered_data = sorted_data[:5]  # Top 5 mais recentes
        except Exception as e:
            print(f"Erro ao aplicar IQR para {market_hash_name}: {e}")
            filtered_data = sorted_data
        
        # Verificar tendência
        trend = self._detect_trend(filtered_data)
        
        # Calcular preço final
        prices_only = [p[0] for p in filtered_data]
        
        if trend == "up":
            # Para tendência de alta, preferir valores mais altos (usar p75 em vez de mediana)
            return np.percentile(prices_only, 75)
        elif trend == "down":
            # Para tendência de queda, ser mais conservador (usar p25)
            return np.percentile(prices_only, 25)
        else:
            # Sem tendência clara, usar mediana
            return np.median(prices_only)
    
    def _detect_trend(self, price_data: List[Tuple[float, datetime]]) -> Optional[str]:
        """
        Detecta se há uma tendência clara nos preços recentes
        
        Args:
            price_data: Lista de tuplas (preço, timestamp) já ordenadas por timestamp
            
        Returns:
            "up", "down" ou None se não houver tendência clara
        """
        if len(price_data) < 5:
            return None
        
        # Obter os 5 preços mais recentes
        recent_prices = [p[0] for p in price_data[:5]]
        
        # Verificar se há padrão consistente
        is_increasing = all(y > x for x, y in zip(recent_prices[:-1], recent_prices[1:]))
        is_decreasing = all(y < x for x, y in zip(recent_prices[:-1], recent_prices[1:]))
        
        if is_increasing:
            return "up"
        elif is_decreasing:
            return "down"
        
        # Se não há padrão claro, tentar calcular a inclinação geral
        try:
            # Converter timestamps para números (dias desde o primeiro)
            first_ts = price_data[-1][1]  # Timestamp mais antigo
            x_values = [(entry[1] - first_ts).total_seconds() / 86400 for entry in price_data]
            y_values = [entry[0] for entry in price_data]
            
            # Calcular correlação
            correlation = np.corrcoef(x_values, y_values)[0, 1]
            
            # Determinar tendência com base na correlação
            if correlation > 0.6:  # Correlação positiva forte
                return "up"
            elif correlation < -0.6:  # Correlação negativa forte
                return "down"
        except Exception:
            pass
            
        return None


# Instância global do gerenciador de preços
price_history_manager = PriceHistoryManager()


def get_case_info(case_name: str) -> Optional[Dict[str, Any]]:
    """
    Obtém informações detalhadas de uma caixa específica do CS2.
    Esta função agora retorna um dicionário vazio e deve ser implementada com scraping real.
    
    Args:
        case_name: Nome ou identificador da caixa
        
    Returns:
        Dicionário com informações sobre a caixa e seus itens, ou None se não encontrado
    """
    # Normalizamos o nome da caixa para a URL (substituímos espaços por hífens, etc.)
    normalized_name = case_name.lower().replace(' ', '-').replace('_', '-')
    url = f"{CSGOSTASH_URL}/crates/{normalized_name}"
    
    try:
        # Implementação futura: fazer o scraping real da página
        # Retornar estrutura vazia para forçar o uso de dados reais em vez de mockados
        print(f"get_case_info: Retornando informações vazias para '{case_name}'. Esta função deve ser implementada com scraping real.")
        
        # Retornar um dicionário mínimo vazio que deve ser preenchido com dados reais
        return {
            "rarities": {},
            "requires_key": True,
            "key_price": 0.0
        }
        
    except Exception as e:
        print(f"Erro ao obter informações da caixa {case_name}: {e}")
        return None


def get_all_cases() -> List[Dict[str, Any]]:
    """
    Obtém informações básicas de todas as caixas disponíveis no CS2.
    Esta função agora retorna uma lista vazia e deve ser implementada com scraping real.
    
    Returns:
        Lista de dicionários com informações básicas de cada caixa
    """
    url = f"{CSGOSTASH_URL}/crates"
    
    try:
        # Implementação futura: fazer o scraping real da página
        # Retornar lista vazia para forçar o uso de dados reais do banco de dados
        # ou outras fontes em vez de dados mockados
        print("get_all_cases: Retornando lista vazia. Esta função deve ser implementada com scraping real.")
        return []
        
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
    Retorna a probabilidade aproximada com base na raridade do item.
    Estes valores são estimativas e devem ser substituídos por dados oficiais
    ou estatísticas reais de abertura de caixas quando disponíveis.
    
    Args:
        rarity: Nome da raridade do item
        
    Returns:
        Probabilidade estimada aproximada
    """
    # Valores aproximados baseados em estimativas da comunidade
    # Estes NÃO são valores oficiais e devem ser usados apenas como referência
    # Devem ser substituídos por dados reais quando disponíveis
    estimated_probabilities = {
        "Covert": 0.0025,  # Aproximadamente 0.25%
        "Classified": 0.0125,  # Aproximadamente 1.25%
        "Restricted": 0.03,  # Aproximadamente 3%
        "Mil-Spec": 0.15,  # Aproximadamente 15%
        "Consumer": 0.80,  # Aproximadamente 80%
        "Knife": 0.0025  # Aproximadamente 0.25%
    }
    
    # Aviso sobre o uso de valores aproximados
    print(f"AVISO: Usando probabilidade estimada aproximada para raridade '{rarity}'. Substitua por dados reais quando disponíveis.")
    
    return estimated_probabilities.get(rarity, 0.0)


# Função para processar preço obtido pelo scraper e atualizá-lo no histórico
def process_scraped_price(market_hash_name: str, price: float) -> float:
    """
    Processa um preço obtido por scraping, apenas filtrando por erros óbvios,
    mas sem impor limites por categoria.
    
    Args:
        market_hash_name: Nome do item no formato do mercado
        price: Preço coletado
        
    Returns:
        Preço processado
    """
    # Verificar se o preço é válido (apenas se é maior que zero)
    if price is None or price <= 0:
        return 0.0
    
    # Adicionar o preço ao histórico (para referência futura)
    price_history_manager.add_price(market_hash_name, price)
    
    # Não aplicar limites por categoria nem filtragem de preços
    # Retornar diretamente o preço obtido
    return price


def classify_item_for_price_range(market_hash_name: str) -> tuple:
    """
    Classifica um item e retorna uma faixa de preço razoável baseada na categoria.
    Usa categorias amplas em vez de itens específicos para mais consistência.
    
    Args:
        market_hash_name: Nome do item no formato do mercado
        
    Returns:
        Tupla (categoria, (min_price, max_price))
    """
    market_hash_name_lower = market_hash_name.lower()
    
    # Mapeamento de categorias de itens para faixas de preço (min, max) em USD
    # NOTA: Valores convertidos de BRL para USD (divididos por ~5)
    categories = [
        # Categoria: Facas
        {
            "category": "knife",
            "keywords": ["★ ", "knife", "karambit", "bayonet", "butterfly", "daggers", "shadow daggers", "falchion", "huntsman", "bowie", "ursus", "stiletto", "navaja", "talon", "classic knife", "skeleton knife", "paracord knife", "survival knife", "nomad knife"],
            "price_range": (60.0, 3000.0)
        },
        # Categoria: Luvas
        {
            "category": "gloves",
            "keywords": ["★ gloves", "★ hand", "sport gloves", "driver gloves", "specialist gloves", "moto gloves", "bloodhound gloves", "hydra gloves", "broken fang gloves"],
            "price_range": (60.0, 1000.0)
        },
        # Categoria: AWP
        {
            "category": "awp",
            "keywords": ["awp"],
            "price_range": (1.0, 3000.0)  # Faixa ampla para cobrir de skins comuns até Dragon Lore/Gungnir
        },
        # Categoria: Rifles populares
        {
            "category": "rifles",
            "keywords": ["ak-47", "m4a4", "m4a1-s", "sg 553", "aug", "famas", "galil", "ssg 08"],
            "price_range": (0.5, 1600.0)  # Faixa ampla para cobrir de skins comuns até Howl/Fire Serpent
        },
        # Categoria: Pistolas
        {
            "category": "pistols",
            "keywords": ["deagle", "desert eagle", "usp-s", "glock", "p250", "five-seven", "tec-9", "p2000", "cz75", "r8 revolver", "dual berettas"],
            "price_range": (0.2, 100.0)
        },
        # Categoria: Submetralhadoras
        {
            "category": "smgs",
            "keywords": ["mp5", "mp7", "mp9", "mac-10", "ump-45", "pp-bizon", "p90"],
            "price_range": (0.2, 40.0)
        },
        # Categoria: Escopetas
        {
            "category": "shotguns",
            "keywords": ["nova", "xm1014", "mag-7", "sawed-off"],
            "price_range": (0.2, 40.0)
        },
        # Categoria: Metralhadoras
        {
            "category": "machine_guns",
            "keywords": ["m249", "negev"],
            "price_range": (0.2, 30.0)
        },
        # Categoria: Caixas
        {
            "category": "cases",
            "keywords": ["case", "caixa"],
            "price_range": (0.1, 10.0)
        },
        # Categoria: Adesivos
        {
            "category": "stickers",
            "keywords": ["sticker", "adesivo"],
            "price_range": (0.1, 200.0)  # Alguns adesivos raros podem ser valiosos
        },
        # Categoria: Agentes
        {
            "category": "agents",
            "keywords": ["agent", "agente", "operator", "soldier", "saidan", "chef", "enforcer", "muhlik"],
            "price_range": (1.0, 20.0)
        },
        # Categoria: Patches e Pins
        {
            "category": "patches_pins",
            "keywords": ["patch", "pin"],
            "price_range": (0.2, 10.0)
        },
        # Categoria: Grafite
        {
            "category": "graffiti",
            "keywords": ["graffiti", "spray"],
            "price_range": (0.1, 2.0)
        },
        # Categoria: Música
        {
            "category": "music",
            "keywords": ["music kit", "kit de música"],
            "price_range": (0.2, 6.0)
        }
    ]
    
    # Verificar raridade com base na descrição do item
    rarities = {
        "factory new": 1.5,
        "minimal wear": 1.2,
        "field-tested": 1.0,
        "well-worn": 0.8,
        "battle-scarred": 0.6,
        "souvenir": 1.5,
        "stattrak": 1.5
    }
    
    # Multiplicador de raridade padrão
    rarity_multiplier = 1.0
    
    # Verificar se o item tem alguma indicação de raridade especial
    for rarity, multiplier in rarities.items():
        if rarity in market_hash_name_lower:
            rarity_multiplier = multiplier
            break
    
    # Verificar a categoria do item
    for category in categories:
        for keyword in category["keywords"]:
            if keyword in market_hash_name_lower:
                min_price, max_price = category["price_range"]
                # Ajustar preços com base na raridade
                min_price *= rarity_multiplier
                max_price *= rarity_multiplier
                return category["category"], (min_price, max_price)
    
    # Padrão para itens desconhecidos: faixa conservadora
    return "unknown", (1.0, 100.0)

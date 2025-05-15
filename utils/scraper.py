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


# Função para processar preço obtido pelo scraper e atualizá-lo no histórico
def process_scraped_price(market_hash_name: str, price: float) -> float:
    """
    Processa um preço obtido por scraping, aplicando filtros estatísticos para evitar valores discrepantes
    
    Args:
        market_hash_name: Nome do item no formato do mercado
        price: Preço coletado
        
    Returns:
        Preço processado e filtrado para evitar outliers
    """
    # Verificar se o preço é válido
    if price is None or price <= 0:
        return 0.0
    
    # DETECÇÃO DE OUTLIER: Verificar se o preço está muito fora da faixa esperada
    # Este é um filtro preliminar para preços absurdamente fora da realidade
    
    # Classificar o item em categorias para determinar os limites de preço razoável
    item_category, price_range = classify_item_for_price_range(market_hash_name)
    min_reasonable_price, max_reasonable_price = price_range
    
    # Se o preço estiver muito fora da faixa razoável (mais de 10x o limite superior),
    # consideramos como um outlier extremo e aplicamos tratamento estatístico
    if price > max_reasonable_price * 10:
        print(f"OUTLIER EXTREMO: Preço absurdo para {market_hash_name}: {price:.2f} está muito acima do limite máximo esperado ({max_reasonable_price:.2f})")
        
        # Se tivermos histórico para este item, usar o histórico em vez do valor atual
        existing_price = price_history_manager.get_clean_price(market_hash_name)
        if existing_price is not None:
            print(f"Usando preço histórico existente: {existing_price:.2f}")
            
            # Ainda registramos o valor original no histórico para referência
            price_history_manager.add_price(market_hash_name, price)
            return existing_price
    
    # Para valores dentro da faixa esperada ou sem histórico, seguir com o processamento normal
    # Adicionar o preço ao histórico
    price_history_manager.add_price(market_hash_name, price)
    
    # Obter o preço limpo baseado no histórico (filtragem estatística)
    clean_price = price_history_manager.get_clean_price(market_hash_name)
    
    # Se não temos dados históricos suficientes, usar o preço atual
    if clean_price is None:
        return price
    
    # Limitar a diferença máxima entre o preço atual e o preço histórico
    # para evitar mudanças drásticas mesmo após filtragem
    if clean_price > price * 2:  # Se o preço filtrado for mais que 2x o preço atual
        print(f"Limitando aumento desproporcional para {market_hash_name}: {price:.2f} -> {clean_price:.2f}")
        return price * 2  # Limitar a 200% do preço atual
    
    if clean_price < price / 2:  # Se o preço filtrado for menos que 50% do preço atual
        print(f"Limitando queda desproporcional para {market_hash_name}: {price:.2f} -> {clean_price:.2f}")
        return price / 2  # Limitar a 50% do preço atual
    
    # Mostrar informação de debug se o preço mudou significativamente
    if abs(clean_price - price) / price > 0.2:  # Diferença > 20%
        print(f"Correção de preço para {market_hash_name}: {price:.2f} -> {clean_price:.2f}")
    
    return clean_price


def classify_item_for_price_range(market_hash_name: str) -> tuple:
    """
    Classifica um item e retorna uma faixa de preço razoável.
    
    Args:
        market_hash_name: Nome do item no formato do mercado
        
    Returns:
        Tupla (categoria, (min_price, max_price))
    """
    market_hash_name_lower = market_hash_name.lower()
    
    # Mapeamento de categorias de itens para faixas de preço (min, max) em reais
    categories = [
        # Categoria: Facas - Itens mais caros
        {
            "category": "knife",
            "keywords": ["★ ", "knife", "karambit", "bayonet", "butterfly"],
            "price_range": (300.0, 5000.0)
        },
        # Categoria: Luvas
        {
            "category": "gloves",
            "keywords": ["★ gloves", "★ hand", "sport gloves", "driver gloves"],
            "price_range": (300.0, 4000.0)
        },
        # Categoria: AWP (Sniper rifle popular)
        {
            "category": "awp",
            "keywords": ["awp"],
            "price_range": (10.0, 500.0)
        },
        # Categoria: Rifles populares
        {
            "category": "popular_rifles",
            "keywords": ["ak-47", "m4a4", "m4a1-s"],
            "price_range": (5.0, 350.0)
        },
        # Categoria: Outras armas
        {
            "category": "other_weapons",
            "keywords": ["deagle", "desert eagle", "usp-s", "glock", "p250"],
            "price_range": (2.0, 150.0)
        },
        # Categoria: Cases (Caixas)
        {
            "category": "cases",
            "keywords": ["case", "caixa"],
            "price_range": (0.5, 30.0)
        },
        # Categoria: Stickers (Adesivos)
        {
            "category": "stickers",
            "keywords": ["sticker", "adesivo"],
            "price_range": (0.5, 50.0)
        },
        # Categoria: Agents (Agentes) - Foco principal nos problemas
        {
            "category": "agents",
            "keywords": ["agent", "agente", "soldier", "operator", "muhlik", 
                         "cmdr", "doctor", "lieutenant", "saidan", "chef", 
                         "cypher", "enforcer", "crasswater", "farlow", "voltzmann"],
            "price_range": (10.0, 40.0)  # Faixa estreita para evitar valores absurdos
        }
    ]
    
    # Verificar cada categoria
    for category in categories:
        for keyword in category["keywords"]:
            if keyword in market_hash_name_lower:
                return category["category"], category["price_range"]
    
    # Padrão para itens desconhecidos
    return "unknown", (1.0, 50.0)

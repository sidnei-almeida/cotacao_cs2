import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
import urllib.parse

# URL de conexão com o PostgreSQL
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:apuculacata@db.ykaatdxdvkcuryswejkm.supabase.co:5432/postgres')

def get_db_connection():
    """Cria uma conexão com o banco de dados PostgreSQL."""
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    """Inicializa o banco de dados com as tabelas necessárias."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabela para armazenar preços de skins
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS skin_prices (
        id SERIAL PRIMARY KEY,
        market_hash_name TEXT NOT NULL,
        price REAL NOT NULL,
        currency INTEGER NOT NULL,
        app_id INTEGER NOT NULL,
        last_updated TIMESTAMP NOT NULL,
        last_scraped TIMESTAMP NOT NULL,
        update_count INTEGER DEFAULT 1,
        UNIQUE(market_hash_name, currency, app_id)
    )
    ''')
    
    # Tabela para armazenar metadata e configurações
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TIMESTAMP NOT NULL
    )
    ''')
    
    # Índice para buscas rápidas por market_hash_name
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_skin_prices_market_hash_name
    ON skin_prices(market_hash_name)
    ''')
    
    conn.commit()
    conn.close()
    
    print(f"Banco de dados PostgreSQL inicializado")

def get_skin_price(market_hash_name: str, currency: int, app_id: int) -> Optional[float]:
    """
    Busca o preço de uma skin no banco de dados.
    
    Args:
        market_hash_name: Nome formatado do item para o mercado
        currency: Código da moeda
        app_id: ID da aplicação na Steam
        
    Returns:
        Preço da skin ou None se não encontrada ou desatualizada
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute('''
    SELECT price, last_updated FROM skin_prices
    WHERE market_hash_name = %s AND currency = %s AND app_id = %s
    ''', (market_hash_name, currency, app_id))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        price, last_updated = result['price'], result['last_updated']
        # Verificar se o preço está atualizado (< 7 dias)
        if datetime.now() - last_updated < timedelta(days=7):
            return price
    
    return None

def save_skin_price(market_hash_name: str, price: float, currency: int, app_id: int):
    """
    Salva ou atualiza o preço de uma skin no banco de dados.
    
    Args:
        market_hash_name: Nome formatado do item para o mercado
        price: Preço atual da skin
        currency: Código da moeda
        app_id: ID da aplicação na Steam
    """
    now = datetime.now()
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Verificar se o item já existe
    cursor.execute('''
    SELECT id, update_count FROM skin_prices
    WHERE market_hash_name = %s AND currency = %s AND app_id = %s
    ''', (market_hash_name, currency, app_id))
    
    result = cursor.fetchone()
    
    if result:
        # Atualizar item existente
        cursor.execute('''
        UPDATE skin_prices
        SET price = %s, last_updated = %s, update_count = update_count + 1
        WHERE id = %s
        ''', (price, now, result['id']))
    else:
        # Inserir novo item
        cursor.execute('''
        INSERT INTO skin_prices 
        (market_hash_name, price, currency, app_id, last_updated, last_scraped, update_count)
        VALUES (%s, %s, %s, %s, %s, %s, 1)
        ''', (market_hash_name, price, currency, app_id, now, now))
    
    conn.commit()
    conn.close()

def get_outdated_skins(days: int = 7, limit: int = 100) -> List[Dict]:
    """
    Retorna uma lista de skins com preços desatualizados.
    
    Args:
        days: Número de dias para considerar um preço desatualizado
        limit: Limite de registros a retornar
        
    Returns:
        Lista de dicionários com informações das skins desatualizadas
    """
    outdated_date = datetime.now() - timedelta(days=days)
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute('''
    SELECT market_hash_name, price, currency, app_id, last_updated
    FROM skin_prices
    WHERE last_updated < %s
    ORDER BY last_updated ASC
    LIMIT %s
    ''', (outdated_date, limit))
    
    results = cursor.fetchall()
    conn.close()
    
    return list(results)

def update_last_scrape_time(market_hash_name: str, currency: int, app_id: int):
    """
    Atualiza o timestamp da última vez que o scraping foi feito para uma skin.
    
    Args:
        market_hash_name: Nome formatado do item para o mercado
        currency: Código da moeda
        app_id: ID da aplicação na Steam
    """
    now = datetime.now()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    UPDATE skin_prices
    SET last_scraped = %s
    WHERE market_hash_name = %s AND currency = %s AND app_id = %s
    ''', (now, market_hash_name, currency, app_id))
    
    conn.commit()
    conn.close()

def set_metadata(key: str, value: str):
    """
    Define um valor de metadata no banco de dados.
    
    Args:
        key: Chave do metadado
        value: Valor a ser armazenado
    """
    now = datetime.now()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO metadata (key, value, updated_at)
    VALUES (%s, %s, %s)
    ON CONFLICT (key) DO UPDATE SET
        value = EXCLUDED.value,
        updated_at = EXCLUDED.updated_at
    ''', (key, value, now))
    
    conn.commit()
    conn.close()

def get_metadata(key: str, default: str = None) -> str:
    """
    Obtém um valor de metadata do banco de dados.
    
    Args:
        key: Chave do metadado
        default: Valor padrão se a chave não existir
        
    Returns:
        Valor do metadado ou o valor padrão
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute('SELECT value FROM metadata WHERE key = %s', (key,))
    result = cursor.fetchone()
    conn.close()
    
    return result['value'] if result else default

def get_stats() -> Dict:
    """
    Retorna estatísticas sobre o banco de dados.
    
    Returns:
        Dicionário com estatísticas
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Total de skins
    cursor.execute('SELECT COUNT(*) as total FROM skin_prices')
    total = cursor.fetchone()['total']
    
    # Preço médio
    cursor.execute('SELECT AVG(price) as avg_price FROM skin_prices')
    avg_price = cursor.fetchone()['avg_price']
    
    # Skins atualizadas recentemente (7 dias)
    recent_date = datetime.now() - timedelta(days=7)
    cursor.execute('SELECT COUNT(*) as recent FROM skin_prices WHERE last_updated > %s', (recent_date,))
    recent = cursor.fetchone()['recent']
    
    # Última atualização
    cursor.execute('SELECT MAX(last_updated) as last_update FROM skin_prices')
    last_update = cursor.fetchone()['last_update']
    
    conn.close()
    
    return {
        'total_skins': total,
        'average_price': round(avg_price, 2) if avg_price else 0,
        'recently_updated': recent,
        'last_update': last_update.isoformat() if last_update else None,
        'database_type': 'PostgreSQL'
    } 
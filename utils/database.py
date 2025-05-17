import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
import urllib.parse
import socket
import json
import threading

# URL de conexão pública para o PostgreSQL no Railway
PUBLIC_DATABASE_URL = 'postgresql://postgres:nGFueZUdBGYipIfpFrxicixchLSgsShM@gondola.proxy.rlwy.net:10790/railway'

# URL de conexão interna (pode não funcionar fora do ambiente Railway)
INTERNAL_DATABASE_URL = 'postgresql://postgres:nGFueZUdBGYipIfpFrxicixchLSgsShM@postgres.railway.internal:5432/railway'

# URL de conexão prioritária com fallback para o público
DATABASE_URL = os.environ.get('DATABASE_URL', PUBLIC_DATABASE_URL)

# Componentes separados como fallback
DB_HOST = os.environ.get('DB_HOST', 'gondola.proxy.rlwy.net')
DB_PORT = os.environ.get('DB_PORT', '10790')
DB_NAME = os.environ.get('DB_NAME', 'railway')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'nGFueZUdBGYipIfpFrxicixchLSgsShM')

# Cache em memória para modo de fallback
in_memory_db = {
    'skin_prices': {},
    'metadata': {},
    'case_prices': {}  # Adicionado para armazenar caixas em memória
}
db_lock = threading.Lock()
DB_AVAILABLE = False  # Flag para indicar se o banco de dados está disponível

def get_db_connection():
    """Cria uma conexão com o banco de dados PostgreSQL."""
    global DB_AVAILABLE
    
    # Lista de modos SSL para tentar, em ordem de preferência
    ssl_modes = ['require', 'prefer', 'verify-ca', 'verify-full']
    last_error = None
    
    # 1. Primeira tentativa: Usar a URL pública (mais confiável)
    try:
        print(f"Tentando conectar com URL pública externa")
        conn = psycopg2.connect(PUBLIC_DATABASE_URL, sslmode='require', connect_timeout=20)
        print(f"Conexão bem-sucedida com URL pública")
        DB_AVAILABLE = True
        return conn
    except Exception as e:
        print(f"Erro ao conectar com URL pública: {e}")
        last_error = e
    
    # 2. Segunda tentativa: usar a URL interna (se disponível)
    if 'railway.internal' in INTERNAL_DATABASE_URL:
        try:
            print(f"Tentando conectar com URL interna do Railway")
            conn = psycopg2.connect(INTERNAL_DATABASE_URL, sslmode='prefer', connect_timeout=15)
            print(f"Conexão bem-sucedida com URL interna")
            DB_AVAILABLE = True
            return conn
        except Exception as e:
            print(f"Erro ao conectar com URL interna: {e}")
    
    # 3. Terceira tentativa: usar componentes separados
    for ssl_mode in ssl_modes:
        try:
            connect_params = {
                'host': DB_HOST,
                'port': DB_PORT,
                'dbname': DB_NAME,
                'user': DB_USER,
                'password': DB_PASSWORD,
                'sslmode': ssl_mode,
                'connect_timeout': 15,
                'application_name': 'elite-skins-api',
                'keepalives': 1,
                'keepalives_idle': 30
            }
            
            print(f"Tentando conectar ao PostgreSQL com parâmetros separados e sslmode={ssl_mode}")
            conn = psycopg2.connect(**connect_params)
            print(f"Conexão bem-sucedida com parâmetros separados e sslmode={ssl_mode}")
            DB_AVAILABLE = True
            return conn
        except Exception as e:
            print(f"Erro ao conectar com parâmetros separados e sslmode={ssl_mode}: {str(e)}")
            last_error = e
    
    # Se chegou aqui, todas as tentativas falharam
    error_msg = f"""
    Erro de conexão com o banco de dados PostgreSQL do Railway:
    - Host: {DB_HOST}
    - Porta: {DB_PORT}
    - Banco: {DB_NAME}
    - Usuário: {DB_USER}
    - Erro: {str(last_error)}
    - Sugestões:
      1. Verifique se o serviço PostgreSQL no Railway está ativo
      2. Confirme se as credenciais estão corretas
      3. Verifique se seu serviço tem permissão para acessar o banco de dados
      
    ENTRANDO EM MODO DE FALLBACK: Dados serão armazenados em memória temporariamente.
    """
    print(error_msg)
    DB_AVAILABLE = False
    # Não lançar erro, permitindo que a aplicação continue em modo de fallback
    return None

def init_db():
    """Inicializa o banco de dados com as tabelas necessárias."""
    try:
        conn = get_db_connection()
        if conn:
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
            
            # NOVA TABELA: Tabela para armazenar preços e conteúdos de caixas
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS case_prices (
                id SERIAL PRIMARY KEY,
                case_name TEXT NOT NULL,
                market_hash_name TEXT NOT NULL,
                price REAL NOT NULL,
                image_url TEXT,
                items_json TEXT,
                last_updated TIMESTAMP NOT NULL,
                update_count INTEGER DEFAULT 1,
                UNIQUE(market_hash_name)
            )
            ''')
            
            # Índice para buscas rápidas por case_name
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_case_prices_case_name
            ON case_prices(case_name)
            ''')
            
            conn.commit()
            conn.close()
            
            print(f"Banco de dados PostgreSQL inicializado")
        else:
            print("Banco de dados não disponível. Operando em modo de fallback (memória).")
    except Exception as e:
        print(f"Erro ao inicializar banco de dados: {e}")
        print("Operando em modo de fallback (memória).")

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
    if DB_AVAILABLE:
        try:
            conn = get_db_connection()
            if not conn:
                # Fallback para cache em memória
                return _get_price_from_memory(market_hash_name, currency, app_id)
                
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
        except Exception as e:
            print(f"Erro ao obter preço do banco: {e}")
            # Fallback para cache em memória
            return _get_price_from_memory(market_hash_name, currency, app_id)
    else:
        # Usar cache em memória quando o banco não está disponível
        return _get_price_from_memory(market_hash_name, currency, app_id)

def _get_price_from_memory(market_hash_name: str, currency: int, app_id: int) -> Optional[float]:
    """Obtém o preço do cache em memória"""
    key = f"{market_hash_name}:{currency}:{app_id}"
    with db_lock:
        if key in in_memory_db['skin_prices']:
            item = in_memory_db['skin_prices'][key]
            if datetime.now() - item['last_updated'] < timedelta(days=7):
                return item['price']
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
    
    # Sempre salva no cache em memória
    key = f"{market_hash_name}:{currency}:{app_id}"
    with db_lock:
        in_memory_db['skin_prices'][key] = {
            'market_hash_name': market_hash_name,
            'price': price,
            'currency': currency,
            'app_id': app_id,
            'last_updated': now,
            'last_scraped': now,
            'update_count': 1
        }
    
    # Se o banco estiver disponível, tenta salvar nele também
    if DB_AVAILABLE:
        try:
            conn = get_db_connection()
            if not conn:
                return
                
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
        except Exception as e:
            print(f"Erro ao salvar preço no banco de dados: {e}")
            # Já está no cache em memória, então só registramos o erro

def get_outdated_skins(days: int = 7, limit: int = 100) -> List[Dict]:
    """
    Retorna uma lista de skins com preços desatualizados.
    
    Args:
        days: Número de dias para considerar um preço desatualizado
        limit: Limite de registros a retornar
        
    Returns:
        Lista de dicionários com informações das skins desatualizadas
    """
    if DB_AVAILABLE:
        try:
            outdated_date = datetime.now() - timedelta(days=days)
            conn = get_db_connection()
            if not conn:
                return _get_outdated_from_memory(days, limit)
                
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
        except Exception as e:
            print(f"Erro ao obter skins desatualizadas do banco: {e}")
            return _get_outdated_from_memory(days, limit)
    else:
        return _get_outdated_from_memory(days, limit)

def _get_outdated_from_memory(days: int = 7, limit: int = 100) -> List[Dict]:
    """Obtém skins desatualizadas do cache em memória"""
    outdated_date = datetime.now() - timedelta(days=days)
    results = []
    
    with db_lock:
        for key, item in in_memory_db['skin_prices'].items():
            if item['last_updated'] < outdated_date:
                results.append(item)
                if len(results) >= limit:
                    break
    
    return results

def update_last_scrape_time(market_hash_name: str, currency: int, app_id: int):
    """
    Atualiza o timestamp da última vez que o scraping foi feito para uma skin.
    
    Args:
        market_hash_name: Nome formatado do item para o mercado
        currency: Código da moeda
        app_id: ID da aplicação na Steam
    """
    now = datetime.now()
    
    # Atualizar no cache em memória
    key = f"{market_hash_name}:{currency}:{app_id}"
    with db_lock:
        if key in in_memory_db['skin_prices']:
            in_memory_db['skin_prices'][key]['last_scraped'] = now
    
    # Se o banco estiver disponível, tenta atualizar nele também
    if DB_AVAILABLE:
        try:
            conn = get_db_connection()
            if not conn:
                return
                
            cursor = conn.cursor()
            
            cursor.execute('''
            UPDATE skin_prices
            SET last_scraped = %s
            WHERE market_hash_name = %s AND currency = %s AND app_id = %s
            ''', (now, market_hash_name, currency, app_id))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Erro ao atualizar tempo de scraping no banco: {e}")

def set_metadata(key: str, value: str):
    """
    Define um valor de metadata no banco de dados.
    
    Args:
        key: Chave do metadado
        value: Valor a ser armazenado
    """
    now = datetime.now()
    
    # Salvar no cache em memória
    with db_lock:
        in_memory_db['metadata'][key] = {
            'value': value,
            'updated_at': now
        }
    
    # Se o banco estiver disponível, tenta salvar nele também
    if DB_AVAILABLE:
        try:
            conn = get_db_connection()
            if not conn:
                return
                
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
        except Exception as e:
            print(f"Erro ao salvar metadata no banco: {e}")

def get_metadata(key: str, default: str = None) -> str:
    """
    Obtém um valor de metadata do banco de dados.
    
    Args:
        key: Chave do metadado
        default: Valor padrão se a chave não existir
        
    Returns:
        Valor do metadado ou o valor padrão
    """
    # Verificar primeiro no cache em memória
    with db_lock:
        if key in in_memory_db['metadata']:
            return in_memory_db['metadata'][key]['value']
    
    # Se não encontrou em memória e o banco está disponível, tenta buscar nele
    if DB_AVAILABLE:
        try:
            conn = get_db_connection()
            if not conn:
                return default
                
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute('SELECT value FROM metadata WHERE key = %s', (key,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                # Atualizar o cache em memória
                with db_lock:
                    in_memory_db['metadata'][key] = {
                        'value': result['value'],
                        'updated_at': datetime.now()
                    }
                return result['value']
        except Exception as e:
            print(f"Erro ao obter metadata do banco: {e}")
            
    return default

def get_stats() -> Dict:
    """
    Retorna estatísticas sobre o banco de dados.
    
    Returns:
        Dicionário com estatísticas
    """
    if DB_AVAILABLE:
        try:
            conn = get_db_connection()
            if not conn:
                return _get_stats_from_memory()
                
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
                'database_type': 'PostgreSQL',
                'mode': 'DB'
            }
        except Exception as e:
            print(f"Erro ao obter estatísticas do banco: {e}")
            return _get_stats_from_memory()
    else:
        return _get_stats_from_memory()

def _get_stats_from_memory() -> Dict:
    """Retorna estatísticas baseadas no cache em memória"""
    with db_lock:
        prices = list(item['price'] for item in in_memory_db['skin_prices'].values())
        total = len(in_memory_db['skin_prices'])
        avg_price = sum(prices) / total if total > 0 else 0
        
        # Skins atualizadas recentemente (7 dias)
        recent_date = datetime.now() - timedelta(days=7)
        recent = sum(1 for item in in_memory_db['skin_prices'].values() if item['last_updated'] > recent_date)
        
        # Última atualização
        last_update = max([item['last_updated'] for item in in_memory_db['skin_prices'].values()]) if total > 0 else None
        
        return {
            'total_skins': total,
            'average_price': round(avg_price, 2),
            'recently_updated': recent,
            'last_update': last_update.isoformat() if last_update else None,
            'database_type': 'Memory',
            'mode': 'FALLBACK'
        }

def save_case_price(case_name: str, market_hash_name: str, price: float, image_url: str = None, items_json: str = None):
    """
    Salva ou atualiza o preço e conteúdo de uma caixa no banco de dados.
    
    Args:
        case_name: Nome da caixa
        market_hash_name: Nome formatado da caixa para o mercado
        price: Preço atual da caixa
        image_url: URL da imagem da caixa
        items_json: JSON dos itens contidos na caixa
    """
    now = datetime.now()
    
    # Sempre salva no cache em memória
    key = market_hash_name
    with db_lock:
        in_memory_db['case_prices'][key] = {
            'case_name': case_name,
            'market_hash_name': market_hash_name,
            'price': price,
            'image_url': image_url,
            'items_json': items_json,
            'last_updated': now,
            'update_count': 1
        }
    
    # Se o banco estiver disponível, tenta salvar nele também
    if DB_AVAILABLE:
        try:
            conn = get_db_connection()
            if not conn:
                return
                
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Verificar se o item já existe
            cursor.execute('''
            SELECT id, update_count FROM case_prices
            WHERE market_hash_name = %s
            ''', (market_hash_name,))
            
            result = cursor.fetchone()
            
            if result:
                # Atualizar item existente
                cursor.execute('''
                UPDATE case_prices
                SET case_name = %s, price = %s, image_url = %s, items_json = %s, 
                    last_updated = %s, update_count = update_count + 1
                WHERE id = %s
                ''', (case_name, price, image_url, items_json, now, result['id']))
            else:
                # Inserir novo item
                cursor.execute('''
                INSERT INTO case_prices 
                (case_name, market_hash_name, price, image_url, items_json, last_updated, update_count)
                VALUES (%s, %s, %s, %s, %s, %s, 1)
                ''', (case_name, market_hash_name, price, image_url, items_json, now))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Erro ao salvar preço da caixa no banco de dados: {e}")
            # Já está no cache em memória, então só registramos o erro

def get_case_price(market_hash_name: str = None, case_name: str = None) -> Optional[Dict]:
    """
    Busca os detalhes de uma caixa no banco de dados.
    
    Args:
        market_hash_name: Nome formatado da caixa para o mercado
        case_name: Nome da caixa (alternativa para busca)
        
    Returns:
        Dicionário com detalhes da caixa ou None se não encontrada
    """
    if not market_hash_name and not case_name:
        return None
    
    if DB_AVAILABLE:
        try:
            conn = get_db_connection()
            if not conn:
                # Fallback para cache em memória
                return _get_case_price_from_memory(market_hash_name, case_name)
                
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if market_hash_name:
                cursor.execute('''
                SELECT * FROM case_prices
                WHERE market_hash_name = %s
                ''', (market_hash_name,))
            else:
                cursor.execute('''
                SELECT * FROM case_prices
                WHERE case_name = %s
                ''', (case_name,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                # Converter itens_json para Python
                if result['items_json']:
                    try:
                        result['items'] = json.loads(result['items_json'])
                    except:
                        result['items'] = []
                else:
                    result['items'] = []
                
                # Remover campo JSON original
                result.pop('items_json', None)
                
                return dict(result)
            
            return None
        except Exception as e:
            print(f"Erro ao obter preço da caixa do banco: {e}")
            # Fallback para cache em memória
            return _get_case_price_from_memory(market_hash_name, case_name)
    else:
        # Usar cache em memória quando o banco não está disponível
        return _get_case_price_from_memory(market_hash_name, case_name)

def _get_case_price_from_memory(market_hash_name: str = None, case_name: str = None) -> Optional[Dict]:
    """Obtém os detalhes da caixa do cache em memória"""
    with db_lock:
        if market_hash_name:
            if market_hash_name in in_memory_db['case_prices']:
                result = in_memory_db['case_prices'][market_hash_name].copy()
                
                # Converter itens_json para Python
                if result.get('items_json'):
                    try:
                        result['items'] = json.loads(result['items_json'])
                    except:
                        result['items'] = []
                else:
                    result['items'] = []
                
                # Remover campo JSON original
                result.pop('items_json', None)
                
                return result
        elif case_name:
            # Buscar por nome da caixa
            for key, item in in_memory_db['case_prices'].items():
                if item['case_name'] == case_name:
                    result = item.copy()
                    
                    # Converter itens_json para Python
                    if result.get('items_json'):
                        try:
                            result['items'] = json.loads(result['items_json'])
                        except:
                            result['items'] = []
                    else:
                        result['items'] = []
                    
                    # Remover campo JSON original
                    result.pop('items_json', None)
                    
                    return result
    
    return None

def get_all_cases(limit: int = 100) -> List[Dict]:
    """
    Retorna a lista de todas as caixas disponíveis.
    
    Args:
        limit: Limite de resultados
        
    Returns:
        Lista de dicionários com informações básicas das caixas
    """
    if DB_AVAILABLE:
        try:
            conn = get_db_connection()
            if not conn:
                return _get_all_cases_from_memory(limit)
                
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute('''
            SELECT id, case_name, market_hash_name, price, image_url, last_updated
            FROM case_prices
            ORDER BY case_name ASC
            LIMIT %s
            ''', (limit,))
            
            results = cursor.fetchall()
            conn.close()
            
            return list(results)
        except Exception as e:
            print(f"Erro ao obter lista de caixas do banco: {e}")
            return _get_all_cases_from_memory(limit)
    else:
        return _get_all_cases_from_memory(limit)

def _get_all_cases_from_memory(limit: int = 100) -> List[Dict]:
    """Obtém a lista de caixas do cache em memória"""
    results = []
    
    with db_lock:
        for key, item in in_memory_db['case_prices'].items():
            # Incluir apenas campos básicos
            results.append({
                'case_name': item['case_name'],
                'market_hash_name': item['market_hash_name'],
                'price': item['price'],
                'image_url': item.get('image_url'),
                'last_updated': item['last_updated']
            })
            
            if len(results) >= limit:
                break
    
    # Ordenar por nome
    results.sort(key=lambda x: x['case_name'])
    return results

def get_outdated_cases(days: int = 1, limit: int = 50) -> List[Dict]:
    """
    Retorna uma lista de caixas com preços desatualizados.
    
    Args:
        days: Número de dias para considerar um preço desatualizado
        limit: Limite de registros a retornar
        
    Returns:
        Lista de dicionários com informações das caixas desatualizadas
    """
    if DB_AVAILABLE:
        try:
            outdated_date = datetime.now() - timedelta(days=days)
            conn = get_db_connection()
            if not conn:
                return _get_outdated_cases_from_memory(days, limit)
                
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute('''
            SELECT id, case_name, market_hash_name, price, last_updated
            FROM case_prices
            WHERE last_updated < %s
            ORDER BY last_updated ASC
            LIMIT %s
            ''', (outdated_date, limit))
            
            results = cursor.fetchall()
            conn.close()
            
            return list(results)
        except Exception as e:
            print(f"Erro ao obter caixas desatualizadas do banco: {e}")
            return _get_outdated_cases_from_memory(days, limit)
    else:
        return _get_outdated_cases_from_memory(days, limit)

def _get_outdated_cases_from_memory(days: int = 1, limit: int = 50) -> List[Dict]:
    """Obtém caixas desatualizadas do cache em memória"""
    outdated_date = datetime.now() - timedelta(days=days)
    results = []
    
    with db_lock:
        for key, item in in_memory_db['case_prices'].items():
            if item['last_updated'] < outdated_date:
                results.append({
                    'case_name': item['case_name'],
                    'market_hash_name': item['market_hash_name'],
                    'price': item['price'],
                    'last_updated': item['last_updated']
                })
                
                if len(results) >= limit:
                    break
    
    return results 
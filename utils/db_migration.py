"""
Utilitário para migração de dados do SQLite para PostgreSQL.
Este script pode ser executado quando for necessário migrar os dados do banco local para o banco no servidor.
"""
import os
import sqlite3
import psycopg2
from psycopg2.extras import execute_values
import time
from typing import Dict, List, Tuple, Optional

# Configurações do SQLite (banco de dados local)
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'skins_cache.db')

# Função para conectar ao PostgreSQL (temporariamente desativada)
def get_postgres_conn(database_url: str = None) -> Optional[psycopg2.extensions.connection]:
    """
    Conecta ao banco de dados PostgreSQL.
    
    Args:
        database_url: URL de conexão com o PostgreSQL (ex: postgresql://user:password@host:port/dbname)
        
    Returns:
        Conexão com o PostgreSQL ou None se falhar
    """
    if not database_url:
        database_url = os.environ.get('DATABASE_URL')
        
    if not database_url:
        print("Erro: URL de conexão do PostgreSQL não fornecida nem encontrada em DATABASE_URL")
        return None
        
    try:
        # Conectar ao PostgreSQL
        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao PostgreSQL: {e}")
        return None

def create_postgres_tables(pg_conn: psycopg2.extensions.connection) -> bool:
    """
    Cria as tabelas no PostgreSQL.
    
    Args:
        pg_conn: Conexão com o PostgreSQL
        
    Returns:
        True se as tabelas foram criadas com sucesso, False caso contrário
    """
    try:
        cursor = pg_conn.cursor()
        
        # Criar tabela de preços de skins
        cursor.execute("""
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
        """)
        
        # Criar tabela de metadata
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
        """)
        
        # Criar índice para busca rápida por market_hash_name
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_skin_prices_market_hash_name
        ON skin_prices(market_hash_name)
        """)
        
        pg_conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao criar tabelas no PostgreSQL: {e}")
        pg_conn.rollback()
        return False

def get_sqlite_data() -> Tuple[List[Dict], List[Dict]]:
    """
    Obtém todos os dados do banco de dados SQLite.
    
    Returns:
        Tupla contendo duas listas: (preços de skins, metadata)
    """
    try:
        # Conectar ao SQLite
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        
        # Obter preços de skins
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM skin_prices")
        skin_prices = [dict(row) for row in cursor.fetchall()]
        
        # Obter metadata
        cursor.execute("SELECT * FROM metadata")
        metadata = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return skin_prices, metadata
    except Exception as e:
        print(f"Erro ao ler dados do SQLite: {e}")
        return [], []

def migrate_to_postgres(database_url: str = None) -> Dict:
    """
    Migra todos os dados do SQLite para o PostgreSQL.
    
    Args:
        database_url: URL de conexão com o PostgreSQL
        
    Returns:
        Dicionário com estatísticas da migração
    """
    print("Iniciando migração de dados do SQLite para PostgreSQL...")
    start_time = time.time()
    
    # Obter dados do SQLite
    skin_prices, metadata = get_sqlite_data()
    
    if not skin_prices and not metadata:
        return {
            "success": False,
            "error": "Não foi possível ler dados do SQLite",
            "duration_seconds": 0
        }
    
    # Conectar ao PostgreSQL
    pg_conn = get_postgres_conn(database_url)
    if not pg_conn:
        return {
            "success": False,
            "error": "Não foi possível conectar ao PostgreSQL",
            "duration_seconds": time.time() - start_time
        }
    
    # Criar tabelas no PostgreSQL
    if not create_postgres_tables(pg_conn):
        pg_conn.close()
        return {
            "success": False,
            "error": "Não foi possível criar tabelas no PostgreSQL",
            "duration_seconds": time.time() - start_time
        }
    
    try:
        cursor = pg_conn.cursor()
        
        # Inserir preços de skins
        if skin_prices:
            # Preparar valores para inserção em lote
            columns = skin_prices[0].keys()
            query = f"""
            INSERT INTO skin_prices ({', '.join(columns)})
            VALUES %s
            ON CONFLICT (market_hash_name, currency, app_id) 
            DO UPDATE SET 
                price = EXCLUDED.price,
                last_updated = EXCLUDED.last_updated,
                last_scraped = EXCLUDED.last_scraped,
                update_count = EXCLUDED.update_count
            """
            
            # Converter para uma lista de tuplas para o execute_values
            values = [[row[col] for col in columns] for row in skin_prices]
            execute_values(cursor, query, values)
        
        # Inserir metadata
        if metadata:
            for item in metadata:
                cursor.execute("""
                INSERT INTO metadata (key, value, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = EXCLUDED.updated_at
                """, (item['key'], item['value'], item['updated_at']))
        
        pg_conn.commit()
        
        # Verificar contagens
        cursor.execute("SELECT COUNT(*) FROM skin_prices")
        skin_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM metadata")
        metadata_count = cursor.fetchone()[0]
        
        pg_conn.close()
        
        duration = time.time() - start_time
        
        return {
            "success": True,
            "duration_seconds": duration,
            "migrated_skins": len(skin_prices),
            "migrated_metadata": len(metadata),
            "postgres_skin_count": skin_count,
            "postgres_metadata_count": metadata_count
        }
    
    except Exception as e:
        print(f"Erro durante a migração: {e}")
        pg_conn.rollback()
        pg_conn.close()
        
        return {
            "success": False,
            "error": str(e),
            "duration_seconds": time.time() - start_time
        }

# Função principal para uso em linha de comando
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrar dados do SQLite para PostgreSQL")
    parser.add_argument("--db-url", help="URL de conexão do PostgreSQL", required=False)
    
    args = parser.parse_args()
    
    # Verificar se DATABASE_URL está definido
    if not args.db_url and "DATABASE_URL" not in os.environ:
        print("Erro: Forneça a URL de conexão como argumento --db-url ou defina a variável de ambiente DATABASE_URL")
        exit(1)
    
    # Executar migração
    result = migrate_to_postgres(args.db_url)
    
    if result["success"]:
        print(f"Migração concluída com sucesso em {result['duration_seconds']:.2f} segundos")
        print(f"- Migrados {result['migrated_skins']} preços de skins")
        print(f"- Migrados {result['migrated_metadata']} metadados")
        print(f"- Total no PostgreSQL: {result['postgres_skin_count']} skins, {result['postgres_metadata_count']} metadados")
    else:
        print(f"Falha na migração: {result.get('error', 'Erro desconhecido')}") 
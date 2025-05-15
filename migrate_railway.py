"""
Script para inicializar tabelas no banco de dados PostgreSQL do Railway.
Execute este script uma vez após a implantação para preparar o banco de dados.
"""
import os
import psycopg2
from datetime import datetime
import time

# URL de conexão pública para o PostgreSQL no Railway
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:nGFueZUdBGYipIfpFrxicixchLSgsShM@gondola.proxy.rlwy.net:10790/railway')

def init_database():
    """Inicializa o banco de dados criando as tabelas necessárias."""
    print(f"Iniciando configuração do banco de dados no Railway...")
    start_time = time.time()
    
    try:
        # Conectar ao PostgreSQL
        print(f"Conectando ao PostgreSQL em {DATABASE_URL.split('@')[1].split('/')[0]}...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Criar tabela para armazenar preços de skins
        print("Criando tabela skin_prices...")
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
        
        # Criar tabela para armazenar metadata e configurações
        print("Criando tabela metadata...")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
        ''')
        
        # Criar índice para buscas rápidas por market_hash_name
        print("Criando índice para market_hash_name...")
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_skin_prices_market_hash_name
        ON skin_prices(market_hash_name)
        ''')
        
        # Inserir registro de configuração
        print("Inserindo registro de configuração inicial...")
        now = datetime.now()
        cursor.execute('''
        INSERT INTO metadata (key, value, updated_at)
        VALUES (%s, %s, %s)
        ON CONFLICT (key) DO UPDATE SET
            value = EXCLUDED.value,
            updated_at = EXCLUDED.updated_at
        ''', ('db_initialized', 'true', now))
        
        # Inserir registro com data da última atualização
        cursor.execute('''
        INSERT INTO metadata (key, value, updated_at)
        VALUES (%s, %s, %s)
        ON CONFLICT (key) DO UPDATE SET
            value = EXCLUDED.value,
            updated_at = EXCLUDED.updated_at
        ''', ('last_update', now.isoformat(), now))
        
        conn.commit()
        
        # Verificar se as tabelas foram criadas
        cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name IN ('skin_prices', 'metadata')")
        table_count = cursor.fetchone()[0]
        
        # Verificar se os índices foram criados
        cursor.execute("SELECT COUNT(*) FROM pg_indexes WHERE indexname = 'idx_skin_prices_market_hash_name'")
        index_count = cursor.fetchone()[0]
        
        # Verificar registros de metadata
        cursor.execute("SELECT COUNT(*) FROM metadata")
        metadata_count = cursor.fetchone()[0]
        
        conn.close()
        
        duration = time.time() - start_time
        
        print(f"Inicialização concluída em {duration:.2f} segundos:")
        print(f"- Tabelas criadas: {table_count}/2")
        print(f"- Índices criados: {index_count}/1")
        print(f"- Registros de metadata: {metadata_count}/2")
        
        return {
            "success": True,
            "duration": duration,
            "tables_created": table_count,
            "indices_created": index_count,
            "metadata_records": metadata_count
        }
    
    except Exception as e:
        print(f"Erro durante a inicialização do banco de dados: {e}")
        return {
            "success": False,
            "error": str(e),
            "duration": time.time() - start_time
        }

if __name__ == "__main__":
    result = init_database()
    
    if result["success"]:
        print("\nBanco de dados PostgreSQL inicializado com sucesso no Railway!")
        print("A API agora usará este banco de dados para armazenar preços de skins.")
    else:
        print(f"\nFalha na inicialização do banco de dados: {result.get('error')}")
        print("A API funcionará em modo de fallback (memória) até que o banco seja configurado corretamente.") 
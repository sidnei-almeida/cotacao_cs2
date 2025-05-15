#!/bin/bash

echo "=== INICIANDO SERVIDOR CS2 VALUATION API ==="
echo "Diretório atual: $(pwd)"
echo "Arquivos no diretório:"
ls -la

# Verificar se os módulos Python necessários estão disponíveis
echo "Verificando módulos Python..."
MAIN_MODULE_OK=false
RAILWAY_MODULE_OK=false
MINIMAL_MODULE_OK=false

# Testar módulos
python -c "import main; print('✅ main.py pode ser importado')" && MAIN_MODULE_OK=true || echo "❌ main.py não pode ser importado"
python -c "import railway_app; print('✅ railway_app.py pode ser importado')" && RAILWAY_MODULE_OK=true || echo "❌ railway_app.py não pode ser importado"
python -c "import minimal_app; print('✅ minimal_app.py pode ser importado')" && MINIMAL_MODULE_OK=true || echo "❌ minimal_app.py não pode ser importado"

# Verificar diretórios críticos
echo "Verificando diretórios críticos..."
[ -d "services" ] && echo "✅ Diretório services encontrado" || echo "❌ Diretório services não encontrado"
[ -d "utils" ] && echo "✅ Diretório utils encontrado" || echo "❌ Diretório utils não encontrado"
[ -d "auth" ] && echo "✅ Diretório auth encontrado" || echo "❌ Diretório auth não encontrado"

# Tentar iniciar a aplicação com diferentes módulos em ordem de preferência
if $MAIN_MODULE_OK; then
    echo "Iniciando com main.py (opção preferencial)..."
    gunicorn main:app -k uvicorn.workers.UvicornWorker -c gunicorn_config.py
elif $RAILWAY_MODULE_OK; then
    echo "Iniciando com railway_app.py (primeira alternativa)..."
    gunicorn railway_app:application -k uvicorn.workers.UvicornWorker -c gunicorn_config.py
elif $MINIMAL_MODULE_OK; then
    echo "Iniciando com minimal_app.py (segunda alternativa)..."
    gunicorn minimal_app:application -k uvicorn.workers.UvicornWorker -c gunicorn_config.py
else
    echo "ERRO: Nenhum módulo pode ser importado. Criando aplicação de emergência..."
    
    # Criar arquivo de emergência para evitar falha total
    cat > emergency_app.py << 'EOL'
from fastapi import FastAPI
import os

app = FastAPI(title="CS2 API - MODO DE EMERGÊNCIA")

@app.get("/")
async def root():
    return {
        "status": "emergency_mode",
        "message": "API em modo de emergência - Todos os módulos principais falharam",
        "cwd": os.getcwd(),
        "files": os.listdir(".")
    }

@app.get("/health")
async def health():
    return {"status": "limited"}

application = app
EOL
    
    echo "Iniciando com emergency_app.py (último recurso)..."
    gunicorn emergency_app:application -k uvicorn.workers.UvicornWorker -c gunicorn_config.py
fi 
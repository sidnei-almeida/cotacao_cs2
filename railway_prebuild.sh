#!/bin/bash

# Script para preparar o ambiente antes do deploy no Railway

echo "=== PREPARANDO AMBIENTE PARA DEPLOY ==="

# Verificar a estrutura de diretórios
echo "Estrutura atual:"
ls -la

# Garantir que o diretório atual está correto
echo "Diretório de trabalho: $(pwd)"

# Verificar se as dependências estão instaladas
echo "Verificando dependências..."
pip install -r requirements.txt

# Verificar arquivos críticos
echo "Verificando arquivos principais:"
if [ -f main.py ]; then
    echo "✅ main.py encontrado"
else
    echo "❌ main.py não encontrado!"
fi

if [ -f railway_app.py ]; then
    echo "✅ railway_app.py encontrado"
else
    echo "❌ railway_app.py não encontrado!"
fi

if [ -d services ]; then
    echo "✅ Diretório 'services' encontrado"
    ls -la services/
else
    echo "❌ Diretório 'services' não encontrado!"
fi

if [ -d auth ]; then
    echo "✅ Diretório 'auth' encontrado"
else
    echo "❌ Diretório 'auth' não encontrado!"
fi

if [ -d utils ]; then
    echo "✅ Diretório 'utils' encontrado"
else
    echo "❌ Diretório 'utils' não encontrado!"
fi

# Testar importação de módulos críticos
echo "Testando importações Python..."
python -c "from main import app; print(f'✅ Importação main.py bem-sucedida! Endpoints: {len(app.routes)}')" || echo "❌ Falha ao importar main.py"
python -c "from railway_app import application; print(f'✅ Importação railway_app.py bem-sucedida! Endpoints: {len(application.routes)}')" || echo "❌ Falha ao importar railway_app.py"

echo "=== PREPARAÇÃO CONCLUÍDA ===" 
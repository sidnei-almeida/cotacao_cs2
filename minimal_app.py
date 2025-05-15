"""
Versão minimalista da API para garantir funcionamento básico em produção.
Este arquivo recria alguns endpoints essenciais da API principal.
"""

import os
import sys
import traceback
from fastapi import FastAPI, Request, Response, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional

# Configurar aplicação
app = FastAPI(
    title="CS2 Valuation API (Minimal Version)",
    description="Versão minimalista da API de cotação de itens de CS2",
    version="0.5.0-minimal"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tentar importar funções dos módulos originais
try:
    # Tentar importar os serviços básicos
    from services.steam_inventory import get_inventory_value
    from services.case_evaluator import get_case_details, list_cases
    from services.steam_market import get_item_price, get_api_status
    
    # Variável para indicar que temos acesso às funções originais
    ORIGINAL_FUNCTIONS_AVAILABLE = True
    print("Funções originais importadas com sucesso!")
    
except Exception as e:
    # Se falhar, criar funções de fallback
    print(f"Erro ao importar funções originais: {str(e)}")
    print(traceback.format_exc())
    
    ORIGINAL_FUNCTIONS_AVAILABLE = False
    
    # Funções de fallback
    def get_inventory_value(steamid: str) -> Dict[str, Any]:
        return {
            "steamid": steamid,
            "total_items": 0,
            "total_value": 0.0,
            "currency": "BRL",
            "items": [],
            "most_valuable_item": None,
            "storage_units": [],
            "market_items": [],
            "storage_units_count": 0,
            "market_items_count": 0,
            "average_item_value": 0.0,
            "note": "API em modo de fallback - função original não disponível"
        }
    
    def get_case_details(case_name: str) -> Dict[str, Any]:
        return {
            "name": case_name,
            "price": 0.0,
            "currency": "BRL",
            "rarity": "unknown",
            "note": "API em modo de fallback - função original não disponível"
        }
    
    def list_cases() -> Dict[str, Any]:
        return {
            "cases": [],
            "count": 0,
            "note": "API em modo de fallback - função original não disponível"
        }
    
    def get_item_price(market_hash_name: str) -> Dict[str, Any]:
        return {
            "name": market_hash_name,
            "price": 0.0,
            "currency": "BRL",
            "success": False,
            "note": "API em modo de fallback - função original não disponível"
        }
    
    def get_api_status() -> Dict[str, Any]:
        return {
            "status": "limited",
            "version": "0.5.0-minimal-fallback",
            "steam_api": False,
            "database": False,
            "scraper": False,
            "note": "API em modo de fallback - funções originais não disponíveis"
        }

# Endpoint raiz
@app.get("/")
async def root():
    return {
        "message": "CS2 Valuation API (Minimal Version)",
        "features": [
            "Versão minimalista da API para garantir funcionamento básico",
            "Alguns endpoints essenciais foram recriados"
        ],
        "endpoints_disponíveis": [
            "/inventory/{steamid} - Análise básica de inventário",
            "/price/{market_hash_name} - Preço de um item específico",
            "/case/{case_name} - Detalhes de uma caixa específica",
            "/cases - Lista de caixas disponíveis",
            "/api/status - Status do sistema",
            "/health - Verificação de saúde da API"
        ],
        "status": "minimalist" if not ORIGINAL_FUNCTIONS_AVAILABLE else "partial",
        "original_functions": ORIGINAL_FUNCTIONS_AVAILABLE,
        "version": "0.5.0-minimal"
    }

# Endpoint de verificação de saúde
@app.get("/health")
async def health():
    return {"status": "ok"}

# Endpoint para diagnóstico de ambiente
@app.get("/environment")
async def environment():
    return {
        "cwd": os.getcwd(),
        "files": os.listdir("."),
        "python_path": sys.path,
        "environment": {k: v for k, v in os.environ.items() 
                       if "password" not in k.lower() 
                       and "secret" not in k.lower() 
                       and "key" not in k.lower()},
        "modules_available": {
            "services": os.path.exists("services"),
            "utils": os.path.exists("utils"),
            "auth": os.path.exists("auth")
        }
    }

# Endpoint de inventário
@app.get("/inventory/{steamid}")
async def inventory(steamid: str, response: Response, request: Request = None):
    """Retorna os itens e preços estimados do inventário"""
    try:
        result = get_inventory_value(steamid)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar inventário: {str(e)}")

# Endpoint de preço
@app.get("/price/{market_hash_name}")
async def price(market_hash_name: str, response: Response, request: Request = None):
    """Retorna o preço atual de um item específico"""
    try:
        result = get_item_price(market_hash_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter preço: {str(e)}")

# Endpoint de caixa
@app.get("/case/{case_name}")
async def case(case_name: str, response: Response, request: Request = None):
    """Retorna informações sobre uma caixa específica"""
    try:
        result = get_case_details(case_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter detalhes da caixa: {str(e)}")

# Endpoint de lista de caixas
@app.get("/cases")
async def cases(response: Response, request: Request = None):
    """Retorna a lista de caixas disponíveis"""
    try:
        result = list_cases()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar caixas: {str(e)}")

# Endpoint de status da API
@app.get("/api/status")
async def api_status(response: Response, request: Request = None):
    """Retorna o status atual da API"""
    try:
        result = get_api_status()
        # Adicionar informação sobre o modo minimalista
        result["minimal_mode"] = not ORIGINAL_FUNCTIONS_AVAILABLE
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter status: {str(e)}")

# Exportar a aplicação para o gunicorn
application = app 
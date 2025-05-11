from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
import uvicorn

# Importando serviços e configurações
from services.steam_inventory import get_inventory_value
from services.case_evaluator import get_case_details, list_cases
from services.steam_market import get_item_price, get_api_status
from utils.config import get_api_config

app = FastAPI(
    title="CS2 Valuation API",
    description="API para avaliação de inventários e caixas do CS2",
    version="0.1.0"
)

# Configuração de CORS para permitir requisições do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especifique os domínios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "CS2 Valuation API",
        "endpoints": [
            "/inventory/{steamid}",
            "/case/{case_name}",
            "/price/{market_hash_name}",
            "/cases",
            "/api/status"
        ]
    }


@app.get("/inventory/{steamid}")
async def inventory(steamid: str):
    """Retorna os itens e preços estimados do inventário público"""
    try:
        result = get_inventory_value(steamid)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/case/{case_name}")
async def case(case_name: str):
    """Retorna os possíveis drops da caixa, preços médios e valor esperado"""
    try:
        result = get_case_details(case_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/price/{market_hash_name}")
async def price(market_hash_name: str):
    """Retorna o preço médio atual do item no Steam Market"""
    try:
        result = get_item_price(market_hash_name)
        return {"name": market_hash_name, "price": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cases")
async def cases():
    """Lista todas as caixas suportadas pela API"""
    try:
        result = list_cases()
        return {"cases": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
async def api_status():
    """Verifica o status da configuração e testa a conexão com o endpoint do mercado da Steam"""
    try:
        # Obter status das configurações gerais
        config_status = get_api_config()
        
        # Testar conexão com as APIs
        api_test_results = get_api_status()
        
        return {
            "config": config_status,
            "connection_test": api_test_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

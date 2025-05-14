from fastapi import FastAPI, HTTPException, Query, Request, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from starlette.middleware.base import BaseHTTPMiddleware
from typing import List, Dict, Any, Optional
import uvicorn
import jwt
from jwt.exceptions import PyJWTError
import os
import datetime

# Importando serviços e configurações
from services.steam_inventory import get_inventory_value, get_storage_unit_contents
from services.case_evaluator import get_case_details, list_cases
from services.steam_market import get_item_price, get_api_status
from utils.config import get_api_config
from auth.steam_auth import steam_login_url, validate_steam_login, create_jwt_token, verify_jwt_token, SECRET_KEY, ALGORITHM

# Configuração de autenticação OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

app = FastAPI(
    title="CS2 Valuation API",
    description="API para avaliação de inventários, distinguindo entre Unidades de Armazenamento e itens do mercado",
    version="0.4.0"  # Atualizada para versão com organização por origem dos itens
)

# Função auxiliar para aplicar headers CORS consistentemente
def apply_cors_headers(response: Response):
    """Aplica cabeçalhos CORS de forma consistente em todas as respostas"""
    response.headers["Access-Control-Allow-Origin"] = "https://elite-skins-2025.github.io"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

# Middleware para adicionar cabeçalhos CORS a todas as respostas
class CorsHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Adicionar cabeçalhos CORS a todas as respostas
        response.headers["Access-Control-Allow-Origin"] = "https://elite-skins-2025.github.io"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response

# Configuração de CORS para permitir requisições do frontend - Atualizada
origins = [
    "http://localhost:5500",  # Desenvolvimento local
    "https://elite-skins-2025.github.io",  # GitHub Pages
    "elite-skins-2025.github.io"  # Adicionado sem https para garantir compatibilidade
]

# Adicionar o middleware CORS antes de outros middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE", "PUT", "PATCH"],  # Especificando métodos explicitamente
    allow_headers=["*"],
    expose_headers=["Content-Type", "Authorization"],  # Expondo cabeçalhos importantes
    max_age=86400,  # Cache de preflight por 24 horas
)

# Adicionar middleware personalizado para garantir cabeçalhos CORS em todas as respostas
app.add_middleware(CorsHeadersMiddleware)

# Adicionar middleware para garantir que OPTIONS seja tratado corretamente
@app.options("/{path:path}")
async def options_route(path: str, request: Request):
    return {}  # Retorna resposta vazia para que o middleware CORS lide com OPTIONS

# Lista de endpoints para a página inicial
AVAILABLE_ENDPOINTS = [
    "/inventory/{steamid}",
    "/inventory/full/{steamid}",
    "/my/inventory",  # Inventário do usuário autenticado
    "/my/inventory/full",  # Análise por categoria do usuário autenticado
    "/my/inventory/complete",  # Inventário completo do usuário autenticado com conteúdo das unidades
    "/case/{case_name}",
    "/price/{market_hash_name}",
    "/cases",
    "/api/status",
    "/auth/steam",  # Autenticação com a Steam
    "/auth/steam/callback"  # Callback da autenticação
]


@app.get("/")
async def root():
    return {
        "message": "CS2 Valuation API (Storage Unit Access Version)",
        "features": [
            "Scraping exclusivo para todos os preços de itens",
            "Classificação de itens por origem (Unidades de Armazenamento ou Mercado)",
            "Análise de inventário por categorias",
            "Acesso ao conteúdo das Unidades de Armazenamento (apenas do próprio usuário autenticado)"
        ],
        "endpoints_públicos": [
            "/inventory/{steamid} - Análise básica de inventário de terceiros",
            "/inventory/full/{steamid} - Análise por categoria de inventário de terceiros",
            "/price/{market_hash_name} - Preço de um item específico",
            "/case/{case_name} - Detalhes de uma caixa específica",
            "/cases - Lista de caixas disponíveis",
            "/api/status - Status do sistema"
        ],
        "endpoints_autenticados": [
            "/my/inventory - Seu próprio inventário básico",
            "/my/inventory/full - Seu próprio inventário com categorias",
            "/my/inventory/complete - Seu inventário completo incluindo conteúdo de Unidades de Armazenamento"
        ],
        "autenticação": [
            "/auth/steam - Login via Steam",
            "/auth/steam/callback - Retorno após autenticação"
        ],
        "version": "0.5.0"
    }


@app.get("/inventory/{steamid}")
async def inventory(steamid: str, response: Response):
    """Retorna os itens e preços estimados do inventário público, diferenciando entre Unidades de Armazenamento e itens do mercado"""
    # Adicionar cabeçalhos CORS manualmente para garantir compatibilidade
    response.headers["Access-Control-Allow-Origin"] = "https://elite-skins-2025.github.io"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    try:
        print(f"Iniciando análise de inventário para {steamid}")
        result = get_inventory_value(steamid)
        
        # Garantir que os campos necessários existam
        if "average_item_value" not in result:
            result["average_item_value"] = round(result["total_value"] / result["total_items"], 2) if result["total_items"] > 0 else 0
            
        if "most_valuable_item" not in result or result["most_valuable_item"] is None:
            # Tentar encontrar o item mais valioso na lista
            most_valuable = None
            highest_price = 0
            
            for item in result.get("items", []):
                if item.get("price", 0) > highest_price:
                    highest_price = item.get("price", 0)
                    most_valuable = {
                        "name": item.get("name", ""),
                        "market_hash_name": item.get("market_hash_name", ""),
                        "price": item.get("price", 0),
                        "source": item.get("source", "market")
                    }
            
            result["most_valuable_item"] = most_valuable
            
        # Arredondar valores para facilitar exibição
        result["total_value"] = round(result["total_value"], 2)
        result["average_item_value"] = round(result["average_item_value"], 2)
        
        # Adicionar contagens por tipo de fonte se não existirem
        if "storage_units_count" not in result:
            result["storage_units_count"] = len(result.get("storage_units", []))
        
        if "market_items_count" not in result:
            result["market_items_count"] = len(result.get("market_items", []))
        
        # Adicionar resumo por fonte
        result["source_summary"] = {
            "storage_units": {
                "count": result["storage_units_count"],
                "value": round(sum(item.get("total", 0) for item in result.get("storage_units", [])), 2)
            },
            "market": {
                "count": result["market_items_count"],
                "value": round(sum(item.get("total", 0) for item in result.get("market_items", [])), 2)
            }
        }
        
        print(f"Análise de inventário concluída para {steamid}: {len(result.get('items', []))} itens encontrados")
        print(f"- Itens de Unidades de Armazenamento: {result['storage_units_count']}")
        print(f"- Itens de Mercado: {result['market_items_count']}")
        
        return result
    except Exception as e:
        print(f"Erro ao processar inventário: {e}")
        import traceback
        traceback.print_exc()
        # Retornar um objeto com informação de erro que o frontend pode interpretar
        return {
            "steamid": steamid,
            "error": str(e),
            "total_items": 0,
            "total_value": 0,
            "items": [],
            "storage_units": [],
            "market_items": []
        }


@app.get("/inventory/full/{steamid}")
async def full_inventory_analysis(steamid: str, response: Response):
    """
    Retorna análise completa do inventário incluindo valor dos itens e classificação por fonte
    """
    # Adicionar cabeçalhos CORS manualmente para garantir compatibilidade
    response.headers["Access-Control-Allow-Origin"] = "https://elite-skins-2025.github.io"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    try:
        # Obter inventário básico
        inventory_result = get_inventory_value(steamid)
        
        # Garantir que os campos necessários existam
        if "average_item_value" not in inventory_result:
            inventory_result["average_item_value"] = round(inventory_result["total_value"] / inventory_result["total_items"], 2) if inventory_result["total_items"] > 0 else 0
            
        if "most_valuable_item" not in inventory_result or inventory_result["most_valuable_item"] is None:
            # Tentar encontrar o item mais valioso na lista
            most_valuable = None
            highest_price = 0
            
            for item in inventory_result.get("items", []):
                if item.get("price", 0) > highest_price:
                    highest_price = item.get("price", 0)
                    most_valuable = {
                        "name": item.get("name", ""),
                        "market_hash_name": item.get("market_hash_name", ""),
                        "price": item.get("price", 0),
                        "source": item.get("source", "market")
                    }
            
            inventory_result["most_valuable_item"] = most_valuable
        
        # Adicionar resumo por fonte se ainda não existir
        if "source_summary" not in inventory_result:
            storage_units = inventory_result.get("storage_units", [])
            market_items = inventory_result.get("market_items", [])
            
            inventory_result["source_summary"] = {
                "storage_units": {
                    "count": len(storage_units),
                    "value": round(sum(item.get("total", 0) for item in storage_units), 2)
                },
                "market": {
                    "count": len(market_items),
                    "value": round(sum(item.get("total", 0) for item in market_items), 2)
                }
            }
        
        # Adicionar análise por categoria
        categories = {}
        for item in inventory_result.get("items", []):
            category = item.get("category", "Outros")
            if category not in categories:
                categories[category] = {
                    "count": 0,
                    "value": 0.0,
                    "items": []
                }
            
            categories[category]["count"] += item.get("quantity", 1)
            categories[category]["value"] += item.get("total", 0)
            categories[category]["items"].append(item)
        
        # Arredondar valores por categoria
        for category in categories:
            categories[category]["value"] = round(categories[category]["value"], 2)
        
        # Adicionar análise por categoria ao resultado
        inventory_result["category_summary"] = categories
        
        # Arredondar valores para facilitar exibição
        inventory_result["total_value"] = round(inventory_result["total_value"], 2)
        inventory_result["average_item_value"] = round(inventory_result["average_item_value"], 2)
        if inventory_result["most_valuable_item"]:
            inventory_result["most_valuable_item"]["price"] = round(inventory_result["most_valuable_item"]["price"], 2)
        
        return inventory_result
    except Exception as e:
        print(f"Erro ao processar análise completa: {e}")
        import traceback
        traceback.print_exc()
        return {
            "steamid": steamid,
            "error": str(e),
            "total_items": 0,
            "total_value": 0,
            "items": [],
            "storage_units": [],
            "market_items": []
        }


@app.get("/case/{case_name}")
async def case(case_name: str, response: Response):
    """Retorna o preço atual da caixa no mercado"""
    # Aplicar cabeçalhos CORS
    apply_cors_headers(response)
    
    try:
        print(f"Buscando preço para caixa: {case_name}")
        result = get_case_details(case_name)
        
        # Formatar valores numéricos para melhor exibição
        result["price"] = round(result.get("price", 0), 2)
        
        # Retornar diretamente o objeto para compatibilidade com o frontend
        return result
    except Exception as e:
        print(f"Erro ao buscar detalhes da caixa '{case_name}': {e}")
        import traceback
        traceback.print_exc()
        # Retornar objeto com informação de erro que o frontend pode interpretar
        return {
            "name": case_name,
            "error": f"Não foi possível encontrar a caixa: {str(e)}",
            "price": 0,
            "source": "market",
            "item_type": "premium_case"
        }


@app.get("/price/{market_hash_name}")
async def price(market_hash_name: str, response: Response):
    """Retorna o preço médio atual do item no Steam Market (via scraping)"""
    # Aplicar cabeçalhos CORS
    apply_cors_headers(response)
    
    try:
        print(f"Buscando preço para: {market_hash_name}")
        result = get_item_price(market_hash_name)
        return {"name": market_hash_name, "price": round(result, 2)}
    except Exception as e:
        print(f"Erro ao obter preço para {market_hash_name}: {e}")
        import traceback
        traceback.print_exc()
        return {"name": market_hash_name, "price": 0, "error": str(e)}


@app.get("/cases")
async def cases(response: Response):
    """Lista todas as caixas suportadas pela API"""
    # Aplicar cabeçalhos CORS
    apply_cors_headers(response)
    
    try:
        # Obter lista de caixas
        result = list_cases()
        
        # Verificar se obteve resultados
        if not result:
            print("Aviso: Função list_cases retornou lista vazia")
            # Se não encontrou caixas, retornar uma lista vazia simples
            # para compatibilidade com o frontend
            return result
        
        # Retornar diretamente a lista de nomes de caixas para compatibilidade com o frontend
        return result
    except Exception as e:
        print(f"Erro ao obter lista de caixas: {e}")
        import traceback
        traceback.print_exc()
        # Retornar uma lista vazia em caso de erro para evitar erros no frontend
        return []


@app.get("/api/status")
async def api_status(response: Response):
    """Verifica o status do sistema e configurações"""
    # Aplicar cabeçalhos CORS
    apply_cors_headers(response)
    
    try:
        # Obter status das configurações gerais
        config_status = get_api_config()
        
        # Testar conexão com as APIs e sistema de scraping
        api_test_results = get_api_status()
        
        return {
            "version": "0.5.0 (Storage Unit Access)",
            "features": [
                "Scraping exclusivo para preços", 
                "Classificação por origem (Unidade/Mercado)",
                "Acesso ao conteúdo das Unidades de Armazenamento",
                "Autenticação via Steam OpenID"
            ],
            "config": config_status,
            "connection_test": api_test_results,
            "api_key_status": "Configurada" if config_status.get("steam_api_key") != "Não configurada" else "Não configurada"
        }
    except Exception as e:
        print(f"Erro ao verificar status da API: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# Funções para autenticação
def get_current_user(token: str = Depends(oauth2_scheme)):
    """Obtém o usuário atual baseado no token JWT"""
    if not token:
        # Retornar None para permitir que o endpoint decida como lidar com ausência de token
        return None
        
    try:
        # Decodificar o token manualmente com tratamento de erro melhorado
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError:
            return {"error": "Token expirado. Faça login novamente."}
        except jwt.InvalidTokenError:
            return {"error": "Token inválido. Formato incorreto."}
        except Exception as e:
            return {"error": f"Erro ao processar token: {str(e)}"}
            
        # Verificar se o payload contém o steam_id
        steam_id = payload.get("steam_id")
        if not steam_id:
            return {"error": "Token não contém SteamID"}
            
        # Retornar informações do usuário
        return {"steam_id": steam_id}
    except Exception as e:
        print(f"Erro na autenticação: {e}")
        return {"error": f"Erro na autenticação: {str(e)}"}


# Endpoints para autenticação com a Steam
@app.get("/auth/steam")
async def steam_auth(request: Request):
    """Redireciona para o login da Steam"""
    # URL base para a API
    base_url = str(request.base_url).rstrip('/')
    redirect_uri = f"{base_url}/auth/steam/callback"
    
    # Gerar URL de login
    login_url = steam_login_url(redirect_uri)
    return RedirectResponse(url=login_url)


@app.get("/auth/steam/callback")
async def steam_callback(request: Request):
    """Callback após o login na Steam"""
    # Extrair parâmetros da resposta
    params = dict(request.query_params)
    
    # Validar autenticação
    steam_id = validate_steam_login(params)
    if steam_id:
        # Gerar token JWT
        token = create_jwt_token({"steam_id": steam_id})
        
        # URL do frontend
        # Detectar se estamos em ambiente de produção ou desenvolvimento
        host = str(request.headers.get("host", ""))
        if "localhost" in host or "127.0.0.1" in host:
            # Ambiente de desenvolvimento local
            frontend_url = "http://localhost:5500/api.html"
        else:
            # Ambiente de produção (GitHub Pages)
            frontend_url = "https://elite-skins-2025.github.io/api.html"
        
        # Redirecionar para o frontend com o token como parâmetro
        redirect_url = f"{frontend_url}?token={token}"
        
        # Retornar um redirecionamento HTTP 302
        return RedirectResponse(url=redirect_url)
    else:
        return {"error": "Falha na autenticação com a Steam"}


# Endpoint para análise completa de inventário (incluindo conteúdo das Unidades de Armazenamento)
# Esta função agora é interna e usada apenas pelo /my/inventory/complete
async def _complete_inventory_analysis(
    steamid: str, 
    current_user: dict,
    session_id: str,
    steam_token: str
):
    """
    Função interna: Retorna análise completa do inventário incluindo o conteúdo das Unidades de Armazenamento.
    Requer que o usuário esteja autenticado e seja o dono do inventário.
    """
    # Verificar se o usuário está autenticado
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Autenticação necessária para acessar este endpoint"
        )
    
    # Verificar se há erro de autenticação
    if "error" in current_user:
        raise HTTPException(
            status_code=401,
            detail=current_user["error"]
        )
    
    # Verificar se o usuário está tentando acessar seu próprio inventário
    if steamid != current_user["steam_id"]:
        raise HTTPException(
            status_code=403,
            detail="Você só pode acessar o conteúdo das suas próprias Unidades de Armazenamento"
        )
    
    # Verificar se todos os parâmetros necessários foram fornecidos
    if not session_id or not steam_token:
        raise HTTPException(
            status_code=400,
            detail="session_id e steam_token são necessários para acessar Unidades de Armazenamento"
        )
    
    try:
        # Obter inventário básico
        inventory_result = get_inventory_value(steamid)
        
        # Processar unidades de armazenamento
        storage_units = inventory_result.get("storage_units", [])
        storage_unit_contents = []
        
        for unit in storage_units:
            unit_id = unit.get("assetid")
            if unit_id:
                # Obter conteúdo da unidade
                contents = get_storage_unit_contents(
                    unit_id,
                    steamid,
                    session_id,
                    steam_token
                )
                
                # Adicionar à lista de conteúdos
                storage_unit_contents.append({
                    "unit_info": unit,
                    "contents": contents
                })
        
        # Adicionar conteúdos ao resultado
        inventory_result["storage_unit_contents"] = storage_unit_contents
        
        # Calcular totais incluindo conteúdo das unidades
        total_units_value = sum(
            content.get("contents", {}).get("total_value", 0)
            for content in storage_unit_contents
        )
        
        inventory_result["storage_units_content_value"] = total_units_value
        inventory_result["grand_total_value"] = inventory_result["total_value"] + total_units_value
        
        # Adicionar uma lista plana com todos os itens (inventário + unidades)
        all_items = inventory_result.get("items", [])[:]  # Cópia da lista original
        
        for unit_content in storage_unit_contents:
            all_items.extend(unit_content.get("contents", {}).get("items", []))
        
        inventory_result["all_items"] = all_items
        inventory_result["all_items_count"] = len(all_items)
        
        return inventory_result
    
    except Exception as e:
        print(f"Erro ao processar inventário completo: {e}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar inventário: {str(e)}"
        )


# Novos endpoints para o usuário autenticado
@app.get("/my/inventory")
async def my_inventory(current_user: dict = Depends(get_current_user)):
    """Retorna os itens e preços estimados do inventário do usuário autenticado"""
    # Verificar se o usuário está autenticado
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Autenticação necessária para acessar este endpoint. Adicione o token JWT no cabeçalho Authorization: Bearer [seu_token]"
        )
    
    # Verificar se há erro de autenticação
    if "error" in current_user:
        raise HTTPException(
            status_code=401,
            detail=current_user["error"]
        )
    
    # Reutiliza a função de inventário existente com o steamid do usuário autenticado
    steamid = current_user["steam_id"]
    return await inventory(steamid)


@app.get("/my/inventory/complete")
async def my_inventory_complete(
    current_user: dict = Depends(get_current_user),
    session_id: str = Query(None),
    steam_token: str = Query(None)
):
    """
    Retorna análise completa do inventário do usuário autenticado incluindo o conteúdo das
    Unidades de Armazenamento.
    """
    # Verificar se o usuário está autenticado
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Autenticação necessária para acessar este endpoint. Adicione o token JWT no cabeçalho Authorization: Bearer [seu_token]"
        )
    
    # Verificar se há erro de autenticação
    if "error" in current_user:
        raise HTTPException(
            status_code=401,
            detail=current_user["error"]
        )
    
    # Verificar se todos os parâmetros necessários foram fornecidos
    if not session_id or not steam_token:
        raise HTTPException(
            status_code=400,
            detail="session_id e steam_token são necessários para acessar Unidades de Armazenamento"
        )
    
    # Reutiliza a função interna com o steamid do usuário autenticado
    steamid = current_user["steam_id"]
    return await _complete_inventory_analysis(
        steamid=steamid,
        current_user=current_user,
        session_id=session_id,
        steam_token=steam_token
    )


@app.get("/my/inventory/full")
async def my_inventory_full(current_user: dict = Depends(get_current_user)):
    """
    Retorna análise completa do inventário do usuário autenticado por categoria.
    """
    # Verificar se o usuário está autenticado
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Autenticação necessária para acessar este endpoint. Adicione o token JWT no cabeçalho Authorization: Bearer [seu_token]"
        )
    
    # Verificar se há erro de autenticação
    if "error" in current_user:
        raise HTTPException(
            status_code=401,
            detail=current_user["error"]
        )
    
    # Reutiliza a função de inventário detalhado com o steamid do usuário autenticado
    steamid = current_user["steam_id"]
    return await full_inventory_analysis(steamid)


@app.get("/cors-test")
async def cors_test(response: Response):
    """Endpoint simples para testar cabeçalhos CORS"""
    # Adicionar cabeçalhos CORS manualmente
    response.headers["Access-Control-Allow-Origin"] = "https://elite-skins-2025.github.io"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    return {
        "cors_status": "OK",
        "message": "Se você conseguir ver esta mensagem, os cabeçalhos CORS estão funcionando corretamente",
        "timestamp": str(datetime.datetime.now()),
        "origin": "https://elite-skins-2025.github.io"
    }


if __name__ == "__main__":
    # Aumentar número de workers e timeout para lidar melhor com requisições longas
    # Como o processamento de inventários grandes pode demorar
    
    # Obter a porta do ambiente (para compatibilidade com Render e outros serviços de hospedagem)
    port = int(os.environ.get("PORT", 8000))
    
    print("Starting server with CORS configuration enabled:")
    print(f"- Allowed origins: {origins}")
    print("- CORS middleware and options handler configured")
    print("- Custom CORS headers middleware added")
    
    # Aumentar os timeouts para lidar melhor com requisições CORS preflight
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=port, 
        reload=True,
        workers=4,  # Mais workers para processar requisições em paralelo
        timeout_keep_alive=120,  # Manter conexões vivas por mais tempo (2 minutos)
        timeout_graceful_shutdown=30,  # Dar mais tempo para shutdown
        log_level="info"  # Aumentar log para debug de CORS
    )

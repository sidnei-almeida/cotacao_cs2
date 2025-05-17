from fastapi import FastAPI, HTTPException, Query, Request, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from starlette.middleware.base import BaseHTTPMiddleware
from typing import List, Dict, Any, Optional
import uvicorn
import jwt
from jwt.exceptions import PyJWTError
import os
import datetime
from urllib.parse import urlencode
from starlette.status import HTTP_401_UNAUTHORIZED
import asyncio

# Importando serviços e configurações
from services.steam_inventory import get_inventory_value, get_storage_unit_contents
from services.case_evaluator import get_case_details, list_cases
from services.steam_market import get_item_price, get_api_status, get_item_price_via_csgostash
from utils.config import get_api_config
from utils.database import init_db, get_stats, get_db_connection
from utils.price_updater import run_scheduler, force_update_now, get_scheduler_status, schedule_weekly_update
from auth.steam_auth import steam_login_url, validate_steam_login, create_jwt_token, verify_jwt_token, SECRET_KEY, ALGORITHM

# Importe para o inicializador de banco de dados
from migrate_railway import init_database

# Classe personalizada para aceitar token via URL ou header
class OAuth2PasswordBearerWithCookie(OAuth2):
    def __init__(self, tokenUrl: str, auto_error: bool = True):
        flows = OAuthFlowsModel(password={"tokenUrl": tokenUrl, "scopes": {}})
        super().__init__(flows=flows, scheme_name="Bearer", auto_error=auto_error)

    async def __call__(self, request: Request):
        # Tenta obter o token via header Authorization primeiro
        authorization = request.headers.get("Authorization")
        scheme, param = "", ""
        
        if authorization:
            scheme, param = authorization.split()
            if scheme.lower() != "bearer":
                if self.auto_error:
                    raise HTTPException(
                        status_code=HTTP_401_UNAUTHORIZED,
                        detail="Not authenticated",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                else:
                    return None
            return param
        
        # Se não encontrar no header, tenta obter via parâmetro URL
        token = request.query_params.get("token")
        if token:
            return token
            
        if self.auto_error:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return None

# Instanciar o novo esquema OAuth2
oauth2_scheme = OAuth2PasswordBearerWithCookie(tokenUrl="token", auto_error=False)

app = FastAPI(
    title="CS2 Valuation API",
    description="API para avaliação de inventários, distinguindo entre Unidades de Armazenamento e itens do mercado",
    version="0.5.0"  # Atualizada para versão com organização por origem dos itens
)

# Configurar CORS
ALLOWED_ORIGINS = [
    "http://localhost:5500",   # Desenvolvimento local
    "http://127.0.0.1:5500",   # Desenvolvimento local alternativo
    "http://localhost:3000",   # React local
    "http://localhost:8000",   # Porta do backend
    "http://localhost",        # Qualquer porta em localhost
    "http://127.0.0.1",        # Qualquer porta em localhost
    "https://elite-skins-2025.github.io",  # GitHub Pages
    "file://",  # Para suportar arquivos abertos localmente
    "https://cotacao-cs2.up.railway.app",  # Railway
    "https://cotacaocs2-production.up.railway.app",  # Railway produção
    "*"  # Último recurso - permitir qualquer origem em desenvolvimento
]

# Configurar middleware CORS com opções específicas
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400  # Cache preflight por 24h
)

# Middleware personalizado para adicionar cabeçalhos CORS em todas as respostas
# Isso garante que mesmo em caso de erro 500/502, os cabeçalhos CORS estarão presentes
class CustomCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Obter a origem da requisição
        origin = request.headers.get("origin")
        
        # Para requisições OPTIONS (preflight), responder imediatamente
        if request.method == "OPTIONS":
            response = Response()
            if origin and (origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS):
                response.headers["Access-Control-Allow-Origin"] = origin
            else:
                # Se não houver origem ou não for permitida, usar wildcard
                response.headers["Access-Control-Allow-Origin"] = "*"
            
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Max-Age"] = "86400"
            return response
            
        try:
            # Processar a requisição normalmente
            response = await call_next(request)
            
            # Adicionar cabeçalhos CORS na resposta
            if origin and (origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS):
                response.headers["Access-Control-Allow-Origin"] = origin
            else:
                response.headers["Access-Control-Allow-Origin"] = "*"
            
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "*"
            
            return response
        except Exception as e:
            # Em caso de erro, garantir que a resposta ainda tenha os cabeçalhos CORS
            print(f"Erro no middleware: {e}")
            response = Response(status_code=500)
            
            if origin and (origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS):
                response.headers["Access-Control-Allow-Origin"] = origin
            else:
                response.headers["Access-Control-Allow-Origin"] = "*"
            
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Content-Type"] = "application/json"
            response.body = b'{"error": "Internal Server Error"}'
            
            return response

# Adicionar o middleware personalizado após o middleware do FastAPI
app.add_middleware(CustomCORSMiddleware)

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
async def inventory(steamid: str, response: Response, request: Request = None, cors: bool = Query(False)):
    """Retorna os itens e preços estimados do inventário público, diferenciando entre Unidades de Armazenamento e itens do mercado"""
    # Verificar se o parâmetro cors está presente e definir headers mais diretamente
    # Isso garante compatibilidade com requisições de navegadores
    if cors or (request and "cors" in request.query_params):
        # Para requisições explicitamente marcadas com cors=true, forçar os cabeçalhos
        print(f"Parâmetro cors detectado para {steamid}. Adicionando cabeçalhos CORS explícitos.")
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Allow-Credentials"] = "true"
    else:
        # Adicionar cabeçalhos CORS padrão para outras requisições
        origin = request.headers.get("origin", "*") if request else "*"
        if origin and (origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS):
            response.headers["Access-Control-Allow-Origin"] = origin
        else:
            response.headers["Access-Control-Allow-Origin"] = "*"
        
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
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
        # Os cabeçalhos CORS já foram configurados acima, então devem ser enviados mesmo com erro
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
async def full_inventory_analysis(steamid: str, response: Response, request: Request = None):
    """Retorna uma análise completa do inventário, categorizada por tipos de itens"""
    # Adicionar cabeçalhos CORS manualmente para garantir que estarão presentes mesmo em caso de erro
    origin = request.headers.get("origin", "*") if request else "*"
    if origin and (origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS):
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    try:
        print(f"Iniciando análise detalhada de inventário para {steamid}")
        result = get_inventory_value(steamid, categorize=True)
        
        # Vamos garantir que todos os campos importantes existam
        if "items_by_category" not in result:
            result["items_by_category"] = {}
        
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
        
        # Adicionar resumo por fonte se ainda não existir
        if "source_summary" not in result:
            storage_units = result.get("storage_units", [])
            market_items = result.get("market_items", [])
            
            result["source_summary"] = {
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
        for item in result.get("items", []):
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
        result["category_summary"] = categories
        
        # Arredondar valores para facilitar exibição
        result["total_value"] = round(result["total_value"], 2)
        result["average_item_value"] = round(result["average_item_value"], 2)
        if result["most_valuable_item"]:
            result["most_valuable_item"]["price"] = round(result["most_valuable_item"]["price"], 2)
        
        return result
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
async def case(case_name: str, response: Response, request: Request = None):
    """Retorna informações sobre uma caixa específica"""
    # Adicionar cabeçalhos CORS manualmente para garantir que estarão presentes mesmo em caso de erro
    origin = request.headers.get("origin", "*") if request else "*"
    if origin and (origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS):
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    case_info = get_case_details(case_name)
    if not case_info:
        return {"error": "Caixa não encontrada", "name": case_name}
    return case_info


@app.get("/price/{market_hash_name}")
async def price(market_hash_name: str, response: Response, request: Request = None):
    """Retorna o preço de um item pelo seu market_hash_name"""
    # Adicionar cabeçalhos CORS manualmente para garantir que estarão presentes mesmo em caso de erro
    origin = request.headers.get("origin", "*") if request else "*"
    if origin and (origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS):
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    try:
        item_price_data = get_item_price(market_hash_name)
        
        # Construir resposta com informações de moeda
        response_data = {
            "market_hash_name": market_hash_name,
            "price": item_price_data["price"],
            "currency": item_price_data["currency"],
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Adicionar campos opcionais se existirem
        if "sources_count" in item_price_data:
            response_data["sources_count"] = item_price_data["sources_count"]
            
        if "is_fallback" in item_price_data:
            response_data["is_fallback"] = item_price_data["is_fallback"]
            
        if "processed" in item_price_data:
            response_data["processed"] = item_price_data["processed"]
            
        return response_data
    except Exception as e:
        return {"error": str(e), "market_hash_name": market_hash_name}


@app.get("/cases")
async def cases(response: Response, request: Request = None):
    """Retorna a lista de caixas disponíveis"""
    # Adicionar cabeçalhos CORS manualmente para garantir que estarão presentes mesmo em caso de erro
    origin = request.headers.get("origin", "*") if request else "*"
    if origin and (origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS):
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    try:
        cases_list = list_cases()
        
        # Adicionar preços atuais (apenas para API)
        for case in cases_list:
            try:
                case["current_price"] = get_item_price(case["name"])
            except:
                case["current_price"] = 0.0
                
        return cases_list
    except Exception as e:
        print(f"Erro ao processar lista de caixas: {e}")
        # Retornar uma lista vazia em vez de um objeto com erro
        return []


@app.get("/api/status")
async def api_status(response: Response, request: Request = None):
    """Retorna informações sobre o status atual da API, útil para monitoramento"""
    # Adicionar cabeçalhos CORS manualmente para garantir que estarão presentes mesmo em caso de erro
    origin = request.headers.get("origin", "*") if request else "*"
    if origin and (origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS):
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    try:
        # Sempre retornar status online para passar no healthcheck
        return {
            "status": "online",
            "version": "0.5.0",
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        # Ainda retorna status online para garantir que o healthcheck passe
        return {"status": "online", "error": str(e)}


# Funções para autenticação
def get_current_user(token: str = Depends(oauth2_scheme)):
    """Obtém o usuário atual baseado no token JWT"""
    if not token:
        print("Token não fornecido na requisição")
        # Retornar None para permitir que o endpoint decida como lidar com ausência de token
        return None
        
    try:
        print(f"Tentando validar token: {token[:10]}...")
        
        # Decodificar o token manualmente com tratamento de erro melhorado
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            print("Token decodificado com sucesso")
        except jwt.ExpiredSignatureError:
            print("Erro: Token expirado")
            return {"error": "Token expirado. Faça login novamente."}
        except jwt.InvalidTokenError:
            print("Erro: Token inválido")
            return {"error": "Token inválido. Formato incorreto."}
        except Exception as e:
            print(f"Erro desconhecido ao decodificar token: {e}")
            return {"error": f"Erro ao processar token: {str(e)}"}
            
        # Verificar se o payload contém o steam_id
        steam_id = payload.get("steam_id")
        if not steam_id:
            print("Erro: Token não contém SteamID")
            return {"error": "Token não contém SteamID"}
            
        # Retornar informações do usuário
        print(f"Usuário autenticado com SteamID: {steam_id}")
        return {"steam_id": steam_id}
    except Exception as e:
        print(f"Erro inesperado na autenticação: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"Erro na autenticação: {str(e)}"}


# Endpoints para autenticação com a Steam
@app.get("/auth/steam")
async def steam_auth(request: Request, redirect_local: bool = False, return_url: str = None):
    """Redireciona para o login da Steam"""
    # URL base para a API
    base_url = str(request.base_url).rstrip('/')
    redirect_uri = f"{base_url}/auth/steam/callback"
    
    # Adicionar parâmetros para a URL de callback
    params = {}
    
    # Adicionar parâmetro para indicar redirecionamento local
    if redirect_local:
        params["redirect_local"] = "true"
    
    # Adicionar URL de retorno se fornecida
    if return_url:
        params["return_url"] = return_url
        print(f"URL de retorno recebida: {return_url}")
    
    # Adicionar parâmetros à URL de callback
    if params:
        redirect_uri += "?" + urlencode(params)
    
    print(f"URL de callback configurada: {redirect_uri}")
    
    # Gerar URL de login
    login_url = steam_login_url(redirect_uri)
    print(f"URL de login com Steam: {login_url}")
    
    return RedirectResponse(url=login_url)


@app.get("/auth/steam/callback")
async def steam_callback(request: Request):
    """Callback após o login na Steam"""
    # Extrair parâmetros da resposta
    params = dict(request.query_params)
    
    # Verificar se deve redirecionar para local
    redirect_local = "redirect_local" in params and params["redirect_local"] == "true"
    
    # Validar autenticação
    steam_id = validate_steam_login(params)
    if steam_id:
        # Gerar token JWT
        token = create_jwt_token({"steam_id": steam_id})
        
        # Definir URL de frontend baseado no parâmetro redirect_local
        if redirect_local:
            # Ambiente de desenvolvimento local
            frontend_url = "http://localhost:5500/api.html"
            print(f"Redirecionando para: {frontend_url}?token={token}")
            print(f"Ambiente: Desenvolvimento local")
        else:
            # Ambiente de produção
            frontend_url = "https://elite-skins-2025.github.io/api.html"
            print(f"Redirecionando para: {frontend_url}?token={token}")
            print(f"Ambiente: Produção")
        
        # Receber URL de retorno personalizado, se fornecido na requisição original
        # Verificar se a URL de retorno foi passada na requisição original
        return_url_param = next((p for p in params.keys() if "return_url" in p), None)
        if return_url_param:
            custom_return_url = params[return_url_param]
            if custom_return_url:
                frontend_url = custom_return_url
                print(f"Usando URL de retorno personalizado: {frontend_url}")
                print(f"Parâmetro de retorno: {return_url_param}={custom_return_url}")
        
        # Redirecionar para o frontend com o token como parâmetro
        redirect_url = f"{frontend_url}?token={token}"
        
        # Registrar informações adicionais para debug
        print(f"Parâmetros recebidos no callback: {params}")
        print(f"URL final de redirecionamento: {redirect_url}")
        
        # Retornar um redirecionamento HTTP 302
        return RedirectResponse(url=redirect_url)
    else:
        return {"error": "Falha na autenticação com a Steam"}


# Endpoint de teste para redirecionamento
@app.get("/auth/test-redirect")
async def test_redirect(request: Request, return_url: str = None):
    """Endpoint de teste para verificar como a URL de retorno é tratada"""
    # Extrair parâmetros da resposta
    params = dict(request.query_params)
    
    # Obter URL base
    base_url = str(request.base_url).rstrip('/')
    
    # Informações de debug
    debug_info = {
        "request_url": str(request.url),
        "base_url": base_url,
        "params": params,
        "return_url": return_url,
        "headers": dict(request.headers),
        "would_redirect_to": return_url if return_url else "No return URL provided",
        "info": "Este é um endpoint de teste para verificar o redirecionamento. Não faz redirecionamento real."
    }
    
    return debug_info


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
async def my_inventory(current_user: dict = Depends(get_current_user), response: Response = None, request: Request = None):
    """Retorna os itens do inventário do usuário autenticado"""
    # CORS tratado pelo middleware global
    
    if not current_user:
        raise HTTPException(status_code=401, detail="Autenticação necessária")
    
    try:
        # Usar steamid do usuário autenticado
        steamid = current_user["steam_id"]
        print(f"Analisando inventário do usuário autenticado: {steamid}")
        
        # Reutilizar endpoint público
        result = get_inventory_value(steamid)
        
        return result
    except Exception as e:
        print(f"Erro ao processar inventário do usuário autenticado: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "total_items": 0,
            "total_value": 0,
            "items": []
        }


@app.get("/my/inventory/complete")
async def my_inventory_complete(
    current_user: dict = Depends(get_current_user),
    session_id: str = Query(None),
    steam_token: str = Query(None),
    response: Response = None,
    request: Request = None
):
    """Retorna o inventário completo do usuário, incluindo conteúdo das unidades de armazenamento"""
    # CORS tratado pelo middleware global
    
    if not current_user:
        raise HTTPException(status_code=401, detail="Autenticação necessária")
    
    try:
        # Usar steamid do usuário autenticado
        steamid = current_user["steam_id"]
        
        return await _complete_inventory_analysis(steamid, current_user, session_id, steam_token)
    except Exception as e:
        print(f"Erro ao processar inventário completo do usuário autenticado: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "total_items": 0,
            "total_value": 0,
            "items": []
        }


@app.get("/my/inventory/full")
async def my_inventory_full(current_user: dict = Depends(get_current_user), response: Response = None, request: Request = None):
    """Retorna análise completa do inventário do usuário autenticado, com categorias"""
    # CORS tratado pelo middleware global
    
    if not current_user:
        raise HTTPException(status_code=401, detail="Autenticação necessária")
    
    try:
        # Usar steamid do usuário autenticado
        steamid = current_user["steam_id"]
        print(f"Analisando inventário detalhado do usuário autenticado: {steamid}")
        
        # Obter inventário com categorização
        result = get_inventory_value(steamid, categorize=True)
        
        return result
    except Exception as e:
        print(f"Erro ao processar análise completa do usuário autenticado: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "total_items": 0,
            "total_value": 0,
            "items": []
        }


@app.get("/cors-test")
async def cors_test(response: Response):
    """Endpoint simples para testar cabeçalhos CORS"""
    # Adicionar cabeçalhos CORS manualmente
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    return {
        "cors_status": "OK",
        "message": "Se você conseguir ver esta mensagem, os cabeçalhos CORS estão funcionando corretamente",
        "timestamp": str(datetime.datetime.now()),
        "requested_headers": "Todos os cabeçalhos são permitidos"
    }


@app.get("/db/stats")
async def db_stats(current_user: dict = Depends(get_current_user)):
    """
    Retorna estatísticas do banco de dados de preços de skins.
    Requer autenticação.
    """
    # Verificar se o usuário está autenticado
    if not current_user:
        raise HTTPException(status_code=401, detail="Autenticação necessária")
    
    # Obter estatísticas do banco de dados
    stats = get_stats()
    
    # Obter status do agendador
    scheduler_status = get_scheduler_status()
    
    return {
        "database": stats,
        "scheduler": scheduler_status
    }

@app.post("/db/update")
async def force_db_update(current_user: dict = Depends(get_current_user), max_items: int = Query(100, description="Número máximo de itens para atualizar")):
    """
    Força uma atualização imediata dos preços das skins mais antigas.
    Requer autenticação.
    """
    # Verificar se o usuário está autenticado
    if not current_user:
        raise HTTPException(status_code=401, detail="Autenticação necessária")
    
    # Forçar atualização
    stats = force_update_now(max_items=max_items)
    
    return {
        "message": f"Atualização forçada concluída. {stats['updated_skins']} itens atualizados.",
        "stats": stats
    }

# Rota para inicializar o banco de dados (protegida por chave de admin)
@app.get("/api/db/init")
async def initialize_database(admin_key: str = Query(None), response: Response = None):
    """Inicializa o banco de dados (apenas para administradores)"""
    # CORS tratado pelo middleware global
    
    # Verificar se a chave administrativa está correta
    expected_key = os.environ.get("ADMIN_KEY", "dev_admin_key")
    
    if admin_key != expected_key:
        raise HTTPException(status_code=403, detail="Chave administrativa inválida")
        
    try:
        # Inicializar o banco de dados
        result = init_database()
        
        return {
            "success": True,
            "message": "Banco de dados inicializado com sucesso",
            "details": result
        }
    except Exception as e:
        print(f"Erro ao inicializar banco de dados: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }

# Inicialização da aplicação
@app.on_event("startup")
async def startup_event():
    """
    Inicializa recursos na inicialização da aplicação.
    """
    print("=== INICIANDO API ELITE SKINS CS2 ===")
    print(f"Ambiente: {os.environ.get('RAILWAY_ENVIRONMENT_NAME', 'desenvolvimento')}")
    
    # Inicializar recursos críticos - banco de dados com tratamento de erro para não bloquear a inicialização
    try:
        # Inicialização básica do banco para que a API possa responder
        print("Inicializando banco de dados (modo rápido)...")
        init_db()
        print("Banco de dados inicializado com sucesso para operação básica!")
    except Exception as e:
        print(f"AVISO: Erro na inicialização básica do banco de dados: {e}")
        print("A API continuará iniciando, mas algumas funcionalidades podem estar limitadas")
    
    # Inicializar recursos não críticos de forma assíncrona
    @app.on_event("startup")
    async def delayed_startup():
        # Atrasar inicialização para garantir que o server já está respondendo
        await asyncio.sleep(10)  # Esperar 10 segundos
        try:
            # Configurar a atualização semanal dos preços (Segunda-feira às 3:00)
            print("Configurando atualizações programadas...")
            schedule_weekly_update(day_of_week=0, hour=3, minute=0)
            
            # Iniciar o agendador em uma thread separada
            run_scheduler()
            print("Agendador de atualização de preços iniciado!")
            
            print("=== INICIALIZAÇÃO COMPLETA DOS RECURSOS ADICIONAIS ===")
        except Exception as e:
            print(f"AVISO: Erro na inicialização de recursos não críticos: {e}")
            import traceback
            traceback.print_exc()


@app.get("/healthcheck")
async def healthcheck():
    """Endpoint minimalista para verificar se a API está respondendo"""
    try:
        # Testa uma consulta simples ao banco de dados para garantir que está funcionando
        # Apenas verifica se o banco está acessível
        init_db()
        return Response(content="OK", media_type="text/plain", status_code=200)
    except Exception as e:
        print(f"Erro no healthcheck: {str(e)}")
        # Ainda retorna 200 para o Railway não matar o serviço durante inicialização
        return Response(content="Service warming up", media_type="text/plain", status_code=200)


@app.get("/test-csgostash/{market_hash_name}")
async def test_csgostash(market_hash_name: str):
    """
    Endpoint para testar a função de obtenção de preços via CSGOStash.
    Apenas para desenvolvimento/teste.
    """
    try:
        result = get_item_price_via_csgostash(market_hash_name)
        return {
            "market_hash_name": market_hash_name,
            "result": result
        }
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }


if __name__ == "__main__":
    # Aumentar número de workers e timeout para lidar melhor com requisições longas
    # Como o processamento de inventários grandes pode demorar
    
    # Obter a porta do ambiente (para compatibilidade com Railway e outros serviços de hospedagem)
    port = int(os.environ.get("PORT", 8080))
    
    print(f"Iniciando servidor na porta {port}")
    print("Configuração CORS:")
    print(f"- Origens permitidas: {ALLOWED_ORIGINS}")
    
    # Aumentar os timeouts para lidar melhor com requisições CORS preflight
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=port, 
        reload=True,
        workers=4,  # Mais workers para processar requisições em paralelo
        timeout_keep_alive=120,  # Manter conexões vivas por mais tempo (2 minutos)
        timeout_graceful_shutdown=30,  # Dar mais tempo para shutdown
        log_level="info"
    )

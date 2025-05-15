"""
Arquivo simplificado para o deploy no Railway.
Este arquivo importa todos os componentes necessários para a API funcionar
e expõe a aplicação FastAPI de forma adequada para o Gunicorn.
"""

import os
import sys
import traceback

# Garantir que estamos no diretório correto
current_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_dir)

# Adicionar diretório atual ao path
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Importações explícitas para garantir que todos os módulos sejam carregados
try:
    # Importar utilitários e serviços
    from utils.config import get_api_config
    from utils.database import init_db, get_stats
    from services.steam_inventory import get_inventory_value, analyze_inventory
    from services.case_evaluator import get_case_details, list_cases
    from services.steam_market import get_item_price, get_api_status
    from auth.steam_auth import steam_login_url, validate_steam_login, create_jwt_token, verify_jwt_token
    
    # Finalmente, importar a aplicação FastAPI principal
    from main import app
    
    # Verificar os endpoints disponíveis
    routes = [{"path": route.path, "name": route.name} for route in app.routes]
    print(f"Aplicação carregada com sucesso! {len(routes)} endpoints disponíveis.")
    
    # Expor a aplicação para o Gunicorn
    application = app
    
except Exception as e:
    # Em caso de erro, criar uma aplicação básica que exibe o erro
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    
    print(f"ERRO AO INICIALIZAR APLICAÇÃO PRINCIPAL: {str(e)}")
    print(f"Traceback completo: {traceback.format_exc()}")
    
    application = FastAPI(
        title="CS2 API (MODO DE ERRO)",
        description="Erro ao inicializar a aplicação principal",
        version="error"
    )
    
    # Adicionar middleware CORS básico
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @application.get("/")
    async def root():
        return {
            "status": "error",
            "message": "Erro ao inicializar a aplicação principal",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "cwd": os.getcwd(),
            "files": os.listdir(".")
        }
    
    @application.get("/health")
    async def health():
        return {"status": "ok"}
    
    @application.get("/error-details")
    async def error_details():
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "cwd": os.getcwd(),
            "files": os.listdir("."),
            "python_path": sys.path,
            "environment": dict(os.environ)
        }

# Verificação final
if not hasattr(application, "routes"):
    print("ERRO: A aplicação não possui rotas definidas!")
else:
    print(f"Aplicação pronta para deploy com {len(application.routes)} endpoints.") 
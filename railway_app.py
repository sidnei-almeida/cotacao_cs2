"""
Arquivo simplificado para o deploy no Railway.
Este arquivo importa todos os componentes necessários para a API funcionar
e expõe a aplicação FastAPI de forma adequada para o Gunicorn.
"""

import os
import sys
import traceback
import importlib.util

# Configuração de diagnóstico
VERBOSE_DEBUG = True

def debug_print(message):
    if VERBOSE_DEBUG:
        print(f"[DEBUG] {message}")

# Garantir que estamos no diretório correto
current_dir = os.path.dirname(os.path.abspath(__file__))
debug_print(f"Diretório atual: {current_dir}")
os.chdir(current_dir)

# Adicionar diretório atual ao path
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
    debug_print(f"Adicionado ao sys.path: {current_dir}")

debug_print(f"sys.path completo: {sys.path}")
debug_print(f"Conteúdo do diretório: {os.listdir(current_dir)}")

# Método alternativo para importar o main.py diretamente
def import_main_directly():
    try:
        debug_print("Tentando importar main.py usando importlib.util...")
        main_path = os.path.join(current_dir, "main.py")
        if not os.path.exists(main_path):
            debug_print(f"ERRO: Arquivo main.py não encontrado em {main_path}")
            return None
            
        spec = importlib.util.spec_from_file_location("main", main_path)
        main_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main_module)
        
        if hasattr(main_module, "app"):
            debug_print("Aplicação importada com sucesso via importlib!")
            return main_module.app
        else:
            debug_print("Módulo main.py importado, mas não contém 'app'")
            return None
    except Exception as e:
        debug_print(f"Erro ao importar main.py diretamente: {str(e)}")
        debug_print(traceback.format_exc())
        return None

# Importações explícitas para garantir que todos os módulos sejam carregados
try:
    debug_print("Iniciando importações...")
    
    # Tentar importar dependências críticas primeiro para verificar
    try:
        debug_print("Verificando imports de utils...")
        import utils
        debug_print("utils importado")
        
        debug_print("Verificando imports de services...")
        import services
        debug_print("services importado")
        
        debug_print("Verificando imports de auth...")
        import auth
        debug_print("auth importado")
    except ImportError as e:
        debug_print(f"ERRO ao importar pacotes básicos: {str(e)}")
    
    # Tentar importar a aplicação FastAPI principal primeiro
    debug_print("Tentando importar app do main diretamente...")
    try:
        from main import app
        debug_print("Importação direta de main.py bem-sucedida!")
    except ImportError as e:
        debug_print(f"Falha na importação direta: {str(e)}")
        debug_print("Tentando método alternativo...")
        app = import_main_directly()
        
        if app is None:
            debug_print("Todos os métodos de importação falharam!")
            raise ImportError("Não foi possível importar a aplicação principal por nenhum método")
    
    # Verificar os endpoints disponíveis
    routes = [{"path": route.path, "name": route.name} for route in app.routes]
    debug_print(f"Aplicação carregada com sucesso! {len(routes)} endpoints disponíveis.")
    debug_print(f"Endpoints: {routes}")
    
    # Expor a aplicação para o Gunicorn
    application = app
    
except Exception as e:
    # Em caso de erro, criar uma aplicação básica que exibe o erro
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    
    debug_print(f"ERRO AO INICIALIZAR APLICAÇÃO PRINCIPAL: {str(e)}")
    debug_print(f"Traceback completo: {traceback.format_exc()}")
    
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
        error_details = {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "cwd": os.getcwd(),
            "files": os.listdir("."),
            "python_path": sys.path,
            "environment": {k: v for k, v in os.environ.items() if k.lower() != "password" and k.lower() != "secret"}
        }
        
        # Verificar a estrutura de pastas críticas
        for directory in ["utils", "services", "auth"]:
            if os.path.exists(directory):
                error_details[f"{directory}_files"] = os.listdir(directory)
            else:
                error_details[f"{directory}_exists"] = False
        
        return error_details

# Verificação final
if not hasattr(application, "routes"):
    debug_print("ERRO: A aplicação não possui rotas definidas!")
else:
    debug_print(f"Aplicação pronta para deploy com {len(application.routes)} endpoints.") 
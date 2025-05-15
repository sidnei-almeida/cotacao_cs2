# Arquivo para inicialização via WSGI
import os
import sys
import traceback

# Adicionar diretório atual ao path do Python
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Importar a aplicação FastAPI do main.py
try:
    print("Tentando importar app do main.py...")
    from main import app as application
    print("Importação bem-sucedida!")
    
    # Verificar os endpoints disponíveis
    routes = [{"path": route.path, "name": route.name} for route in application.routes]
    print(f"Endpoints disponíveis: {routes}")
    
except Exception as e:
    # Se falhar ao importar a aplicação principal, criar uma aplicação básica
    print(f"ERRO ao importar a aplicação principal: {str(e)}")
    print(f"Traceback completo: {traceback.format_exc()}")
    print(f"Diretório atual: {os.getcwd()}")
    print(f"Arquivos no diretório: {os.listdir('.')}")
    
    from fastapi import FastAPI
    application = FastAPI()
    
    @application.get("/")
    async def root():
        return {
            "status": "error",
            "message": "Erro ao iniciar aplicação principal",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "cwd": os.getcwd(),
            "files": os.listdir(".")
        }
    
    @application.get("/health")
    async def health():
        return {"status": "ok"}

# Para executar com Gunicorn: gunicorn wsgi:application -k uvicorn.workers.UvicornWorker 
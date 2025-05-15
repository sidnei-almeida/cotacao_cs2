# Arquivo para inicialização via WSGI
import os
import sys

# Adicionar diretório atual ao path do Python
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Importar a aplicação FastAPI do main.py
try:
    from main import app as application
except Exception as e:
    # Se falhar ao importar a aplicação principal, criar uma aplicação básica
    from fastapi import FastAPI
    application = FastAPI()
    
    @application.get("/")
    async def root():
        return {
            "status": "error",
            "message": "Erro ao iniciar aplicação principal",
            "error": str(e),
            "cwd": os.getcwd(),
            "files": os.listdir(".")
        }
    
    @application.get("/health")
    async def health():
        return {"status": "ok"}

# Para executar com Gunicorn: gunicorn wsgi:application -k uvicorn.workers.UvicornWorker 
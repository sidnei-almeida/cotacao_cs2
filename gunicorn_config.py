import os

# Obter a porta do ambiente
port = os.environ.get("PORT", "8000")

# Configurações do Gunicorn
bind = f"0.0.0.0:{port}"
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 120
errorlog = "-"  # Log para stdout
accesslog = "-"  # Log para stdout
loglevel = "info" 
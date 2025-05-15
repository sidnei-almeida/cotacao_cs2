FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Porta que o FastAPI vai usar
EXPOSE 8080

# Comando para iniciar a aplicação
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "--timeout", "120", "--keep-alive", "120", "--bind", "0.0.0.0:8080", "main:app"] 
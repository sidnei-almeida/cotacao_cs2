# CS2 Valuation API

API para avaliação de inventários de Counter-Strike 2, especialmente para análise de Unidades de Armazenamento e itens do mercado.

## Características

- Scraping exclusivo para preços de itens
- Classificação de itens por origem (Unidades de Armazenamento ou Mercado)
- Análise de inventário por categorias
- Acesso ao conteúdo das Unidades de Armazenamento (apenas para o próprio usuário autenticado)
- Autenticação via Steam OpenID

## Instalação Local

1. Clone o repositório
2. Crie um ambiente virtual: `python -m venv .venv`
3. Ative o ambiente:
   - Windows: `.venv\Scripts\activate`
   - Linux/Mac: `source .venv/bin/activate`
4. Instale as dependências: `pip install -r requirements.txt`
5. Execute a API: `python main.py`

## Deploy no Render

### Opção 1: Deploy via Dashboard

1. Crie uma conta no [Render](https://render.com/)
2. No Dashboard, clique em "New +" e selecione "Web Service"
3. Conecte seu repositório GitHub
4. Configure o serviço:
   - Nome: `cs2-valuation-api` (ou outro de sua preferência)
   - Runtime: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn -k uvicorn.workers.UvicornWorker -w 4 main:app -b 0.0.0.0:$PORT`
5. Clique em "Create Web Service"

### Opção 2: Deploy via render.yaml

1. Certifique-se de que o arquivo `render.yaml` está no repositório
2. No Dashboard do Render, clique em "New +" e selecione "Blueprint"
3. Conecte seu repositório GitHub
4. O Render detectará automaticamente o arquivo render.yaml e criará os serviços configurados

## Conexão com Frontend no GitHub Pages

Após o deploy, sua API estará disponível em uma URL como:
`https://cs2-valuation-api.onrender.com`

O frontend no GitHub Pages deve ser configurado para acessar esta URL. O CORS já está configurado para permitir solicitações de:
- `http://localhost:5500` (desenvolvimento local)
- `https://elite-skins-2025.github.io` (GitHub Pages)

## Variáveis de Ambiente

Se necessário, você pode configurar as seguintes variáveis de ambiente no Render:

- `SECRET_KEY`: Chave secreta para JWT (gerada automaticamente se não for fornecida)
- `STEAM_API_KEY`: Chave API da Steam (opcional, para funcionalidades avançadas) 
# Deploy da API no Render.com

Este guia contém instruções para fazer o deploy da API de cotação CS2 no Render.com.

## Pré-requisitos

- Conta no [Render](https://render.com/)
- Repositório Git com o código da API

## Passo a passo

1. **Login no Render**

   Acesse o dashboard do Render em [https://dashboard.render.com/](https://dashboard.render.com/) e faça login na sua conta.

2. **Criar um novo serviço Web**

   - Clique em "New" e selecione "Web Service"
   - Conecte o repositório Git com o código da API
   - Dê um nome para o serviço (recomendado: `cs2-valuation-api`)
   - Defina o Root Directory como `cotacao_cs2` (ou o diretório onde está o arquivo `main.py`)

3. **Configurar o ambiente**

   - Em "Environment", selecione "Python 3"
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn -k uvicorn.workers.UvicornWorker -w 4 --timeout 120 --keep-alive 120 main:app -b 0.0.0.0:$PORT`
   - Selecione o plano adequado para suas necessidades (o plano gratuito é suficiente para testes)

4. **Configurar variáveis de ambiente**

   No painel "Environment Variables", adicione as seguintes variáveis:

   - `JWT_SECRET_KEY`: Uma string longa e segura para assinatura dos tokens JWT
   - `PYTHON_VERSION`: `3.10.0` (ou a versão desejada)

5. **Configurações adicionais**

   - Em "Advanced", habilite "Auto-Deploy" se desejar que o Render atualize automaticamente quando houver novos commits

6. **Criar o serviço**

   Clique em "Create Web Service" e aguarde o deploy. O processo pode levar alguns minutos.

7. **Testando a API**

   Após o deploy, você poderá acessar a API através da URL fornecida pelo Render, geralmente no formato:
   `https://seu-servico.onrender.com`

   Verifique se a API está funcionando corretamente acessando:
   `https://seu-servico.onrender.com/api/status`

8. **Atualizar o frontend**

   Certifique-se de atualizar a URL da API no frontend (arquivo `api.html`):

   ```javascript
   const API_BASE_URL = isLocalhost 
                        ? 'http://localhost:8000'  // Ambiente de desenvolvimento
                        : 'https://seu-servico.onrender.com';  // Ambiente de produção
   ```

## Resolução de problemas

Se encontrar problemas durante o deploy, verifique:

1. **Logs do Render**: No dashboard do Render, acesse os logs do seu serviço para identificar erros.
2. **Configurações de CORS**: Verifique se todas as origens necessárias estão configuradas em `main.py`.
3. **Variáveis de ambiente**: Confirme se todas as variáveis de ambiente necessárias foram configuradas.
4. **Problemas de banco de dados**: Se estiver usando um banco de dados, verifique a conexão.

## Notas importantes

- **Plano Gratuito**: O plano gratuito do Render desliga o serviço após períodos de inatividade, o que pode causar lentidão na primeira requisição após um período sem uso.
- **Autenticação Steam**: Confirme se as URLs de callback para autenticação Steam estão corretamente configuradas para a URL do Render. 
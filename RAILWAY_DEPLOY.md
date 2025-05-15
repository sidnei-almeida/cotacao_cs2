# Deploy no Railway

Este guia descreve como fazer o deploy da API Elite Skins CS2 no Railway.

## Configuração no Railway

1. Crie uma conta no [Railway](https://railway.app/)
2. Inicie um novo projeto selecionando "Deploy from GitHub"
3. Autorize o Railway a acessar seu repositório e selecione o repositório do projeto
4. Na configuração inicial, defina o diretório raiz como `cotacao_cs2`
5. Adicione um serviço PostgreSQL ao seu projeto clicando em "New" e selecionando "Database" > "PostgreSQL"

## Variáveis de Ambiente

As variáveis de ambiente já estão configuradas no arquivo `railway.toml` para usar a conexão pública do PostgreSQL:

| Nome da Variável | Valor |
|------------------|-------|
| `DATABASE_URL` | `postgresql://postgres:SENHA@gondola.proxy.rlwy.net:10790/railway` |
| `DB_HOST` | `gondola.proxy.rlwy.net` |
| `DB_PORT` | `10790` |
| `DB_NAME` | `railway` |
| `DB_USER` | `postgres` |
| `DB_PASSWORD` | `SENHA` |
| `PORT` | `8080` (definido automaticamente pelo Railway) |

**Nota importante**: Estamos usando o endpoint público do PostgreSQL (`gondola.proxy.rlwy.net`) em vez do interno, pois o endpoint interno pode não resolver corretamente em todos os ambientes do Railway.

## Como implantar

1. Através da CLI do Railway (recomendado):
   ```bash
   # Instale a CLI do Railway
   npm i -g @railway/cli
   
   # Faça login
   railway login
   
   # Inicie um projeto (ou vincule-se a um existente)
   railway init
   
   # Implante (a partir da pasta cotacao_cs2)
   cd cotacao_cs2
   railway up
   ```

2. Ou através do painel do Railway (mais simples):
   - Conecte seu repositório GitHub
   - Configure o diretório `cotacao_cs2` como pasta de origem
   - Clique em "Deploy"

## Verificar Status

Após o deploy, você pode verificar se a API está funcionando acessando o endpoint:

```
https://[seu-app-railway].railway.app/api/status
```

## Resolução de Problemas

- **Erro de conexão com o banco de dados**: 
  - Verifique se o serviço PostgreSQL está ativo no Railway
  - Confirme se as credenciais estão corretas
  - Verifique se o endpoint público `gondola.proxy.rlwy.net` é acessível
  - Se a porta ou o host mudaram, atualize-os em `database.py` e `railway.toml`

- **Erro de inicialização**: 
  - Verifique os logs no painel do Railway para identificar o problema

- **CORS**: 
  - Se houver problemas de CORS, verifique se o domínio do frontend está na lista de origens permitidas no arquivo `main.py`

## Sistema de Fallback

A API possui um sistema de fallback que permite o funcionamento mesmo em caso de falha na conexão com o PostgreSQL:

1. Quando não consegue conectar ao banco de dados, utiliza armazenamento em memória
2. Os dados são sincronizados quando a conexão é restabelecida
3. Isso garante alta disponibilidade da API mesmo durante problemas temporários

## Notas

- O Railway oferece monitoramento e logs integrados para facilitar o diagnóstico de problemas
- Lembre-se que o plano gratuito do Railway tem limite de uso mensal ($5 de crédito)
- Para melhor desempenho, considere utilizar uma região próxima aos seus usuários 
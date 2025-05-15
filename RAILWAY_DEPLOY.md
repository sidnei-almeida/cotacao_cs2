# Deploy no Railway

Este guia descreve como fazer o deploy da API Elite Skins CS2 no Railway.

## Configuração no Railway

1. Crie uma conta no [Railway](https://railway.app/)
2. Inicie um novo projeto selecionando "Deploy from GitHub"
3. Autorize o Railway a acessar seu repositório e selecione o repositório do projeto
4. Na configuração inicial, defina o diretório raiz como `cotacao_cs2`

## Variáveis de Ambiente Necessárias

Configure as seguintes variáveis de ambiente no projeto Railway:

| Nome da Variável | Valor |
|------------------|-------|
| `DATABASE_URL` | `postgresql://postgres:SENHA@db.ykaatdxdvkcuryswejkm.supabase.co:5432/postgres?sslmode=prefer` |
| `DB_HOST` | `db.ykaatdxdvkcuryswejkm.supabase.co` |
| `DB_PORT` | `5432` |
| `DB_NAME` | `postgres` |
| `DB_USER` | `postgres` |
| `DB_PASSWORD` | `SENHA` |
| `PORT` | `8080` |

Substitua `SENHA` pela senha real do seu banco de dados.

## Verificar Status

Após o deploy, você pode verificar se a API está funcionando acessando o endpoint:

```
https://[seu-app-railway].railway.app/api/status
```

## Resolução de Problemas

- **Erro de conexão com o banco de dados**: Verifique se as credenciais do Supabase estão corretas e se as variáveis de ambiente foram configuradas.
- **Erro de inicialização**: Verifique os logs do Railway para identificar o problema.
- **CORS**: Se houver problemas de CORS, verifique se o domínio do frontend está na lista de origens permitidas no arquivo `main.py`.

## Notas

- O Railway oferece monitoramento e logs integrados para facilitar o diagnóstico de problemas
- Lembre-se que o plano gratuito do Railway tem limite de uso mensal ($5 de crédito)
- Para melhor desempenho, considere utilizar uma região próxima aos seus usuários 
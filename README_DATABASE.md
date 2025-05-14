# Sistema de Cache em Banco de Dados para Elite Skins API

## Visão Geral

Este sistema implementa um cache em banco de dados para preços de skins de CS2, reduzindo significativamente as requisições para APIs externas e melhorando o desempenho e a confiabilidade da aplicação.

### Principais Funcionalidades

- **Cache em SQLite**: Armazena localmente os preços das skins para evitar múltiplas requisições para a mesma skin
- **Atualização automática semanal**: Job que atualiza automaticamente os preços mais antigos do banco de dados
- **API para gerenciamento**: Endpoints para visualizar estatísticas e forçar atualizações
- **Migração para PostgreSQL**: Suporte para migrar facilmente os dados para PostgreSQL quando for feito o deploy

## Funcionamento

1. Quando um preço de skin é solicitado, o sistema:
   - Primeiro verifica o cache em memória (para consultas repetidas na mesma sessão)
   - Em seguida, consulta o banco de dados SQLite
   - Se não encontrar ou o preço estiver desatualizado, faz scraping (como antes)
   - Armazena o resultado tanto no cache em memória quanto no banco de dados

2. Um job semanal executa em background para atualizar os preços mais antigos do banco de dados, mesmo quando não há requisições ativas para essas skins.

## Estrutura do Banco de Dados

### Tabela `skin_prices`
- `id`: ID único do registro
- `market_hash_name`: Nome da skin no mercado da Steam
- `price`: Preço atual da skin
- `currency`: Código da moeda
- `app_id`: ID da aplicação na Steam
- `last_updated`: Data/hora da última atualização do preço
- `last_scraped`: Data/hora do último scraping
- `update_count`: Contador de atualizações

### Tabela `metadata`
- `key`: Chave do metadado
- `value`: Valor do metadado
- `updated_at`: Data/hora da última atualização

## Como Usar

### Gerenciamento via API

Os seguintes endpoints foram adicionados:

1. `/api/status`: Agora inclui estatísticas do banco de dados
   ```json
   {
     "status": "online",
     "components": {
       "database": {
         "total_skins": 1245,
         "recently_updated": 236,
         "average_price": 42.80
       }
     }
   }
   ```

2. `/db/stats`: Retorna estatísticas detalhadas do banco de dados (requer autenticação)
   ```json
   {
     "database": {
       "total_skins": 1245,
       "average_price": 42.80,
       "recently_updated": 236,
       "last_update": "2023-10-28T15:32:47"
     },
     "scheduler": {
       "last_update": "2023-10-25T03:00:12",
       "next_update": "2023-11-01T03:00:00"
     }
   }
   ```

3. `/db/update`: Força a atualização imediata de preços (requer autenticação)
   - Parâmetro `max_items`: Número máximo de itens para atualizar (padrão: 100)

### Migração para PostgreSQL

Quando estiver pronto para migrar do SQLite para PostgreSQL:

1. Configure a variável de ambiente `DATABASE_URL` no seu ambiente de produção no Render
2. Execute o script de migração uma vez:
   ```bash
   python utils/db_migration.py
   ```

3. Depois, atualize o arquivo `utils/database.py` para usar PostgreSQL em vez de SQLite. Um arquivo de exemplo para essa mudança será fornecido.

## Configurações

As principais configurações podem ser ajustadas:

1. **Período de Atualização:** Padrão é semanal (segunda-feira às 3h)
   - Pode ser alterado em `main.py` na função `startup_event()`

2. **Quantidade de Itens por Atualização:** Padrão é 100 skins por execução
   - Definido pela constante `UPDATE_BATCH_SIZE` em `utils/price_updater.py`

3. **Tempo de Validade do Cache:** Padrão é 7 dias
   - Pode ser alterado na função `get_skin_price()` em `utils/database.py`

## Benefícios

- **Menor uso de API:** Reduz drasticamente as requisições para APIs externas
- **Melhor performance:** Respostas mais rápidas para usuários
- **Maior confiabilidade:** Sistema funciona mesmo se a API externa estiver indisponível
- **Economia de recursos:** Menos processamento em tempo real

## Considerações Futuras

Para quando migrar para PostgreSQL:

1. O arquivo `utils/database.py` precisará ser atualizado para usar PostgreSQL
2. Você precisará configurar a variável de ambiente `DATABASE_URL` no Render
3. O agendador de atualizações (`schedule_weekly_update`) precisará ser adaptado para funcionar com múltiplas instâncias

## Resolução de Problemas

### Banco de dados não está sendo atualizado
- Verifique se o agendador está em execução: `/db/stats` deve mostrar a próxima atualização
- Você pode forçar uma atualização imediata com `/db/update`

### Erros durante a migração para PostgreSQL
- Verifique se a variável `DATABASE_URL` está correta
- Confirme que o PostgreSQL está acessível a partir do seu servidor
- Verifique se há erros no formato de data/hora ao migrar dados 
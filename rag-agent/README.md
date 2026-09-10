# RAG Agent

Agente RAG com VPN forçada, LLM dinâmico via OpenRouter, e banco de dados híbrido
(vetorial + full-text + grafo de entidades) para busca que cruza informação entre
documentos diferentes.

## Setup local (sem VPN — teste de esqueleto)

Use `docker/docker-compose-local.yml` para testar schema, ingestão, fila e retrieval
sem depender de credenciais WireGuard reais (o Gluetun do compose de produção nunca
fica saudável sem VPN de verdade, e travaria a subida dos outros serviços).

1. Copie `.env.example` para `.env` e preencha pelo menos `OPENROUTER_API_KEY` e
   `API_AUTH_TOKEN`. `DATABASE_URL`/`REDIS_URL` já apontam para os nomes de serviço
   corretos (`postgres`, `redis`) por padrão.
2. `docker compose -f docker/docker-compose-local.yml up -d --build`
3. `curl http://localhost:8000/health` — deve responder com `postgres: ok` (o
   `vpn_status` fica `unknown`/`degraded` neste modo, o que é esperado sem Gluetun).

## Deploy real na VPS (com VPN)

1. Copie `.env.example` para `.env` e preencha os valores (mínimo: `POSTGRES_PASSWORD`
   fora do `.env` — exporte como variável de ambiente antes do compose, `OPENROUTER_API_KEY`,
   `API_AUTH_TOKEN`).
2. Instale dependências: `pip install -r requirements.txt`.
3. Suba a infraestrutura:
   ```
   docker compose -f docker/docker-compose-vps-vpn.yml config   # valida sintaxe
   docker compose -f docker/docker-compose-vps-vpn.yml up -d --build
   ```
4. Confirme saúde: `curl http://localhost:8000/health` (local, sem VPN real — kill switch
   só é validável de fato após deploy na VPS com credenciais WireGuard reais).

## Endpoints

- `POST /ingest?source_path=<caminho relativo>` — multipart, campo `file`. Enfileira o
  documento e responde imediatamente `{"document_id": ..., "status": "enfileirado"}`.
- `GET /ingest/status/{document_id}` — consulta progresso: `enfileirado` → `processando`
  → `concluido` | `erro_processamento`. Usado pelo uploader local para confirmar antes
  de mover o arquivo.
- `POST /query` — `{"question": "...", "model": "...", "top_k": 8}`. `model` deve estar
  em `GET /models`.
- `GET /models` — lista modelos permitidos (editável em `config/models.yaml`).
- `GET /health` — status agregado (Postgres + kill switch VPN).

Todos os endpoints exceto `/models` e `/health` exigem `Authorization: Bearer <API_AUTH_TOKEN>`.

## Testes manuais

```
python test_ingest.py docs/exemplo1.pdf docs/exemplo2.pdf
python test_query.py "O que os dois documentos têm em comum?"
python test_graph.py "Entidade de Teste"
```

## Backup e restore do Postgres

O serviço `postgres_backup` roda `pg_dump` diariamente para `../backups/`, mantendo
7 dias de histórico. Para restaurar:

```
docker compose -f docker/docker-compose-vps-vpn.yml exec -T postgres \
    pg_restore -U rag_user -d rag_db --clean --if-exists < backups/rag_db_YYYYMMDD_HHMMSS.dump
```

**Teste o restore antes de precisar dele de verdade** — rode o processo acima contra um
banco de teste e confirme que os dados voltam íntegros.

## Troubleshooting

- **Worker não processa nada**: confirme que `rag_worker` está rodando (`docker compose ps`)
  e que o Redis está saudável (`docker compose logs redis`).
- **`/ingest` retorna 401**: token no header não bate com `API_AUTH_TOKEN` do `.env`.
- **PDF cai sempre no OCR (lento)**: `pymupdf_parser.has_extractable_text` amostra as
  5 primeiras páginas — se o documento for majoritariamente imagem nas primeiras páginas
  mas tiver texto depois, ajuste `min_chars` ou o número de páginas amostradas.
- **Caminho de arquivo > 260 caracteres no Windows**: `app/ingestion/router.py` já aplica
  o prefixo `\\?\` automaticamente — se ainda houver erro, confirme que o caminho passado
  é absoluto antes de chegar no router.
- **Apache AGE não carrega**: cada sessão que roda Cypher precisa de `LOAD 'age';` e
  `SET search_path = ag_catalog, "$user", public;` antes da consulta — já embutido em
  `app/db.py::run_cypher`.

## Segurança — limitações conhecidas desta fase

- Proteção **apenas em trânsito** (HTTPS + token). Dados ficam em texto plano no Postgres
  (sem criptografia em repouso). Ver plano de implementação para detalhes e itens de
  produção adiados deliberadamente (rate limiting, rotação de credenciais, auditoria de
  acesso, migração de schema versionada, observabilidade, controle de custo de LLM).

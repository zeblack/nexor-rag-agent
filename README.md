# Nexor RAG Agent

Agente RAG (Retrieval-Augmented Generation) com três diferenciais técnicos:

1. **Tráfego de saída forçado por VPN** (Gluetun + WireGuard) com kill switch
   verificado ativamente pela própria aplicação.
2. **Escolha dinâmica de LLM via OpenRouter**, validada contra uma lista de
   modelos permitidos configurável.
3. **Banco de dados híbrido** que cruza informação entre documentos diferentes:
   busca vetorial (pgvector) + full-text (tsvector nativo do Postgres) + grafo
   de entidades e relações (Apache AGE), permitindo perguntas que atravessam
   múltiplos documentos.

📖 **[Documentação técnica completa](DOCUMENTACAO.md)** — explica em detalhe
como cada componente funciona: ingestão de documentos, banco de dados híbrido,
busca e resposta, VPN, escolha de LLM, e o uploader local.

## Estrutura do repositório

- [`rag-agent/`](rag-agent/) — serviço principal: API FastAPI, orquestrador de
  parsers com fallback em cascata, fila de ingestão assíncrona (Celery/Redis),
  embeddings (BGE-M3), reranking (BGE-Reranker) e busca híbrida. Veja o
  [README do rag-agent](rag-agent/README.md) para setup local e deploy.
- [`uploader/`](uploader/) — script cliente local que varre uma pasta
  recursivamente, enfileira os arquivos encontrados e envia um a um para o
  endpoint `/ingest` do agente, com retomada automática em caso de
  interrupção e confirmação de que cada documento foi de fato processado
  (upload → parsing → chunking → embedding) antes de marcá-lo como concluído.

## Como os dois componentes se conectam

O `uploader` é um cliente HTTP do `rag-agent` — ele não acessa o banco de
dados diretamente. Isso permite rodar o agente em um servidor (ex: VPS) e o
uploader na máquina onde os documentos originais estão, sem precisar mover a
base de arquivos inteira antes de começar a indexação.

## Segurança e segredos

Nenhum segredo real (chaves de API, credenciais de VPN, senhas de banco) está
neste repositório. Cada componente traz um `.env.example` com placeholders —
copie para `.env` localmente e preencha com valores reais antes de rodar.
`rag-agent/docker/extract_wireguard_env.py` ajuda a converter um perfil
WireGuard (`.conf`) em variáveis de ambiente prontas para o `.env`, sem que o
arquivo `.conf` original precise entrar no repositório.

## Licença

MIT — veja [LICENSE](LICENSE).

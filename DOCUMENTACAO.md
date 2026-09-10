# Documentação Técnica — Nexor RAG Agent

Este documento explica em detalhe o que o agente faz, como cada peça funciona,
e por que as decisões de arquitetura foram tomadas dessa forma. Para instruções
rápidas de setup, veja o [README](README.md) e o [README do rag-agent](rag-agent/README.md).

## Índice

1. [Visão geral](#visão-geral)
2. [Arquitetura em alto nível](#arquitetura-em-alto-nível)
3. [Componente 1 — Ingestão de documentos](#componente-1--ingestão-de-documentos)
4. [Componente 2 — Banco de dados híbrido](#componente-2--banco-de-dados-híbrido)
5. [Componente 3 — Busca e resposta (`/query`)](#componente-3--busca-e-resposta-query)
6. [Componente 4 — VPN forçada e kill switch](#componente-4--vpn-forçada-e-kill-switch)
7. [Componente 5 — Escolha dinâmica de LLM](#componente-5--escolha-dinâmica-de-llm)
8. [Componente 6 — Uploader local](#componente-6--uploader-local)
9. [Referência de endpoints da API](#referência-de-endpoints-da-api)
10. [Segurança e limitações conhecidas](#segurança-e-limitações-conhecidas)
11. [Como rodar (resumo)](#como-rodar-resumo)

---

## Visão geral

O Nexor RAG Agent é um sistema de **Retrieval-Augmented Generation (RAG)**:
você envia documentos (PDF, DOCX, planilhas, e-mails, apresentações...), o
sistema os indexa, e depois você faz perguntas em linguagem natural que são
respondidas com base no conteúdo desses documentos — citando de onde veio
cada trecho usado na resposta.

O que diferencia este projeto de um RAG "padrão de tutorial" é:

- **Não é só busca por similaridade semântica.** O banco combina três formas
  de busca (vetorial, texto e grafo de entidades) para responder perguntas
  que exigem cruzar informação entre documentos diferentes.
- **Todo tráfego de rede que sai do agente é forçado a passar por VPN**, com
  verificação ativa de que isso está de fato acontecendo.
- **O modelo de linguagem usado para gerar a resposta é escolhido em tempo de
  execução**, por parâmetro de API, não fixo no código.

---

## Arquitetura em alto nível

```
                    ┌─────────────┐
   uploader   ───►  │   FastAPI   │  ───►  fila (Celery + Redis)
  (cliente)         │  (rag_agent)│              │
                    └─────────────┘              ▼
                          │                ┌─────────────┐
                          │  /query        │  rag_worker │
                          ▼                │  (processa) │
                    ┌─────────────┐        └─────────────┘
                    │  Postgres   │◄───────────────┘
                    │ (pgvector + │   grava chunks,
                    │  full-text +│   embeddings,
                    │  Apache AGE)│   entidades no grafo
                    └─────────────┘
                          ▲
                          │
                    ┌─────────────┐
                    │ OpenRouter  │  (LLM escolhido por parâmetro)
                    └─────────────┘

  Todo o tráfego de rag_agent e rag_worker passa por Gluetun (VPN WireGuard)
  no deploy de produção.
```

Quatro processos rodam em containers separados (via Docker Compose):

| Serviço | Papel |
|---|---|
| `postgres` | Banco de dados híbrido (pgvector + full-text + Apache AGE) |
| `redis` | Broker da fila de tarefas assíncronas |
| `rag_agent` | API HTTP (FastAPI) — recebe uploads e perguntas |
| `rag_worker` | Processa a fila: parsing, chunking, embedding, extração de entidades |

Por que separar `rag_agent` de `rag_worker`? Porque processar um documento
(especialmente PDFs escaneados que exigem OCR) pode levar de segundos a
minutos. Se isso rodasse dentro do próprio request HTTP, o cliente ficaria
esperando uma conexão aberta esse tempo todo, e a API não conseguiria atender
outros pedidos em paralelo. Com a fila, o `POST /ingest` responde
imediatamente (`"enfileirado"`), e o `rag_worker` processa em segundo plano,
podendo até rodar em múltiplas instâncias para paralelizar o processamento de
vários documentos ao mesmo tempo.

---

## Componente 1 — Ingestão de documentos

### O fluxo completo de um documento

1. Um cliente (o `uploader`, ou qualquer script HTTP) faz `POST /ingest` com
   o arquivo e seu caminho de origem.
2. A API calcula o hash SHA-256 do conteúdo bruto do arquivo e monta o
   `document_id` como `<hash>:<caminho>`. Isso significa que **dois arquivos
   com o mesmo nome mas conteúdo diferente nunca são confundidos**, e um
   arquivo idêntico reenviado (mesmo hash) não gera duplicata no banco
   (constraint `UNIQUE` em `content_hash`).
3. O arquivo é salvo num volume Docker compartilhado (`/tmp/rag_ingest`) —
   único jeito de `rag_agent` (que recebeu o upload) e `rag_worker` (que vai
   processar) acessarem o mesmo arquivo, já que rodam em containers
   diferentes.
4. Um registro é criado na tabela `documents` com status `enfileirado`, e uma
   tarefa é publicada na fila Celery.
5. A API responde imediatamente: `{"document_id": "...", "status": "enfileirado"}`.
6. O `rag_worker`, quando disponível, pega a tarefa da fila e executa, em
   ordem: **parsing → extração de metadata → chunking → embedding → gravação
   no banco**.
7. Assim que os chunks e embeddings estão gravados, o status vira `concluido`
   — o documento já está pronto para ser encontrado em buscas.
8. **Depois disso**, de forma independente (sem bloquear o passo anterior), o
   worker dispara uma segunda tarefa: extração de entidades para o grafo
   (explicada na seção do banco de dados).

O cliente consulta o progresso via `GET /ingest/status/{document_id}`, que
retorna `enfileirado` → `processando` → `concluido` (ou `erro_processamento`
se algo falhar, com a mensagem de erro anexada).

### Por que um "orquestrador de parsers" em vez de uma biblioteca só

Documentos do mundo real vêm em dezenas de formatos, e cada formato tem uma
forma certa (e várias erradas) de extrair o texto. `app/ingestion/router.py`
decide qual parser usar **pela extensão do arquivo**, com fallback em
cascata quando o parser principal falha:

| Extensão | Estratégia |
|---|---|
| `.pdf` | Testa primeiro se o PDF tem texto extraível (PyMuPDF). Se tiver, extrai direto — rápido e barato. Se não tiver (é um scan/imagem), usa Docling com OCR — mais lento, mas o único jeito de "ler" uma imagem. |
| `.docx` | python-docx (parágrafos e tabelas) |
| `.xlsx` / `.xlsb` | openpyxl / pyxlsb (todas as abas, célula por célula) |
| `.odt` / `.ods` | odfpy (equivalentes OpenDocument) |
| `.pptx` | python-pptx (texto de cada slide) |
| `.msg` | extract-msg (e-mails do Outlook: remetente, assunto, corpo) |
| `.pages` / `.numbers` | Extrai o preview de texto embutido no pacote (iWork da Apple não tem parser Python maduro para o formato binário completo) |
| `.one` / `.onetoc2` | Não suportado nesta versão — levanta erro explícito em vez de falhar silenciosamente ou produzir lixo (formato binário do OneNote sem biblioteca de extração confiável disponível) |

Arquivos que claramente não são documentos (`.exe`, `.dll`, `Thumbs.db`,
`.DS_Store`, `.bpm`) são **ignorados por política**, não tratados como erro —
o router reconhece esses casos e pula, deixando o log claro sobre o motivo.

Todo caminho de arquivo passa pelo prefixo de caminho estendido do Windows
(`\\?\`) internamente, porque em árvores de arquivo reais é comum encontrar
caminhos com mais de 260 caracteres (limite clássico do Windows) — sem esse
prefixo, a leitura falharia silenciosamente.

### Extração de metadata: caminho da pasta antes de LLM

Muita informação útil sobre um documento já está na estrutura de pastas onde
ele foi salvo — por exemplo, uma árvore organizada por ano/mês/responsável.
`app/ingestion/path_metadata.py` usa expressões regulares para extrair esses
campos (ano, mês, nome de pessoa) **direto do caminho relativo**, sem gastar
nenhuma chamada de LLM.

Só os campos que essa extração determinística não conseguiu preencher caem
para `app/ingestion/metadata_extractor.py`, que chama o LLM (via OpenRouter)
para tentar extrair do **conteúdo** do documento (ex: um identificador ou
título mencionado no texto). Essa ordem de prioridade (determinístico
primeiro, LLM como último recurso) economiza custo e é mais confiável — regex
sobre uma pasta bem nomeada é 100% precisa; pedir para um LLM "adivinhar" um
campo é probabilístico.

---

## Componente 2 — Banco de dados híbrido

Este é o diferencial central do projeto. Um RAG "padrão" guarda só
`documento → pedaços de texto (chunks) → vetor de embedding de cada pedaço`,
e busca por similaridade de vetor. Isso funciona bem para "encontre o trecho
mais parecido com a pergunta", mas não responde bem a perguntas que exigem
**cruzar informação entre documentos diferentes** (ex: "o que esses dois
documentos têm em comum?").

Para isso, o schema (`rag-agent/init-db/`) combina três camadas:

### Camada 1 — Busca vetorial (semântica)

Tabela `chunks`, coluna `embedding VECTOR(1024)` (extensão `pgvector`). Cada
chunk de texto é transformado num vetor numérico pelo modelo de embedding
**BGE-M3** (explicado abaixo). Perguntas parecidas em *significado* — mesmo
usando palavras diferentes — ficam matematicamente próximas nesse espaço
vetorial. Índice `ivfflat` acelera a busca por similaridade de cosseno.

### Camada 2 — Busca full-text (lexical)

Coluna `content_tsv TSVECTOR`, gerada automaticamente pelo próprio Postgres a
partir do texto de cada chunk (`to_tsvector('portuguese', content)`), com
índice GIN. Captura casos que a busca vetorial pode não priorizar bem — por
exemplo, um código ou termo técnico exato que precisa bater literalmente.

### Camada 3 — Grafo de entidades (Apache AGE)

Essa é a camada que permite cruzar documentos. Depois que um documento é
processado, uma tarefa assíncrona (`entity_extraction_task.py`) pede ao LLM
para identificar entidades (pessoas, organizações, valores, datas...) e
relações entre elas, mencionadas no texto de cada chunk. Essas entidades
viram vértices num grafo (consultável via Cypher, a linguagem de consulta de
grafos), usando `MERGE` — ou seja, se a mesma entidade (ex: o nome de uma
organização) aparecer em dois documentos diferentes, ela vira **um só
vértice**, com arestas para os dois documentos. É esse compartilhamento de
vértice que permite responder "quais documentos mencionam X" atravessando
qualquer número de arquivos.

### Como as três camadas se combinam numa busca (`/query`)

1. A pergunta do usuário é transformada em embedding e comparada contra os
   embeddings de todos os chunks (busca vetorial) — resultado: top-20
   candidatos por similaridade semântica.
2. Em paralelo, a mesma pergunta é usada numa busca full-text nativa do
   Postgres — resultado: top-20 candidatos por correspondência lexical.
3. Os dois rankings são combinados por **Reciprocal Rank Fusion (RRF)** — uma
   técnica que soma `1 / (k + posição no ranking)` de cada lista, favorecendo
   itens que aparecem bem posicionados em qualquer uma das duas buscas, sem
   precisar normalizar escalas de score diferentes (cosseno vs. `ts_rank`).
4. Para os chunks que sobraram depois da fusão, o grafo é consultado: quais
   entidades aparecem nesses chunks, e em que **outros** documentos essas
   mesmas entidades também aparecem. Isso enriquece a resposta com contexto
   de documentos que a busca por texto/vetor sozinha talvez não tivesse
   priorizado.
5. Por fim, um modelo de **reranking** (BGE-Reranker) — mais lento, porém
   mais preciso que embeddings simples, porque compara a pergunta e cada
   chunk par a par — corta a lista para os 5 melhores candidatos finais.
6. Esses 5 chunks viram o contexto enviado ao LLM escolhido, que gera a
   resposta final. A resposta da API inclui as citações (de qual documento e
   trecho veio cada informação usada) e a lista de documentos que
   contribuíram via cruzamento do grafo — dando transparência sobre
   *como* a resposta foi montada.

### Links de similaridade cruzada (`chunk_links`)

Além do grafo de entidades, existe uma tabela auxiliar `chunk_links` que
guarda pares de chunks (de documentos diferentes) cuja similaridade de
embedding passa de um limiar configurável. É uma segunda forma, mais barata
computacionalmente, de sinalizar "esses dois trechos, de documentos
diferentes, provavelmente falam da mesma coisa" — útil para expansões de
contexto futuras sem depender só da extração de entidade via LLM.

---

## Componente 3 — Busca e resposta (`/query`)

Já coberto em detalhe na seção anterior. Resumo do contrato da API:

```
POST /query
{
  "question": "sua pergunta em linguagem natural",
  "model": "id-do-modelo-em-/models",
  "top_k": 8
}
```

Retorna:
```
{
  "answer": "resposta gerada pelo LLM com base no contexto recuperado",
  "citations": [{"document_id": "...", "source_path": "...", "chunk_index": 0, "snippet": "..."}],
  "graph_documents": ["document_id_de_outro_documento_relacionado", ...]
}
```

---

## Componente 4 — VPN forçada e kill switch

No deploy de produção (`docker-compose-vps-vpn.yml`), os containers
`rag_agent` e `rag_worker` rodam com `network_mode: "service:gluetun"` — ou
seja, **todo o tráfego de rede desses dois containers passa fisicamente pela
interface de rede do container Gluetun**, que mantém um túnel WireGuard
ativo. Não é uma configuração de proxy que o código da aplicação escolhe
usar ou não — é uma restrição de rede a nível de container, então mesmo que
uma biblioteca de terceiro tente fazer uma chamada direta, ela sai pela VPN
de qualquer forma.

Isso sozinho não garante que, se a VPN cair, o tráfego simplesmente volte a
sair sem proteção (esse cenário existe em configurações mal feitas de VPN
"opcional"). Por isso existe uma segunda camada: `app/vpn_healthcheck.py`
roda uma rotina assíncrona, dentro da própria aplicação, que periodicamente
consulta um serviço externo de IP (`api.ipify.org`) e compara com o IP
esperado da VPN. Se divergir, o estado interno vira `degraded`, refletido em
`GET /health` — dando visibilidade ativa e verificável de que a VPN está
funcionando de fato, não só configurada.

---

## Componente 5 — Escolha dinâmica de LLM

Em vez de fixar um modelo de linguagem no código, o agente se conecta ao
**OpenRouter** — um agregador que dá acesso a dezenas de modelos de diferentes
fornecedores através de uma única API. A lista de modelos que o `/query`
aceita é configurável em `rag-agent/config/models.yaml`, e o cliente escolhe
qual usar **a cada chamada**, passando o parâmetro `model`. A API valida esse
valor contra a lista permitida antes de gastar qualquer chamada externa —
uma tentativa de usar um modelo não cadastrado retorna erro `400` imediato.

Essa escolha de design significa que trocar, adicionar, ou remover modelos
disponíveis é uma mudança de configuração (editar o YAML), não uma mudança de
código.

---

## Componente 6 — Uploader local

O `uploader/` é um programa cliente separado, pensado para rodar na máquina
onde os documentos originais estão (que pode ser diferente de onde o agente
está hospedado). Ele resolve o problema prático de "tenho uma pasta com
milhares de arquivos em subpastas, quero indexar tudo, e não posso perder o
progresso se a conexão cair no meio":

1. **`scanner.py`** varre a pasta escolhida recursivamente, calcula o hash de
   cada arquivo elegível (aplicando a mesma lista de exclusões do agente:
   ignora `Thumbs.db`, `.DS_Store`, executáveis etc.), e registra cada
   arquivo numa fila local (SQLite).
2. **`uploader.py`** processa a fila **um arquivo por vez** (não em paralelo,
   por design — dá controle e previsibilidade sobre a carga no servidor):
   envia o arquivo via `POST /ingest`, e então faz *polling* em
   `GET /ingest/status/{document_id}` até receber `concluido`.
3. Só depois da confirmação de que o documento foi de fato processado
   (não só "aceito pela API"), **`file_mover.py`** move o arquivo físico da
   pasta original para uma subpasta espelho `up-ok/` — dando uma segunda
   confirmação visual, independente do banco de dados: o que já saiu da
   pasta original está garantidamente indexado.
4. Se o processo for interrompido (rede cair, usuário fechar o terminal), o
   estado fica salvo na fila SQLite. Rodar de novo retoma exatamente de onde
   parou — nunca reprocessa o que já foi confirmado, nunca perde o que
   estava pendente.
5. Cada evento (envio, resposta, cada tentativa de polling, confirmação,
   erro) é gravado em log estruturado (JSON Lines), e um comando
   `python main.py --report` mostra a qualquer momento quantos arquivos estão
   em cada estado, com destaque para falhas permanentes que precisam de
   atenção manual.

---

## Referência de endpoints da API

| Método e caminho | Autenticação | Descrição |
|---|---|---|
| `POST /ingest?source_path=<caminho>` | Sim | Envia um arquivo (multipart, campo `file`). Responde imediatamente com `document_id` e status `enfileirado`. |
| `GET /ingest/status/{document_id}` | Sim | Consulta o progresso do processamento de um documento. |
| `POST /query` | Sim | Faz uma pergunta contra a base indexada. Corpo: `question`, `model`, `top_k`. |
| `GET /models` | Não | Lista os modelos de LLM permitidos e qual é o padrão. |
| `GET /health` | Não | Status agregado: conexão com Postgres e estado do kill switch de VPN. |

Autenticação é via header `Authorization: Bearer <API_AUTH_TOKEN>`, mesmo
valor configurado no `.env` do servidor.

---

## Segurança e limitações conhecidas

Este é um esqueleto funcional, não um sistema pronto para produção com dado
sensível real sem revisão adicional. Itens explicitamente fora do escopo
atual, documentados para não serem esquecidos:

- **Proteção só em trânsito.** HTTPS (a ser configurado na frente da API, via
  reverse proxy) e o token de autenticação protegem o dado *durante o envio*.
  Uma vez gravado no Postgres, o conteúdo dos documentos e os metadados
  extraídos ficam em **texto plano** — sem criptografia em repouso.
- **Sem rate limiting** — nada impede hoje que um cliente autenticado envie
  requisições em volume descontrolado.
- **Sem rotação de credenciais** automatizada (token de API, senha de banco).
- **Sem log de auditoria** de quem consultou o quê via `/query`.
- **Sem controle de custo/orçamento** sobre o uso do LLM — cada `/query`
  consome créditos do OpenRouter sem limite configurado.
- **Migração de schema** é feita hoje por scripts SQL fixos de inicialização
  (`init-db/`), não por uma ferramenta de migração versionada — evoluir o
  schema em produção exigiria disciplina manual.
- **Sem ambiente de staging** separado — hoje existem só "local" (sem VPN,
  para desenvolvimento) e "produção" (com VPN, para a VPS).

Nenhum desses pontos impede o uso do agente como esqueleto de estudo,
laboratório, ou prova de conceito. Todos importam antes de operar com dado
real sensível em ambiente de produção continuada.

---

## Como rodar (resumo)

Para instruções completas, veja o [README do rag-agent](rag-agent/README.md).
Resumo rápido para testar localmente, sem VPN:

```bash
cd rag-agent
cp .env.example .env
# edite .env: preencha OPENROUTER_API_KEY e API_AUTH_TOKEN
docker compose -f docker/docker-compose-local.yml up -d --build
curl http://localhost:8000/health
```

Para enviar documentos de uma pasta local:

```bash
cd uploader
cp .env.example .env
# edite .env: aponte API_URL para o endereço do agente e preencha API_TOKEN
pip install -r requirements.txt
python main.py --root "/caminho/para/sua/pasta" --allow-insecure-local
```

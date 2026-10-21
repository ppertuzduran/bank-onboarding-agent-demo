# Orquestador Agéntico — Onboarding Digital Bancario (PoC)

PoC de un orquestador que coordina sub-agentes especializados durante el onboarding digital de un cliente bancario. Fase 1: implementación local. Fase 2: despliegue en AWS.

## Arquitectura

Ver `docs/architecture.md`.

El orquestador es Python puro (máquina de estados) que coordina:
- `identity_agent` — llama a `verify_identity` (mock).
- `risk_agent` — llama a `check_risk_lists` (mock).
- `documentation_agent` — RAG sobre documentos de política bancaria cifrados.
- `response_agent` — stub determinístico que arma el mensaje final al cliente con plantillas.

Las decisiones de aptitud son **deterministas** (umbrales), no las toma un LLM, para mitigar prompt injection.

## Puesta en marcha local

### 1. Entorno

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   | Unix: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Generar FERNET_KEY y pegarla en .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Documentos sintéticos → cifrado → índice

```bash
python -m scripts.generate_synthetic_docs
python -m scripts.encrypt_documents
python -m scripts.build_index
```

### 3. Evaluación hit@k

```bash
python -m scripts.evaluate_hitk
```

Reporta hit@1, hit@3, hit@5 sobre `eval/test_questions.json`.

### 4. Levantar el API + interfaz

```bash
uvicorn app.main:app --reload --port 8000
```

- Interfaz: http://localhost:8000/
- Swagger: http://localhost:8000/docs
- Endpoint: `POST /api/v1/onboarding/start`

### 5. Tests

```bash
pytest -q
```

## Decisiones de diseño

| Área | Elección | Razón |
|---|---|---|
| Orquestación | Lógica Python (máquina de estados) | Simplicidad para demo; sin dependencia de framework agéntico. |
| LLM Fase Local | Stub determinístico + plantillas | Cuenta AWS sin cuota en Bedrock; reproducible y sin coste. |
| Embeddings Local | `paraphrase-multilingual-MiniLM-L12-v2` | Soporta español, instalación directa, offline. |
| Vector store | ChromaDB persistente | Metadata filtering nativo; migración conceptual simple a OpenSearch. |
| Cifrado local | Fernet (AES-128-CBC + HMAC) | Estándar, stdlib `cryptography`; migrar a S3 + SSE-KMS en Fase 2. |
| Estado | dict en memoria + snapshot SQLite | Demo; auditoría básica sin dependencias extra. |

## Mapeo Fase Local → Fase AWS

| Local | AWS (Fase 2) |
|---|---|
| Fernet local | S3 + SSE-KMS |
| ChromaDB | OpenSearch Serverless |
| sentence-transformers | Bedrock Titan Embeddings V2 |
| Stub determinístico | Bedrock Claude Haiku / Nova |
| SQLite | DynamoDB |
| uvicorn local | Lambda + API Gateway o ECS Fargate |

## Estructura

```
app/
  main.py                # FastAPI
  config.py              # Settings
  schemas.py             # Pydantic
  orchestrator.py        # Máquina de estados
  state.py               # Sesiones + SQLite
  security.py            # Fernet + sanitización
  agents/                # 4 sub-agentes
  tools/                 # 3 tools mockeadas
  rag/                   # chunker + embedder + retriever
scripts/                 # generate_synthetic_docs, encrypt, build_index, evaluate_hitk
static/index.html        # Interfaz mínima
eval/test_questions.json # 15 preguntas para hit@k
tests/                   # pytest
docs/architecture.md
```

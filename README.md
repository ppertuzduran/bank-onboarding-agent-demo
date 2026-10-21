# Orquestador Agéntico — Onboarding Digital Bancario (PoC)

PoC de un orquestador que coordina sub-agentes especializados durante el onboarding digital de un cliente bancario. Diseñado con estándares de seguridad y calidad de producción.

- **Fase 1 (implementada):** stack local completo con cifrado at-rest, API Key auth, rate limiting, security headers, audit logging estructurado, RFC 7807 errors y CI.
- **Fase 2 (planificada):** despliegue AWS (Bedrock Titan V2, S3+KMS, pgvector/OpenSearch, DynamoDB, App Runner).

Ver [`docs/architecture.md`](docs/architecture.md) para el diagrama y [`SECURITY.md`](SECURITY.md) para el modelo de amenazas.

## Arquitectura (resumen)

- **Orquestador:** máquina de estados Python determinista. Las decisiones de aptitud **no las toma un LLM** — se derivan de reglas (umbral de confianza + nivel de riesgo), mitigando prompt injection.
- **Sub-agentes:** `IdentityAgent`, `RiskAgent`, `DocumentationAgent` (RAG), `ResponseAgent` (plantillas en Fase Local; Bedrock en Fase AWS). Todos heredan `BaseAgent` ABC.
- **Tools mock (stdlib):** `IdentityVerifier`, `RiskListChecker`, `DocumentationPreparer`.
- **RAG:** chunking por sección markdown, contextual embeddings (document + section embebidos en el texto), ChromaDB persistente, filtros por producto.
- **Cifrado:** Fernet para documentos originales (nunca escritos en claro durante el indexado).
- **Estado:** `SessionStore` thread-safe (dict + snapshot SQLite).

## Seguridad y calidad

| Área | Implementación |
|---|---|
| **AuthN** | API Key (`X-API-Key`) con `secrets.compare_digest` (constant-time). |
| **AuthZ** | Dependency `require_api_key` en cada endpoint `/api/`. |
| **Rate limiting** | Token-bucket in-memory por IP o por key, 30 req/min configurable. |
| **Headers de seguridad** | HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, Cache-Control no-store para `/api/`. |
| **CORS** | Lista explícita de orígenes, nada de `*`. |
| **Validación de input** | Pydantic v2 + whitelists (`Product` enum, regex para nombre/documento). |
| **Errores** | RFC 7807 `application/problem+json`, sin stack traces hacia el cliente. |
| **Logging** | JSON estructurado con `request_id`, PII redactada (document_id, email). |
| **Audit** | `AuditLogger` tipado con eventos (`onboarding.started/completed/escalated`, `auth.failure`, etc.). |
| **Request tracing** | `X-Request-ID` propagado (acepta del cliente si es válido, genera uuid4 si no). |
| **Cifrado at-rest** | Fernet local → S3 + SSE-KMS en Fase AWS. |
| **Secretos** | `.env` fuera de git; `gitleaks` en CI. |
| **CI** | Ruff (lint), mypy (types), pytest (unit), bandit + pip-audit (seguridad). |
| **Container** | Dockerfile multi-stage, usuario no-root (uid 10001), HEALTHCHECK. |
| **Readiness** | `/readyz` verifica Chroma dir, SQLite y presencia de Fernet key. |

## Puesta en marcha local

### 1. Entorno

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   | Unix: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Generar FERNET_KEY y pegarla en .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# (opcional) definir API_KEY en .env para forzar auth incluso en LOCAL
```

### 2. Documentos sintéticos → cifrado → índice

```bash
python -m scripts.generate_synthetic_docs
python -m scripts.encrypt_documents
python -m scripts.build_index         # imprime modelo + dimensión del vector
```

### 3. Evaluación hit@k

```bash
python -m scripts.evaluate_hitk       # reporta hit@1, hit@3, hit@5
```

### 4. Levantar el API

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- UI: http://127.0.0.1:8000/
- Swagger: http://127.0.0.1:8000/docs
- Liveness: http://127.0.0.1:8000/healthz
- Readiness: http://127.0.0.1:8000/readyz
- Endpoint: `POST /api/v1/onboarding/start` (header `X-API-Key` si `API_KEY` está configurada)

### 5. Tests y calidad

```bash
pytest -q
ruff check app tests scripts
mypy app
bandit -r app -lll
```

### 6. Container

```bash
docker build -t onboarding-orchestrator:0.2.0 .
docker run --rm -p 8000:8000 --env-file .env onboarding-orchestrator:0.2.0
```

## Request de ejemplo

```bash
curl -X POST http://127.0.0.1:8000/api/v1/onboarding/start \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"prospect_name":"Juan Perez","document_id":"1712345678","product":"cuenta_ahorros"}'
```

## Mapeo Fase Local → Fase AWS

| Local | AWS (Fase 2) |
|---|---|
| Fernet | S3 + SSE-KMS (CMK dedicada) |
| ChromaDB | pgvector en Aurora Serverless v2 (o OpenSearch si el presupuesto lo permite) |
| sentence-transformers | Bedrock Titan Embeddings V2 (1024-dim) |
| Stub + plantillas | Bedrock Claude Haiku / Nova |
| SQLite | DynamoDB on-demand |
| uvicorn | App Runner (contenedor) o Lambda + API Gateway |
| IAM user (deploy) | IAM user con MFA. Runtime usa IAM role asumido por App Runner/Lambda. |
| Secretos en `.env` | Secrets Manager + rotación |
| Logs JSON stdout | CloudWatch Logs → Firehose → S3 (retención larga) + Athena |

## Decisiones de diseño

| Decisión | Rationale |
|---|---|
| Orquestación por lógica Python (no LangGraph) | Simplicidad PoC; menos superficie para introducir bugs/injection. |
| Decisiones por reglas, no por LLM | Mitiga prompt injection de forma estructural. |
| Contextual embeddings (document+section en el texto) | Mejora hit@k sin reranking adicional. |
| Chunking por sección markdown | Alineado con la estructura de las políticas bancarias (párrafos cortos con títulos). |
| Rate limiting in-memory | Suficiente para PoC. En producción multi-réplica, migrar a Redis. |
| API Key compartido | Suficiente para PoC. En producción, OAuth2/OIDC con JWT por cliente. |

## Estructura

```
app/
  main.py            # FastAPI + lifespan + middleware stack
  config.py          # Pydantic Settings
  schemas.py         # Request, Result, enums, outputs tools
  orchestrator.py    # Máquina de estados determinista
  auth.py            # APIKeyAuth (constant-time compare)
  middleware.py      # SecurityHeaders, RequestID, RateLimit (token bucket)
  errors.py          # RFC 7807 handlers
  audit.py           # LoggingBootstrap + AuditLogger JSON
  security.py        # EncryptionService (Fernet), PIIRedactor
  state.py           # SessionStore thread-safe
  agents/            # BaseAgent + 4 sub-agentes
  tools/             # 3 tools mock (stdlib)
  rag/               # SectionChunker, EmbeddingProvider ABC, ChromaRetriever
scripts/             # generate, encrypt, build_index, evaluate_hitk
static/index.html    # UI vanilla
eval/                # 16 preguntas para hit@k
tests/               # unit + integration
docs/architecture.md
SECURITY.md
Dockerfile
pyproject.toml       # ruff + mypy + pytest config
.github/workflows/ci.yml
```

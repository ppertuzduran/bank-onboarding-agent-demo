# Arquitectura — Orquestador Agéntico de Onboarding

## Diagrama general (Fase Local)

```
                           ┌─────────────────────┐
                           │  index.html (form)  │
                           └──────────┬──────────┘
                                      │  POST /api/v1/onboarding/start
                                      │  {prospect_name, document_id, product}
                                      ▼
            ┌──────────────────────────────────────────────────┐
            │                FastAPI (app.main)                │
            │   - validación Pydantic                          │
            │   - sanitización (app.security)                  │
            └──────────────────────┬───────────────────────────┘
                                   │
                                   ▼
            ┌──────────────────────────────────────────────────┐
            │          Orquestador (app.orchestrator)          │
            │   Máquina de estados determinista:               │
            │   INIT → IDENTITY → RISK → DOCS → RESPONSE       │
            │                     ↓ (si falla)                 │
            │                 ESCALATED                        │
            │   - lee/escribe estado en app.state              │
            │   - decisiones por reglas (NO por LLM)           │
            └───┬─────────────┬────────────┬────────────┬──────┘
                │             │            │            │
                ▼             ▼            ▼            ▼
          ┌─────────┐   ┌─────────┐  ┌──────────┐  ┌──────────┐
          │identity │   │  risk   │  │   docs   │  │ response │
          │ _agent  │   │ _agent  │  │  _agent  │  │  _agent  │
          └────┬────┘   └────┬────┘  └────┬─────┘  └────┬─────┘
               │             │            │             │
               ▼             ▼            ▼             ▼
       ┌──────────────┐┌────────────┐┌─────────┐ ┌─────────────┐
       │ verify_      ││ check_risk ││ RAG     │ │ plantillas  │
       │  identity    ││ _lists     ││ pipeline│ │ determinist.│
       │ (mock)       ││ (mock)     │└────┬────┘ └─────────────┘
       └──────────────┘└────────────┘     │
                                          ▼
                              ┌───────────────────────┐
                              │  app.rag.retriever    │
                              │  - ChromaDB (persist) │
                              │  - top-k por sección  │
                              └───────────┬───────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │ data/encrypted/*.enc  │  ← Fernet AES-128
                              │ data/synthetic_docs/  │     (originales
                              │                       │      cifrados at-rest)
                              └───────────────────────┘

   Estado conversacional:  dict en memoria + snapshot en SQLite (data/state.sqlite)
```

## Flujo del orquestador

```
                    ┌─────────┐
                    │  INIT   │ (recibe payload, crea session_id)
                    └────┬────┘
                         ▼
                    ┌──────────┐
                    │ IDENTITY │  verify_identity(document_id)
                    └────┬─────┘
                         │
             confidence ≥ 0.8 ∧ verified==True
                         │
                    ┌────▼────┐             confidence < 0.8
                    │   RISK  │ ─────────────────────────────┐
                    └────┬────┘                              │
                         │                                   │
                    risk ∈ {low, medium}                     │
                         │               risk == high        │
                    ┌────▼────┐  ─────────────────────────┐  │
                    │  DOCS   │ (RAG)                     │  │
                    └────┬────┘                           │  │
                         │                                │  │
                    ┌────▼─────┐                          │  │
                    │ RESPONSE │ ◄── requisitos documentales│  │
                    └────┬─────┘                          │  │
                         │                                ▼  ▼
                    ┌────▼─────┐                       ┌──────────────┐
                    │ COMPLETED│                       │  ESCALATED   │
                    └──────────┘                       │ + propuesta  │
                                                       │ de resolución│
                                                       └──────────────┘
```

## Componentes

### Orquestador (`app/orchestrator.py`)
Función `run_onboarding(payload) -> OnboardingResult` que ejecuta la máquina de estados. Mantiene en el estado:
- `session_id` (uuid4)
- `payload` (datos sanitizados)
- `steps[]` (trazas de cada agente)
- `status` (IN_PROGRESS | COMPLETED | ESCALATED)
- `decision` (APPROVED | REJECTED | ESCALATED)
- `message_to_client`
- `required_documents[]`
- `policy_snippets[]` (chunks RAG citados)

### Sub-agentes (`app/agents/*.py`)
Cada agente es una función `run(state) -> AgentOutput` que:
1. Lee del estado lo que necesita.
2. Invoca su tool (o pipeline RAG).
3. Devuelve un dict con `agent`, `output`, `requires_escalation`, `reason`.

### Tools (`app/tools/*.py`)
Mocks implementados **solo con librerías estándar** (`random`, `hashlib`, `uuid`). Deterministas por `document_id` para tests reproducibles.

### RAG (`app/rag/`)
- `chunker.py` — chunking por sección (título/subtítulo markdown).
- `embedder.py` — sentence-transformers multilingüe.
- `retriever.py` — ChromaDB persistente con filtros por `product`/`category` en metadata.

### Seguridad (`app/security.py`)
- Fernet para cifrar/descifrar documentos originales.
- Sanitización de inputs: regex para `document_id` (dígitos, longitud), `prospect_name` (letras/espacios), `product` (whitelist).
- Logger que redacta PII.

## Mitigaciones de riesgo (resumen)

| Riesgo | Mitigación en el diseño |
|---|---|
| Prompt injection vía campos del cliente | Decisiones por reglas, no por LLM. Validación y sanitización en el borde. |
| Leak de PII en logs | Logger con filtro de redacción. |
| Alucinación del RAG | Umbral de similitud + política "no inventar": si no hay chunks relevantes, respuesta explícita de "información no disponible". |
| Documentos en claro en disco | Fernet at-rest; descifrado solo en memoria durante el indexado. |
| Credenciales AWS filtradas | `.env` fuera de git; `boto3` lee de perfil/env; nunca hardcoded. |

## Mapeo Fase Local → Fase AWS

| Componente local | AWS |
|---|---|
| Fernet local | S3 + SSE-KMS (bucket cifrado con CMK dedicada) |
| ChromaDB | OpenSearch Serverless (colección vectorial) |
| sentence-transformers | Bedrock Titan Embeddings V2 |
| Stub determinístico | Bedrock Claude Haiku / Nova |
| SQLite | DynamoDB |
| uvicorn | Lambda + API Gateway (o ECS Fargate si latencia frío importa) |
| IAM | IAM user `onboarding-poc` con política mínima (invoke model + GetObject específico + OpenSearch query) |

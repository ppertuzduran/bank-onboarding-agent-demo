# Política de Seguridad

## Reporte de vulnerabilidades

Si descubres una vulnerabilidad en este proyecto, **no abras un issue público**.
Envía un correo con los detalles y pasos de reproducción al mantenedor del repositorio.
Nos comprometemos a responder en un plazo de 72 horas y publicar un parche
antes de divulgar los detalles.

## Mitigaciones implementadas (resumen)

| Vector | Mitigación |
|---|---|
| **Prompt injection** | Las decisiones de aptitud se toman por **reglas deterministas**, no por LLM. El contenido textual del cliente no modula la decisión. |
| **PII en logs** | Logger JSON con redacción regex de `document_id` y correos antes de emitir. |
| **Documentos sensibles at-rest** | Cifrado **Fernet (AES-128-CBC + HMAC-SHA256)**. En Fase AWS: S3 + SSE-KMS con CMK dedicada. |
| **Credenciales filtradas** | `.env` fuera de git; `boto3` lee de perfiles/roles; nunca hardcoded. `gitleaks` corre en CI. |
| **Autenticación** | API Key en header `X-API-Key`, comparación en tiempo constante (`secrets.compare_digest`). |
| **Abuso / DoS** | Rate limiting token-bucket por IP o por API key, con `Retry-After` en 429. |
| **Clickjacking** | `X-Frame-Options: DENY` + `Content-Security-Policy: frame-ancestors 'none'`. |
| **MIME sniffing** | `X-Content-Type-Options: nosniff`. |
| **XSS** | CSP estricta (sin `unsafe-eval`, orígenes limitados). |
| **CORS mal configurado** | Lista explícita de orígenes permitidos; nada de `*`. |
| **Caché de respuestas sensibles** | `Cache-Control: no-store` + `Pragma: no-cache` en `/api/`. |
| **TLS downgrade** | `Strict-Transport-Security` en producción. |
| **Information disclosure en errores** | Respuestas RFC 7807 sin stack traces hacia el cliente. |
| **Alucinaciones del RAG** | Umbral de similitud + política "si no hay chunks relevantes, no inventar". |
| **Vulnerabilidades en dependencias** | `pip-audit` y `bandit` en CI. |

## Alineación con estándares

- **OWASP API Security Top 10 (2023)** — autenticación, authorization-at-endpoint, rate limiting, input validation, excessive data exposure.
- **OWASP ASVS v4.0** — niveles 1 y 2 (logging, cifrado at-rest, validación).
- **ISO/IEC 27001** — controles A.8 (gestión de activos: datos cifrados) y A.14 (desarrollo seguro).
- **PCI-DSS** (relevante en banca) — req. 3 (cifrado), 10 (audit trails), 7 (least privilege).

## Modelo de amenazas (resumen)

**Activos a proteger:** documentación bancaria interna, PII del cliente,
decisiones de aptitud, logs de auditoría.

**Actores:**
- Cliente final que envía su payload (no confiable).
- Atacante externo con acceso al API (requiere API key).
- Operador interno con acceso al host (requiere IAM role / permisos específicos).

**Supuestos:**
- TLS termina en un reverse proxy en producción (API Gateway, ALB, CloudFront).
- Los secretos vienen de Secrets Manager / Parameter Store en entornos superiores.
- Los documentos en claro **nunca** se escriben a disco por el pipeline de indexado.

**Deuda conocida (PoC):**
- Un único API key compartido; para producción, usar OAuth2/OIDC con JWT por cliente.
- Rate limiting in-memory — no soporta múltiples réplicas; migrar a Redis.
- SQLite para estado — reemplazar por DynamoDB en Fase AWS.

---
type: lesson
domain: jarvis
source: production
severity: high
component: security
status: verified
source_type: JARVIS_INTERNAL
confidence: high
tags:
  - jarvis
  - lesson
  - security
  - secrets
  - sanitization
prerequisites:
  - "[[Credential Sanitization and Secret Masking]]"
related:
  - "[[How to Sanitize Secrets Before Logging or Ingestion]]"
  - "[[Structured Logging and Distributed Trace Context]]"
used_by:
  - "[[JARVIS Security Sandbox and Policy Engine]]"
failure_modes:
  - "[[Threat Modeling for Autonomous Coding Agents]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: JARVIS Incident Report - Incident INC-2026-08-15
    type: JARVIS_INTERNAL
    url: internal://incidents/INC-2026-08-15
---

# ðŸ“ Lesson - Accidental Secret Leaks in Telemetry Broadcast

## 1. Failure
Durante uma missÃ£o de teste de integraÃ§Ã£o com a API do GitHub, o agente capturou uma saÃ­da de erro do Git contendo a URL de clone autenticada com Personal Access Token (`https://ghp_xxxx@github.com/...`). O `ConnectionManager` fez o broadcast da mensagem JSON bruta para o canal WebSocket de telemetria sem sanitizaÃ§Ã£o, expondo o token em tempo real na interface do utilizador e no arquivo de log do cliente.

---

## 2. Root Cause
1. **Falta de SanitizaÃ§Ã£o no Pipeline de Broadcast**: O middleware WebSocket confiava que as mensagens geradas pelas ferramentas jÃ¡ vinham higienizadas pelo agente, enquanto o agente assumia que o logger cuidaria da redaÃ§Ã£o.
2. **AusÃªncia de Filtro de Entropia / Regex na SaÃ­da de Comandos**: A ferramenta de execuÃ§Ã£o em terminal devolvia `stdout` e `stderr` brutos diretamente ao payload de telemetria.

---

## 3. Why Existing Protection Failed
O arquivo `.gitignore` protegia o `.env` de ser commitado no Git, mas nÃ£o existia nenhum filtro de interceptaÃ§Ã£o ativa no canal de telemetria WebSocket do FastAPI.

---

## 4. Corrective Action
1. **Middleware de SanitizaÃ§Ã£o ObrigatÃ³rio**: Criado o filtro `mask_secrets_in_text` (ver [[Credential Sanitization and Secret Masking]]) integrado diretamente no mÃ©todo `ConnectionManager.broadcast` e no formatador global do `logging`.
2. **HigienizaÃ§Ã£o de Remotes do Git**: Comandos Git agora utilizam `git config credential.helper` ou headers HTTP para autenticaÃ§Ã£o em vez de incluir tokens em texto claro nas URLs dos remotes.

---

## 5. Generalizable Principle
> *SanitizaÃ§Ã£o de segredos deve ser aplicada como um invariante de fronteira de saÃ­da (Exit Barrier) em todos os canais de telemetria, logs e sockets.*

---

## 6. Related Concepts
- [[Credential Sanitization and Secret Masking]]
- [[How to Sanitize Secrets Before Logging or Ingestion]]
- [[FastAPI and WebSocket Lifecycle Management]]
- [[Structured Logging and Distributed Trace Context]]

---

## 7. Tests Added
- `tests/test_secret_sanitization.py::test_websocket_broadcast_masks_github_pat`
- `tests/test_secret_sanitization.py::test_log_formatter_masks_api_keys`

## Query Relevance
Incidente de vazamento de segredos em telemetria websocket postmortem.


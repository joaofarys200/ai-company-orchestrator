---
type: index
domain: general
difficulty: intermediate
tags:
  - runbooks
  - operational-guides
  - troubleshooting
  - jarvis-agents
  - disaster-recovery
  - moc
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
---

# 🛠️ Operational Runbooks & Troubleshooting Index

Este MOC consolida todos os 20 runbooks práticos e procedimentos operacionais ("How-to") distribuídos pelos subdomínios de `08 - Runbooks/`.

---

## 🤖 08 - Runbooks/AI
- [[How to Handle Malformed Model Output]] — Parsing resiliente e auto-reparo de JSONs truncados ou inválidos emitidos por LLMs.
- [[How to Detect and Break Agent Infinite Loops]] — Detecção algorítmica de repetições estéreis e circuit breaking para agentes.
- [[Runbook - How to Recover from RHO Rule Explosion and Saturated Context]] — Poda estrutural e compactação de reflexões no prompt.

## 💻 08 - Runbooks/Coding
- [[How to Safely Validate and Apply Code Patches]] — Pipeline de verificação de sintaxe, linting e testes antes da escrita em disco.
- [[How to Diagnose Python Import and Module Resolution Failures]] — Resolução de problemas de `sys.path`, namespaces e dependências circulares.
- [[How to Safely Rollback Failed Code Changes]] — Procedimento de emergência para reversão atómica de alterações no workspace.

## ⚙️ 08 - Runbooks/Backend
- [[How to Diagnose and Resolve SQLite Database Locked Errors]] — Desbloqueio de banco de dados, ajuste de pragmas WAL e timeouts.
- [[Runbook - How to Recover from Corrupted SQLite Databases]] — Restauração de banco corrompido com utilitário `.recover`.
- [[Runbook - How to Resolve Stale Distributed Locks and Fencing Collisions]] — Resolução de locks obsoletos e colisões de fencing.
- [[How to Recover Interrupted Background Workers]] — Checkpointing e reinício seguro de tarefas de background interrompidas.

## 🌐 08 - Runbooks/Computer Use
- [[How to Detect and Fix Stale Element and Navigation Race Conditions]] — Tratamento de atrasos de hidratação e promessas de navegação no Playwright.
- [[How to Detect Failed Playwright Deployments]] — Diagnóstico de tela branca e erros não tratados de console no navegador.

## 🛡️ 08 - Runbooks/Security
- [[How to Validate Webhook Cryptographic Signatures]] — Validação de integridade HMAC com proteção contra timing attacks.
- [[How to Sanitize Secrets Before Logging or Ingestion]] — Filtro e expressões regulares de redação de credenciais sensíveis.
- [[Runbook - How to Detect and Mitigate Sandbox Escape Attempts]] — Resposta a incidentes de violação de path jail e contenção de processos.

## 🚀 08 - Runbooks/DevOps
- [[How to Triage and Fix Broken CI-CD Pipelines]] — Protocolo de diagnóstico de falhas em runners de integração contínua.
- [[How to Implement Circuit Breakers for Flaky External APIs]] — Implementação de circuit breaker em clientes HTTP assíncronos.
- [[Runbook - How to Recover from Worker Thrashing and CPU Throttling]] — Resolução de sobrecarga de CPU e eliminação de processos órfãos.

## 📈 08 - Runbooks/Business
- [[How to Validate Product Ideas with Low-Cost Experiments]] — Protocolo de validação de hipóteses de mercado com smoke tests.
- [[How to Calculate Net Revenue Retention and Unit Margins]] — Fórmulas contábeis para auditoria de NRR e margens brutas unitárias.

---

## 🔗 Raiz de Navegação
- [[00 - Knowledge Index]] — Índice mestre do cofre.

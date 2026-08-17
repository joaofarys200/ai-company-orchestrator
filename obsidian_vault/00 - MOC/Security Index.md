---
type: index
domain: security
difficulty: intermediate
tags:
  - security
  - devsecops
  - sandboxing
  - cryptography
  - zero-trust
  - wasm
  - privacy
  - moc
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
---

# 🛡️ Security & Sandboxing Knowledge Index

Este MOC estabelece os princípios de segurança ofensiva/defensiva, proteção de credenciais, sandboxing com namespaces/WASM, privacidade diferencial, mitigação de replay attacks e modelagem de ameaças.

---

## 🔐 Authentication, Nonces & Signatures
- [[HMAC Signature Verification for Webhooks]] — Validação criptográfica de integridade de eventos e prevenção de timing attacks.
- [[Replay Attack Prevention with Nonce and Timestamp Windows]] — Prevenção de repetição de webhooks com janelas temporais e nonces.
- [[Comparison - HMAC Signatures vs Asymmetric Public-Key Signatures]] — Comparativo entre HMAC simétrico e chaves públicas Ed25519.

## 🔑 Cryptography & Networking
- [[TCP Handshake and BBR Congestion Control]] — Estabelecimento seguro de sessões TCP e controle de congestionamento ótimo.
- [[Tratado_Completo_de_Ciberseguranca_Redes_e_DevSecOps]] — Monografia sobre redes TCP/IP, criptografia e DevSecOps.

## 🙈 Secrets Management, Entropy & Privacy
- [[Credential Sanitization and Secret Masking]] — Detecção de tokens via expressões regulares e substituição preventiva.
- [[Shannon Entropy and Heuristic Secret Scanners]] — Detecção matemática de segredos de alta entropia sem prefixos conhecidos.
- [[Differential Privacy and Privacy Budgets in Agent Telemetry]] — Garantias matemáticas $(\epsilon, \delta)$ e mecanismo de Laplace para métricas.

## 🧱 Sandboxing, WASM & Zero Trust
- [[Zero Trust Architecture and Microsegmentation]] — Princípios NIST SP 800-207 e redução de blast radius.
- [[Defensive Sandboxing and Linux Namespaces]] — As 7 dimensões de isolamento por namespaces do kernel e cgroups.
- [[Least-Privilege Process Sandboxing and Execution Jail]] — Isolamento de subprocessos, chroot virtual e limites de CPU/memória.
- [[WASM Sandboxing and Capability-Based Security]] — Memória linear isolada, inicialização sub-milissegundo e modelo WASI.
- [[Comparison - Docker Container vs Linux Namespaces vs WASM Isolation]] — Comparativo estrutural entre containers, namespaces e WASM.
- [[Seguranca_Defensiva_DevSecOps_e_Sandboxing]] — Monografia sobre defesa em profundidade e execução segura no JARVIS.

## 🌐 Web Security & Prompt Injection
- [[SSRF Defense in Agentic Fetchers]] — Mitigação de Server-Side Request Forgery contra IPs locais e metadata endpoints de cloud.
- [[Indirect Prompt Injection via Web Pages]] — Proteção contra comandos maliciosos embutidos em HTML/CSS externo.

## 🛡️ Agent Security & Threat Modeling
- [[Threat Modeling for Autonomous Coding Agents]] — Metodologia STRIDE aplicada a pipelines de desenvolvimento agêntico.

---

## 🛠️ Runbooks Relacionados em 08 - Runbooks/Security
- [[How to Validate Webhook Cryptographic Signatures]] — Implementação à prova de timing attacks com `hmac.compare_digest`.
- [[How to Sanitize Secrets Before Logging or Ingestion]] — Filtro de redação de credenciais em pipelines de telemetria.
- [[Runbook - How to Detect and Mitigate Sandbox Escape Attempts]] — Resposta a incidentes de violação de path jail e SSRF.

## 📝 Lições de Produção em 09 - JARVIS/Lessons
- [[Lesson - Accidental Secret Leaks in Telemetry Broadcast]] — Fuga de Personal Access Token do GitHub pelo WebSocket.
- [[Lesson - Bounded Autonomy Escape in Subprocess Invocation]] — Evasão de path jail por encadeamento de comandos no shell.

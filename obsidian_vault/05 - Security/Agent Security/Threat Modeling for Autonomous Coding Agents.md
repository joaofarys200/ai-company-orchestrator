---
type: concept
domain: security
difficulty: advanced
tags:
  - security
  - threat-modeling
  - stride
  - coding-agents
  - devsecops
status: verified
---

# 🛡️ Threat Modeling for Autonomous Coding Agents

## 1. O Modelo de Ameaças STRIDE Aplicado a Agentes de IA
A metodologia **STRIDE** (Microsoft) categoriza as ameaças contra os fluxos de trabalho de agentes autónomos de desenvolvimento:

| Categoria STRIDE | Ameaça Específica em Agentes de IA | Mitigação no JARVIS OS |
|---|---|---|
| **Spoofing (Falsificação)** | Atacante forja mensagens de webhook ou impersona o utilizador no WebSocket | [[HMAC Signature Verification for Webhooks]] e JWTs persistentes |
| **Tampering (Adulteração)** | Injeção de código malicioso via repositórios clonados ou indirect prompt injection | [[Least-Privilege Process Sandboxing and Execution Jail]] e validação AST |
| **Repudiation (Repúdio)** | Agente executa ação destrutiva sem rastreabilidade de auditoria | [[Structured Logging and Distributed Trace Context]] e logs de auditoria imutáveis |
| **Information Disclosure (Vazamento)** | Credenciais do `.env` impressas em logs de erro ou enviadas no prompt | [[Credential Sanitization and Secret Masking]] |
| **Denial of Service (DoS)** | Model loops ou fork bombs em subprocessos consumindo 100% da CPU/Tokens | [[Agent Loop Detection and Circuit Breaker]] e limites de recursos |
| **Elevation of Privilege (Elevação)** | Agente escapa da sandbox e obtém acesso de administrador no host | Execução com utilizador sem privilégios e path jail restrito |

---

## 2. Superfície de Ataque do Pipeline Agêntico

```
[ Entradas Não Confiáveis ]
- Prompts de Utilizador
- Repositórios Git Clonados
- Páginas Web (Playwright)
- Webhooks Externos
          |
          v
+-----------------------------+
|  Filtro de Entrada / WAF    |  <--- Deteção de Injeções e Regex Sanitizer
+--------------+--------------+
               |
               v
+-----------------------------+
|  Model Harness / LLM Core   |  <--- Token Budgets e Circuit Breakers
+--------------+--------------+
               |
               v
+-----------------------------+
|  Sandboxed Tool Execution   |  <--- Path Jail, Sem Shell=True, Timeouts
+-----------------------------+
```

---

## 3. Matriz de Risco e Severidade

1. **Risco Crítico**: Execução remota de comandos no host (RCE) via `subprocess.run(shell=True)`.
2. **Risco Alto**: Extração de tokens de API via SSRF ou logs públicos.
3. **Risco Médio**: Flakiness ou loop infinito de chamadas a APIs pagas gerando custos.

---

## 4. Related Concepts
- [[Least-Privilege Process Sandboxing and Execution Jail]]
- [[Prompt Injection Defense in Autonomous Agents]]
- [[SSRF Defense in Agentic Fetchers]]
- [[Seguranca_Defensiva_DevSecOps_e_Sandboxing]]

---

## 5. Sources
- *Microsoft STRIDE Threat Modeling Methodology*: https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats
- *OWASP Top 10 for LLMs - LLM06: Excessive Agency & LLM08: Vector and Embedding Weaknesses*

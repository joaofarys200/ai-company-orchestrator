---
type: runbook
domain: security
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - runbook
  - security
  - sandbox-escape
  - path-jail
  - incident-response
prerequisites:
  - "[[Least-Privilege Process Sandboxing and Execution Jail]]"
  - "[[Defensive Sandboxing and Linux Namespaces]]"
related:
  - "[[Zero Trust Architecture and Microsegmentation]]"
  - "[[eBPF Syscall Tracing and Sandbox Process Auditing]]"
used_by:
  - "[[JARVIS Security Sandbox and Policy Engine]]"
failure_modes:
  - "[[Lesson - Bounded Autonomy Escape in Subprocess Invocation]]"
implementation:
  - "[[JARVIS Security Sandbox and Policy Engine]]"
sources:
  - title: JARVIS Security Incident Response Protocol
    type: JARVIS_INTERNAL
    url: internal://workspace_policy.py
---

# 🛠️ï¸ Runbook - How to Detect and Mitigate Sandbox Escape Attempts

## 1. Symptoms
- Alerta de segurança crítico `POLICY_VIOLATION_BLOCKED` no log de telemetria.
- Tentativa de execução de comandos contendo strings como `..`, `/etc/`, `C:\Windows`, `format`, `rm -rf /` ou `curl` direcionado a IPs privados (SSRF).

---

## 2. Preconditions
- O processo do agente está em execução dentro da sandbox.

---

## 3. Diagnosis
1. Verificar a stacktrace e o payload exato rejeitado por `workspace_policy.py`.
2. Identificar se a tentativa partiu de um prompt injetado indiretamente de uma página web externa lida pelo agente.

---

## 4. Commands / Queries
```bash
# Inspecionar logs de violações de segurança no banco de dados
sqlite3 database.db "SELECT * FROM telemetry_logs WHERE category = 'POLICY_VIOLATION' ORDER BY timestamp DESC LIMIT 10;"
```

---

## 5. Decision Tree
```
[ Violação de Path Jail ou Comando Perigoso? ]
                     |
                     v
       [ Matar Processo Imediatamente com SIGKILL ]
                     |
                     v
       [ Congelar Missão em SECURITY_HALTED ]
                     |
                     v
       [ Isolar Contexto de Dados Externos ]
```

---

## 6. Recovery
1. Encerrar imediatamente a árvore de processos do agente infrator.
2. Reverter o workspace para o último commit seguro usando `git reset --hard HEAD`.
3. Sanitizar o buffer de contexto removendo o fragmento de dados externos que originou a injeção.

---

## 7. Verification
Executar teste de contenção de caminho com `tests/test_sandbox_policy.py` para comprovar que o jail permanece intransponível.

---

## 8. Rollback
Se a sandbox tiver sofrido alterações indevidas, restaurar o diretório `workspace/` a partir do backup atÃ´mico.

---

## 9. Prevention
Preservar a proibição estrita de `shell=True` e aplicar delimitação estrita em dados externos (ver [[ADR-010 - Untrusted External Data Isolation via Boundary Delimiters]]).

---

## 10. Evidence
- Entrada no log de auditoria com timestamp, hash do comando rejeitado e PID neutralizado.


## Query Relevance
Como detectar e mitigar tentativas de escape de sandbox e violação de path jail.


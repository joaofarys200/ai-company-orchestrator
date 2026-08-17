---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
difficulty: advanced
tags:
  - jarvis
  - security
  - policy-manager
  - path-jail
  - permissions
prerequisites:
  - "[[Least-Privilege Process Sandboxing and Execution Jail]]"
  - "[[Zero Trust Architecture and Microsegmentation]]"
related:
  - "[[JARVIS Security Sandbox and Policy Engine]]"
  - "[[Defensive Sandboxing and Linux Namespaces]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Lesson - Bounded Autonomy Escape in Subprocess Invocation]]"
implementation:
  - "[[JARVIS Security Sandbox and Policy Engine]]"
sources:
  - title: JARVIS Codebase - workspace_policy.py and sandbox.py
    type: JARVIS_INTERNAL
    url: internal://workspace_policy.py
---

# 🛡️ JARVIS PermissionPolicyManager and Workspace Policy

## 1. Purpose
O `PermissionPolicyManager` e o módulo `workspace_policy.py` governam todas as permissões de acesso ao sistema de ficheiros, rede e execução de processos no JARVIS OS, garantindo isolamento estrito (*Path Jail*) contra operações perigosas.

---

## 2. Responsibilities
- Validar se qualquer caminho de leitura ou gravação reside dentro da raiz do projeto (`workspace/`).
- Bloquear operações de Path Traversal (`..`, links simbólicos maliciosos, caminhos absolutos no anfitrião).
- Interceptar comandos de terminal perigosos (`rm -rf /`, `format`, modificações de registo do SO).
- Desativar a execução de interpretadores com `shell=True`.

---

## 3. Inputs & Outputs
- **Inputs**: Caminhos de ficheiros alvo, listas de argumentos de comandos de terminal.
- **Outputs**: Autorização binária (`True` / `PermissionError`), caminhos canônicos normalizados.

---

## 4. State Management & Invariants
- `os.path.commonpath([real_jail, real_target]) == real_jail` é um invariante obrigatório em todas as operações de I/O em disco.

---

## 5. Dependencies
- [`workspace_policy.py`](file:///c:/Users/joaor/Desktop/JarvisOS/workspace_policy.py)
- [`sandbox.py`](file:///c:/Users/joaor/Desktop/JarvisOS/sandbox.py)

---

## 6. Failure Modes & Recovery
- **Failure**: Tentativa de evasão de sandbox via caminhos relativos complexos.
- **Recovery**: Rejeição imediata, interrupção do subprocesso e registo do evento de segurança em log.

---

## 7. Security Boundaries
- Representa a primeira e mais rígida barreira defensiva do sistema operacional JARVIS.

---

## 8. Evidence Produced & Tests
- **Evidence**: Registos em `telemetry_logs` com categoria `POLICY_VIOLATION_BLOCKED`.
- **Tests**: `tests/test_sandbox_policy.py`, `tests/test_workspace_policy.py`.

---

## 9. Related Concepts
- [[Least-Privilege Process Sandboxing and Execution Jail]]
- [[ADR-002 - Process Sandboxing and Path Jail Enforcement]]
- [[Lesson - Bounded Autonomy Escape in Subprocess Invocation]]

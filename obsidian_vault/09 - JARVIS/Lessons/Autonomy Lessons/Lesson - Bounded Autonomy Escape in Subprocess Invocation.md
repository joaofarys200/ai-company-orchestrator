---
type: lesson
domain: jarvis
source: production
severity: high
component: autonomy
status: verified
source_type: JARVIS_INTERNAL
confidence: high
tags:
  - jarvis
  - lesson
  - autonomy
  - sandbox
  - security
prerequisites:
  - "[[Least-Privilege Process Sandboxing and Execution Jail]]"
  - "[[Threat Modeling for Autonomous Coding Agents]]"
related:
  - "[[JARVIS Security Sandbox and Policy Engine]]"
  - "[[JARVIS Mission State Machine and Autonomy]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Prompt Injection Defense in Autonomous Agents]]"
implementation:
  - "[[ADR-002 - Process Sandboxing and Path Jail Enforcement]]"
sources:
  - title: JARVIS Incident Report - Incident INC-2026-08-13
    type: JARVIS_INTERNAL
    url: internal://incidents/INC-2026-08-13
---

# 📝 Lesson - Bounded Autonomy Escape in Subprocess Invocation

## 1. Failure
Durante a execução de um script gerado pelo agente para instalar dependências locais, o comando continha um argumento com caminho absoluto fora do workspace (`cd /tmp && pip install ...`), o que contornou o isolamento relativo do path jail e gravou ficheiros no diretório global temporário do sistema anfitrião.

---

## 2. Root Cause
1. **Uso de Shell String em vez de Argument List**: Uma função legada de terminal executava comandos concatenando strings com `shell=True` no Windows PowerShell, permitindo que operadores como `&&`, `;` e `cd` mudassem o diretório de trabalho do processo filho.
2. **Falta de Canonicidade no Path Resolution**: O validador de caminhos não resolvia links simbólicos (`os.path.realpath`) antes da comparação de prefixo.

---

## 3. Why Existing Protection Failed
A função `workspace_policy.py` inspecionava apenas o argumento `cwd` do `subprocess.Popen`, mas não validava o conteúdo interno da string executada pelo interpretador de comandos.

---

## 4. Corrective Action
1. **Banimento Global de `shell=True`**: Todos os subprocessos do JARVIS agora passam estritamente listas de argumentos (`shell=False`), neutralizando comandos compostos.
2. **Enforce de Path Jail Canónico com `os.path.commonpath`**:

```python
import os

def enforce_jail(target_path: str, jail_root: str):
    real_target = os.path.realpath(os.path.abspath(target_path))
    real_jail = os.path.realpath(os.path.abspath(jail_root))
    if os.path.commonpath([real_jail, real_target]) != real_jail:
        raise PermissionError(f"Acesso negado fora do jail: {real_target}")
```
3. **Formalização em ADR**: Registado no [[ADR-002 - Process Sandboxing and Path Jail Enforcement]].

---

## 5. Generalizable Principle
> *Nunca confie em restrições de diretório de trabalho (`cwd`) se a ferramenta permitir execução com interpretador de shell irrestrito.*

---

## 6. Related Concepts
- [[Least-Privilege Process Sandboxing and Execution Jail]]
- [[JARVIS Security Sandbox and Policy Engine]]
- [[Threat Modeling for Autonomous Coding Agents]]
- [[ADR-002 - Process Sandboxing and Path Jail Enforcement]]

---

## 7. Tests Added
- `tests/test_sandbox_policy.py::test_command_chaining_blocked`
- `tests/test_sandbox_policy.py::test_path_traversal_symlink_escape_blocked`

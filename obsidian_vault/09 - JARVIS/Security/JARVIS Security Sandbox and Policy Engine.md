---
type: concept
domain: jarvis
difficulty: intermediate
tags:
  - jarvis
  - security
  - sandbox
  - workspace-policy
  - path-jail
status: verified
---

# 🛡️ JARVIS Security Sandbox and Policy Engine

## 1. Definição & Implementação no Código
A camada de segurança do JARVIS OS é regida por dois ficheiros centrais:
1. [`sandbox.py`](file:///c:/Users/joaor/Desktop/JarvisOS/sandbox.py): Fornece a execução isolada de processos e comandos de terminal dentro do diretório autorizado `sandbox_dir/`.
2. [`workspace_policy.py`](file:///c:/Users/joaor/Desktop/JarvisOS/workspace_policy.py): Aplica regras estritas de acesso ao sistema de ficheiros, impedindo escrita ou execução fora da árvore do workspace.

---

## 2. Regras de Bloqueio da Política
- **Proibição de Path Traversal**: Rejeição imediata de caminhos contendo `..` ou caminhos absolutos fora da raiz do projeto.
- **Bloqueio de Comandos Destrutivos**: Vetos a comandos de formatação de disco, desativação de firewalls ou alteração de registos do SO.
- **Isolamento de Subprocessos**: Execução com `shell=False` para prevenir command injection via metacaracteres.

---

## 3. Related Concepts
- [[Least-Privilege Process Sandboxing and Execution Jail]]
- [[Threat Modeling for Autonomous Coding Agents]]
- [[Seguranca_Defensiva_DevSecOps_e_Sandboxing]]
- [[JARVIS Component Architecture]]

---

## 4. Sources
- *JARVIS OS Codebase — `sandbox.py`, `workspace_policy.py`*

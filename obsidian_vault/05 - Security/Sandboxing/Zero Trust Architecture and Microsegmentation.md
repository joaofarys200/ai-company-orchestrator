---
type: concept
domain: security
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: advanced
tags:
  - security
  - zero-trust
  - microsegmentation
  - nist
  - devsecops
prerequisites:
  - "[[Least-Privilege Process Sandboxing and Execution Jail]]"
related:
  - "[[SSRF Defense in Agentic Fetchers]]"
  - "[[Threat Modeling for Autonomous Coding Agents]]"
used_by:
  - "[[JARVIS Security Sandbox and Policy Engine]]"
failure_modes:
  - "[[Lesson - Bounded Autonomy Escape in Subprocess Invocation]]"
implementation:
  - "[[ADR-002 - Process Sandboxing and Path Jail Enforcement]]"
sources:
  - title: NIST SP 800-207 - Zero Trust Architecture
    type: PRIMARY_SOURCE
    url: https://csrc.nist.gov/publications/detail/sp/800-207/final
---

# 🛡️ Zero Trust Architecture and Microsegmentation

## 1. Pergunta Central
> *Como estruturar sistemas e pipelines agênticos sob a premissa de que a rede interna já está comprometida e que nenhuma requisição deve ser confiada implicitamente?*

---

## 2. Princípios Nucleares do Zero Trust (NIST SP 800-207)
1. **Never Trust, Always Verify**: Toda a chamada (mesmo originada de `localhost` ou da mesma subnet) deve autenticar e autorizar explicitamente a identidade e a política do emissor.
2. **Assume Breach**: O design deve conter o raio de impacto (*Blast Radius*) assumindo que um processo ou agente já foi explorado por injeção de prompt.
3. **Microsegmentação de Rede e I/O**: Isolamento estrito de portas e descritores de ficheiros por serviço.

---

## 3. Aplicação em Agentes Autónomos
- **Subprocessos de Sandbox**: Proibidos de aceder a portas de base de dados administrativas locais sem credenciais de usuário de menor privilégio.
- **Tokens de Acesso com Escopo Delimitado**: Devon recebe tokens que permitem exclusivamente push na branch da tarefa ativa, sem permissão de exclusão de repositórios.

---

## 4. Related Concepts
- [[Least-Privilege Process Sandboxing and Execution Jail]]
- [[SSRF Defense in Agentic Fetchers]]
- [[Threat Modeling for Autonomous Coding Agents]]

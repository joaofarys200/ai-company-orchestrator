---
type: concept
domain: software-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - software-engineering
  - git
  - monorepo
  - subtrees
  - submodules
  - repository-topology
prerequisites:
  - "[[Safe Rollback and Git Transactional Strategies]]"
related:
  - "[[Clean Architecture and Hexagonal Ports]]"
  - "[[CI-CD Pipeline Failure Triage and Automated Healing]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[How to Safely Rollback Failed Code Changes]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Git Subtree Documentation and Best Practices (Git Core Team)
    type: PRIMARY_SOURCE
    url: https://git-scm.com/docs/git-subtree
---

# 📦 Git Monorepos, Subtrees and Boundary Topologies

## 1. Pergunta Central
> *Qual a topologia ótima de versionamento de código (Monorepo, Git Subtrees ou Git Submodules) para agentes autónomos que constroem e mantêm múltiplos microserviços e bibliotecas compartilhadas?*

---

## 2. Comparativo de Topologias de Repositório

| Dimensão | Multi-Repo Tradicional | Git Submodules | Git Subtrees | Monorepo Unificado |
|---|---|---|---|---|
| **Rastreabilidade de Commits** | Isolada por repo | Apontador para SHA externo (detached HEAD frequente) | Histórico incorporado diretamente | **100% Atómico num único commit** |
| **Complexidade para Agentes** | Alta (múltiplos clones/pulls) | Muito Alta (requer `submodule update --init`) | Baixa (pastas normais) | **Mínima (navegação em árvore única)** |
| **Refatoração Multi-Módulo** | Quebrada (requer PRs cruzados) | Frágil | Atómica no commit raiz | **Atómica com validação instantânea** |
| **Isolamento de Sandbox** | Fácil | Moderado | Fácil via subpastas | **Requer Path Jail por Subdiretório** |

---

## 3. Comandos Canônicos de Git Subtree
Para incorporar uma biblioteca compartilhada sem as armadilhas de ponteiro dos submodules:

```bash
# Adicionar repositório como subtree numa subpasta
git subtree add --prefix=packages/shared-auth https://github.com/org/shared-auth.git main --squash

# Sincronizar alterações da subpasta de volta para o repo remoto
git subtree push --prefix=packages/shared-auth https://github.com/org/shared-auth.git main
```

---

## 4. Related Concepts
- [[Safe Rollback and Git Transactional Strategies]]
- [[Clean Architecture and Hexagonal Ports]]
- [[CI-CD Pipeline Failure Triage and Automated Healing]]

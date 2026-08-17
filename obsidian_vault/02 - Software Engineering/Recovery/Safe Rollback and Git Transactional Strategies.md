---
type: pattern
domain: software-engineering
difficulty: intermediate
tags:
  - software-engineering
  - git
  - rollback
  - recovery
  - safety
status: verified
---

# 🔄 Safe Rollback and Git Transactional Strategies

## 1. O Problema da Corrupção de Workspace
Durante execuções de agentes autónomos, múltiplos ficheiros podem ser editados em sequência. Se a 4ª edição quebrar o build ou introduzir uma falha irreparável, deixar o repositório num estado híbrido (metade modificado, metade antigo) impede a compilação e bloqueia futuras missões.

---

## 2. Padrão de Transação de Workspace via Git (Git Workspace Transaction)

Tratar cada missão ou conjunto de patches como uma **transação atómica**:

```
[ Início da Missão do Agente ]
              |
              v
[ 1. Criar Checkpoint / Snapshot Git ]
  - git stash / git branch jarvis/mission-102
              |
              v
[ 2. Agente Aplica Alterações nos Ficheiros ]
              |
              v
[ 3. Validação Automatizada (Build + Testes) ]
              |
      +-------+-------+
      |               |
  (Sucesso)        (Falha Irrecuperável)
      |               |
      v               v
[ 4. COMMIT & MERGE ]  [ 4. ATOMIC ROLLBACK ]
  - git commit -m ...   - git reset --hard HEAD / git clean -fd
```

---

## 3. Comandos de Reversão Segura e Isolamento

```bash
# Criar snapshot atómico antes de iniciar a missão
git checkout -b task/agent-refactor-sandbox

# Se a validação for bem-sucedida:
git add .
git commit -m "feat(sandbox): implement process resource limits"
git checkout main
git merge --ff-only task/agent-refactor-sandbox
git branch -d task/agent-refactor-sandbox

# Se a validação falhar completamente (Rollback Total):
git reset --hard HEAD
git clean -fd
git checkout main
git branch -D task/agent-refactor-sandbox
```

---

## 4. Rollback sem Git (Fallback com Backups em Memória / Disco)
Em ambientes onde o Git não está inicializado no diretório da sandbox, o motor cria cópias em buffer (`.bak` ou em dicionário de memória `original_buffers = {path: content}`) antes de permitir qualquer escrita no disco.

---

## 5. Related Concepts
- [[Patch Generation and Safe Application]]
- [[Compiler Feedback and Test-Driven Self-Repair]]
- [[How to Safely Rollback Failed Code Changes]]
- [[Database Crash Consistency and Recovery]]

---

## 6. Sources
- *Pro Git Book (Chacon & Straub)*: https://git-scm.com/book/en/v2
- *Git Reset & Clean Documentation*: https://git-scm.com/docs/git-reset

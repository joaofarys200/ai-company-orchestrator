---
type: troubleshooting
domain: software-engineering
difficulty: intermediate
tags:
  - software-engineering
  - troubleshooting
  - rollback
  - git
  - recovery
status: verified
---

# 🛠️ How to Safely Rollback Failed Code Changes

## 1. Sintomas & Situação de Emergência
- O agente aplicou patches que quebraram o analisador sintático ou introduziram falhas em cascata no repositório.
- A suite de testes passou de 100% verde para dezenas de falhas de compilação.
- É necessário restaurar o workspace para o último estado estável conhecido de forma 100% atómica.

---

## 2. Árvore de Procedimentos de Rollback

```
                             [ Falha Crítica Pós-Patch ]
                                          |
                   +----------------------+----------------------+
                   |                                             |
          (Ambiente com Git)                             (Sem Git / Sandbox Isolada)
                   |                                             |
         +---------+---------+                         +---------+---------+
         |                   |                         |                   |
    [ Alterações        [ Commits                      [ Restaurar de      [ Restaurar do
    não commitadas ]    locais criados ]               Buffer de Backup ]  Checkpoint SQLite]
         |                   |                         `file.py.bak`       `state_store.db`
         v                   v
   `git reset --hard`  `git reset --hard HEAD~1`
   `git clean -fd`
```

---

## 3. Comandos de Recuperação Imediata

### Cenário 1: Desfazer todas as modificações não commitadas
```powershell
# Reverter todas as alterações em ficheiros rastreados e apagar ficheiros novos criados
git reset --hard HEAD
git clean -fd
```

### Cenário 2: Reverter apenas um ficheiro específico
```powershell
# Restaurar apenas o ficheiro corrompido para o estado do branch main
git checkout HEAD -- backend/server.py
```

### Cenário 3: Rollback em Sandbox via Python (Sem Git)
```python
import os
import shutil

def rollback_file_from_backup(file_path: str) -> bool:
    bak_path = f"{file_path}.bak"
    if os.path.exists(bak_path):
        shutil.copy2(bak_path, file_path)
        os.remove(bak_path)
        return True
    return False
```

---

## 4. Pós-Recuperação
Após o rollback:
1. Executar `pytest` para confirmar que a suite voltou ao estado verde original.
2. Registar o motivo da falha do patch no log da missão para evitar que o agente repita a mesma abordagem.

---

## 5. Related Concepts
- [[Safe Rollback and Git Transactional Strategies]]
- [[Patch Generation and Safe Application]]
- [[Compiler Feedback and Test-Driven Self-Repair]]

---

## 6. Sources
- *Git SCM Reference - git-reset*: https://git-scm.com/docs/git-reset
- *Git SCM Reference - git-clean*: https://git-scm.com/docs/git-clean

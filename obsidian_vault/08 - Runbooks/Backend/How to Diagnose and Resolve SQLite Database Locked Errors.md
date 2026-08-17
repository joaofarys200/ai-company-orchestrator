---
type: troubleshooting
domain: backend-systems
difficulty: intermediate
tags:
  - backend
  - troubleshooting
  - sqlite
  - concurrency
  - database-locked
status: verified
---

# 🛠️ How to Diagnose and Resolve SQLite Database Locked Errors

## 1. Sintomas & Mensagens de Erro
- `sqlite3.OperationalError: database is locked`
- `sqlite3.BusyError: database is busy`
- Bloqueio persistente em operações `INSERT` ou `UPDATE` quando múltiplos agentes ou threads tentam aceder à base de dados simultaneamente.

---

## 2. Árvore de Decisão e Causas Raiz

```
                           [ Erro: SQLite Database is Locked ]
                                           |
                   +-----------------------+-----------------------+
                   |                                               |
        (Modo de Journal Inadequado)                      (Transações Longas Não Fechadas)
                   |                                               |
                   v                                               v
    O banco está em modo DELETE                     Um cursor/transação executou
    em vez de WAL (bloqueio total                   `BEGIN` e ficou à espera de I/O
    entre leitores e escritores).                   ou timeout sem dar `commit()`.
```

---

## 3. Procedimento Sistemático de Correção (Runbook)

### Passo 1: Ativar Imediatamente o Modo WAL e Ajustar o Timeout
Executar na base de dados:

```sql
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 10000;
PRAGMA synchronous = NORMAL;
```

### Passo 2: Auditar Uso de Context Managers em Python
Garantir que todas as conexões usam o padrão `with conn:` para commits automáticos ou blocos `try ... finally` com fecho estrito:

```python
# FORMA CORRETA E SEGURA
import sqlite3

def safe_db_write(db_path: str, query: str, params: tuple):
    with sqlite3.connect(db_path, timeout=10.0) as conn:
        conn.execute("PRAGMA busy_timeout = 10000;")
        cursor = conn.cursor()
        cursor.execute(query, params)
        # O commit ocorre automaticamente ao sair do bloco 'with'
```

### Passo 3: Fechar Processos Zumbis que Bloqueiam o Ficheiro
Se o erro persistir no Windows:

```powershell
# Identificar se há múltiplos processos Python a segurar handles no database.db
Get-Process python -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, WorkingSet64
```

---

## 4. Prevenção Definitiva
1. Nunca partilhar o mesmo objeto `sqlite3.Connection` entre múltiplas threads concorrentes (`check_same_thread=False` deve ser acompanhado de locks de aplicação ou conexões por thread).
2. Manter as transações de escrita o mais curtas possíveis (apenas o `INSERT`/`UPDATE` estrito, sem fazer chamadas de rede ou inferências de IA dentro do bloco da transação).

---

## 5. Related Concepts
- [[SQLite WAL Mode and Concurrency]]
- [[Optimistic vs Pessimistic Locking]]
- [[Database Crash Consistency and Recovery]]

---

## 6. Sources
- *SQLite Documentation - How to Handle Database Locked*: https://www.sqlite.org/rescode.html#busy
- *Python sqlite3 standard library reference*: https://docs.python.org/3/library/sqlite3.html

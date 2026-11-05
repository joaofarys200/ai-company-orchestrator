# 3. CAS AND CONCURRENCY VALIDATION

**Status:** IMPLEMENTED | INTEGRATED | UNIT_TESTED | INTEGRATION_TESTED | INDEPENDENTLY_VALIDATED  
**Data:** 2026-11-05  
**Componente:** `services/obsidian_graph_engine.py` (`NoteFileLock`, `atomic_write_note`)

---

## 3.1 Mecanismo de Lock de Ficheiro Cross-Process (`NoteFileLock`)

Foi introduzido um mecanismo de lock por nota ao nível do sistema de ficheiros em `data/obsidian/.locks/<rel_path_hash>.lock`.
- **Atomiicidade:** Utiliza `os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR)`.
- **Registo de Metadados de Lock:** Registo do PID do processo, timestamp de aquisição e UUID do lock.
- **Detetor de Stale Lock:** Evicção automática de locks abandonados após 60.0 segundos de inatividade do processo titular.
- **Timeout Limitado:** Timeout configurável (5.0s por omissão) antes de lançar `ObsidianConcurrencyError`.

---

## 3.2 Cobertura Integral do Ciclo de Escrita Atómica

O lock é detido durante todo o ciclo:
`[Aquisição do Lock] -> [Leitura do Estado Atual] -> [Validação de Hash Esperado] -> [Criação do Snapshot] -> [Escrita Temporária] -> [Verificação CAS Final] -> [os.replace Atómico] -> [Libertação do Lock]`

Se dois processos tentarem escrever na mesma nota em simultâneo, o segundo aguarda com polling seguro ou falha com erro explícito de concorrência. Se escreverem em notas distintas, procedem em paralelo sem contenção.

---

## 3.3 Limitações Concorrentes Externas (Declaração Honesta)

Se um editor externo (ex.: Obsidian desktop) modificar diretamente o ficheiro na mesma fração de segundo em que o `os.replace` ocorre, o sistema operativo realiza a substituição ao nível do inode. No entanto, a verificação prévia de CAS e a criação imediata de snapshot prévio garantem que nenhuma informação é destruída sem histórico completo de recuperação.

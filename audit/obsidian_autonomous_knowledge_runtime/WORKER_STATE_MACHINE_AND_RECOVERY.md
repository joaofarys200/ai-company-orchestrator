# 6. WORKER STATE MACHINE AND RECOVERY

**Status:** IMPLEMENTED | INTEGRATED | UNIT_TESTED | INTEGRATION_TESTED | INDEPENDENTLY_VALIDATED  
**Data:** 2026-11-05  
**Componente:** `services/obsidian_graph_engine.py`

---

## 6.1 Máquina de Estados da Fila de Melhoria

Estados suportados:
- `PENDING`: Aguarda processamento pelo worker.
- `IN_PROGRESS`: Bloqueado pelo worker e em processamento atómico.
- `PROPOSAL_CREATED`: Proposta gerada com identificador único persistido.
- `AWAITING_REVIEW`: Proposta generativa aguarda validação do operador humano.
- `APPLIED`: Proposta validada e escrita no cofre com snapshot prévio.
- `REJECTED`: Proposta descartada ou rejeitada pelo operador.
- `FAILED_VALIDATION`: Proposta falhou requisitos estruturais ou de esquema.
- `BLOCKED_BY_ENVIRONMENT`: Daemon local Ollama ou modelo `qwen3.5:9b` indisponível.
- `RECONCILIATION_REQUIRED`: Item encontrado em `IN_PROGRESS` após encerramento forçado do processo.

---

## 6.2 Recuperação de Interrupções e Locks Concorrentes

- **Lock de Worker Único (`worker.lock`):** Impede que múltiplos cliques em "+1 Ciclo" ou chamadas simultâneas disparem tarefas sobrepostas.
- **Persistência Prévia de Estado:** O estado `IN_PROGRESS` é gravado no disco antes de qualquer invocação de modelo ou operação de ficheiro.
- **Reconciliação no Arranque:** A função `reconcile_interrupted_queue()` deteta automaticamente anomalias de processos interrompidos e marca-as como `RECONCILIATION_REQUIRED`.

---
type: decision
domain: jarvis
difficulty: advanced
tags:
  - jarvis
  - adr
  - architectural-decision
  - crash-recovery
  - git-transactions
  - watchdog
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
---

# 📋 ADR-011 - Mission Crash Recovery and Git Transactional Reset

## Status
**Aceite / Em Produção**

## Contexto
Quedas repentinas de energia, finalizações abruptas de processo (`SIGKILL`) ou encerramentos inesperados do servidor podem deixar arquivos do workspace em estado corrompido ou intermediário e tarefas travadas em `IN_PROGRESS`.

## Problema
Como restaurar o workspace do projeto e o estado da missão para uma versão consistente e comprovadamente válida após um crash.

## Decisão
Implementar a **Recuperação Transacional com Git e Watchdog de Inicialização**:
1. Antes de iniciar qualquer passo mutatório, o `PatchEngine` cria um commit/checkpoint Git na sandbox (`git commit -m "checkpoint_before_step_N"`).
2. Na reinicialização do backend, o `MissionRecoveryWatchdog` varre a base de dados procurando por missões com estado `IN_PROGRESS` sem heartbeat recente.
3. Para cada missão zumbi, o watchdog reverte o workspace para o último commit de checkpoint válido (`git reset --hard <last_valid_sha>`) e marca o passo como `FAILED_CRASH_RECOVERED`, permitindo reexecução determinística.

## Consequences
- **Positivas**: Elimina estados zumbis e garante consistência do código em disco.
- **Negativas**: Pequeno overhead de snapshot Git antes de cada passo de código.

## Tests
- `tests/test_mission_autonomy.py`

## Related ADRs
- [[ADR-002 - Process Sandboxing and Path Jail Enforcement]]

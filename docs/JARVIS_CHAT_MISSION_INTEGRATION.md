# JARVIS OS — Integração Chat & Sistema de Missões (Fase 10.6)

## 1. Visão Geral e Arquitetura Unificada

A Fase 10.6 consolida a integração definitiva entre a interface de chat do JARVIS OS e o pipeline oficial de missões (`MissionStateStore`, `MissionGate`, `MissionAutonomyController`, `ProjectBuilder`, `Swarm`).

O chat não constitui um caminho paralelo nem um mecanismo isolado de execução; funciona como uma porta de entrada canónica de resolução de intenções:

```
[ CHAT INPUT / WEBSOCKET ]
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│  ChatRequestResolver (backend/services/chat_mission_bridge)  │
│  - Avaliação de Segurança (SafetyClassifier)                │
│  - Detecção Determinística de Intenção:                     │
│    • CONVERSATIONAL  ──► Chat Casual / Contexto             │
│    • ANALYSIS        ──► ProjectIntake / Fresh Snapshot     │
│    • REFUSED_POLICY  ──► Refusa com Badge de Segurança      │
│    • EXECUTABLE      ──► Pipeline Oficial de Missões        │
└─────────────────────────────────────────────────────────────┘
          │ (EXECUTABLE_DIRECTIVE)
          ▼
┌─────────────────────────────────────────────────────────────┐
│  MissionStateStore (agents/mission_state.py)                │
│  - Criação de Missão Canónica (status: DRAFT)               │
│  - Criação de WorkPackage & Critério de Aceitação           │
│  - Transição de Estado: DRAFT -> READY                      │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│  Mission Gate                                               │
│  - Validação de Políticas e Permissões                      │
│  - Verificação de Freshness de Snapshot                     │
│  - Invariantes Financeiros / Reality Check (se economic)    │
│  - Transição de Estado: READY -> ACTIVE ou BLOCKED          │
└─────────────────────────────────────────────────────────────┘
          │ (ACTIVE)
          ▼
┌─────────────────────────────────────────────────────────────┐
│  Executores Oficiais                                        │
│  - ProjectBuilder / MissionAutonomyController / Swarm       │
│  - Registo de Evidência Canónica (EXECUTION_LOG / HASH)     │
│  - Satisfação de Critérios de Aceitação                     │
│  - Conclusão do Work Package (COMPLETED)                    │
│  - Conclusão da Missão (COMPLETED / FAILED)                 │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
[ RESPOSTA E STREAMING WEBSOCKET / UI CHAT CARD ]
```

---

## 2. Invariantes e Regras de Segurança

1. **Zero Bypass de Execução**: Nenhuma diretiva vinda do frontend pode executar código ou criar ficheiros sem criar previamente a entidade de missão oficial no `MissionStateStore`.
2. **Invariante Económico (`money`)**:
   - Diretivas económicas (`money`, arbitragem, monetização) atravessam exatamente o mesmo pipeline canónico de missões.
   - Nenhuma transação fictícia nem benchmarks locais são convertidos em receita sem prova de liquidação bancária real (`EvidenceLevel.SETTLED`).
3. **Remoção de Legado `OPENCLAW`**:
   - Todo o sistema de mensagens foi normalizado para emissores canónicos: `JARVIS`, `CLIENTE`/`USER`, `SISTEMA`, ou especialistas (`Alex`, `Clara`, `Devon`, `Quinn`).
   - O banco de dados SQLite executa auto-migração na inicialização: `UPDATE messages SET sender = 'JARVIS' WHERE UPPER(sender) = 'OPENCLAW'`.
4. **Encoding UTF-8 de Ponta a Ponta**:
   - Todos os ficheiros do repositório, payloads JSON (`ensure_ascii=False`), fluxos WebSocket e streams `sys.stdout`/`sys.stderr` foram saneados para UTF-8 genuíno, eliminando artefatos de mojibake (`ðŸ`, `â€¦`, `Ã`, `Â`).

---

## 3. Estrutura de Estados da Missão

```
   [DRAFT]
      │
      ▼
   [READY] ──────────┐ (Bloqueio no Gate)
      │              ▼
      ▼          [BLOCKED]
   [ACTIVE]
      │
      ├──────────────────────┐
      ▼                      ▼
 [COMPLETED]              [FAILED]
 (com Evidence          (em caso de erro)
  e Critério Satisfeito)
```

---

## 4. Suites de Teste Automatizadas

As seguintes suites garantem a integridade de todas as camadas:

| Ficheiro de Teste | Descrição |
| :--- | :--- |
| `tests/test_chat_utf8_encoding.py` | Garante persistência SQLite e payloads WebSocket UTF-8 puros. |
| `tests/test_canonical_sender.py` | Verifica a normalização e bloqueio estrito de `OPENCLAW`. |
| `tests/test_chat_mission_bridge.py` | Testa a resolução de intenções e criação no `MissionStateStore`. |
| `tests/test_chat_mission_states.py` | Valida o ciclo completo de vida de estados (`ACTIVE` -> `COMPLETED`/`FAILED`). |
| `tests/test_chat_safety_and_gates.py` | Testa recusas de segurança e bloqueios automáticos no Mission Gate. |
| `tests/test_chat_money_pipeline.py` | Assegura que missões do projeto `money` cumprem todas as regras. |
| `tests/test_chat_mission_e2e_integration.py` | Validação ponta-a-ponta com streaming WebSocket de missões e chat. |
| `scripts/verify_live_chat_mission_qa.py` | Teste automatizado contra servidor em tempo real (Porta 8001). |

---

## 5. Verificação em Produção

Para executar a suite completa de integração do chat:
```bash
.\venv\Scripts\python.exe -m pytest tests/test_chat_utf8_encoding.py tests/test_canonical_sender.py tests/test_chat_mission_bridge.py tests/test_chat_mission_states.py tests/test_chat_safety_and_gates.py tests/test_chat_money_pipeline.py tests/test_chat_mission_e2e_integration.py -v
```
Resultado: **17 passed in 1.72s (100% sucesso)**.
Total repositório: **988 passed, 2 skipped, 113 subtests passed**.

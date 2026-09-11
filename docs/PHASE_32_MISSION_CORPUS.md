# JARVIS OS — Corpus Oficial de Missões Long-Horizon da Fase 32

## 1. Visão Geral do Corpus

A **Fase 32** avalia a retenção de autonomia do JARVIS OS quando a escala de uma missão cresce de tarefas atómicas (6 a 12 transições) para **dezenas e centenas de transições encadeadas** (10 a 500 transições de tarefas).

O corpus é composto por **10 missões complexas**, estruturadas de acordo com as 5 categorias regulamentares e mapeadas nos 5 níveis de complexidade progressiva:

```
+-------------------+--------------------------------------------------------------------------------------+
| Categoria         | Distribuição Regulamentar                                                            |
+-------------------+--------------------------------------------------------------------------------------+
| SOFTWARE_PROJECT  | 3 Missões (LH_01, LH_02, LH_03)                                                      |
| FULL_STACK_APP    | 2 Missões (LH_04, LH_05)                                                             |
| LARGE_FEATURE_SET | 2 Missões (LH_06, LH_07)                                                             |
| REFACTOR_MIGRATION| 2 Missões (LH_08, LH_09)                                                             |
| COMPLEX_BUG_FEAT  | 1 Missão  (LH_10)                                                                    |
+-------------------+--------------------------------------------------------------------------------------+
```

### Níveis de Complexidade Progressiva (Task Transitions Horizon)
- **LEVEL_1**: 10–20 task transitions
- **LEVEL_2**: 20–50 task transitions
- **LEVEL_3**: 50–100 task transitions
- **LEVEL_4**: 100–200 task transitions
- **LEVEL_5**: 200–500 task transitions

---

## 2. Catálogo Detalhado das 10 Missões Long-Horizon

### Missão LH_01: Enterprise Asset & IT Equipment Inventory Engine
- **ID**: `MISSION_LH_01`
- **Categoria**: `SOFTWARE_PROJECT`
- **Nível de Complexidade**: `LEVEL_1` (16–20 transições)
- **Prompt**: *"Cria um motor de inventário de ativos com categorização multinível, cálculo de depreciação e exportação."*
- **Requisitos Formais**:
  1. Categorização multinível de ativos (equipamento, infraestrutura, software).
  2. Cálculo dinâmico de depreciação anual com regras contábeis padrão.
  3. Exportação de relatórios estruturados JSON e CSV.
  4. Persistência transacional SQLite com verificação de constraints.
- **Falhas Injetadas**: 1 falha cirúrgica de sintaxe (`SYNTAX_ERROR`).
- **Recuperação de Interrupção**: Interrupção a 50% das tarefas, retomada por checkpoint ACID.

---

### Missão LH_02: Real-time IoT Telemetry & Health Monitoring Engine
- **ID**: `MISSION_LH_02`
- **Categoria**: `SOFTWARE_PROJECT`
- **Nível de Complexidade**: `LEVEL_2` (32–45 transições)
- **Prompt**: *"Desenvolve um agregador de telemetria IoT com limiares de alerta, séries temporais e failover."*
- **Requisitos Formais**:
  1. Agregação de telemetria por janelas de tempo deslizantes.
  2. Verificação determinística de limiares críticos de alerta.
  3. Registo de failover e integridade de sensores distribuídos.
  4. Testes automatizados de concorrência e integridade de dados.
- **Falhas Injetadas**: 2 falhas sequenciais (`SYNTAX_ERROR`, `TEST_FAILURE`).
- **Recuperação de Interrupção**: Interrupções a 33% e 66% das tarefas.

---

### Missão LH_03: Distributed Workflow DAG Runner & Task Scheduler
- **ID**: `MISSION_LH_03`
- **Categoria**: `SOFTWARE_PROJECT`
- **Nível de Complexidade**: `LEVEL_3` (65–85 transições)
- **Prompt**: *"Implementa um orquestrador de workflows DAG com resolução topológica de dependências e filas de retry."*
- **Requisitos Formais**:
  1. Resolução determinística de dependências topológicas (Kahn algorithm O(V+E)).
  2. Filas de retry com backoff exponencial e controlo de jitter.
  3. Dead-letter queue para tarefas falhadas com registo de proveniência.
  4. Verificação formal de ausência de ciclos no grafo de execução.
- **Falhas Injetadas**: 2 falhas sequenciais (`IMPORT_ERROR`, `CONTRACT_MISMATCH`).
- **Recuperação de Interrupção**: Interrupções a 25%, 50% e 75% das tarefas.

---

### Missão LH_04: E-Commerce Order Fulfillment & Warehouse Logistics Platform
- **ID**: `MISSION_LH_04`
- **Categoria**: `FULL_STACK_APPLICATION`
- **Nível de Complexidade**: `LEVEL_3` (75–95 transições)
- **Prompt**: *"Cria uma plataforma de logística com reserva de stock, verificação de pagamento simulado e tracking de encomendas."*
- **Requisitos Formais**:
  1. Reserva atómica de stock de armazém com proteção contra race conditions.
  2. Processamento simulado de pagamento com garantia de idempotência.
  3. Tracking de estados de expedição e histórico auditável de eventos.
  4. Dashboard reativo com contadores estatísticos em tempo real.
- **Falhas Injetadas**: 3 falhas sequenciais (`SYNTAX_ERROR`, `BUILD_FAILURE`, `CONTRACT_MISMATCH`).
- **Recuperação de Interrupção**: Interrupções a 30% e 70% das tarefas.

---

### Missão LH_05: Multi-Tenant SaaS Workspace & Document Management Engine
- **ID**: `MISSION_LH_05`
- **Categoria**: `FULL_STACK_APPLICATION`
- **Nível de Complexidade**: `LEVEL_4` (130–160 transições)
- **Prompt**: *"Desenvolve um sistema multi-tenant com permissões RBAC herdadas, versionamento de documentos e quotas."*
- **Requisitos Formais**:
  1. Isolamento rigoroso de workspaces multi-tenant em storage e runtime.
  2. Hierarquia de permissões RBAC com herança de papéis e revogação dinâmica.
  3. Histórico imutável de revisões de documentos com diff estruturado.
  4. Aplicação de quotas por tenant com alertas de saturação.
- **Falhas Injetadas**: 3 falhas sequenciais reparadas autonomamente.
- **Recuperação & Transporte**: Interrupções a 25%, 50% e 75%; teste de fallback de transporte (QUIC RIO -> QUIC Python fallback).

---

### Missão LH_06: Autonomous CI/CD Pipeline & Quality Gate Engine
- **ID**: `MISSION_LH_06`
- **Categoria**: `LARGE_FEATURE_SET`
- **Nível de Complexidade**: `LEVEL_2` (38–50 transições)
- **Prompt**: *"Implementa um pipeline de CI/CD autónomo com linting, testes multi-estágio e rollback automático."*
- **Requisitos Formais**:
  1. Execução encadeada de quality gates de linting, tipagem e segurança.
  2. Validação multi-estágio de suites de testes de regressão.
  3. Mecanismo automático de rollback em caso de falha de validação.
  4. Hashing SHA-256 de artefactos para verificação de proveniência de build.
- **Falhas Injetadas**: 1 falha de build reparada cirurgicamente.
- **Recuperação de Interrupção**: Interrupção a 50% das tarefas.

---

### Missão LH_07: Real-Time Financial Settlement & Double-Entry Ledger
- **ID**: `MISSION_LH_07`
- **Categoria**: `LARGE_FEATURE_SET`
- **Nível de Complexidade**: `LEVEL_4` (140–180 transições)
- **Prompt**: *"Constrói um livro-razão financeiro com partidas dobradas, câmbios dinâmicos e conciliação bancária."*
- **Requisitos Formais**:
  1. Invariante estrito de partidas dobradas (total de débitos == total de créditos).
  2. Conversão cambial multi-moeda com cache resiliente de taxas de câmbio.
  3. Relatório automatizado de conciliação bancária e apuramento de saldos.
  4. Trilha imutável de auditoria criptográfica por transação.
- **Falhas Injetadas**: 4 falhas sequenciais reparadas cirurgicamente.
- **Recuperação & Transporte**: Interrupções a 20%, 50% e 80%; fallback de transporte verificado.

---

### Missão LH_08: Zero-Downtime Microservices Datastore Migration Engine
- **ID**: `MISSION_LH_08`
- **Categoria**: `REFACTOR / MIGRATION`
- **Nível de Complexidade**: `LEVEL_3` (70–90 transições)
- **Prompt**: *"Refatora um esquema monolítico para microsserviços desacoplados com verificação dual-write e validação."*
- **Requisitos Formais**:
  1. Migração desacoplada de dados com suporte a dual-write ativo.
  2. Verificação contínua de paridade de dados entre fontes primária e réplica.
  3. Contratos de compatibilidade retroativa de APIs.
  4. Suite completa de testes de migração e rollback transacional.
- **Falhas Injetadas**: 2 falhas de contrato reparadas em runtime.
- **Recuperação de Interrupção**: Interrupções a 40% e 80% das tarefas.

---

### Missão LH_09: Full Architecture Modernization & High-Concurrency Event Bus
- **ID**: `MISSION_LH_09`
- **Categoria**: `REFACTOR / MIGRATION`
- **Nível de Complexidade**: `LEVEL_5` (240–300 transições)
- **Prompt**: *"Moderniza uma arquitetura legada síncrona para barramento assíncrono com filas batch e stress tests."*
- **Requisitos Formais**:
  1. Desacoplamento de endpoints síncronos para barramento assíncrono pub/sub.
  2. Filas de processamento em lote (batch queues) com agregação determinística.
  3. Camada de cache resiliente com expiração dinâmica e invalidação cirúrgica.
  4. Testes de carga e stress para validação de concorrência massiva.
- **Falhas Injetadas**: 5 falhas sequenciais reparadas ao longo de 250+ transições.
- **Recuperação & Transporte**: Interrupções a 20%, 40%, 60% e 80%; preservação de checkpoints ACID.

---

### Missão LH_10: Distributed Concurrency Deadlock Repair & Dynamic SubDAG Replan
- **ID**: `MISSION_LH_10`
- **Categoria**: `COMPLEX BUG + FEATURE + TEST`
- **Nível de Complexidade**: `LEVEL_4` (150–190 transições)
- **Prompt**: *"Diagnostica e resolve deadlock de concorrência distribuída com expansão dinâmica de subDAG e browser QA."*
- **Requisitos Formais**:
  1. Diagnóstico cirúrgico de condição de corrida e deadlock de concorrência.
  2. Arbitragem de leases com prevenção formal de starvation de agentes.
  3. Expansão adaptativa de subDAG em runtime (`KEEP`, `ADAPT`, `REPLAN`).
  4. Validação final interativa em browser real com 0 erros de consola.
- **Falhas Injetadas**: 4 falhas sequenciais reparadas cirurgicamente.
- **Recuperação & Transporte**: Interrupções a 25%, 50% e 75%; integridade de leases e checkpoint verificada.

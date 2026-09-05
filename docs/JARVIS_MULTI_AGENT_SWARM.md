# JARVIS OS — Fase 14: Hierarchical Task Distribution & Multi-Agent Swarm Execution

## 1. Visão Geral e Princípios Arquiteturais

A **Fase 14** evolui o Mission Runtime do JARVIS OS de um executor de tarefas isoladas para uma **camada hierárquica de distribuição e execução paralela especializada entre múltiplos agentes**, governada estritamente por um coordenador determinístico.

```
                  ┌──────────────────────────────┐
                  │    MISSION ORCHESTRATOR      │
                  │   (Autoridade e Lifecycle)   │
                  └──────────────┬───────────────┘
                                 │
                  ┌──────────────▼───────────────┐
                  │      SWARM COORDINATOR       │
                  │  (Leases, Quotas, Scheduling)│
                  └──────────────┬───────────────┘
                                 │
                  ┌──────────────▼───────────────┐
                  │          AGENT POOL          │
                  │ (Registry, Health & Scoring) │
                  └───────┬──────────────┬───────┘
                          │              │
             ┌────────────▼─────┐  ┌─────▼────────────┐
             │ ArchitectureAgent│  │   CodingAgent    │
             │   TestingAgent   │  │   BrowserAgent   │
             │   ResearchAgent  │  │   ReviewAgent    │
             └──────────────────┘  └──────────────────┘
```

### Invariantes Centrais
1. **Coordenação Determinística vs Autonomous Chaos**: O swarm NÃO opera como agentes autônomos sem controle ou com decisões arbitrárias delegadas a LLMs. O runtime determinístico mantém a autoridade absoluta sobre estado de tarefas, ownership de arquivos, leases, concorrência, quotas, retries, cancelamentos, checkpoints e evidências.
2. **Separação de Papéis**: O agente executa a tarefa dentro de sua especialidade e produz um `AgentResult`. O `SwarmCoordinator` e o `MissionLifecycleOrchestrator` validam o contrato e decidem a transição de estado (`TaskStateTransition`).
3. **Single-Host First**: Totalmente auto-contido em processos locais/assíncronos, sem introdução de dependências pesadas externas (Kubernetes, Celery, Ray).

---

## 2. Componentes Centrais do Swarm

### 2.1 `AgentRegistry`
Mantém o registro e ciclo de vida dos agentes na frota:
- Estados de saúde: `ONLINE`, `BUSY`, `IDLE`, `DEGRADED`, `UNHEALTHY`, `OFFLINE`.
- Rastreio contínuo de concorrência ativa, sucessos acumulados, falhas e último heartbeat.

### 2.2 `LeaseManager`
Garante exclusividade e atomicidade na execução das tarefas:
- **Task Lease Exclusivo**: Cada tarefa atribuída recebe um lease com identificador único (`lease_id`), TTL configurável (default 15s) e tentativa associada (`attempt_id`).
- **Heartbeat Contínuo**: O agente renova ativamente seu lease via callbacks assíncronos.
- **Detecção de Expiração & Reap**: Leases cujo heartbeat expirou além do TTL são recolhidos e marcados como `INTERRUPTED`, liberando a tarefa para reatribuição a um agente saudável.

### 2.3 `HierarchicalQuotaManager`
Controla o consumo de recursos em três níveis hierárquicos:
1. **Global Max Concurrency**: Limite superior de tarefas concorrentes em todo o swarm.
2. **Category Quotas**: Limites máximos independentes por categoria (`ARCHITECTURE`, `RESEARCH`, `CODING`, `TESTING`, `BROWSER`, `REVIEW`, `GENERAL`).
3. **Agent Concurrency**: Concorrência máxima permitida por instância individual de agente.
4. **Resource Classes**: Rastreia alocação de classes especializadas de recursos (`CPU`, `IO`, `MEMORY`, `GPU`, `BROWSER`, `NETWORK`).

### 2.4 `FileOwnershipRegistry`
Evita colisões destrutivas no workspace compartilhado:
- Antes de iniciar a execução, os caminhos/escopos declarados na tarefa (`metadata.path_scope`) são reivindicados no registro.
- Detecta antecipadamente colisões diretas ou sobreposições de diretórios ascendentes/descendentes. Se outro agente possuir o lock de caminho, a concessão é rejeitada com `CONFLICT_DETECTED`.

### 2.5 `AgentSelector` (Algoritmo Determinístico de Scoring)
A seleção do agente ótimo para cada tarefa pronta é calculada por scoring ponderado determinístico:

$$\text{Score} = 100.0 + S_{\text{specialist}} + S_{\text{cat}} + (P_{\text{task}} \times 10.0) + S_{\text{load}} + S_{\text{reliability}}$$

Onde:
- **Especialista Primário ($S_{\text{specialist}} = +100.0$)**: Concedido quando o `agent_type` do agente corresponde exatamente à categoria da tarefa (ex: `TestingAgent` para tarefa `TESTING`), priorizando o especialista primário sobre agentes generalistas.
- **Match de Categoria ($S_{\text{cat}} = +50.0$)**: Concedido quando a categoria da tarefa consta nas capabilities do agente.
- **Peso de Prioridade**: Adiciona $10.0 \times \text{prioridade}$ da tarefa.
- **Bônus / Penalidade de Carga ($S_{\text{load}}$)**: $+30.0$ se o agente estiver `IDLE` (0 tarefas ativas); $-20.0 \times \text{tarefas ativas}$ se ocupado.
- **Confiabilidade ($S_{\text{reliability}}$)**: Bônus de histórico de sucessos ($\min(20.0, 2.0 \times \text{sucessos})$) menos penalidade por falhas passadas ($\min(40.0, 10.0 \times \text{falhas})$).
- **Desempate Determinístico**: Ordenação lexicográfica estável por `agent_id` em caso de pontuações idênticas.

### 2.6 `TaskScheduler` com Aging Determinístico
Para evitar inanição (*starvation*) entre ramos paralelos do DAG, tarefas prontas que aguardam há múltiplos ciclos de escalonamento recebem incremento determinístico de prioridade efetiva:
$$\text{Priority}_{\text{effective}} = \text{Priority}_{\text{base}} + (0.5 \times \text{cycles\_waiting})$$

### 2.7 `ResultValidator` & Cache de Idempotência
Valida o contrato estrito de `AgentResult` e descarta submissões duplicadas através de chave de idempotência composta: `(task_id, attempt_id, result_id)`.

---

## 3. Frota de Agentes Especializados & Princípio de Menor Privilégio

| Agente | Tipo | Categorias | Ferramentas Permitidas | Restrições de Segurança / Menor Privilégio |
|---|---|---|---|---|
| `ArchitectureAgent` | `ARCHITECTURE` | ARCHITECTURE, REVIEW | Leitura de repo, escrita em docs | Proibido executar scripts de teste ou mutações no código produtivo |
| `ResearchAgent` | `RESEARCH` | RESEARCH | Web search, documentação, leitura | **Bloqueio total de comandos destrutivos e escrita no workspace** |
| `CodingAgent` | `CODING` | CODING | AST patch, file edit, replacer | Restrito aos arquivos sob seu escopo de ownership aprovado |
| `TestingAgent` | `TESTING` | TESTING, REVIEW | Test runners, coverage, assertions | Isolado do ambiente de deploy e transações financeiras |
| `BrowserAgent` | `BROWSER` | BROWSER, TESTING | Playwright, screenshot, DOM inspect | **Bloqueio total de mutação de estado econômico e transações** |
| `ReviewAgent` | `REVIEW` | REVIEW, ARCHITECTURE | Diff review, security audit, signoff | Somente leitura e emissão de assinaturas criptográficas de evidência |

---

## 4. Handoff e Isolamento de Contexto

O `CrossAgentHandoffManager` constrói o contexto de entrada de cada agente filtrando estritamente os outputs e evidências gerados pelas tarefas predecessoras imediatas:
- Não expõe todo o estado global do orquestrador ao agente.
- O agente receptor recebe apenas as evidências estruturadas relevantes e os artefatos produzidos pelos seus antecedentes diretos no DAG.

---

## 5. Checkpoints e Reconciliação Pós-Falha

O estado completo do swarm é serializado no objeto `Checkpoint` de cada missão (`swarm_state`):
- Agentes registrados e contadores de saúde.
- Leases ativos e timestamps de expiração.
- Quotas consumidas e caminhos em ownership.
- Métricas globais de escalonamento.

Na recuperação (`recover_from_checkpoint`):
- Leases órfãos deixados por processos encerrados abruptamente são cancelados e reconciliados.
- Tarefas que estavam em execução no momento do crash são identificadas e marcadas como `INTERRUPTED` para reatribuição imediata.

---

## 6. Resultados de Performance & Empirical FIRST_REAL_LIMIT

### 6.1 Benchmark de Paralelismo do Swarm

Testes executados com 32 tarefas paralelas sob carga artificial de 50ms:

| Número de Agentes | Tarefas | Makespan Medido (ms) | Speedup Observado | Eficiência de Paralelismo |
|---|---|---|---|---|
| **1 Agente** | 32 | 1,842.10 ms | 1.00x | 100.0% (Baseline) |
| **2 Agentes** | 32 | 985.40 ms | 1.87x | 93.5% |
| **4 Agentes** | 32 | 520.15 ms | 3.54x | 88.5% |
| **8 Agentes** | 32 | 320.80 ms | 5.74x | 71.8% |

### 6.2 Identificação Empírica do Novo Limite (`FIRST_REAL_LIMIT`)

- **Novo `FIRST_REAL_LIMIT`**:
  > **Single-host asyncio TaskGraph lease loop & NTFS checkpoint serialization latency**: Sob concorrência sustentada acima de 250 tarefas com persistência síncrona de checkpoints em disco NTFS, o overhead de I/O de serialização atinge ~10.16 ms a 19.36 ms por tarefa, estabelecendo a barreira real onde o throughput é dominado pela velocidade do sistema de arquivos e a fila de coroutines do event loop em thread única.

---

## 7. Protocolo WebSocket e Integração Frontend

### Operações Suportadas
- `mission_swarm_status`: Retorna o estado completo da frota, leases ativos, quotas e métricas.
- `mission_swarm_reassign`: Permite intervenção controlada para reatribuir tarefas a agentes alternativos.

### Frontend Dashboard (`MissionPlanner.tsx`)
O painel **Multi-Agent Swarm Fleet (Fase 14)** providencia:
- Visualização ao vivo do status de cada um dos 7 agentes especializados.
- Barra de telemetria de concorrência global, lease TTL e locks de caminho.
- Botão interativo para consulta e atualização de telemetria via WebSocket.

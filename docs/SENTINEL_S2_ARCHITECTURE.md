# JARVIS OS — Security Sentinel (Fase S2: Arquitetura do Continuous Watchdog)

## 1. Visão Geral e Princípios Fundamentais

A **Fase S2** do Security Sentinel transforma o módulo de um auditor sob demanda num **motor de monitorização contínua passiva em tempo real**, perfeitamente integrado no ecossistema do JARVIS OS.

### Princípios Invariantes:
1. **100% READ-ONLY**: Sob nenhuma circunstância o Sentinel executa ações destrutivas (`kill process`, alteração de chaves de registo, alteração de regras de firewall, eliminação de ficheiros, etc.). Todas as ações são estritamente de observação e auditoria defensiva.
2. **Defesa em Profundidade**: Múltiplos coletores independentes recolhem sinais de processos, conexões de rede, persistência, ficheiro `hosts`, extensões de browser e telemetria de segurança nativa do Windows (Defender e Firewall).
3. **Concorrência Segura & Anti-Race**: O motor `SentinelWatchdogService` emprega um guardião de concorrência com `asyncio.Lock()` que impede auditorias simultâneas colidentes ou degradação de performance por sobreposição de tarefas.
4. **Contratos Fortemente Tipados & Versionamento de Esquema**: Todos os payloads de telemetria e eventos possuem `schema_version = 1` com validação determinística em TypeScript e Python.

---

## 2. Arquitetura de Componentes

```
┌────────────────────────────────────────────────────────┐
│                   Windows Subsystem                    │
│  (Processes, Sockets, Registry, Tasks, Services, Hosts)│
└──────────────────────────┬─────────────────────────────┘
                           │ 100% Read-Only Extraction
                           ▼
┌────────────────────────────────────────────────────────┐
│                   Baseline Engine                      │
│   - Capture Snapshot (SHA-256 integrity hash)          │
│   - Deterministic Diff (Base vs Current)               │
└──────────────────────────┬─────────────────────────────┘
                           │ BaselineDiff
                           ▼
┌────────────────────────────────────────────────────────┐
│              Event Correlation Engine                  │
│   - Multi-Signal Cross-Layer Correlation               │
│   - Deterministic Fingerprinting                       │
│   - Timeline & Deduplication                           │
│   - Known Good Suppression                             │
└──────────────────────────┬─────────────────────────────┘
                           │ SecurityEvents & Status
                           ▼
┌────────────────────────────────────────────────────────┐
│             Sentinel Watchdog Service                  │
│   - Asyncio Task Loop (Default interval: 60s)          │
│   - Concurrency Lock (asyncio.Lock)                    │
│   - Lifecycle: Start / Stop / Pause / Resume           │
└──────────────────────────┬─────────────────────────────┘
                           │ WebSocket / IPC Broadcast
                           ▼
┌────────────────────────────────────────────────────────┐
│              Frontend / SentinelDashboard              │
│   - Posture Banner (GOOD/MONITORING/ATTENTION/HIGH)    │
│   - Real-Time KPI Cards & Resource Telemetry           │
│   - Processes, Network, Persistence & Extension Tables │
│   - User Explicit "Accept as Known Good" Action        │
└────────────────────────────────────────────────────────┘
```

---

## 3. Contratos de Comunicação e Mensagens WebSocket / IPC

| Tipo de Mensagem | Direção | Propósito |
|---|---|---|
| `sentinel_get_status` | Cliente ➔ Servidor | Solicita telemetria operacional, status do loop, postura de segurança e métricas de CPU/RAM. |
| `sentinel_status` | Servidor ➔ Cliente | Resposta com o payload de status e telemetria do Watchdog. |
| `sentinel_run_audit` | Cliente ➔ Servidor | Dispara uma auditoria imediata protegida pelo lock de concorrência. |
| `sentinel_audit_completed`| Servidor ➔ Cliente | Notificação de auditoria concluída com resumo e duração do scan. |
| `sentinel_event` | Servidor ➔ Cliente | Broadcast em tempo real de uma nova anomalia ou evento correlacionado detetado. |
| `sentinel_get_baseline` | Cliente ➔ Servidor | Solicita o snapshot do baseline ativo com inventário normalizado. |
| `sentinel_baseline` | Servidor ➔ Cliente | Resposta com todos os processos, portas, persistência e extensões do baseline. |
| `sentinel_accept_known_good`| Cliente ➔ Servidor | Ação explícita do utilizador para marcar uma alteração como legítima (*Known Good*). |
| `sentinel_known_good_updated`| Servidor ➔ Cliente | Confirmação de alteração aprovada e supressão de alertas futuros para essa assinatura. |

---

## 4. Estratégia de Deduplicação e Linha do Tempo

Para evitar fadiga de alertas (*alert fatigue*), alterações persistentes que se mantêm ao longo de múltiplos scans **não geram incidentes duplicados a cada 60 segundos**. O Sentinel utiliza uma assinatura determinística:

$$\text{fingerprint} = \text{category} : \text{asset\_key} : \text{anomaly\_type}$$

Quando a mesma anomalia persiste:
1. O evento existente tem o seu contador de ocorrências incrementado (`occurrence_count += 1`).
2. A marca temporal `last_seen` é atualizada.
3. Uma nova entrada é adicionada à `observation_timeline`.
4. O evento mantém o seu estado `OPEN` até resolução ou aprovação explícita como `KnownGoodItem`.

---
type: runbook
domain: devops
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - runbook
  - devops
  - sre
  - performance
  - worker-thrashing
  - cpu-throttling
prerequisites:
  - "[[SLI-SLO Metrics and Error Budgets]]"
  - "[[Healthchecks and Circuit Breakers]]"
related:
  - "[[Adaptive Rate Limiting and Token Bucket with Jitter]]"
  - "[[How to Recover Interrupted Background Workers]]"
used_by:
  - "[[JARVIS MissionRecoveryWatchdog and Crash Recovery]]"
failure_modes:
  - "[[Lesson - SQLite Lock Starvation from Unclosed Readers]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Linux Cgroups v2 CPU Bandwidth Throttling Documentation
    type: PRIMARY_SOURCE
    url: https://docs.kernel.org/admin-guide/cgroup-v2.html
---

# 🛠️ Runbook - How to Recover from Worker Thrashing and CPU Throttling

## 1. Symptoms
- Uso de CPU atinge 100% contínuo no anfitrião.
- Heartbeats do WebSocket atrasam mais de 5 segundos, provocando desconexões repetidas de clientes.
- Múltiplos workers em paralelo competindo pelos mesmos núcleos de CPU (*Worker Thrashing*).

---

## 2. Preconditions
- O JARVIS OS está executando múltiplos agentes ou compilações simultâneas na sandbox.

---

## 3. Diagnosis
1. Executar no terminal:
   ```bash
   # Windows PowerShell
   Get-Process | Sort-Object CPU -Descending | Select-Object -First 5
   ```
2. Verificar se processos órfãos de Node.js, Python ou Playwright estão em loops infinitos consumindo 100% de um núcleo.

---

## 4. Commands / Queries
```bash
# Identificar PIDs de subprocessos fora do pool ativo
ps aux | grep -E "node|python|playwright" | grep -v "server.py"
```

---

## 5. Decision Tree
```
[ Uso de CPU > 95% por mais de 30s? ]
                 |
                 v
   [ Pausar Missões em Background ]
                 |
                 v
   [ Matar Processos Órfãos / Zumbis ]
                 |
                 v
   [ Limitar Concorrência do Swarm (Max Workers = Core_Count / 2) ]
```

---

## 6. Recovery
1. Enviar sinal `SIGTERM` aos processos identificados como órfãos.
2. Reduzir a concorrência de execução do `SwarmOrchestrator` em `agents/swarm.py`.
3. Reiniciar a conexão WebSocket.

---

## 7. Verification
Verificar se o uso de CPU retorna a níveis saudáveis ($< 40\%$) e se o ping de telemetria responde em $< 50\text{ms}$.

---

## 8. Rollback
Se a degradação persistir, reiniciar o daemon principal do backend (`server.py`).

---

## 9. Prevention
Configurar limites de CPU e memória em `sandbox.py` para todos os processos filhos.

---

## 10. Evidence
- Gráficos de telemetria em `telemetry_logs` demonstrando normalização do uso de CPU.

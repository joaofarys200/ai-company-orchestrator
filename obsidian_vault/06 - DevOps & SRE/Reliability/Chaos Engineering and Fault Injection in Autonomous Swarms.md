---
type: concept
domain: devops
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - devops
  - chaos-engineering
  - fault-injection
  - swarm
  - reliability
prerequisites:
  - "[[Google SRE Incident Response and Postmortems]]"
  - "[[JARVIS MissionRecoveryWatchdog and Crash Recovery]]"
related:
  - "[[Healthchecks and Circuit Breakers]]"
  - "[[Safe Rollback and Git Transactional Strategies]]"
used_by:
  - "[[JARVIS System Architecture]]"
failure_modes:
  - "[[Lesson - SQLite Lock Starvation from Unclosed Readers]]"
implementation:
  - "[[JARVIS MissionRecoveryWatchdog and Crash Recovery]]"
sources:
  - title: Principles of Chaos Engineering (Basiri et al., IEEE Software 2016)
    type: PRIMARY_SOURCE
    url: https://principlesofchaos.org/
  - title: Chaos Monkey - Resiliency in the Cloud (Netflix Technology Blog)
    type: PRIMARY_SOURCE
    url: https://netflixtechblog.com/chaos-monkey-released-into-the-wild-803f272a50a
---

# 🐒 Chaos Engineering and Fault Injection in Autonomous Swarms

## 1. Pergunta Central
> *Como provar empiricamente que um enxame de agentes autónomos é capaz de recuperar o estado de missões complexas matando processos aleatoriamente (`kill -9`) durante a escrita em banco de dados e conexões de rede?*

---

## 2. As 4 Etapas da Experimentação de Caos

```
[ 1. Definir o Estado Estável (Steady State) ]
  - Métrica: 100% das missões ativas terminam em COMPLETED ou PAUSED_RECOVERED (nunca estado inconsistente)
                       |
                       v
[ 2. Formular a Hipótese de Falha ]
  - Hipótese: "Se matarmos o processo do agente Devon durante um git commit na sandbox, o MissionRecoveryWatchdog restaurará o workspace sem dados corrompidos em menos de 10 segundos."
                       |
                       v
[ 3. Injetar a Falha no Ambiente de Teste ]
  - Injetação de latência de disco, interrupção forçada com SIGKILL, corrupção de pacotes WebSocket
                       |
                       v
[ 4. Verificar Invariantes e Reforçar Salvaguardas ]
```

---

## 3. Invariantes de Recuperação do JARVIS OS
1. **Invariante de Persistência**: A base SQLite WAL nunca sofre corrupção irrecuperável (`PRAGMA quick_check == 'ok'`).
2. **Invariante de Workspace**: A sandbox sempre coincide com o último snapshot SHA-256 verificado.

---

## 4. Related Concepts
- [[Google SRE Incident Response and Postmortems]]
- [[JARVIS MissionRecoveryWatchdog and Crash Recovery]]
- [[Database Crash Consistency and Recovery]]

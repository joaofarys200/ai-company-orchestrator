---
type: concept
domain: backend-systems
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: advanced
tags:
  - backend
  - distributed-systems
  - consensus
  - raft
  - paxos
prerequisites:
  - "[[Distributed Transactions and Saga Pattern]]"
  - "[[Engenharia_de_Sistemas_Distribuidos_e_Concorrencia]]"
related:
  - "[[Distributed Locks and Fencing Tokens]]"
  - "[[Transactional Outbox Pattern]]"
  - "[[DDIA_Designing_Data_Intensive_Applications_BOK]]"
used_by:
  - "[[JARVIS System Architecture]]"
failure_modes:
  - "[[Database Crash Consistency and Recovery]]"
implementation:
  - "[[JARVIS State Store and Persistence]]"
sources:
  - title: In Search of an Understandable Consensus Algorithm (Ongaro & Ousterhout, Stanford)
    type: PRIMARY_SOURCE
    url: https://raft.github.io/raft.pdf
---

# 🤝 Consenso Distribuido Algoritmo Raft Quorum e Eleicao de Lider

## 1. Pergunta Central
> *Como o algoritmo de consenso distribuído Raft garante quorum e eleição de líder único na presença de partições de rede?*

---

## 2. A Mecânica do Protocolo Raft
O Raft decompõe o problema do consenso distribuído em três subproblemas ortogonais e independentes:

```
[ Estado de um Nó Raft ]
           |
     (Timeout de Eleição)
           v
    [ CANDIDATE ] -- (Obtém Maioria de Votos Q > N/2) --> [ LEADER ]
           ^                                                  |
           | (Descobre Termo Mais Alto)                       | (Heartbeat / Log Append)
           +-------------------- [ FOLLOWER ] <---------------+
```

### 2.1. Eleição de Líder (Leader Election)
- O tempo é dividido em **Termos (Terms)** arbitrados por inteiros sequenciais crescentes ($Term_1, Term_2, \dots$).
- Cada seguidor possui um temporizador de eleição aleatório (*Randomized Election Timeout*, tipicamente $150\text{ms} - 300\text{ms}$).
- Se um seguidor não receber heartbeats do líder antes do timeout expirar, transita para `CANDIDATE`, incrementa o seu termo e envia requisições `RequestVote` a todos os nós.
- Um nó é eleito líder se e somente se obtiver votos da maioria estrita do quorum:
  $$\text{Quorum} \ge \left\lfloor \frac{N}{2} \right\rfloor + 1$$

### 2.2. Replicação de Log (Log Replication)
- O cliente envia todos os comandos de escrita exclusivamente para o **Líder**.
- O Líder anexa o comando ao seu log local e envia RPCs `AppendEntries` em paralelo para todos os seguidores.
- Quando o comando é replicado com sucesso na maioria dos nós ($\ge Q$), o líder aplica a alteração à sua Máquina de Estados Finita local (**Commit**) e responde ao cliente com sucesso.

---

## 3. Segurança e Invariantes do Raft
1. **Election Safety**: No máximo um líder pode ser eleito por termo.
2. **Leader Append-Only**: O líder nunca sobrescreve ou trunca os seus próprios logs; apenas anexa novos registos.
3. **Log Matching Property**: Se dois logs contêm uma entrada com o mesmo índice e termo, então os logs são idênticos em todas as entradas desde o início até esse índice.

---

## 4. Used When
- Em clusters de coordenação distribuída (ex: etcd, Consul, ZooKeeper, CockroachDB).
- Na eleição de líder único (*Single Active Leader*) para orquestradores de agentes em ambientes multi-máquina.

---

## 5. Common Failure Modes
- **Split-Brain**: Se uma partição de rede isolar os nós sem quorum, a partição minoritária não consegue eleger líder nem confirmar escritas (preservando consistência $CP$).
- **Eleições Divididas Repetidas (Split Votes)**: Se múltiplos nós dispararem eleições no mesmo milissegundo. Mitigado por timeouts randomizados com jitter.

---

## 6. Related Concepts
- [[Distributed Locks and Fencing Tokens]]
- [[Distributed Transactions and Saga Pattern]]
- [[DDIA_Designing_Data_Intensive_Applications_BOK]]

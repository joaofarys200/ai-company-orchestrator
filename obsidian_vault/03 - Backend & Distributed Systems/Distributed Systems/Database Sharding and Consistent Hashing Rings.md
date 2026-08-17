---
type: concept
domain: backend-systems
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - backend
  - distributed-systems
  - sharding
  - consistent-hashing
  - database-partitioning
prerequisites:
  - "[[Database Isolation Levels and Phantom Reads in SQLite and Postgres]]"
related:
  - "[[Consensus and Raft Protocol]]"
  - "[[DDIA_Designing_Data_Intensive_Applications_BOK]]"
used_by:
  - "[[JARVIS State Store and Persistence]]"
failure_modes:
  - "[[Database Crash Consistency and Recovery]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Consistent Hashing and Random Trees - Distributed Caching Protocols for Relieving Hot Spots on the World Wide Web (Karger et al., STOC 1997)
    type: PRIMARY_SOURCE
    url: https://dl.acm.org/doi/10.1145/258533.258660
  - title: Dynamo - Amazon's Highly Available Key-value Store (DeCandia et al., SOSP 2007)
    type: PRIMARY_SOURCE
    url: https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf
---

# 🗄️ Database Sharding and Consistent Hashing Rings

## 1. Pergunta Central
> *Como particionar horizontalmente dados de estado de milhões de missões entre múltiplos nós de banco de dados e redistribuir chaves quando nós são adicionados ou removidos sem remapear todas as chaves do sistema?*

---

## 2. O Problema do Hash Módulo Tradicional ($hash(key) \pmod N$)
Com hash módulo tradicional, quando o número de nós $N$ muda de 4 para 5, quase **100% das chaves** são mapeadas para nós diferentes, gerando tempestade de migração e invalidação massiva de cache.

---

## 3. O Anel de Hashing Consistente (Consistent Hashing Ring)

```
                       [ Posição 0 / 2^32 - 1 ]
                              /        \
                    (Nó A)   /          \   (Nó B)
                            |     ● Chave X (Caminha no sentido horário -> Cai no Nó B)
                    (Nó D)   \          /   (Nó C)
                              \        /
```

- Tanto as chaves de dados quanto os nós físicos (ou nós virtuais *vnodes*) são mapeados num anel circular de $0$ a $2^{32}-1$ usando a mesma função hash criptográfica (SHA-256).
- Uma chave é atribuída ao primeiro nó encontrado caminhando no sentido horário no anel.
- **Propriedade Matemática**: Ao adicionar ou remover um nó, **apenas $K/N$ chaves** precisam ser migradas (onde $K$ é o número total de chaves e $N$ é o número de nós).

---

## 4. Related Concepts
- [[Database Isolation Levels and Phantom Reads in SQLite and Postgres]]
- [[Consensus and Raft Protocol]]
- [[DDIA_Designing_Data_Intensive_Applications_BOK]]

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
  - consensus
  - raft
  - joint-consensus
  - membership-changes
prerequisites:
  - "[[Consensus and Raft Protocol]]"
related:
  - "[[Distributed Locks and Fencing Tokens]]"
  - "[[DDIA_Designing_Data_Intensive_Applications_BOK]]"
used_by:
  - "[[JARVIS State Store and Persistence]]"
failure_modes:
  - "[[Database Crash Consistency and Recovery]]"
implementation:
  - "[[JARVIS System Architecture]]"
sources:
  - title: In Search of an Understandable Consensus Algorithm - Section 6: Cluster membership changes (Ongaro & Ousterhout)
    type: PRIMARY_SOURCE
    url: https://raft.github.io/raft.pdf
---

# 🤝 Raft Joint Consensus and Dynamic Membership Changes

## 1. Pergunta Central
> *Como adicionar ou remover nós de um cluster Raft em produção (ex: migrar de 3 nós para 5 nós) sem paragem de serviço e sem permitir que dois líderes concorrentes sejam eleitos durante a fase de transição?*

---

## 2. O Perigo da Troca Direta de Configuração (Split-Brain)
Se a configuração do cluster mudar diretamente de $C_{\text{old}}$ (3 nós: $A, B, C$) para $C_{\text{new}}$ (5 nós: $A, B, C, D, E$), devido a atrasos de rede, nós com $C_{\text{old}}$ podem eleger o nó $A$ (maioria em 3), enquanto nós que já receberam $C_{\text{new}}$ elegem o nó $D$ (maioria em 5), quebrando o invariante de líder único.

---

## 3. O Mecanismo de Consenso Conjunto (Joint Consensus: $C_{\text{old,new}}$)

```
[ Configuração Antiga: C_old ]
              |
              v (Líder propõe entrada de transição no Log)
[ Configuração Conjunta: C_old,new ]
  - Qualquer decisão (eleição ou commit) exige DUAS MAIORIAS INDEPENDENTES:
    1. Maioria dos nós de C_old
    2. Maioria dos nós de C_new
              |
              v (Quando C_old,new é confirmado por ambas as maiorias)
[ Configuração Nova: C_new ] (Transição Concluída com Segurança 100% Garantida)
```

---

## 4. Related Concepts
- [[Consensus and Raft Protocol]]
- [[Distributed Locks and Fencing Tokens]]
- [[Distributed Transactions and Saga Pattern]]

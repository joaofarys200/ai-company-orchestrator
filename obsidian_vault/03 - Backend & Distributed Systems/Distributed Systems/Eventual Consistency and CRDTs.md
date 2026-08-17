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
  - crdt
  - eventual-consistency
  - replication
prerequisites:
  - "[[Engenharia_de_Sistemas_Distribuidos_e_Concorrencia]]"
related:
  - "[[Consensus and Raft Protocol]]"
  - "[[DDIA_Designing_Data_Intensive_Applications_BOK]]"
used_by:
  - "[[JARVIS State Store and Persistence]]"
failure_modes:
  - "[[Database Crash Consistency and Recovery]]"
implementation:
  - "[[JARVIS System Architecture]]"
sources:
  - title: Conflict-free Replicated Data Types (Shapiro et al., INRIA)
    type: PRIMARY_SOURCE
    url: https://inria.hal.science/inria-00555588/document
---

# 🌐 Eventual Consistency and CRDTs

## 1. Pergunta Central
> *Como permitir que múltiplos nós ou utilizadores editem documentos de texto e estados de aplicação offline sem comunicação em tempo real e depois sincronizem os dados de forma determinística sem conflitos de merge manuais?*

---

## 2. Tipos de CRDTs (Conflict-free Replicated Data Types)

1. **State-based CRDTs (CvRDT)**:
   - Os nós enviam os seus estados completos uns aos outros.
   - A convergência é garantida por uma função de junção (*Join / Merge Function*) que forma um semirreticulado superior (*Join-Semilattice*):
     $$\text{merge}(A, B) = A \sqcup B$$
   - A operação de merge deve ser **Associativa**, **Comutativa** e **Idempotente**:
     - Comutativa: $A \sqcup B = B \sqcup A$
     - Associativa: $(A \sqcup B) \sqcup C = A \sqcup (B \sqcup C)$
     - Idempotente: $A \sqcup A = A$

2. **Operation-based CRDTs (CmRDT)**:
   - Os nós enviam operações atómicas comutativas pela rede.

---

## 3. Exemplo Prático: PN-Counter (Positive-Negative Counter)

```python
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class PNCounter:
    node_id: str
    P: Dict[str, int] = field(default_factory=dict)
    N: Dict[str, int] = field(default_factory=dict)

    def increment(self, value: int = 1):
        self.P[self.node_id] = self.P.get(self.node_id, 0) + value

    def decrement(self, value: int = 1):
        self.N[self.node_id] = self.N.get(self.node_id, 0) + value

    def read_value(self) -> int:
        return sum(self.P.values()) - sum(self.N.values())

    def merge(self, other: "PNCounter"):
        """Fusão idempotente e comutativa garantindo convergência exata."""
        all_nodes = set(self.P.keys()).union(other.P.keys()).union(self.N.keys()).union(other.N.keys())
        for node in all_nodes:
            self.P[node] = max(self.P.get(node, 0), other.P.get(node, 0))
            self.N[node] = max(self.N.get(node, 0), other.N.get(node, 0))
```

---

## 4. Related Concepts
- [[Consensus and Raft Protocol]]
- [[Distributed Locks and Fencing Tokens]]
- [[DDIA_Designing_Data_Intensive_Applications_BOK]]

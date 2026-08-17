---
type: concept
domain: software-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: intermediate
tags:
  - software-engineering
  - ddd
  - tactical-patterns
  - aggregates
  - repositories
prerequisites:
  - "[[Clean Architecture and Hexagonal Ports]]"
related:
  - "[[DDD_Domain_Driven_Design_and_Enterprise_Patterns]]"
  - "[[Idempotency in Software Systems]]"
used_by:
  - "[[JARVIS System Architecture]]"
failure_modes:
  - "[[Lesson - Regex Refactoring Syntax Corruption]]"
implementation:
  - "[[JARVIS State Store and Persistence]]"
sources:
  - title: Domain-Driven Design - Tackling Complexity in the Heart of Software (Eric Evans)
    type: PRIMARY_SOURCE
    url: https://www.domainlanguage.com/ddd/
---

# 🏛️ Domain-Driven Design Tactical Patterns

## 1. Pergunta Central
> *Como modelar a lógica de domínio complexa em classes desacopladas que expressam diretamente a Linguagem Ubíqua (Ubiquitous Language) sem se contaminarem com detalhes de banco de dados ou frameworks?*

---

## 2. Blocos Táticos Fundamentais do DDD

```
[ Bounded Context: Gestão de Missões ]
  |
  +---> [ Aggregate Root: Mission ]
  |       - Entity com Identidade Global (`id = "mis-102"`)
  |       - Garante Invariantes de Negócio (ex: transição de status)
  |       - Contém Value Objects (`MissionPriority`, `Budget`)
  |
  +---> [ Value Object: TaskDeadline ]
  |       - Imutável; comparado por valor estrutural (não por ID)
  |
  +---> [ Repository Interface: MissionRepositoryPort ]
  |       - Abstração de persistência orientada a coleções
  |
  +---> [ Domain Event: MissionCompletedEvent ]
          - Publicado quando o agregado atinge um estado final válido
```

---

## 3. Implementação Canônica de Value Object e Aggregate em Python

```python
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True) # Imutabilidade garante semântica de Value Object
class TokenBudget:
    max_input_tokens: int
    max_output_tokens: int

    def __post_init__(self):
        if self.max_input_tokens <= 0 or self.max_output_tokens <= 0:
            raise ValueError("Token budgets devem ser estritamente positivos.")

class MissionAggregate:
    def __init__(self, mission_id: str, title: str, budget: TokenBudget):
        self.id = mission_id
        self.title = title
        self.budget = budget
        self.status = "PENDING"
        self._events: List[str] = []

    def start_execution(self):
        if self.status != "PENDING":
            raise ValueError(f"Não é possível iniciar missão no estado {self.status}")
        self.status = "IN_PROGRESS"
        self._events.append("MISSION_STARTED")
```

---

## 4. Related Concepts
- [[Clean Architecture and Hexagonal Ports]]
- [[DDD_Domain_Driven_Design_and_Enterprise_Patterns]]
- [[Idempotency in Software Systems]]

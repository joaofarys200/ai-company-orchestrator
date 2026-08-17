---
type: concept
domain: software-engineering
difficulty: intermediate
tags:
  - software-engineering
  - architecture
  - clean-architecture
  - hexagonal
  - ports-and-adapters
status: verified
---

# 🏛️ Clean Architecture and Hexagonal Ports

## 1. Definição & A Regra de Dependência
A **Clean Architecture** (Arquitetura Limpa - Robert C. Martin) e a **Arquitetura Hexagonal / Ports & Adapters** (Alistair Cockburn) são estilos arquiteturais cujo princípio inviolável é a **Regra da Dependência**:

> *O código-fonte de camadas internas NUNCA deve depender de elementos de camadas externas. Dependências apontam exclusivamente para o centro (para o Domínio).*

```
           +-------------------------------------------------------+
           | Frameworks & Drivers (FastAPI, SQLite, UI, CLI)       |
           |   +-----------------------------------------------+   |
           |   | Interface Adapters (Controllers, Repositories)|   |
           |   |   +---------------------------------------+   |   |
           |   |   | Application Business Rules (UseCases) |   |   |
           |   |   |   +-------------------------------+   |   |   |
           |   |   |   | Enterprise Domain (Entities)  |   |   |   |
           |   |   |   +-------------------------------+   |   |   |
           |   |   +---------------------------------------+   |   |
           |   +-----------------------------------------------+   |
           +-------------------------------------------------------+
```

---

## 2. Portas e Adaptadores (Ports & Adapters)

- **Port (Porta - Interface Abstrata)**: Define o contrato exigido pelo UseCase (ex: `MissionRepositoryPort`, `ModelClientPort`).
- **Adapter (Adaptador - Implementação Concreta)**: Implementa a porta usando uma tecnologia específica (ex: `SQLiteMissionRepository`, `GeminiModelClient`).

### Exemplo em Python

```python
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass

# 1. DOMÍNIO (Entidade pura, sem dependências de frameworks)
@dataclass
class Mission:
    id: str
    title: str
    status: str

# 2. PORTA (Contrato abstrato definido pela camada de aplicação)
class MissionRepositoryPort(ABC):
    @abstractmethod
    async def get_by_id(self, mission_id: str) -> Optional[Mission]:
        pass

    @abstractmethod
    async def save(self, mission: Mission) -> None:
        pass

# 3. USE CASE (Lógica de aplicação dependendo apenas da porta)
class CompleteMissionUseCase:
    def __init__(self, repo: MissionRepositoryPort):
        self.repo = repo

    async def execute(self, mission_id: str) -> None:
        mission = await self.repo.get_by_id(mission_id)
        if not mission:
            raise ValueError("Missão não encontrada")
        mission.status = "COMPLETED"
        await self.repo.save(mission)

# 4. ADAPTER (Implementação concreta de infraestrutura)
class SQLiteMissionAdapter(MissionRepositoryPort):
    def __init__(self, db_connection):
        self.db = db_connection

    async def get_by_id(self, mission_id: str) -> Optional[Mission]:
        row = await self.db.fetch_one("SELECT id, title, status FROM missions WHERE id = ?", (mission_id,))
        return Mission(id=row[0], title=row[1], status=row[2]) if row else None

    async def save(self, mission: Mission) -> None:
        await self.db.execute("INSERT OR REPLACE INTO missions (id, title, status) VALUES (?, ?, ?)",
                             (mission.id, mission.title, mission.status))
```

---

## 3. Benefícios para Agentes Autónomos
1. **Testabilidade Absoluta**: O agente pode testar toda a lógica de negócio unitariamente injetando mocks nas portas, sem precisar subir servidores ou bases de dados reais.
2. **Substituibilidade Tecnológica**: Se o sistema migrar de SQLite para PostgreSQL ou de Gemini para Ollama, apenas o Adapter muda; a camada de aplicação permanece intocada.

---

## 4. Related Concepts
- [[DDD_Domain_Driven_Design_and_Enterprise_Patterns]]
- [[Engenharia_de_Software_e_Arquitetura_Clean_Code]]
- [[Unit Tests vs End-to-End Tests in Agent Validation]]
- [[Idempotency in Software Systems]]

---

## 5. Sources
- *Robert C. Martin - Clean Architecture: A Craftsman's Guide to Software Structure and Design*
- *Alistair Cockburn - Hexagonal Architecture (Ports and Adapters)*: https://alistair.cockburn.us/hexagonal-architecture/

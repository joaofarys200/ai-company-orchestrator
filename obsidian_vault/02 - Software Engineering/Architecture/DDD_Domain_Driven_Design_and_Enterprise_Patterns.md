---
type: concept
domain: software-engineering
difficulty: advanced
tags:
  - software-engineering
  - ddd
  - architecture
status: verified
---

# ðŸ° DDD BOK â€” Domain-Driven Design & Enterprise Architecture Patterns

## ðŸ“Œ 1. VisÃ£o Geral
Este volume compila a metodologia de **Domain-Driven Design (DDD)** desenvolvida por Eric Evans e Martin Fowler para governar a modelaÃ§Ã£o de software complexo no **JARVIS OS**.

---

## ðŸ—£ï¸ 2. Linguagem UbÃ­qua & Contextos Delimitados (Bounded Contexts)

### 2.1. Linguagem UbÃ­qua (Ubiquitous Language)
- Todo o cÃ³digo (nomes de classes, variÃ¡veis, mÃ©todos, ficheiros), documentaÃ§Ã£o e especificaÃ§Ãµes utilizam rigorosamente a mesma terminologia do domÃ­nio do utilizador/negÃ³cio.
- Evitar nomes genÃ©ricos ou ambÃ­guos como `Manager`, `Processor`, `DataHolder`.

### 2.2. Contextos Delimitados (Bounded Contexts)
- Cada subsistema (ex: *Model Harness*, *Workspace Analytics*, *Voice Runtime*) define a sua prÃ³pria fronteira de modelo e vocabulÃ¡rio.
- **Anti-Corruption Layer (ACL)**: Quando dois contextos delimitados precisam de comunicar, uma camada de traduÃ§Ã£o (ACL) isola o modelo interno de contaminaÃ§Ã£o por modelos externos.

---

## ðŸ§± 3. Blocos de ConstruÃ§Ã£o TÃ¡ticos do DDD

```
                  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                  â”‚          ENTIDADE (Entity)          â”‚
                  â”‚  Possui ID Ãºnico e ciclo de vida    â”‚
                  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                     â”‚
         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
         â–¼                           â–¼                           â–¼
  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”             â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”             â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
  â”‚ AGREGADO    â”‚             â”‚ VALUE OBJECTâ”‚             â”‚ EVENTO DE   â”‚
  â”‚ (Aggregate) â”‚             â”‚ (ImutÃ¡vel)  â”‚             â”‚ DOMÃNIO     â”‚
  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜             â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜             â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

1. **Entidades (Entities)**: Objetos definidos por uma identidade Ãºnica imutÃ¡vel que persiste ao longo do tempo (ex: `ProjectContext(project_id="proj_123")`).
2. **Value Objects**: Objetos imutÃ¡veis sem identidade prÃ³pria, definidos unicamente pelos seus atributos (ex: `MetricSample(value=98.5, timestamp=1700000000)`).
3. **Agregados (Aggregates)**: Grupo de entidades e Value Objects ligados por uma raiz (*Aggregate Root*) que garante invariantes de consistÃªncia estritos em cada transaÃ§Ã£o.
4. **RepositÃ³rios (Repositories)**: Interfaces que abstraem a persistÃªncia e recuperaÃ§Ã£o de agregados do disco ou base de dados.


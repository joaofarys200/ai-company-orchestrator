# 🏰 DDD BOK — Domain-Driven Design & Enterprise Architecture Patterns

## 📌 1. Visão Geral
Este volume compila a metodologia de **Domain-Driven Design (DDD)** desenvolvida por Eric Evans e Martin Fowler para governar a modelação de software complexo no **JARVIS OS**.

---

## 🗣️ 2. Linguagem Ubíqua & Contextos Delimitados (Bounded Contexts)

### 2.1. Linguagem Ubíqua (Ubiquitous Language)
- Todo o código (nomes de classes, variáveis, métodos, ficheiros), documentação e especificações utilizam rigorosamente a mesma terminologia do domínio do utilizador/negócio.
- Evitar nomes genéricos ou ambíguos como `Manager`, `Processor`, `DataHolder`.

### 2.2. Contextos Delimitados (Bounded Contexts)
- Cada subsistema (ex: *Model Harness*, *Workspace Analytics*, *Voice Runtime*) define a sua própria fronteira de modelo e vocabulário.
- **Anti-Corruption Layer (ACL)**: Quando dois contextos delimitados precisam de comunicar, uma camada de tradução (ACL) isola o modelo interno de contaminação por modelos externos.

---

## 🧱 3. Blocos de Construção Táticos do DDD

```
                  ┌─────────────────────────────────────┐
                  │          ENTIDADE (Entity)          │
                  │  Possui ID único e ciclo de vida    │
                  └──────────────────┬──────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
  ┌─────────────┐             ┌─────────────┐             ┌─────────────┐
  │ AGREGADO    │             │ VALUE OBJECT│             │ EVENTO DE   │
  │ (Aggregate) │             │ (Imutável)  │             │ DOMÍNIO     │
  └─────────────┘             └─────────────┘             └─────────────┘
```

1. **Entidades (Entities)**: Objetos definidos por uma identidade única imutável que persiste ao longo do tempo (ex: `ProjectContext(project_id="proj_123")`).
2. **Value Objects**: Objetos imutáveis sem identidade própria, definidos unicamente pelos seus atributos (ex: `MetricSample(value=98.5, timestamp=1700000000)`).
3. **Agregados (Aggregates)**: Grupo de entidades e Value Objects ligados por uma raiz (*Aggregate Root*) que garante invariantes de consistência estritos em cada transação.
4. **Repositórios (Repositories)**: Interfaces que abstraem a persistência e recuperação de agregados do disco ou base de dados.

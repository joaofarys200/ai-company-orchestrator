---
type: concept
domain: software-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: intermediate
tags:
  - software-engineering
  - solid
  - clean-code
  - metrics
  - refactoring
prerequisites:
  - "[[Engenharia_de_Software_e_Arquitetura_Clean_Code]]"
related:
  - "[[Clean Architecture and Hexagonal Ports]]"
  - "[[Compiler Feedback and Test-Driven Self-Repair]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Lesson - Regex Refactoring Syntax Corruption]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Clean Code - A Handbook of Agile Software Craftsmanship (Robert C. Martin)
    type: PRIMARY_SOURCE
    url: https://en.wikipedia.org/wiki/Robert_C._Martin
---

# 🧼 SOLID Principles and Clean Code Metrics

## 1. Pergunta Central
> *Quais métricas quantitativas (Complexidade Ciclomática, Acoplamento Aferente/Eferente e Instabilidade) permitem que agentes de código meçam e preservem a manutenibilidade do software?*

---

## 2. Princípios SOLID & Métricas Quantitativas

| Princípio | Definição Operacional | Métrica de Qualidade Alvo |
|---|---|---|
| **S - Single Responsibility** | Um módulo deve ter apenas um motivo para mudar | Linhas por Função $\le 40$; Métodos por Classe $\le 10$ |
| **O - Open/Closed** | Aberto para extensão, fechado para modificação | Extensão via Herança/Polimorfismo sem tocar código base |
| **L - Liskov Substitution** | Subclasses devem ser substituíveis pelas suas classes base | Pré-condições não fortalecidas; Pós-condições não enfraquecidas |
| **I - Interface Segregation** | Clientes não devem depender de métodos que não usam | Interfaces com $\le 4$ métodos especializados |
| **D - Dependency Inversion** | Dependa de abstrações, não de implementações | Acoplamento Eferente ($C_e$) direcionado para interfaces abstratas |

---

## 3. Fórmula da Complexidade Ciclomática de McCabe
A Complexidade Ciclomática ($M$) mede o número de caminhos linearmente independentes no grafo de fluxo de controlo de uma função:

$$M = E - N + 2P$$
- $E$: Número de arestas no CFG.
- $N$: Número de nós.
- $P$: Componentes conexos ($P = 1$ para uma única função).

**Limiar de Qualidade**: Funções com $M > 10$ são rejeitadas pelo agente de qualidade Quinn e exigem refatoração imediata.

---

## 4. Related Concepts
- [[Clean Architecture and Hexagonal Ports]]
- [[Control Flow Graph (CFG) and Static Analysis]]
- [[Engenharia_de_Software_e_Arquitetura_Clean_Code]]

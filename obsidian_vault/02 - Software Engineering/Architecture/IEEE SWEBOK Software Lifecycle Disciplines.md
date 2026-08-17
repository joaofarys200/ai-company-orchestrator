---
type: concept
domain: software-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: advanced
tags:
  - software-engineering
  - swebok
  - ieee
  - lifecycle
  - requirements
prerequisites:
  - "[[SWEBOK_Software_Engineering_Body_of_Knowledge]]"
related:
  - "[[Clean Architecture and Hexagonal Ports]]"
  - "[[Unit Tests vs End-to-End Tests in Agent Validation]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Lesson - Regex Refactoring Syntax Corruption]]"
implementation:
  - "[[JARVIS System Architecture]]"
sources:
  - title: IEEE Computer Society - Guide to the Software Engineering Body of Knowledge (SWEBOK v4)
    type: PRIMARY_SOURCE
    url: https://www.computer.org/education/bodies-of-knowledge/software-engineering
---

# 📚 IEEE SWEBOK Software Lifecycle Disciplines

## 1. Pergunta Central
> *Quais são as disciplinas formais de engenharia de software preconizadas pelo IEEE que governam a elicitação de requisitos, design, construção, testes e manutenção em sistemas autónomos?*

---

## 2. As Áreas de Conhecimento Fundamentais (KAs)

```
[ Requisitos de Software ]
           | (SRS com Critérios de Aceitação)
           v
   [ Design & Arquitetura ]
           | (Diagramas de Componentes / Portas)
           v
 [ Construção de Software ]
           | (TDD, AST, Refatoração Segura)
           v
     [ Testes de Software ]
           | (Pirâmide de Testes: Unit, Integration, E2E)
           v
 [ Manutenção & Evolução ]
```

---

## 3. Critérios de Rastreabilidade Bidirecional
Todo o requisito funcional elicitado pela Clara deve mapear para:
1. Pelo menos um teste unitário automatizado no Quinn;
2. Pelo menos um commit ou patch atómico gerado pelo Devon;
3. Documentação técnica e runbook no cofre Obsidian.

---

## 4. Related Concepts
- [[SWEBOK_Software_Engineering_Body_of_Knowledge]]
- [[Clean Architecture and Hexagonal Ports]]
- [[Unit Tests vs End-to-End Tests in Agent Validation]]

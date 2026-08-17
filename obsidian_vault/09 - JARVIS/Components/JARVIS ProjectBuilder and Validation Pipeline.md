---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
difficulty: advanced
tags:
  - jarvis
  - project-builder
  - validation-pipeline
  - prevalidation
  - flight-recorder
prerequisites:
  - "[[Compiler Feedback and Test-Driven Self-Repair]]"
  - "[[Unit Tests vs End-to-End Tests in Agent Validation]]"
related:
  - "[[JARVIS PatchEngine and CodingSession Architecture]]"
  - "[[CI-CD Pipeline Failure Triage and Automated Healing]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Lesson - Regex Refactoring Syntax Corruption]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: JARVIS Codebase - ProjectBuilder and Validation Pipeline Test Suites
    type: JARVIS_INTERNAL
    url: internal://tests/test_project_builder.py
---

# ðŸ—ï¸ JARVIS ProjectBuilder and Validation Pipeline

## 1. Purpose
O `ProjectBuilder` Ã© o mÃ³dulo responsÃ¡vel por transformar intenÃ§Ãµes de desenvolvimento e planos estruturados em projetos completos e executÃ¡veis dentro da sandbox, gerindo compilaÃ§Ã£o, instalaÃ§Ã£o de pacotes e validaÃ§Ã£o em mÃºltiplos estÃ¡gios.

---

## 2. Responsibilities
- Inicializar a estrutura de diretÃ³rios e ficheiros de configuraÃ§Ã£o (`package.json`, `requirements.txt`, `vite.config.js`).
- Executar pipelines de prÃ©-validaÃ§Ã£o antes da entrega de cÃ³digo final ao utilizador.
- Gravar o histÃ³rico completo de aÃ§Ãµes no Flight Recorder para reproduÃ§Ã£o determinÃ­stica de builds.
- Integrar com o linter e suite de testes de aceitaÃ§Ã£o.

---

## 3. Inputs & Outputs
- **Inputs**: EspecificaÃ§Ã£o funcional da aplicaÃ§Ã£o, templates de projeto, dependÃªncias.
- **Outputs**: AplicaÃ§Ã£o funcional construÃ­da, servidor de preview ativo, log de execuÃ§Ã£o de testes.

---

## 4. State Management & Invariants
- Nenhum projeto Ã© marcado como `VALIDATED` se o processo de build ou o teste de fumaÃ§a inicial falhar.

---

## 5. Dependencies
- [`sandbox.py`](file:///c:/Users/joaor/Desktop/JarvisOS/sandbox.py)
- [`workspace_policy.py`](file:///c:/Users/joaor/Desktop/JarvisOS/workspace_policy.py)

---

## 6. Failure Modes & Recovery
- **Failure**: Falha na instalaÃ§Ã£o de dependÃªncias npm/pip ou conflitos de versÃ£o.
- **Recovery**: Triage de log pelo agente Quinn com sugestÃ£o de pinagem de versÃ£o compatÃ­vel.

---

## 7. Security Boundaries
- InstalaÃ§Ã£o e execuÃ§Ã£o ocorrem estritamente dentro do diretÃ³rio do projeto na sandbox sem acesso de escrita a outros projetos.

---

## 8. Evidence Produced & Tests
- **Evidence**: Registo de logs de build no Flight Recorder (`.flight_recorder.json`).
- **Tests**: `tests/test_project_builder.py`, `tests/test_project_builder_flight_recorder.py`.

---

## 9. Related Concepts
- [[CI-CD Pipeline Failure Triage and Automated Healing]]
- [[Docker Container Security and Resource Capping]]
- [[JARVIS Component Architecture]]


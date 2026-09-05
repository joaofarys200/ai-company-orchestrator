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
O `ProjectBuilder` é o módulo responsável por transformar intenções de desenvolvimento e planos estruturados em projetos completos e executáveis dentro da sandbox, gerindo compilação, instalação de pacotes e validação em múltiplos estágios.

---

## 2. Responsibilities
- Inicializar a estrutura de diretórios e ficheiros de configuração (`package.json`, `requirements.txt`, `vite.config.js`).
- Executar pipelines de pré-validação antes da entrega de código final ao utilizador.
- Gravar o histórico completo de ações no Flight Recorder para reprodução determinística de builds.
- Integrar com o linter e suite de testes de aceitação.

---

## 3. Inputs & Outputs
- **Inputs**: Especificação funcional da aplicação, templates de projeto, dependências.
- **Outputs**: Aplicação funcional construída, servidor de preview ativo, log de execução de testes.

---

## 4. State Management & Invariants
- Nenhum projeto é marcado como `VALIDATED` se o processo de build ou o teste de fumaça inicial falhar.

---

## 5. Dependencies
- [`sandbox.py`](file:///c:/Users/joaor/Desktop/JarvisOS/sandbox.py)
- [`workspace_policy.py`](file:///c:/Users/joaor/Desktop/JarvisOS/workspace_policy.py)

---

## 6. Failure Modes & Recovery
- **Failure**: Falha na instalação de dependências npm/pip ou conflitos de versão.
- **Recovery**: Triage de log pelo agente Quinn com sugestão de pinagem de versão compatível.

---

## 7. Security Boundaries
- Instalação e execução ocorrem estritamente dentro do diretório do projeto na sandbox sem acesso de escrita a outros projetos.

---

## 8. Evidence Produced & Tests
- **Evidence**: Registo de logs de build no Flight Recorder (`.flight_recorder.json`).
- **Tests**: `tests/test_project_builder.py`, `tests/test_project_builder_flight_recorder.py`.

---

## 9. Related Concepts
- [[CI-CD Pipeline Failure Triage and Automated Healing]]
- [[Docker Container Security and Resource Capping]]
- [[JARVIS Component Architecture]]


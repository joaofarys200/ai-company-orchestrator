---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
difficulty: advanced
tags:
  - jarvis
  - project-builder
  - dependency-resolution
  - npm
  - pip
  - flight-recorder
prerequisites:
  - "[[JARVIS ProjectBuilder and Validation Pipeline]]"
  - "[[Coding Agent Failure Mode and Recovery Matrix]]"
related:
  - "[[Patch Generation and Safe Application]]"
  - "[[Compiler Feedback and Test-Driven Self-Repair]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[How to Diagnose Python Import and Module Resolution Failures]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: JARVIS Codebase - ProjectBuilder and Dependency Resolution Tests
    type: JARVIS_INTERNAL
    url: internal://tests/test_project_builder.py
---

# 📦 JARVIS ProjectBuilder Dependency Resolution Engine

## 1. Purpose
O motor de resolução de dependências do `ProjectBuilder` inspeciona a árvore de arquivos gerada pelo agente Devon, detecta imports ausentes ou pacotes não instalados e orquestra a resolução segura e determinística de dependências Python (`requirements.txt`, `pyproject.toml`) e Node.js (`package.json`).

---

## 2. Responsibilities
- Analisar via AST todos os arquivos do projeto para extrair módulos de terceiros importados.
- Cruzar a lista de imports com o ambiente de execução local e identificar pacotes faltantes.
- Gerar arquivos de manifesto de dependências com versões congeladas (*Lockfiles* / Pins).
- Executar a instalação em modo isolado na sandbox com verificação de integridade SHA-256 dos wheels/tarballs.
- Gravar no *Flight Recorder* todas as saídas de compilação de pacotes C/Rust nativos.

---

## 3. Inputs & Outputs
- **Inputs**: Árvore de código fonte na sandbox, arquivos de manifesto (`package.json`, `requirements.txt`).
- **Outputs**: Ambiente de runtime preparado, lockfiles gerados, relatório de resolução de dependências.

---

## 4. Dependencies
- [`tests/test_project_builder.py`](file:///c:/Users/joaor/Desktop/JarvisOS/tests/test_project_builder.py)
- [`sandbox.py`](file:///c:/Users/joaor/Desktop/JarvisOS/sandbox.py)

---

## 5. Failure Modes & Recovery
- **Failure**: Conflito de versões de dependências transitivas (*Dependency Hell*).
- **Recovery**: O RHO captura o erro do pip/npm e executa resolução com árvore de restrições relaxadas.

---

## 6. Related Concepts
- [[JARVIS ProjectBuilder and Validation Pipeline]]
- [[Coding Agent Failure Mode and Recovery Matrix]]
- [[How to Diagnose Python Import and Module Resolution Failures]]

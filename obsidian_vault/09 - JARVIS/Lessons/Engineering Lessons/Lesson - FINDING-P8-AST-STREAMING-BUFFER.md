---
title: Lesson - FINDING-P8-AST-STREAMING-BUFFER
component: agents/patch_engine.py
provenance: JARVIS_INTERNAL
tags: [self-healing, patch-engine, phase-8]
---

# Failure
Alocação excessiva de memória durante patching concorrente de grandes ficheiros AST.

# Root Cause
Buffers de tokens não geradores retidos em memória durante a fase de transação.

# Corrective Action
Implementado streaming lazy de nós AST via geradores Python.

# Generalizable Principle
Sempre utilizar geradores e chunking preguiçoso em processamento de código estruturado.

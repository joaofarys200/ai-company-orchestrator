---
type: lesson
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
difficulty: intermediate
tags:
  - lesson
  - jarvis
  - rag
  - bm25
  - lexical-pollution
  - retrieval
prerequisites:
  - "[[RAG Architecture and Retrieval Strategies]]"
related:
  - "[[Vector Indexes - HNSW and Approximate Nearest Neighbor Partitioning]]"
  - "[[JARVIS Obsidian Tools and RAG System]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Hallucination Mitigation Techniques]]"
implementation:
  - "[[JARVIS Obsidian Tools and RAG System]]"
sources:
  - title: JARVIS Codebase - agents/obsidian_tools.py scoring investigation
    type: JARVIS_INTERNAL
    url: internal://agents/obsidian_tools.py
---

# ðŸ“ Lesson - Low-Score BM25 Pollution in Short Semantic Queries

## Failure
Em queries RAG curtas (ex: "como tratar erros"), o algoritmo léxico BM25 recuperava notas genéricas com centenas de ocorrências da palavra "erros" (como grandes monografias de sistemas distribuídos) em detrimento do runbook específico de tratamento de saídas malformadas, poluindo o contexto do modelo.

---

## Symptoms
- O agente Devon recebia chunks de 10k tokens de teoria geral em vez do passo a passo do runbook.
- Degradação do tempo de resposta (TTFT) e respostas evasivas.

---

## Detection
Auditoria de recuperação RAG em `tests/test_obsidian_tools.py` revelou pontuação artificialmente inflada por contagem bruta de termos.

---

## Root Cause
O ranqueamento léxico puro sem peso específico para correspondência no título da nota ou no frontmatter favorecia arquivos com tamanho massivo de texto.

---

## Why Existing Protection Failed
Não havia normalização por tamanho do documento nem ponderação de bÃ´nus por casamento exato no título da nota.

---

## Blast Radius
Injeção de contexto irrelevante em todos os agentes que consultavam o cofre Obsidian para resolução rápida de incidentes.

---

## Recovery
Ajustar o threshold de corte e priorizar correspondência de tags e títulos no algoritmo de score em `agents/obsidian_tools.py`.

---

## Corrective Action
Implementar bÃ´nus de $+15$ pontos para correspondência no título do arquivo e $+10$ pontos para termos encontrados no bloco YAML de tags.

---

## Preventive Control
Adicionar testes de regressão de ranking semântico com queries curtas e polissêmicas no benchmark contínuo do RAG.

---

## Generalizable Principle
> *Em sistemas RAG híbridos para bases de engenharia, a correspondência no título canÃ´nico da nota e nos metadados estruturados deve sempre sobrepujar a frequência pura de termos em monografias extensas.*

---

## Tests
- `tests/test_obsidian_tools.py::test_rag_search_relevance`

---

## Related Concepts
- [[RAG Architecture and Retrieval Strategies]]
- [[Vector Indexes - HNSW and Approximate Nearest Neighbor Partitioning]]
- [[Context Engineering and Compression]]

---

## Related Runbooks
- [[How to Handle Malformed Model Output]]

---

## Evidence
- Métrica de score no script de benchmark do cofre.


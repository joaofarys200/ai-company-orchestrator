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
Em queries RAG curtas (ex: "como tratar erros"), o algoritmo lÃ©xico BM25 recuperava notas genÃ©ricas com centenas de ocorrÃªncias da palavra "erros" (como grandes monografias de sistemas distribuÃ­dos) em detrimento do runbook especÃ­fico de tratamento de saÃ­das malformadas, poluindo o contexto do modelo.

---

## Symptoms
- O agente Devon recebia chunks de 10k tokens de teoria geral em vez do passo a passo do runbook.
- DegradaÃ§Ã£o do tempo de resposta (TTFT) e respostas evasivas.

---

## Detection
Auditoria de recuperaÃ§Ã£o RAG em `tests/test_obsidian_tools.py` revelou pontuaÃ§Ã£o artificialmente inflada por contagem bruta de termos.

---

## Root Cause
O ranqueamento lÃ©xico puro sem peso especÃ­fico para correspondÃªncia no tÃ­tulo da nota ou no frontmatter favorecia arquivos com tamanho massivo de texto.

---

## Why Existing Protection Failed
NÃ£o havia normalizaÃ§Ã£o por tamanho do documento nem ponderaÃ§Ã£o de bÃ´nus por casamento exato no tÃ­tulo da nota.

---

## Blast Radius
InjeÃ§Ã£o de contexto irrelevante em todos os agentes que consultavam o cofre Obsidian para resoluÃ§Ã£o rÃ¡pida de incidentes.

---

## Recovery
Ajustar o threshold de corte e priorizar correspondÃªncia de tags e tÃ­tulos no algoritmo de score em `agents/obsidian_tools.py`.

---

## Corrective Action
Implementar bÃ´nus de $+15$ pontos para correspondÃªncia no tÃ­tulo do arquivo e $+10$ pontos para termos encontrados no bloco YAML de tags.

---

## Preventive Control
Adicionar testes de regressÃ£o de ranking semÃ¢ntico com queries curtas e polissÃªmicas no benchmark contÃ­nuo do RAG.

---

## Generalizable Principle
> *Em sistemas RAG hÃ­bridos para bases de engenharia, a correspondÃªncia no tÃ­tulo canÃ´nico da nota e nos metadados estruturados deve sempre sobrepujar a frequÃªncia pura de termos em monografias extensas.*

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
- MÃ©trica de score no script de benchmark do cofre.


---
type: comparison
domain: ai-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - ai-engineering
  - rag
  - comparison
  - bm25
  - vector-embeddings
  - hybrid-rag
prerequisites:
  - "[[RAG Architecture and Retrieval Strategies]]"
  - "[[Vector Indexes - HNSW and Approximate Nearest Neighbor Partitioning]]"
related:
  - "[[Semantic Caching for LLM Responses and Invalidation Strategies]]"
  - "[[Context Engineering and Compression]]"
used_by:
  - "[[JARVIS Obsidian Tools and RAG System]]"
failure_modes:
  - "[[Lesson - Low-Score BM25 Pollution in Short Semantic Queries]]"
implementation:
  - "[[JARVIS Obsidian Tools and RAG System]]"
sources:
  - title: Dense Passage Retrieval for Open-Domain Question Answering (Karpukhin et al., EMNLP 2020)
    type: PRIMARY_SOURCE
    url: https://arxiv.org/abs/2004.04906
  - title: Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods (Cormack et al., SIGIR 2009)
    type: PRIMARY_SOURCE
    url: https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
---

# âš–ï¸ Comparison: Lexical BM25 vs Dense Vector Embeddings vs Hybrid RAG

## 1. Tabela Comparativa de Motores de Recuperação

| Dimensão | BM25 Léxico Tradicional | Embeddings Densos Vetoriais | RAG Híbrido com RRF (Reciprocal Rank Fusion) |
|---|---|---|---|
| **Busca de Símbolos Exatos (IDs/Nomes de Função)** | **Perfeita ($100\%$ de precisão em nomes raros)** | Pobre (Muitas vezes confunde `get_user` com `fetch_account`) | **Excelente (Preserva correspondência exata de tokens)** |
| **Compreensão Semântica e SinÃ´nimos** | Nula (Falha se a query usar palavras diferentes) | **Excelente (Mapeia conceitos semanticamente próximos)** | **Excelente (Combina significado semântico com palavras-chave)** |
| **Infraestrutura e Custo** | **Zero GPUs, CPU pura ultrarrápida** | Requer modelo de embedding e índice HNSW | Requer modelo de embedding + motor léxico leve |
| **Resiliência a Queries Fora de Domínio** | Alta (Não alucina similaridade falsa) | Média (Pode retornar vizinho mais próximo mesmo irrelevante) | **Máxima (Pontuação combinada com threshold de corte)** |

---

## 2. Decisão de Engenharia para o JARVIS

### When should JARVIS choose BM25?
- Ao buscar símbolos exatos de código, identificadores de erro ou nomes de arquivos (`MissionStateStore`, `EADDRINUSE`).

### When should JARVIS choose Dense Vector Embeddings?
- Ao buscar conceitos de alto nível ou perguntas conceituais abertas ("Como funciona o ciclo de vida do agente?").

### When should JARVIS choose Hybrid RAG com RRF?
- Na memória principal do cofre Obsidian (`agents/obsidian_tools.py`), garantindo que tanto termos técnicos exatos quanto intenções conceituais sejam encontrados com precisão.

### What failure mode does each introduce?
- **BM25**: Cegueira a sinÃ´nimos e paráfrases.
- **Dense Vectors**: Falsos positivos com distâncias curtas para conceitos não-relacionados.
- **Hybrid RAG**: Maior complexidade na calibração de pesos de ranqueamento.

---

## 3. Related Concepts
- [[RAG Architecture and Retrieval Strategies]]
- [[Vector Indexes - HNSW and Approximate Nearest Neighbor Partitioning]]
- [[Lesson - Low-Score BM25 Pollution in Short Semantic Queries]]


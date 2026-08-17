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

## 1. Tabela Comparativa de Motores de RecuperaÃ§Ã£o

| DimensÃ£o | BM25 LÃ©xico Tradicional | Embeddings Densos Vetoriais | RAG HÃ­brido com RRF (Reciprocal Rank Fusion) |
|---|---|---|---|
| **Busca de SÃ­mbolos Exatos (IDs/Nomes de FunÃ§Ã£o)** | **Perfeita ($100\%$ de precisÃ£o em nomes raros)** | Pobre (Muitas vezes confunde `get_user` com `fetch_account`) | **Excelente (Preserva correspondÃªncia exata de tokens)** |
| **CompreensÃ£o SemÃ¢ntica e SinÃ´nimos** | Nula (Falha se a query usar palavras diferentes) | **Excelente (Mapeia conceitos semanticamente prÃ³ximos)** | **Excelente (Combina significado semÃ¢ntico com palavras-chave)** |
| **Infraestrutura e Custo** | **Zero GPUs, CPU pura ultrarrÃ¡pida** | Requer modelo de embedding e Ã­ndice HNSW | Requer modelo de embedding + motor lÃ©xico leve |
| **ResiliÃªncia a Queries Fora de DomÃ­nio** | Alta (NÃ£o alucina similaridade falsa) | MÃ©dia (Pode retornar vizinho mais prÃ³ximo mesmo irrelevante) | **MÃ¡xima (PontuaÃ§Ã£o combinada com threshold de corte)** |

---

## 2. DecisÃ£o de Engenharia para o JARVIS

### When should JARVIS choose BM25?
- Ao buscar sÃ­mbolos exatos de cÃ³digo, identificadores de erro ou nomes de arquivos (`MissionStateStore`, `EADDRINUSE`).

### When should JARVIS choose Dense Vector Embeddings?
- Ao buscar conceitos de alto nÃ­vel ou perguntas conceituais abertas ("Como funciona o ciclo de vida do agente?").

### When should JARVIS choose Hybrid RAG com RRF?
- Na memÃ³ria principal do cofre Obsidian (`agents/obsidian_tools.py`), garantindo que tanto termos tÃ©cnicos exatos quanto intenÃ§Ãµes conceituais sejam encontrados com precisÃ£o.

### What failure mode does each introduce?
- **BM25**: Cegueira a sinÃ´nimos e parÃ¡frases.
- **Dense Vectors**: Falsos positivos com distÃ¢ncias curtas para conceitos nÃ£o-relacionados.
- **Hybrid RAG**: Maior complexidade na calibraÃ§Ã£o de pesos de ranqueamento.

---

## 3. Related Concepts
- [[RAG Architecture and Retrieval Strategies]]
- [[Vector Indexes - HNSW and Approximate Nearest Neighbor Partitioning]]
- [[Lesson - Low-Score BM25 Pollution in Short Semantic Queries]]


---
type: concept
domain: ai-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - ai-engineering
  - rag
  - vector-search
  - hnsw
  - ann
  - embeddings
prerequisites:
  - "[[RAG Architecture and Retrieval Strategies]]"
related:
  - "[[Semantic Caching for LLM Responses and Invalidation Strategies]]"
  - "[[Context Engineering and Compression]]"
used_by:
  - "[[JARVIS Obsidian Tools and RAG System]]"
failure_modes:
  - "[[Hallucination Mitigation Techniques]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Efficient and Robust Approximate Nearest Neighbor Search Using Hierarchical Navigable Small World Graphs (Malkov & Yashunin, IEEE TPAMI 2020)
    type: PRIMARY_SOURCE
    url: https://arxiv.org/abs/1603.09320
---

# 🧭 Vector Indexes: HNSW and Approximate Nearest Neighbor Partitioning

## 1. Pergunta Central
> *Como realizar buscas de similaridade semântica por cosseno em coleções com milhões de vetores de alta dimensionalidade (ex: 1536d) em menos de 2 milissegundos com alta taxa de revocação (*Recall*)?*

---

## 2. A Hierarquia de Grafos HNSW (Hierarchical Navigable Small World)
Inspirado nas redes de mundo pequeno (*Small World*) e nas Skip Lists, o HNSW constrói um grafo multicamadas:

```
[ Camada Superior: Layer 2 ] -> P poucos nós conectados por arestas de longo alcance (Salto Rápido)
                                   | (Procura o nó mais próximo da query e desce de nível)
                                   v
[ Camada Intermediária: Layer 1 ] -> Mais nós com arestas de alcance médio
                                   |
                                   v
[ Camada Base: Layer 0 ]        -> Todos os nós conectados aos seus vizinhos mais próximos locais
```

- **Complexidade de Busca**: $O(\log N)$ em vez de $O(N)$ da busca exata (*Flat / Brute-force*).
- **Parâmetros Críticos**:
  - `M`: Número máximo de conexões por nó (trade-off entre tamanho do índice na RAM e recall).
  - `efConstruction` / `efSearch`: Tamanho da lista dinâmica de exploração na construção e na busca.

---

## 3. Comparativo de Índices Vetoriais

| Tipo de Índice | Latência de Busca ($N=1\text{M}$) | Consumo de Memória RAM | Recall Médio |
|---|---|---|---|
| **Flat (Exato / Brute-Force)** | $50 - 200\text{ ms}$ (Lento) | Baixo (Apenas vetores crus) | **100% (Exato)** |
| **IVF-PQ (Inverted File + Product Quant.)** | $1 - 5\text{ ms}$ | Muito Baixo (Vetores comprimidos) | 85 - 92% |
| **HNSW (Hierarchical Graph)** | **$< 2\text{ ms}$ (Ultrarrápido)** | Alto (Vetores + Grafo) | **95 - 99%** |

---

## 4. Related Concepts
- [[RAG Architecture and Retrieval Strategies]]
- [[Semantic Caching for LLM Responses and Invalidation Strategies]]
- [[Context Engineering and Compression]]

---
type: concept
domain: ai-engineering
difficulty: intermediate
tags:
  - ai-engineering
  - rag
  - vector-search
  - embeddings
  - retrieval
  - bm25
status: verified
---

# 📚 RAG Architecture and Retrieval Strategies

## 1. Definição & Pipeline Clássico
**Retrieval-Augmented Generation (RAG)** é o padrão arquitetural que combina recuperação determinística de informação de bases de conhecimento externas com a capacidade de síntese e raciocínio de modelos generativos (LLMs).

Permite que agentes de IA acedam a dados privados, atualizados e de domínio específico sem necessidade de re-treino (fine-tuning) do modelo.

```
                    [ DOCUMENTOS DO OBSIDIAN / CÓDIGO ]
                                     |
                                     v
                       [ Chunking & Metadados ]
                                     |
              +----------------------+----------------------+
              |                                             |
              v                                             v
     [ Embeddings Densos ]                           [ Índice Léxico BM25 ]
              |                                             |
              v                                             v
      (Vector Database)                              (Inverted Index)
              \                                             /
               \--- [ Hybrid Search & Fusion RRF ] --------/
                                    |
                                    v
                           [ Cross-Encoder Re-ranking ]
                                    |
                                    v
                      [ Top-K Passages + Prompt ]
                                    |
                                    v
                            [ LLM Generation ]
```

---

## 2. Componentes Fundamentais de um Pipeline RAG Moderno

### 2.1. Estratégias de Chunking
- **Hierarchical / Parent-Child Chunking**:
  - Divide o documento em pequenos chunks (ex: 200 tokens) para alta precisão de busca vetorial.
  - No momento do retrieval, envia ao LLM o bloco pai maior (ex: 1000 tokens) para contexto semântico completo.
- **AST / Semantic Chunking**:
  - Para código ou notas técnicas com seções (`##`, `###`), o corte é feito estritamente nas fronteiras de classes, funções ou títulos Markdown, evitando quebrar blocos de código a meio.

### 2.2. Busca Híbrida (Dense Vector + Sparse BM25)
- **Vetorial (Dense)**: Captura semelhança semântica e sinónimos (ex: "armazenar dados" $\leftrightarrow$ "persistência").
- **Léxica (BM25 / Keyword)**: Captura correspondências exatas essenciais para código (ex: nomes de funções `buscar_contexto_obsidian`, números de erro `429`, flags `--dry-run`).
- **Reciprocal Rank Fusion (RRF)** para combinar as pontuações:
  $$RRF\_Score(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
  (onde $k \approx 60$ e $r_m(d)$ é o ranking do documento no método $m$).

### 2.3. Cross-Encoder Re-Ranking
- Um modelo leve de re-ranking (como `bge-reranker-large` ou `cohere-rerank`) reordena os top-20 candidatos da busca híbrida para selecionar os top-3 mais relevantes antes de injetar no prompt.

---

## 3. Implementação de Busca Híbrida com RRF

```python
import math
from collections import defaultdict
from typing import List, Dict, Any

def reciprocal_rank_fusion(
    bm25_ranked_ids: List[str],
    vector_ranked_ids: List[str],
    k: int = 60
) -> List[tuple[str, float]]:
    """
    Combina dois rankings independentes usando RRF.
    """
    rrf_scores: Dict[str, float] = defaultdict(float)

    for rank, doc_id in enumerate(bm25_ranked_ids, start=1):
        rrf_scores[doc_id] += 1.0 / (k + rank)

    for rank, doc_id in enumerate(vector_ranked_ids, start=1):
        rrf_scores[doc_id] += 1.0 / (k + rank)

    sorted_docs = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)
    return sorted_docs
```

---

## 4. Used When
- No Obsidian RAG do **JARVIS OS** para recuperar tratados, notas de arquitetura e runbooks operacionais.
- Em agentes de codificação ao pesquisar documentação de APIs ou implementações de referência no workspace.

---

## 5. Common Failure Modes
- **Naive Fixed-Size Chunking**: Chunks de 500 caracteres que cortam funções no meio da linha ou separam a pergunta da resposta.
- **Top-K Context Saturation**: Injetar demasiados chunks irrelevantes que diluem a atenção do modelo e aumentam a taxa de alucinação.
- **Stale Embedding Index**: Não invalidar ou atualizar embeddings quando as notas do cofre são editadas.

---

## 6. Related Concepts
- [[Context Engineering and Compression]]
- [[Hallucination Mitigation Techniques]]
- [[Model Harness Architecture]]

---

## 7. Sources
- *Lewis et al., 2020 - Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*: https://arxiv.org/abs/2005.11401
- *Cormack, Clarke & Büttcher - Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods (SIGIR)*: https://dl.acm.org/doi/10.1145/1571941.1572114

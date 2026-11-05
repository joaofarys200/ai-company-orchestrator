---
type: concept
domain: ai-engineering
difficulty: advanced
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
tags:
  - ai-engineering
  - rag
  - reranking
  - rrf
  - mmr
  - grounding
---

# 🔎 Agentic RAG, Query Decomposition and Cross-Encoder Reranking

## 1. Limitações do RAG Estático Single-Shot
O RAG linear clássico (`query -> top-k -> generate`) falha em perguntas multi-salto (*multi-hop*), consultas comparativas entre múltiplos documentos e cenários em que o gerador remoto está indisponível. O **Agentic RAG** transforma a recuperação num pipeline iterativo com decomposição, fusão híbrida, *reranking* de atenção cruzada e fallback extrativo determinístico.

---

## 2. Pipeline em 4 Estágios de Alta Precisão

1. **Query Decomposition & Rewriting**:
   - Perguntas compostas ($Q$) são decompostas em sub-queries ortogonais $\{q_1, \dots, q_m\}$ com filtros explícitos de metadados (`document_id`, `section_id`, `domain`).
2. **Fusão Híbrida via Reciprocal Rank Fusion (RRF)**:
   - Combina rankings lexicais (BM25) e vetoriais densos sem depender de calibração de escalas de score bruto ($k \approx 60$):
     $$\text{RRF}(d) = \sum_{r \in \mathcal{R}} \frac{1}{k + \text{rank}_r(d)}$$
3. **Cross-Encoder Reranking & Diversificação MMR**:
   - Um Cross-Encoder avalia pares $(Q, d_i)$ conjuntamente (capturando interações finas token-a-token nos top-30 candidatos).
   - Para evitar passagens quase-duplicadas na janela de contexto, aplica-se **Maximal Marginal Relevance (MMR)**:
     $$\text{MMR} = \arg\max_{d_i \in R \setminus S} \left[ \lambda \cdot \text{Sim}(d_i, Q) - (1 - \lambda) \max_{d_j \in S} \text{Sim}(d_i, d_j) \right]$$
4. **Síntese Ancorada com Fallback Extrativo TF-MMR**:
   - Cada afirmação gerada deve referenciar passagens recuperadas (`OBSERVED` vs `INFERRED`). Se o LLM falhar ou atingir quota `429`, a seleção direta de frases por saliência TF + MMR garante sínteses 100% fiéis à fonte sem textos pré-fabricados.

---

## 3. Implementação de Referência (RRF + Seleção MMR)

```python
from typing import Dict, List, Set

def reciprocal_rank_fusion(rankings: List[List[str]], k: int = 60) -> List[str]:
    scores: Dict[str, float] = {}
    for rank_list in rankings:
        for idx, doc_id in enumerate(rank_list, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + idx)
    return [doc_id for doc_id, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]

def jaccard_tokens(a: Set[str], b: Set[str]) -> float:
    return len(a & b) / max(1, len(a | b))
```

---

## 4. Conceitos Relacionados & Fontes
- [[RAG Architecture and Retrieval Strategies]]
- [[Comparison - Lexical BM25 vs Dense Vector Embeddings vs Hybrid RAG]]
- [[Hallucination Mitigation Techniques]]
- [[Lesson - Low-Score BM25 Pollution in Short Semantic Queries]]
- [[JARVIS Multimodal Study Engine and Grounded Synthesis Pipeline]]
- **Fontes**: Carbonell & Goldstein (1998), *The Use of MMR, Diversity-Based Reranking* (SIGIR); Cormack et al. (2009), *Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods* (SIGIR).


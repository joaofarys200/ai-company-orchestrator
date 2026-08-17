---
type: concept
domain: ai-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: evolving
difficulty: advanced
tags:
  - ai-engineering
  - llm-serving
  - semantic-caching
  - embeddings
  - cache-invalidation
prerequisites:
  - "[[Vector Indexes - HNSW and Approximate Nearest Neighbor Partitioning]]"
  - "[[Model Harness Architecture]]"
related:
  - "[[Context Engineering and Compression]]"
  - "[[Structured Outputs and Schema Validation]]"
used_by:
  - "[[JARVIS Model Harness Implementation]]"
failure_modes:
  - "[[Lesson - Unhandled Rate Limits and Context Explosion]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: GPTCache - An Open-Source Semantic Cache for LLM Applications (Bang et al., 2023)
    type: PRIMARY_SOURCE
    url: https://github.com/zilliztech/GPTCache
---

# 🧠 Semantic Caching for LLM Responses and Invalidation Strategies

## 1. Pergunta Central
> *Como reaproveitar respostas caras de LLMs para perguntas com redação diferente mas semântica equivalente e quais estratégias de invalidação impedem que o cache retorne respostas obsoletas quando o código da base é alterado?*

---

## 2. O Fluxo do Cache Semântico

```
[ Prompt do Agente / Query ] -> Gerar Embedding do Prompt: v_q
                                       |
                                       v
[ Busca no Índice HNSW de Prompts Anteriores ] -> Encontra prompt mais próximo v_c com distância d
                                       |
                     +-----------------+-----------------+
                     |                                   |
             (d <= Threshold: ex 0.05)           (d > Threshold)
                     |                                   |
                     v                                   v
             [ CACHE HIT ]                        [ CACHE MISS ]
     Retorna Resposta em < 5ms              Chama LLM (1500ms)
     Custo: $0.00                           Armazena (v_q, Resposta) no Cache
```

---

## 3. Riscos de Falsos Positivos e Estratégia de Invalidação
- **Risco**: Uma negação sutil ("Mostre arquivos sem teste" vs "Mostre arquivos com teste") pode ter cosseno $> 0.95$, gerando retorno incorreto.
- **Estratégia de Invalidação (Hash de Contexto)**:
  A chave do cache semântico deve ser composta obrigatoriamente por:
  $$\text{Chave} = \text{Embed}(Prompt) \oplus \text{SHA256}(\text{Git HEAD Commit SHA})$$
  Se qualquer arquivo do workspace é modificado, o cache de código daquele repositório é automaticamente invalidado.

---

## 4. Related Concepts
- [[Vector Indexes - HNSW and Approximate Nearest Neighbor Partitioning]]
- [[Context Engineering and Compression]]
- [[Model Harness Architecture]]

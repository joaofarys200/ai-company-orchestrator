---
type: concept
domain: ai-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: advanced
tags:
  - ai-engineering
  - model-serving
  - kv-cache
  - vllm
  - ollama
  - memory-optimization
prerequisites:
  - "[[Model Harness Architecture]]"
  - "[[Ollama Local Model Serving]]"
related:
  - "[[Context Engineering and Compression]]"
  - "[[Anti-Pattern - Unbounded Context Accumulation]]"
used_by:
  - "[[JARVIS Model Harness Implementation]]"
failure_modes:
  - "[[Lesson - Unhandled Rate Limits and Context Explosion]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Efficient Memory Management for Large Language Model Serving with PagedAttention (Kwon et al., SOSP 2023)
    type: PRIMARY_SOURCE
    url: https://arxiv.org/abs/2309.06180
---

# 🧠 KV-Cache Dynamics and Memory Optimization in Agent Workloads

## 1. Pergunta Central
> *Por que o consumo de memória VRAM em agentes autónomos cresce linearmente com o tamanho do contexto e como técnicas como PagedAttention e Prefix Caching reduzem o Time to First Token (TTFT) em diálogos longos?*

---

## 2. Mecanismo do Key-Value (KV) Cache
Durante a fase autoregressiva de decodificação, para calcular a atenção do token atual $t_i$, o Transformer precisa dos vetores Key ($K$) e Value ($V$) de todos os tokens anteriores $t_1, \dots, t_{i-1}$.

Para evitar recomputar esses vetores a cada token gerado, eles são mantidos na VRAM da GPU no **KV-Cache**.
A memória necessária por requisição em FP16 é dada por:

$$\text{Memória KV (bytes)} = 2 \times 2 \times n_{\text{layers}} \times n_{\text{heads}} \times d_{\text{head}} \times \text{seq\_len} \times b$$
- $b$: Batch size.
- $\text{seq\_len}$: Comprimento total da sequência (prompt + geração).

Para um modelo de 70B tokens com 32k de contexto, o KV-cache de uma única sessão pode ultrapassar **16 GB de VRAM**, superando o próprio tamanho dos pesos do modelo.

---

## 3. Otimizações Críticas para Agentes

### 3.1. PagedAttention & Fragmentação Zero
Inspirado na paginação de memória virtual de sistemas operativos, divide o KV-cache em blocos não-contíguos na GPU, reduzindo o desperdício de memória por pré-alocação estática de 60-80% para menos de 4%.

### 3.2. Automatic Prefix Caching (APC)
Em agentes autónomos, o system prompt e as definições de ferramentas (`tools schema`) permanecem idênticos entre turnos. O servidor (vLLM/Ollama) reutiliza os blocos KV já computados do prefixo comum, reduzindo o **Time to First Token (TTFT)** em até 85%.

---

## 4. Related Concepts
- [[Context Engineering and Compression]]
- [[Anti-Pattern - Unbounded Context Accumulation]]
- [[Ollama Local Model Serving]]

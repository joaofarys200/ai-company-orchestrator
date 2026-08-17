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
  - gpu
  - cuda
  - triton
  - kernel-fusion
  - memory-bandwidth
prerequisites:
  - "[[KV-Cache Dynamics and Memory Optimization in Agent Workloads]]"
related:
  - "[[Model Quantization Dynamics - GGUF, AWQ, GPTQ and KV-Cache Impact]]"
  - "[[Ollama Local Model Serving]]"
used_by:
  - "[[JARVIS AirLLM Layer-by-Layer Offloading Architecture]]"
failure_modes:
  - "[[Lesson - Unhandled Rate Limits and Context Explosion]]"
implementation:
  - "[[JARVIS Model Harness Implementation]]"
sources:
  - title: Triton - An Intermediate Language and Compiler for Tiled Neural Network Computations (Tillet et al., MAPL 2019)
    type: PRIMARY_SOURCE
    url: https://triton-lang.org/
  - title: FlashAttention - Fast and Memory-Efficient Exact Attention with IO-Awareness (Dao et al., NeurIPS 2022)
    type: PRIMARY_SOURCE
    url: https://arxiv.org/abs/2205.14135
---

# ⚡ GPU Kernel Compilation: CUDA, Triton and Memory Bandwidth

## 1. Pergunta Central
> *Por que a inferência autoregressiva de LLMs em GPUs é limitada pela largura de banda de memória (Memory-Bound) em vez do poder de cálculo (Compute-Bound) e como a fusão de kernels em Triton/FlashAttention elimina os gargalos de High Bandwidth Memory (HBM)?*

---

## 2. A Distinção Fundamental: Compute-Bound vs. Memory-Bound

No modelo de teto de desempenho (*Roofline Model*), a intensidade operacional $I$ é a razão entre operações de ponto flutuante (FLOPs) e bytes transferidos da memória:

$$I = \frac{\text{FLOPs}}{\text{Bytes Transferidos}}$$

```
[ Pré-preenchimento / Prompt Processing ] -> Matriz x Matriz (GEMM) -> Intensidade Alta -> COMPUTE-BOUND
[ Decodificação Token a Token ]           -> Matriz x Vetor  (GEMV) -> Intensidade Baixa -> MEMORY-BOUND
```

Durante a decodificação token a token:
- A GPU deve ler todos os pesos do modelo (ex: 18 GB para 9B em FP16) da HBM para a SRAM dos Streaming Multiprocessors (**SM**) a fim de gerar **um único token**.
- Se a GPU possui 1000 GB/s de largura de banda, a velocidade teórica máxima é:
  $$\text{Velocidade Máxima} = \frac{1000\text{ GB/s}}{18\text{ GB/token}} \approx 55.5\text{ tokens/s}$$
  independentemente de possuir 50 ou 500 TFLOPs de computação bruta.

---

## 3. Fusão de Kernels e FlashAttention
Em implementações ingênuas do PyTorch, operações encadeadas (ex: `Softmax(Q @ K.T / sqrt(d)) @ V`) gravam matrizes intermediárias completas de tamanho $O(N^2)$ na HBM e leem-nas de volta no kernel seguinte.

**Kernel Fusion em OpenAI Triton / FlashAttention**:
1. Divide as matrizes de entrada em blocos (*Tiles*) que cabem inteiramente na **SRAM rápida (L1)** dos SMs.
2. Executa a multiplicação de matrizes, a escala, a normalização online do Softmax e a multiplicação com $V$ num único kernel fundido.
3. Reduz os acessos à memória HBM de $O(N^2)$ para $O(N)$, acelerando o processamento em até $4\times$.

---

## 4. When Should JARVIS Care?
- Ao hospedar modelos locais (como `qwen2.5-coder` ou `llama-3`) em hardware com VRAM restrita.
- Ao compilar kernels customizados para processamento de embeddings e atenção com comprimentos de contexto longos.

---

## 5. Related Concepts
- [[KV-Cache Dynamics and Memory Optimization in Agent Workloads]]
- [[Model Quantization Dynamics - GGUF, AWQ, GPTQ and KV-Cache Impact]]
- [[Ollama Local Model Serving]]

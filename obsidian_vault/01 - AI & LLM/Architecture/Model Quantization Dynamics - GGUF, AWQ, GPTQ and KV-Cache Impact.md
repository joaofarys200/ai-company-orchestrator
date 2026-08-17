---
type: comparison
domain: ai-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: evolving
difficulty: advanced
tags:
  - ai-engineering
  - model-serving
  - quantization
  - gguf
  - awq
  - gptq
  - kv-cache
prerequisites:
  - "[[KV-Cache Dynamics and Memory Optimization in Agent Workloads]]"
  - "[[GPU Kernel Compilation - CUDA, Triton and Memory Bandwidth]]"
related:
  - "[[Ollama Local Model Serving]]"
  - "[[Model Harness Architecture]]"
used_by:
  - "[[JARVIS Model Harness Implementation]]"
failure_modes:
  - "[[Lesson - Unhandled Rate Limits and Context Explosion]]"
implementation:
  - "[[JARVIS AirLLM Layer-by-Layer Offloading Architecture]]"
sources:
  - title: AWQ - Activation-aware Weight Quantization for LLM Compression and Acceleration (Lin et al., MLSys 2024)
    type: PRIMARY_SOURCE
    url: https://arxiv.org/abs/2306.00978
  - title: GPTQ - Accurate Post-Training Quantization for Generative Pre-trained Transformers (Frantar et al., ICLR 2023)
    type: PRIMARY_SOURCE
    url: https://arxiv.org/abs/2210.17323
---

# ⚖️ Model Quantization Dynamics: GGUF, AWQ, GPTQ and KV-Cache Impact

## 1. Pergunta Central
> *Qual a diferença técnica entre formatos de quantização de pesos (GGUF, AWQ, GPTQ) e quantização de ativações/KV-cache (FP8/INT4) para execução local de agentes de código com perda mínima de raciocínio lógico?*

---

## 2. Comparativo de Formatos de Quantização

| Formato | Arquitetura Alvo | Método de Compressão | Vantagem Principal | Desvantagem Principal |
|---|---|---|---|---|
| **GGUF (llama.cpp)** | CPU + GPU (Metal / CUDA / ROCm) | K-quants (quantização mista por bloco) | **Excelente suporte a offload parcial CPU/VRAM** | Menor throughput em batches grandes de GPU pura |
| **AWQ (Activation-aware)** | GPU (vLLM / TensorRT-LLM) | Protege os 1% de pesos com maiores ativações | **Máxima preservação de raciocínio de código** | Requer calibração com dataset de ativação |
| **GPTQ** | GPU (AutoGPTQ / ExLlamaV2) | Inversão de Hessiana de segunda ordem linha a linha | **Decodificação ultrarrápida (ExLlamaV2)** | Mais sensível a overfitting do dataset de calibração |
| **FP8 (E4M3 / E5M2)** | GPUs Modernas (NVIDIA Ada / Hopper) | Ponto flutuante nativo em hardware de 8 bits | **Aceleração nativa nos Tensor Cores sem perda** | Suporte limitado em GPUs antigas |

---

## 3. Quantização do KV-Cache (INT8 / FP8)
Quantizar o KV-cache de FP16 (2 bytes) para FP8 (1 byte) reduz o consumo de memória do contexto pela metade, permitindo dobrar a janela de contexto de 32k para 64k tokens na mesma GPU sem degradação mensurável em tarefas de patching de código.

---

## 4. Related Concepts
- [[KV-Cache Dynamics and Memory Optimization in Agent Workloads]]
- [[GPU Kernel Compilation - CUDA, Triton and Memory Bandwidth]]
- [[Ollama Local Model Serving]]

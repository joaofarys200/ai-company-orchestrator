---
type: architecture
domain: jarvis
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: evolving
difficulty: advanced
tags:
  - jarvis
  - airllm
  - model-serving
  - layer-offloading
  - low-vram
prerequisites:
  - "[[GPU Kernel Compilation - CUDA, Triton and Memory Bandwidth]]"
  - "[[Model Quantization Dynamics - GGUF, AWQ, GPTQ and KV-Cache Impact]]"
related:
  - "[[Ollama Local Model Serving]]"
  - "[[Model Harness Architecture]]"
used_by:
  - "[[JARVIS Model Harness Implementation]]"
failure_modes:
  - "[[Lesson - Unhandled Rate Limits and Context Explosion]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: JARVIS Codebase - services/airllm_server/config.py and server implementation
    type: JARVIS_INTERNAL
    url: internal://services/airllm_server/config.py
---

# 🧠 JARVIS AirLLM Layer-by-Layer Offloading Architecture

## 1. Purpose
O microserviço experimental `AirLLMServer` permite a execução de modelos massivos de linguagem (como modelos de 70B parâmetros) em GPUs de consumo de 4GB a 8GB de VRAM, descarregando pesos camada por camada do disco NVMe/RAM para a memória de vídeo apenas no momento exato do cálculo.

---

## 2. Responsibilities
- Carregar configurações validadas via `AirLLMServerConfig` (`AIRLLM_MODEL_REPO`, `AIRLLM_COMPRESSION`, `AIRLLM_PORT`).
- Suportar compressão de pesos em 4-bit e 8-bit (`SUPPORTED_COMPRESSIONS`).
- Transmitir ativações entre camadas sucessivas do Transformer mantendo apenas uma camada ativa por vez na VRAM.
- Expor endpoint HTTP compatível com OpenAI/vLLM para geração de texto.

---

## 3. Inputs & Outputs
- **Inputs**: Requisições HTTP POST com prompt e hiperparâmetros (`temperature`, `max_sequence_length`).
- **Outputs**: Payloads de texto gerados e métricas de latência por camada.

---

## 4. State Management & Invariants
- Durante a inferência, a VRAM nunca excede o tamanho da maior camada individual quantizada ($\approx 1.2\text{GB}$).

---

## 5. Dependencies
- [`services/airllm_server/config.py`](file:///c:/Users/joaor/Desktop/JarvisOS/services/airllm_server/config.py)
- [`services/airllm_server/prompting.py`](file:///c:/Users/joaor/Desktop/JarvisOS/services/airllm_server/prompting.py)

---

## 6. Failure Modes & Recovery
- **Failure**: Velocidade de leitura em disco NVMe insuficiente gerando latência inaceitável.
- **Recovery**: O `ModelHarness` detecta timeout alto e roteia missões urgentes para o Ollama local ou API em nuvem.

---

## 7. Security Boundaries
- Isolamento em subprocesso dedicado vinculado exclusivamente ao endereço `127.0.0.1`.

---

## 8. Evidence Produced & Tests
- **Evidence**: Logs de inicialização e profiling de carregamento de camadas.
- **Tests**: `tests/test_airllm_config.py`.

---

## 9. Related Concepts
- [[GPU Kernel Compilation - CUDA, Triton and Memory Bandwidth]]
- [[Model Quantization Dynamics - GGUF, AWQ, GPTQ and KV-Cache Impact]]
- [[Ollama Local Model Serving]]

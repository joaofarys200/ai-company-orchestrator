---
type: technology
domain: ai-engineering
difficulty: intermediate
tags:
  - ai-engineering
  - ollama
  - local-llm
  - inference
  - latency
status: verified
---

# 🦙 Ollama Local Model Serving

## 1. O que é & Arquitetura
**Ollama** é um runtime e servidor de inferência local de modelos de linguagem de código aberto construído sobre `llama.cpp`. Ele empacota pesos de modelos, parâmetros de amostragem, templates de prompt e quantizações GGUF num formato unificado chamado `Modelfile`.

No **JARVIS OS**, o Ollama serve como o motor primário de inferência *on-premise*, garantindo privacidade total, zero custo por token e operabilidade mesmo sem conexão com a internet.

```
+--------------------------------------------------------------+
|                    JARVIS OS (Python Backend)                |
+------------------------------+-------------------------------+
                               | HTTP POST /api/generate
                               v
+--------------------------------------------------------------+
|                    Ollama Daemon (Port 11434)                |
|  +--------------------------------------------------------+  |
|  | Engine: llama.cpp (GGUF Quantization Q4_K_M / Q8_0)   |  |
|  | Context Management / Memory-Mapped I/O (mmap)          |  |
|  | GPU Acceleration (CUDA / Metal / ROCm / Vulkan)        |  |
|  +--------------------------------------------------------+  |
+--------------------------------------------------------------+
```

---

## 2. Configuração de Modelos para Agentes (Modelfile)

Para otimizar modelos de codificação (como `Qwen2.5-Coder-7B-Instruct` ou `DeepSeek-Coder`), utiliza-se um `Modelfile` customizado:

```dockerfile
FROM qwen2.5-coder:7b-instruct-q4_K_M

# Definir tamanho da janela de contexto para 16k tokens
PARAMETER num_ctx 16384

# Controlar determinismo para código
PARAMETER temperature 0.1
PARAMETER top_p 0.95
PARAMETER repeat_penalty 1.1

# Template de Sistema Estrito
SYSTEM """
Tu és um especialista em engenharia de software para o JARVIS OS.
Emite sempre código tipado, seguro e respostas estruturadas em JSON quando solicitado.
"""
```

---

## 3. Integração com API REST em Python

```python
import httpx
import json
from typing import AsyncGenerator, Dict, Any

OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"

async def call_ollama(
    model: str,
    prompt: str,
    system_prompt: str = "",
    json_mode: bool = True,
    timeout: float = 60.0
) -> Dict[str, Any]:
    """
    Invoca o Ollama de forma assíncrona com suporte a modo JSON estrito.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "format": "json" if json_mode else "",
        "options": {
            "temperature": 0.1,
            "num_ctx": 16384
        }
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status()
        result = response.json()
        
        if json_mode:
            return json.loads(result["response"])
        return {"raw_text": result["response"]}
```

---

## 4. Vantagens e Limitações

| Vantagens | Limitações |
|---|---|
| Latência zero de rede; resposta imediata | Limitado pela VRAM local da GPU (ex: 8GB VRAM = máx ~7B/8B Q4) |
| Custo marginal zero por milhão de tokens | Menor capacidade em raciocínio abstrato longo que modelos Tier Frontier |
| Suporte nativo a GGUF e offload de camadas GPU/CPU | Requer gestão ativa de memória para evitar OOM (Out Of Memory) |

---

## 5. Used When
- Tarefas frequentes e automatizadas de baixa latência (linting, pequenas correções de sintaxe, extração de entidades).
- Execução em ambientes com restrição de transferência de dados sensíveis ou sem conexão à internet.

---

## 6. Common Failure Modes
- **VRAM OOM Crash**: Carregar um modelo grande demais para a GPU resulta em queda drástica de velocidade para CPU (fallback) ou término abrupto do daemon.
- **Context Truncation Silenciosa**: Se o prompt exceder `num_ctx`, o Ollama descarta os tokens mais antigos sem lançar erro explícito se não configurado.

---

## 7. Related Concepts
- [[Model Routing and Fallback Strategies]]
- [[Model Harness Architecture]]
- [[Structured Outputs and Schema Validation]]

---

## 8. Sources
- *Ollama GitHub Repository & Documentation*: https://github.com/ollama/ollama
- *llama.cpp Project & GGUF Format Specification*: https://github.com/ggerganov/llama.cpp

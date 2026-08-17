---
type: concept
domain: ai-engineering
difficulty: advanced
tags:
  - ai-engineering
  - model-harness
  - llm
  - reliability
  - architecture
status: verified
---

# 🛡️ Model Harness Architecture

## 1. Definição & Propósito
Um **Model Harness** (Chassis de Execução de Modelos) é uma camada de abstração de software interposta entre os agentes de IA e os provedores de modelos de linguagem (APIs remotas como Gemini, OpenAI, Anthropic ou endpoints locais como Ollama).

O seu propósito fundamental é transformar a inferência probabilística e propensa a falhas de rede de um LLM numa primitiva de computação confiável, determinística, com limites rígidos de tempo, orçamentos de tokens e tolerância a falhas.

```
+------------------+
|  Agent / Logic   |  (Pede uma inferência com schema)
+--------+---------+
         |
         v
+------------------+
|  Model Harness   |  <--- Circuit Breaker / Timeout / Retry / Schema Validator
+--------+---------+
         |
    +----+----+
    |         |
    v         v
+-------+ +--------+
| Local | | Cloud  |
| Model | | Model  |
+-------+ +--------+
```

---

## 2. Responsabilidades Centrais do Harness

1. **Gestão de Timeout e Deadlines**:
   - Definição de prazos estritos por requisição (ex: 30s para geração rápida, 120s para código complexo).
   - Cancelamento cooperativo assíncrono via `asyncio.wait_for` ou contexts em Go/Rust.
2. **Políticas de Retry com Exponential Backoff & Jitter**:
   - Falhas transitórias de rede (`503 Service Unavailable`, `429 Too Many Requests`, timeouts TCP) são tratadas com retentativas calculadas por:
     $$T_{\text{wait}} = \min(T_{\text{max}}, T_{\text{base}} \times 2^{\text{attempt}}) \pm \text{jitter}$$
3. **Validação e Enforcing de Schema**:
   - Validação imediata contra um modelo Pydantic ou JSON Schema antes de entregar o payload ao agente chamador.
4. **Fallback e Redirecionamento Automático**:
   - Se o modelo primário devolver erro de cota ou falha repetida de schema, o harness redireciona transparentemente a requisição para um modelo alternativo (fallback model).
5. **Token Budgeting e Contabilidade**:
   - Contagem precisa de tokens de entrada e saída, alertando antes que a janela de contexto atinja o limite máximo.

---

## 3. Implementação de Referência (Python Async)

```python
import asyncio
import json
import random
import time
from typing import Any, Callable, Dict, Optional, Type
from pydantic import BaseModel, ValidationError

class ModelHarnessError(Exception):
    pass

class ModelHarness:
    def __init__(self, primary_client: Any, fallback_client: Optional[Any] = None, max_retries: int = 3):
        self.primary = primary_client
        self.fallback = fallback_client
        self.max_retries = max_retries

    async def execute_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        timeout_seconds: float = 45.0
    ) -> BaseModel:
        attempt = 0
        last_error = None
        client = self.primary

        while attempt < self.max_retries:
            try:
                # 1. Executar com timeout rígido
                raw_response = await asyncio.wait_for(
                    client.generate(prompt=prompt),
                    timeout=timeout_seconds
                )
                
                # 2. Parsing e Validação de Schema
                data = json.loads(raw_response)
                validated_obj = schema.model_validate(data)
                return validated_obj

            except (asyncio.TimeoutError, ValidationError, json.JSONDecodeError, Exception) as err:
                attempt += 1
                last_error = err
                
                # Se falhar repetidamente no primário, alterna para fallback
                if attempt >= 2 and self.fallback and client != self.fallback:
                    client = self.fallback
                
                if attempt < self.max_retries:
                    # Backoff exponencial com jitter
                    sleep_time = min(10.0, 1.5 ** attempt) + random.uniform(0.1, 0.5)
                    await asyncio.sleep(sleep_time)

        raise ModelHarnessError(f"Harness falhou após {self.max_retries} tentativas. Último erro: {last_error}")
```

---

## 4. Used When
- Sempre que um agente autónomo interage com um LLM para tarefas críticas de código, tomada de decisões ou chamadas de ferramentas.
- Em ambientes de produção onde flutuações de latência ou limites de taxa de API (`429`) não podem parar a execução da missão.

---

## 5. Common Failure Modes
- **Retry Storms**: Múltiplos agentes a retentar em simultâneo sem jitter, saturando ainda mais a API com limite de taxa atingido.
- **Silent Schema Drift**: Quando o modelo devolve JSON válido, mas omite campos obrigatórios que passam despercebidos sem validação estrita Pydantic.
- **Memory Leaks de Contexto**: Manter histórico ilimitado de tentativas com erro dentro da mesma janela de prompt.

---

## 6. Related Concepts
- [[Model Routing and Fallback Strategies]]
- [[Structured Outputs and Schema Validation]]
- [[Agent Loop Detection and Circuit Breaker]]
- [[How to Handle Malformed Model Output]]

---

## 7. Sources
- *Google Cloud Vertex AI Resiliency Best Practices*: https://cloud.google.com/vertex-ai/docs/reference/rest
- *OpenAI API Reliability Guide*: https://platform.openai.com/docs/guides/rate-limits/error-mitigation
- *Anthropic API Error Handling & Structured Outputs*: https://docs.anthropic.com/en/docs/build-with-claude/tool-use

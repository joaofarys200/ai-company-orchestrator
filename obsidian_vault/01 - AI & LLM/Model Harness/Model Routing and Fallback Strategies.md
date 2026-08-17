---
type: pattern
domain: ai-engineering
difficulty: intermediate
tags:
  - ai-engineering
  - model-routing
  - fallback
  - cost-optimization
  - latency
status: verified
---

# 🔀 Model Routing and Fallback Strategies

## 1. Problema & Contexto
Nem todas as tarefas de um agente de IA requerem um modelo de ponta (fronteira) com elevado custo financeiro e latência de processamento. Tarefas simples (como classificação de intenção, extração de entidades ou validação de sintaxe) podem ser executadas por modelos locais pequenos e rápidos, enquanto tarefas de síntese de código e raciocínio de alta complexidade exigem modelos de maior capacidade.

Além disso, indisponibilidades de serviço ou esgotamento de cotas de API exigem mecanismos determinísticos de fallback.

---

## 2. Estratégias de Roteamento

### 2.1. Roteamento Baseado em Complexidade (Complexity-Based Routing)
- **Tier 1 (Fast / Local)**: Modelos locais leves (ex: `qwen2.5-coder:7b`, `llama3.2:3b` via Ollama) para:
  - Triagem de prompts;
  - Resumos de parágrafos;
  - Geração de queries de pesquisa.
- **Tier 2 (High-Capability / Cloud)**: Modelos avançados (ex: Gemini 1.5 Pro, Claude 3.5 Sonnet, GPT-4o) para:
  - Arquitetura de software;
  - Refatorações multi-arquivo;
  - Raciocínio lógico e depuração profunda.

### 2.2. Cascata de Degradação Graciosa (Graceful Fallback Cascade)
```
[Requisição de Missão]
         |
         v
+------------------+
| Modelo Primário  | -- (Sucesso) --> Retorna Resposta
+--------+---------+
         | (Falha: 429, 503, Timeout, Schema Invalido)
         v
+------------------+
| Modelo Secundário| -- (Sucesso) --> Retorna Resposta (com flag: degraded_tier=true)
+--------+---------+
         | (Falha)
         v
+------------------+
| Modelo Local     | -- (Sucesso) --> Retorna Resposta Mínima
| de Contingência  |
+--------+---------+
         | (Falha Crítica)
         v
+------------------+
| Circuit Breaker  | --> Notifica Operador / Reverte Estado Seguro
+------------------+
```

---

## 3. Matriz de Decisão de Roteamento

| Dimensão | Tier Local (Ollama) | Tier Intermediário (Flash/Mini) | Tier Avançado (Pro/Sonnet) |
|---|---|---|---|
| **Latência Média** | 50ms - 300ms (on-device) | 400ms - 1.2s | 1.5s - 6.0s |
| **Custo por 1M tokens** | $0.00 (computação local) | ~$0.10 - $0.50 | ~$3.00 - $15.00 |
| **Janela de Contexto** | 8k - 32k tokens | 128k - 1M tokens | 200k - 2M tokens |
| **Capacidade de Raciocínio** | Média/Limitada a sintaxe | Alta para tarefas padrão | Máxima para arquitetura e edge cases |
| **Privacidade** | Total (sem tráfego externo) | Tráfego encriptado TLS | Tráfego encriptado TLS |

---

## 4. Implementação de Roteador de Modelos

```python
from enum import Enum
from typing import Dict, Any

class ModelTier(str, Enum):
    LOCAL_FAST = "local_fast"
    CLOUD_EFFICIENT = "cloud_efficient"
    CLOUD_FRONTIER = "cloud_frontier"

class ModelRouter:
    def __init__(self, clients: Dict[ModelTier, Any]):
        self.clients = clients

    def select_tier_for_task(self, task_type: str, context_length: int) -> ModelTier:
        if context_length > 32000:
            return ModelTier.CLOUD_FRONTIER
            
        if task_type in ["classification", "summarization", "keyword_extract"]:
            return ModelTier.LOCAL_FAST
        elif task_type in ["unit_test_gen", "lint_fix", "json_format"]:
            return ModelTier.CLOUD_EFFICIENT
        elif task_type in ["architecture_design", "ast_refactor", "security_audit"]:
            return ModelTier.CLOUD_FRONTIER
        
        return ModelTier.CLOUD_EFFICIENT
```

---

## 5. Common Failure Modes
- **Looping Fallbacks**: Fallback que tenta um modelo que também está indisponível sem checar healthcheck prévio.
- **Incompatibilidade de Ferramentas (Tool Calling)**: Trocar de modelo durante uma conversa onde o modelo secundário não suporta a mesma sintaxe de Function Calling do primário.

---

## 6. Related Concepts
- [[Model Harness Architecture]]
- [[Ollama Local Model Serving]]
- [[Structured Outputs and Schema Validation]]
- [[How to Implement Circuit Breakers for Flaky External APIs]]

---

## 7. Sources
- *Google Vertex AI Model Selection Matrix*: https://cloud.google.com/vertex-ai/docs/generative-ai/learn/models
- *Ollama Library & API Specs*: https://github.com/ollama/ollama/blob/main/docs/api.md

---
type: concept
domain: jarvis
difficulty: intermediate
tags:
  - jarvis
  - model-harness
  - llm
  - agents
status: verified
---

# 🤖 JARVIS Model Harness Implementation

## 1. O Papel do Model Harness no JARVIS
O **JARVIS Model Harness** é a camada que desacopla os agentes (Clara, Devon, Alex, Quinn) dos modelos de linguagem subjacentes (Gemini 1.5/2.0, Claude 3.5, OpenAI GPT-4o ou Ollama local).

---

## 2. Padrões Implementados
- **Gestão de Retries e Timeouts**: Prevenção de bloqueios por indisponibilidade de rede ou rate limits (`429`).
- **Validação de Schemas Pydantic**: Conversão determinística de respostas LLM em objetos estruturados tipados.
- **Roteamento Inteligente**: Uso de modelos locais rápidos para tarefas de baixa complexidade e modelos frontier para síntese de arquitetura e código.

---

## 3. Related Concepts
- [[Model Harness Architecture]]
- [[Model Routing and Fallback Strategies]]
- [[Structured Outputs and Schema Validation]]
- [[JARVIS Component Architecture]]

---

## 4. Sources
- *JARVIS OS Codebase — `agents/`*

---
type: troubleshooting
domain: ai-engineering
difficulty: intermediate
tags:
  - ai-engineering
  - troubleshooting
  - malformed-json
  - parser
  - regex
status: verified
---

# 🛠️ How to Handle Malformed Model Output

## 1. Sintomas & Diagnóstico
- `json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2`
- `ValidationError: 1 validation error for AgentPlan`
- O modelo devolve texto conversacional antes/depois do JSON (ex: *"Com certeza, aqui está o JSON solicitado: ```json { ... } ```"*).
- JSON truncado no meio de uma chave ou array devido ao esgotamento de `max_tokens`.

---

## 2. Pipeline Sistemático de Recuperação e Parsing Resiliente

```
                  [ Resposta Raw do Modelo ]
                              |
                              v
             +----------------------------------+
             | Tentativa 1: json.loads direto   | ---> (Sucesso) -> Retorna Dict
             +----------------+-----------------+
                              | (Falha)
                              v
             +----------------------------------+
             | Tentativa 2: Extração por Regex  |
             | r"```(?:json)?\s*([\s\S]*?)\s*```"| ---> (Sucesso) -> Retorna Dict
             +----------------+-----------------+
                              | (Falha)
                              v
             +----------------------------------+
             | Tentativa 3: Auto-Repair de      |
             | Chaves/Aspas e Fecho de Tags     | ---> (Sucesso) -> Retorna Dict
             +----------------+-----------------+
                              | (Falha)
                              v
             +----------------------------------+
             | Tentativa 4: Prompt de Reparação |
             | Sintática Instantânea ao LLM     | ---> Retorna Dict ou Erro Final
             +----------------------------------+
```

---

## 3. Implementação do Módulo de Reparação (Python)

```python
import json
import re
from typing import Any, Dict, Optional

def extract_and_repair_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Extrai e repara payloads JSON malformados gerados por LLMs.
    """
    if not raw_text or not raw_text.strip():
        return None

    cleaned = raw_text.strip()

    # 1. Tentativa Direta
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 2. Extrair de blocos Markdown ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.DOTALL)
    if match:
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            cleaned = candidate

    # 3. Encontrar o primeiro '{' ou '[' e o último '}' ou ']'
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        candidate = cleaned[start_idx : end_idx + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # Substituir aspas simples por aspas duplas se for JSON quase válido
            candidate_fixed = re.sub(r"(?<!\\)'", '"', candidate)
            # Remover vírgulas à direita antes de fecho (trailing commas)
            candidate_fixed = re.sub(r",\s*([\}\]])", r"\1", candidate_fixed)
            try:
                return json.loads(candidate_fixed)
            except json.JSONDecodeError:
                pass

    return None
```

---

## 4. Prevenção na Raiz
1. Ativar `response_format={"type": "json_object"}` ou `json_schema` na API do modelo.
2. Definir `temperature: 0.1` ou `0.0` para saídas estruturadas determinísticas.
3. Garantir que `max_tokens` do output seja pelo menos $2\times$ o tamanho esperado do payload para prevenir truncamento de buffer.

---

## 5. Related Concepts
- [[Structured Outputs and Schema Validation]]
- [[Model Harness Architecture]]
- [[Tool Calling Protocols and Structured Invocation]]

---

## 6. Sources
- *RFC 8259 - The JavaScript Object Notation (JSON) Data Interchange Format*: https://datatracker.ietf.org/doc/html/rfc8259
- *Python json module standard library documentation*: https://docs.python.org/3/library/json.html

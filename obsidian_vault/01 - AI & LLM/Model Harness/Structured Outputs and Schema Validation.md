---
type: concept
domain: ai-engineering
difficulty: intermediate
tags:
  - ai-engineering
  - structured-outputs
  - json-schema
  - pydantic
  - validation
status: verified
---

# 📐 Structured Outputs and Schema Validation

## 1. Definição & Importância
**Structured Outputs** é a técnica de forçar modelos de linguagem a emitirem respostas que aderem estritamente a uma gramática formal predefinida (habitualmente **JSON Schema**), garantindo tipos primitivos, campos obrigatórios e estruturas aninhadas válidas.

Na ausência de saídas estruturadas, os agentes de IA dependem de parsing de texto livre ou expressões regulares, introduzindo fragilidade extrema, alucinações de campos e erros de execução em tempo de execução (`JSONDecodeError`, `KeyError`, `AttributeError`).

---

## 2. Abordagens de Garantia Estrutural

```
+-------------------------------------------------------------+
| Nível 1: Prompting ("Responda apenas em JSON")               | -> Baixa Confiabilidade
+-------------------------------------------------------------+
| Nível 2: Schema Enforcement na API (OpenAI/Gemini JSON Mode) | -> Média/Alta Confiabilidade
+-------------------------------------------------------------+
| Nível 3: Grammar-Guided Constrained Decoding (GBNF / Outlines)| -> 100% Confiabilidade Sintática
+-------------------------------------------------------------+
```

1. **Constrained Decoding (Decodificação Gramatical)**:
   - Em tempo de amostragem de tokens (logits), o motor de inferência (como `llama.cpp` ou endpoints nativos) mascara todos os tokens de vocabulário que violariam o parser JSON/Gramática naquele índice específico.
   - Garante matematicamente que o output não conterá erros de parênteses ou tipos inválidos.
2. **Pydantic Model Validation (Camada de Aplicação)**:
   - Validação semântica e de domínio (ex: intervalos numéricos, expressões regulares de caminhos de ficheiros, listas não-vazias).

---

## 3. Exemplo Prático com Pydantic v2

```python
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator
import os

class FilePatchAction(BaseModel):
    file_path: str = Field(..., description="Caminho relativo do ficheiro no workspace")
    action: Literal["CREATE", "MODIFY", "DELETE"] = Field(..., description="Ação a ser executada")
    diff_content: Optional[str] = Field(None, description="Diff unificado para modificações ou conteúdo completo")
    reasoning: str = Field(..., description="Justificação técnica da alteração")

    @field_validator("file_path")
    @classmethod
    def prevent_path_traversal(cls, v: str) -> str:
        clean = v.replace("\\", "/").strip().lstrip("/")
        if ".." in clean.split("/"):
            raise ValueError("Path traversal não permitido ('..')")
        return clean

class AgentPlanResponse(BaseModel):
    task_id: str
    actions: List[FilePatchAction] = Field(..., min_length=1)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
```

---

## 4. Used When
- Toda a comunicação entre agentes (Orquestrador -> Especialista).
- Ferramentas de manipulação de código (geração de patches, planos de refatoração, relatórios de testes).
- Ingestão de dados não estruturados para bases de dados relacionais ou SQLite.

---

## 5. Common Failure Modes
- **JSON Markdown Wrap**: O modelo envolve o JSON em blocos ```json ... ``` que precisam de strip antes do `json.loads`.
- **Stringified Numbers/Booleans**: O modelo envia `"true"` em vez de `true`, ou `"123"` em vez de `123` (resolvido por coerção de tipos do Pydantic).
- **Truncated JSON por Context Budget**: O modelo atinge `max_output_tokens` e a string JSON é cortada a meio da árvore.

---

## 6. Related Concepts
- [[Model Harness Architecture]]
- [[How to Handle Malformed Model Output]]
- [[Tool Calling Protocols and Structured Invocation]]
- [[Abstract Syntax Tree (AST) Parsing and Manipulation]]

---

## 7. Sources
- *Pydantic v2 Official Documentation*: https://docs.pydantic.dev/latest/
- *JSON Schema Specification (Draft 2020-12)*: https://json-schema.org/draft/2020-12/json-schema-core.html
- *OpenAI Structured Outputs Guide*: https://platform.openai.com/docs/guides/structured-outputs

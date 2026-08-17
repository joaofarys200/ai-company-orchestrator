---
type: concept
domain: ai-engineering
difficulty: intermediate
tags:
  - ai-engineering
  - tool-calling
  - function-calling
  - agents
  - openapi
status: verified
---

# 🔧 Tool Calling Protocols and Structured Invocation

## 1. Definição & Ciclo de Vida
**Tool Calling** (ou Function Calling) é o protocolo pelo qual um modelo de linguagem decide quando invocar uma ferramenta externa (ex: ler ficheiro, executar comando em sandbox, pesquisar na base de dados), gerando os argumentos em formato estruturado (JSON) com base numa definição de esquema previamente fornecida.

O modelo **não executa** a ferramenta diretamente; ele emite a intenção de execução, a aplicação anfitriã (*Host Runner*) executa a função no ambiente seguro e devolve o resultado (*Tool Output*) para o contexto do modelo continuar o raciocínio.

```
+---------------+                +-------------------+                +---------------+
|     Agent     | -- (Prompt) -> |        LLM        |                |  Host System  |
| Orchestrator  |                | (Inference Engine)|                |   (Sandbox)   |
+-------+-------+                +---------+---------+                +-------+-------+
        |                                  |                                  |
        |                                  | Decide chamar ferramenta         |
        |                                  | tool_name: "read_file"           |
        | <------ Tool Call Request -------+ args: {"path": "main.py"}        |
        |                                                                     |
        | --------------------- Execute Tool in Sandbox --------------------> |
        |                                                                     |
        | <------------------ Return Raw Output / Error --------------------- |
        |                                                                     |
        | ---------------- Ingest Output & Continue Inference --------------> |
        |                                  |                                  |
        | <---------------------- Final Text Answer ------------------------- |
```

---

## 2. Especificação Canónica de Ferramentas (OpenAPI/JSON Schema)

```json
{
  "name": "apply_patch",
  "description": "Aplica um patch de código unificado a um ficheiro existente dentro do workspace.",
  "parameters": {
    "type": "object",
    "properties": {
      "file_path": {
        "type": "string",
        "description": "Caminho relativo do ficheiro (ex: backend/server.py)"
      },
      "patch_diff": {
        "type": "string",
        "description": "Diff unificado contendo as linhas a alterar"
      },
      "dry_run": {
        "type": "boolean",
        "description": "Se verdadeiro, simula a aplicação sem alterar o disco"
      }
    },
    "required": ["file_path", "patch_diff"]
  }
}
```

---

## 3. Gestão de Erros e Feedback Loop
Quando uma ferramenta falha (ex: `FileNotFoundError` ou `PermissionDenied`), a saída deve ser retroalimentada com clareza diagnóstica para permitir auto-correção:

```python
async def execute_tool_safely(tool_name: str, arguments: dict) -> dict:
    try:
        if tool_name == "apply_patch":
            result = await apply_patch_tool(**arguments)
            return {"status": "SUCCESS", "output": result}
    except Exception as e:
        # Devolver erro detalhado para o LLM poder corrigir os parâmetros
        return {
            "status": "ERROR",
            "error_type": type(e).__name__,
            "message": str(e),
            "hint": "Verifica se o caminho do ficheiro existe usando a ferramenta list_dir."
        }
```

---

## 4. Used When
- Automação de tarefas no SO pelo JARVIS (edição de código, consulta de bases de dados, testes automatizados).
- Execução de comandos controlados em ambientes de sandbox.

---

## 5. Common Failure Modes
- **Hallucinated Arguments**: O modelo inventa parâmetros adicionais que não constam no JSON Schema da ferramenta.
- **Malformed Escape Sequences**: Falha ao escapar quebras de linha `\n` ou aspas `\"` em strings longas de diff de código.
- **Infinite Retry Loop on Static Failure**: O agente tenta invocar a mesma ferramenta 10 vezes com os mesmos argumentos errados sem mudar de abordagem.

---

## 6. Related Concepts
- [[Model Harness Architecture]]
- [[Structured Outputs and Schema Validation]]
- [[Agent Loop Detection and Circuit Breaker]]
- [[Least-Privilege Process Sandboxing and Execution Jail]]

---

## 7. Sources
- *OpenAPI 3.1.0 Specification*: https://spec.openapis.org/oas/v3.1.0
- *Anthropic Claude Tool Use Documentation*: https://docs.anthropic.com/en/docs/build-with-claude/tool-use

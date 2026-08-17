---
type: concept
domain: ai-engineering
difficulty: intermediate
tags:
  - ai-engineering
  - hallucination-mitigation
  - verification
  - reliability
  - rag
status: verified
---

# 🔍 Hallucination Mitigation Techniques

## 1. Definição
Alucinação em LLMs é a geração de asserções, parâmetros de API, caminhos de ficheiros ou dados factuais que soam plausíveis e confiantes, mas são factualmente falsos ou inexistentes no ambiente de execução.

Em sistemas agênticos como o **JARVIS OS**, alucinações em código levam a imports inexistentes (`ModuleNotFoundError`), APIs descontinuadas ou invocações de ferramentas com argumentos incorretos.

---

## 2. Taxonomia de Técnicas de Mitigação

```
                           +------------------------------------+
                           |  Mitigação de Alucinações em IA   |
                           +-----------------+------------------+
                                             |
           +---------------------------------+---------------------------------+
           |                                                                   |
           v                                                                   v
+-----------------------+                                           +-----------------------+
|  Mitigações em Design |                                           |  Mitigações em Runtime|
|  (Grounding & Prompts)|                                           |  (Validação Externa)  |
+-----------+-----------+                                           +-----------+-----------+
            |                                                                   |
  - Retrieval-Augmented Gen (RAG)                                     - Compiladores & Linters (pyright/tsc)
  - Citações obrigatórias de fontes                                   - Execução de Testes Unitários
  - "Responda 'NÃO SEI' se ausente"                                   - Validação de Esquemas Pydantic
  - Fornecer assinaturas exatas de API                                - Verificação de existência no FS
```

### 2.1. Grounding com RAG e Citação de Linhas
- O modelo deve ser instruído a ancorar todas as respostas nos trechos de código/documentação fornecidos.
- Restrição explícita no System Prompt:
  > *"Utiliza APENAS as funções e classes presentes no contexto fornecido. Se uma função não existir no ficheiro inspecionado, não a inventes; declara explicitamente que a funcionalidade necessita de ser implementada."*

### 2.2. Verificação Determinística por Ferramentas (Tool-Assisted Verification)
- Antes de aceitar um plano do agente:
  1. Verificar se os caminhos dos ficheiros existem no disco (`os.path.exists`).
  2. Verificar se os símbolos importados existem via inspeção AST.
  3. Executar o analisador de tipos (ex: `mypy` ou `pyright`).

---

## 3. Padrão de Dupla Verificação (Critic / Verifier Agent)

```python
async def verify_agent_output(candidate_code: str, file_path: str) -> tuple[bool, str]:
    """
    Verifica determinística e estaticamente o código gerado antes de aplicar.
    """
    import ast
    
    # 1. Validação de Sintaxe
    try:
        parsed_ast = ast.parse(candidate_code)
    except SyntaxError as e:
        return False, f"Sintaxe Python inválida: {e.msg} na linha {e.lineno}"

    # 2. Verificação de imports alucinados comuns
    for node in ast.walk(parsed_ast):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ["non_existent_pkg", "fake_gemini_lib"]:
                    return False, f"Import alucinado detetado: {alias.name}"
                    
    return True, "Código verificado com sucesso."
```

---

## 4. Used When
- Na geração de código que integra com bibliotecas externas.
- Na extração de fatos técnicos a partir de documentação interna.
- Na tomada de decisões de arquitetura e infraestrutura.

---

## 5. Common Failure Modes
- **Sycophancy (Concordância Cega)**: O agente concorda com uma premissa errada dada no prompt do utilizador e alucina fatos para justificar o erro.
- **Over-Confidence**: O modelo expressa alta confiança em números de portas, versões de pacotes ou parâmetros que mudaram nas versões recentes.

---

## 6. Related Concepts
- [[Model Harness Architecture]]
- [[RAG Architecture and Retrieval Strategies]]
- [[Compiler Feedback and Test-Driven Self-Repair]]
- [[Structured Outputs and Schema Validation]]

---

## 7. Sources
- *Ji et al., 2023 - Survey of Hallucination in Natural Language Generation*: https://arxiv.org/abs/2202.03629
- *OpenAI Prompt Engineering Best Practices - Reduce Hallucinations*: https://platform.openai.com/docs/guides/prompt-engineering

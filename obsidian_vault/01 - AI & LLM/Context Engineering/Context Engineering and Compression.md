---
type: concept
domain: ai-engineering
difficulty: advanced
tags:
  - ai-engineering
  - context-engineering
  - compression
  - token-budget
  - llm
status: verified
---

# 🧠 Context Engineering and Compression

## 1. Definição & O Problema do Efeito "Lost in the Middle"
**Context Engineering** é a disciplina de estruturar, ordenar, podar e comprimir a informação injetada na janela de contexto de um modelo de linguagem para maximizar a precisão do raciocínio e minimizar a latência e o custo de inferência.

Pesquisas empíricas (Liu et al., 2023 - *Lost in the Middle*) demonstram que LLMs apresentam desempenho significativamente superior quando a informação crítica está localizada **no início** (System Prompt) ou **no final imediato** (Prompt do utilizador / Última mensagem) da janela de contexto, sofrendo degradação substancial quando factos chave estão no meio de contextos longos (>32k tokens).

---

## 2. Técnicas de Compressão e Gestão de Contexto

```
+----------------------------------------------------------------+
| System Instructions & Core Constraints (Fixos no topo)        |
+----------------------------------------------------------------+
| Dynamic Working Memory / Scratchpad (Estado atual da missão)   |
+----------------------------------------------------------------+
| Relevant RAG Snippets (Top-k com BM25/Dense Reranked)          |
+----------------------------------------------------------------+
| Rolling Conversation History (Resumido via sliding window)     |
+----------------------------------------------------------------+
| Current User Goal / Immediate Execution Task (Fim do prompt)   |
+----------------------------------------------------------------+
```

### 2.1. Sliding Window com Sumarização Progressiva
- Mantém na íntegra apenas as últimas $N$ mensagens ($N \approx 4-6$).
- Mensagens anteriores a $N$ são condensadas periodicamente num parágrafo de "Estado Consolidado da Missão", descartando detalhes verbosos de logs de ferramentas já concluídas.

### 2.2. AST-Aware Code Truncation
- Ao alimentar código de um repositório para o agente:
  - O código do ficheiro alvo de modificação é incluído na íntegra.
  - Ficheiros de dependência ou interfaces têm apenas as assinaturas de funções e docstrings incluídas (removendo corpos de funções via AST), reduzindo o consumo de tokens em até 75%.

### 2.3. Desduplicação e Limpeza de Saídas de Ferramentas
- Logs extensos de compiladores ou suites de teste (`pytest`, `npm test`) contêm centenas de linhas de sucesso repetitivas.
- O filtro deve extrair exclusivamente o stacktrace de falha (`AssertionError`, `TypeError`, `FAILED`) e a contagem final (`3 passed, 1 failed`).

---

## 3. Algoritmo de Token Budgeting (Python)

```python
import tiktoken

def allocate_context_budget(
    system_prompt: str,
    rag_context: str,
    chat_history: list[dict],
    current_prompt: str,
    max_budget: int = 16000
) -> str:
    encoder = tiktoken.get_encoding("cl100k_base")
    
    # 1. Tokens reservados para sistema e tarefa atual (prioridade máxima)
    sys_tokens = len(encoder.encode(system_prompt))
    curr_tokens = len(encoder.encode(current_prompt))
    reserved = sys_tokens + curr_tokens + 1000  # margem para resposta
    
    available_budget = max_budget - reserved
    if available_budget <= 0:
        raise ValueError("System prompt + Current prompt excedem o orçamento total.")

    # 2. Alocar 40% do restante para RAG e 60% para histórico recente
    rag_budget = int(available_budget * 0.4)
    history_budget = int(available_budget * 0.6)

    # 3. Truncar RAG
    rag_tokens = encoder.encode(rag_context)
    if len(rag_tokens) > rag_budget:
        rag_context = encoder.decode(rag_tokens[:rag_budget]) + "\n...[Contexto truncado]"

    # 4. Podar histórico (do mais recente para o mais antigo)
    pruned_history = []
    accumulated_tokens = 0
    for msg in reversed(chat_history):
        msg_str = f"{msg['role']}: {msg['content']}\n"
        msg_tok = len(encoder.encode(msg_str))
        if accumulated_tokens + msg_tok > history_budget:
            break
        pruned_history.insert(0, msg_str)
        accumulated_tokens += msg_tok

    # Montagem final
    return f"{system_prompt}\n\n=== CONTEXTO RELEVANTE ===\n{rag_context}\n\n=== HISTÓRICO RECENTE ===\n{''.join(pruned_history)}\n\n=== TAREFA ATUAL ===\n{current_prompt}"
```

---

## 4. Used When
- Na construção de prompts para agentes autónomos que realizam missões de longa duração com muitas iterações.
- Ao injetar resultados de busca em base de código e documentação local do Obsidian.

---

## 5. Common Failure Modes
- **Truncating Critical Assertions**: Cortar a mensagem de erro do teste que continha o detalhe exato do bug.
- **Context Poisoning**: Deixar mensagens de alucinações de turnos anteriores acumularem-se no histórico sem correção, contaminando os turnos seguintes.

---

## 6. Related Concepts
- [[Anti-Pattern - Unbounded Context Accumulation]]
- [[RAG Architecture and Retrieval Strategies]]
- [[Model Harness Architecture]]

---

## 7. Sources
- *Liu et al., 2023 - Lost in the Middle: How Language Models Use Long Contexts*: https://arxiv.org/abs/2307.03172
- *OpenAI Cookbook - How to count tokens with tiktoken*: https://cookbook.openai.com/examples/how_to_count_tokens_with_tiktoken

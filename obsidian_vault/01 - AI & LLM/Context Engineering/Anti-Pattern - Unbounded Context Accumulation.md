---
type: anti-pattern
domain: ai-engineering
difficulty: intermediate
tags:
  - ai-engineering
  - anti-pattern
  - context-engineering
  - memory-management
status: verified
---

# ⚠️ Anti-Pattern - Unbounded Context Accumulation

## 1. O Problema
O anti-padrão de **Acumulação Desenfreada de Contexto** ocorre quando a framework de agentes concatena ingenuamente todas as mensagens de turnos anteriores, saídas completas de terminais, ficheiros inteiros lidos e erros de traceback na mesma lista `messages = [...]` enviada ao modelo em cada novo turno de raciocínio.

---

## 2. Por que Acontece
1. **Conveniência de Implementação**: É trivial fazer `messages.append({"role": "user", "content": tool_output})` sem lógica de podagem.
2. **Falsa Suposição de Janela Infinita**: Assumir que, pelo facto de os modelos suportarem 1M ou 2M tokens de contexto, "mais contexto é sempre melhor".

---

## 3. Consequências Danosas
- **Degradação de Atenção (Attention Dilution)**: O modelo esquece as restrições originais do *System Prompt* e foca-se excessivamente em detalhes obsoletos de 15 turnos atrás.
- **Context Poisoning**: Se o agente cometeu um raciocínio errado no turno 3, esse erro permanece no histórico e age como um "exemplo few-shot involuntário", levando o modelo a repetir o erro.
- **Explosão de Custos e Latência**: A latência de primeiro token (TTFT) cresce quadraticamente ou linearmente com o tamanho do prompt, e o consumo de créditos de API escala desnecessariamente.

---

## 4. Como Detetar o Anti-Padrão
- O tamanho do prompt cresce monotonicamente a cada iteração sem nunca diminuir.
- O agente começa a responder com base em ficheiros que já foram deletados ou refatorados em turnos anteriores.
- A latência por turno salta de 1s para >15s após 10 passos da missão.

---

## 5. Arquitetura de Correção (Padrão Recomendado)

```
[ INÍCIO DE NOVO PASSO DA MISSÃO ]
               |
               v
+-------------------------------------------------------------+
| 1. System Prompt Limpo (Constantes e Regras)                |
+-------------------------------------------------------------+
| 2. Scratchpad Consolidado (Sumário do estado atual)         |
+-------------------------------------------------------------+
| 3. Apenas os últimos 2 turnos de execução de ferramentas    |
+-------------------------------------------------------------+
| 4. Snippets pontuais relevantes via RAG (BM25/Vetorial)     |
+-------------------------------------------------------------+
```

---

## 6. Related Concepts
- [[Context Engineering and Compression]]
- [[Model Harness Architecture]]
- [[Planner-Executor Agent Pattern]]
- [[Agent Loop Detection and Circuit Breaker]]

---

## 7. Sources
- *Anthropic Research - Context Window Management*: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips
- *Lost in the Middle: How Language Models Use Long Contexts (Liu et al., 2023)*

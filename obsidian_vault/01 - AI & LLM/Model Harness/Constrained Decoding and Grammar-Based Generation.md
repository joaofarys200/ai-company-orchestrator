---
type: concept
domain: ai-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: advanced
tags:
  - ai-engineering
  - model-harness
  - constrained-decoding
  - grammars
  - pydantic
  - structured-outputs
prerequisites:
  - "[[Structured Outputs and Schema Validation]]"
  - "[[Model Harness Architecture]]"
related:
  - "[[Tool Calling Protocols and Structured Invocation]]"
  - "[[How to Handle Malformed Model Output]]"
used_by:
  - "[[JARVIS Model Harness Implementation]]"
failure_modes:
  - "[[Lesson - Unhandled Rate Limits and Context Explosion]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Outlines - Fast and Reliable Structured Generation with LLMs (Willard & Louf, 2023)
    type: PRIMARY_SOURCE
    url: https://arxiv.org/abs/2307.09702
  - title: Guidance - Controlled Generation Language
    type: PRIMARY_SOURCE
    url: https://github.com/guidance-ai/guidance
---

# 📐 Constrained Decoding and Grammar-Based Generation

## 1. Pergunta Central
> *Como garantir matematicamente que a saída de um modelo autoregressivo esteja 100% em conformidade com um esquema JSON ou gramática EBNF sem depender de tentativas e erros pós-geração?*

---

## 2. Mecanismo: Máscara de Logits Guiada por Autómato (Logit Masking via DFA/PDA)

Na amostragem autoregressiva padrão, para cada token $t_i$, o modelo calcula a distribuição de probabilidade sobre todo o vocabulário $V$:

$$P(t_i \mid t_{<i}) = \text{softmax}(z_i)$$

Com **Constrained Decoding (Decodificação Restrita)**:
1. O esquema JSON ou especificação OpenAPI é convertido num **Autômato Finito Determinístico (DFA)** ou **Autômato com Pilha (PDA)**.
2. A cada passo $i$, o estado atual do autômato determina o subconjunto de tokens válidos $V_{\text{valid}} \subseteq V$.
3. Uma máscara booleana $-\infty$ é aplicada aos logits de todos os tokens inválidos:
   $$z_i'(v) = \begin{cases} z_i(v) & \text{se } v \in V_{\text{valid}} \\ -\infty & \text{se } v \notin V_{\text{valid}} \end{cases}$$
4. A amostragem resultante é garantida por construção a produzir JSON sintaticamente perfeito.

```
[ Estado Atual do DFA: esperando fechar string ou vírgula ]
                  |
        (Calcula Logits do Vocabulário)
                  |
                  v
[ Token "age" -> Válido | Token "while" -> Inválido (-inf) | Token "}" -> Válido ]
                  |
                  v (Softmax sobre tokens válidos)
[ Saída 100% Determinística e Parseável ]
```

---

## 3. Trade-offs & Desempenho
- **Vantagens**: Elimina 100% das falhas de sintaxe JSON (`JSONDecodeError`); dispensa loops caros de repetição de prompt.
- **Desvantagens**: Overhead de pré-computação do autômato e indexação de prefixos de vocabulário; pode enviesar levemente a qualidade semântica se a restrição for excessivamente estrita.

---

## 4. Aplicação no JARVIS OS
Utilizado pelo `ModelHarness` para garantir que respostas dos agentes Clara e Devon que requerem chamadas de função ou planos de DAG nunca emitam chaves inexistentes ou tipos incompatíveis.

---

## 5. Related Concepts
- [[Structured Outputs and Schema Validation]]
- [[Tool Calling Protocols and Structured Invocation]]
- [[How to Handle Malformed Model Output]]

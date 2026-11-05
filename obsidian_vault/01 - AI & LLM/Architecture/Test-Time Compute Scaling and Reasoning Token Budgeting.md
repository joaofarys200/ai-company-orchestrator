---
type: concept
domain: ai-engineering
difficulty: advanced
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
tags:
  - ai-engineering
  - llm
  - test-time-compute
  - reasoning-models
  - token-budgeting
  - model-harness
---

# 🧠 Test-Time Compute Scaling and Reasoning Token Budgeting

## 1. Definição & Fundamento Matemático
O **Test-Time Compute Scaling** desloca parte do ganho de capacidade do pré-treino para o momento da inferência, alocando tokens adicionais de raciocínio latente/explícito (`<think>...</think>` ou *Chain-of-Thought* verificada) antes de emitir a resposta final.

Num pedido com limite total `max_output_tokens` ($B_{\text{total}}$), o orçamento divide-se estritamente entre raciocínio interno ($T_{\text{think}}$) e payload útil ($T_{\text{payload}}$):

$$B_{\text{total}} = T_{\text{think}} + T_{\text{payload}} \implies T_{\text{payload}} \le B_{\text{total}} - T_{\text{think}}$$

Quando $T_{\text{think}} \to B_{\text{total}}$, ocorre **Thinking-Token Starvation**: o modelo esgota o orçamento a raciocinar e trunca o JSON ou código final a meio da sintaxe (`finish_reason = MAX_TOKENS` / `length`).

---

## 2. Estratégias de Escalonamento em Inferência

| Estratégia | Mecanismo | Custo de Latência/Tokens | Caso de Uso Ideal |
|---|---|---|---|
| **Sequential CoT (`<think>`)** | Trajetória única auto-regressiva com revisão interna | Linear em $T_{\text{think}}$ | Síntese estruturada, debugging, planeamento |
| **Best-of-$N$ + Verifier** | $N$ amostras independentes avaliadas por compilador/testes | $N \times$ tokens (paralelizável) | Geração de patches validados por `pytest` |
| **Process Reward Model (PRM)** | Pontuação passo a passo em busca em árvore (MCTS/Beam) | Alto ($O(b \cdot d)$) | Provas formais, matemática, refatoração crítica |

---

## 3. Regras de Orçamentação no Model Harness

1. **Reserva Explícita de Payload**: Garantir $B_{\text{total}} \ge T_{\text{think\_expected}} + 2.5 \times T_{\text{schema\_min}}$ (`8192` tokens em esquemas densos) e limitar cardinalidades no prompt (máx. 4–7 itens por array).
2. **Calibração de Esforço**: Extração/classificação simples usa orçamento de raciocínio baixo/zero; arquitetura, provas e diagnóstico causal usam orçamento elevado.
3. **Strip Determinístico Pré-Parser**: Remover `<think>...</think>` fechados e descartar blocos `<think>` abertos antes de `json.loads` / Pydantic.
4. **Sem Retry Cego em `429`/Truncagem**: Nunca repetir o mesmo prompt sem aumentar $B_{\text{total}}$ ou comprimir o esquema pedido.

---

## 4. Implementação de Referência (Budget Guard)

```python
import re

THINK_CLOSED_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

def clean_reasoning_output(raw: str) -> str:
    cleaned = THINK_CLOSED_RE.sub("", raw or "")
    if "<think>" in cleaned.lower():
        cleaned = cleaned[:cleaned.lower().find("<think>")]
    return cleaned.strip()
```

---

## 5. Conceitos Relacionados & Fontes
- [[Model Harness Architecture]]
- [[Structured Outputs and Schema Validation]]
- [[Deterministic vs Stochastic Inference in Coding Pipelines]]
- [[Runbook - How to Prevent Thinking-Token Starvation and Mid-JSON Truncation]]
- **Fontes**: Snell et al. (2024), *Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters* (arXiv:2408.03314); Wei et al. (2022), *Chain-of-Thought Prompting Elicits Reasoning in LLMs*.

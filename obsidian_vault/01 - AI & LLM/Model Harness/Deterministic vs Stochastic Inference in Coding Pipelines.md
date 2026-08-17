---
type: comparison
domain: ai-engineering
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: intermediate
tags:
  - ai-engineering
  - model-harness
  - sampling
  - temperature
  - coding-agents
  - deterministic-inference
  - stochastic-inference
prerequisites:
  - "[[Model Harness Architecture]]"
related:
  - "[[Compiler Feedback and Test-Driven Self-Repair]]"
  - "[[Patch Generation and Safe Application]]"
used_by:
  - "[[JARVIS Model Harness Implementation]]"
failure_modes:
  - "[[Lesson - Regex Refactoring Syntax Corruption]]"
implementation:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
sources:
  - title: The Curious Case of Neural Text Degeneration (Holtzman et al., ICLR 2020)
    type: PRIMARY_SOURCE
    url: https://arxiv.org/abs/1904.09751
---

# ⚖️ Inferencia Deterministica vs Estocastica em Coding Pipelines

## 1. Pergunta Central
> *Como calibrar a inferência determinística (temperatura zero) vs amostragem estocástica (temperatura e top_p) para agentes de código e geração de patches?*

---

## 2. Tabela Comparativa de Estratégias de Amostragem

| Parâmetro | Decodificação Gulosa (Greedy / $T=0.0$) | Amostragem Moderada ($T=0.2 - 0.4$, $top\_p=0.9$) | Amostragem Criativa ($T \ge 0.7$) |
|---|---|---|---|
| **Mecanismo** | Seleciona sempre $\arg\max P(t_i \mid t_{<i})$ | Modula logits com temperatura baixa e corta a cauda via nucleus sampling | Distribuição ampla sobre vocabulário |
| **Reprodutibilidade** | 100% Determinístico (mesmo seed/hardware) | Parcialmente estocástico | Altamente divergente |
| **Aplicação Ideal** | **Geração de Patches, AST Refactoring, JSON Schemas** | **Exploração de Arquitetura, Decomposição de DAG** | **Brainstorming de Ideias de Mercado, Ideação** |
| **Risco Principal** | Loops repetitivos estéreis se preso num mínimo local | Pequenas variações entre execuções | **Alucinações de sintaxe e quebra de imports** |

---

## 3. Padrão de Roteamento de Temperatura no JARVIS OS

O `ModelHarness` do JARVIS define a temperatura com base no papel e tarefa do agente:

```python
def resolve_inference_params(agent_role: str, task_type: str) -> dict:
    if task_type in ("code_patching", "ast_refactoring", "schema_validation"):
        return {"temperature": 0.0, "top_p": 1.0}  # Determinismo rigoroso para Devon
    elif task_type in ("planning", "quality_audit"):
        return {"temperature": 0.2, "top_p": 0.95} # Baixa estocasticidade para Clara/Quinn
    elif task_type in ("market_ideation", "copywriting"):
        return {"temperature": 0.7, "top_p": 0.9}  # Criatividade para Alex
    return {"temperature": 0.1, "top_p": 0.9}
```

---

## 4. Related Concepts
- [[Compiler Feedback and Test-Driven Self-Repair]]
- [[Patch Generation and Safe Application]]
- [[Model Harness Architecture]]

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
  - evaluation
  - llm-as-a-judge
  - benchmarks
  - quality-gates
---

# 📏 LLM Evaluation Rigor - LLM-as-a-Judge, Calibration and Regression Gates

## 1. Hierarquia de Avaliação de Sistemas com LLMs
Alterar prompts, modelos, chunking ou parâmetros de temperatura sem uma suite de avaliação quantitativa introduz regressões silenciosas. Uma arquitetura de avaliação rigorosa aplica três camadas por ordem crescente de custo:

1. **Asserções Determinísticas de Nível 1 (Custo Zero, CI Bloqueante)**:
   - Validação de esquema JSON/Pydantic, verificação sintática AST, compilação/testes reais, ausência de marcadores proibidos (*anti-prefab / anti-placeholder*), integridade de citações e limites de latência/tokens.
2. **Métricas de Fidelidade e Recuperação de Nível 2 (RAG Triad)**:
   - *Context Recall / Precision@k* sobre pares `(query, gold_passage_id)`.
   - *Answer Faithfulness*: proporção de afirmações na resposta suportadas diretamente pelas passagens recuperadas ($F = \frac{|C_{\text{suportadas}}|}{|C_{\text{totais}}|}$).
3. **LLM-as-a-Judge Calibrado de Nível 3**:
   - Rubricas discretas binárias ou de 1–3 pontos (nunca escalas vagas 1–10 sem âncoras concretas) validadas contra um conjunto humano anotado (*Golden Set*).

---

## 2. Vieses Críticos de LLM-as-a-Judge e Correções

| Viés Conhecido | Sintoma | Mitigação Obrigatória |
|---|---|---|
| **Position Bias** | Juiz prefere consistentemente a resposta `A` (ou `B`) em comparações | Executar avaliação dupla trocando ordem `(A,B)` e `(B,A)`; exigir acordo |
| **Verbosity / Length Bias** | Respostas longas e prolixas recebem nota superior mesmo com erros | Penalizar afirmações não suportadas e avaliar densidade factual |
| **Self-Enhancement Bias** | Modelo pontua melhor textos gerados pela sua própria família | Usar juiz distinto do gerador ou rubricas baseadas em factos atómicos |

---

## 3. Calibração Estatística do Juiz
Um juiz automático só pode bloquear pipelines se atingir concordância substancial com anotadores humanos medida pelo **Kappa de Cohen** ($\kappa \ge 0.70$):

$$\kappa = \frac{p_o - p_e}{1 - p_e}$$

E, quando a prevalência real de aprovação $p$ é estimada via um classificador com sensibilidade $q_1$ (TPR) e especificidade $q_0$ (TNR), corrige-se o estimador de Rogan-Gladen:

$$\hat{\theta} = \text{clip}_{[0,1]}\left(\frac{\hat{p}_{\text{obs}} + q_0 - 1}{q_1 + q_0 - 1}\right)$$

---

## 4. Conceitos Relacionados & Fontes
- [[Structured Outputs and Schema Validation]]
- [[Hallucination Mitigation Techniques]]
- [[Unit Tests vs End-to-End Tests in Agent Validation]]
- [[Property-Based Testing, Metamorphic Relations and Fuzzing]]
- **Fontes**: Zheng et al. (2023), *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena* (NeurIPS); Es et al. (2024), *RAGAS: Automated Evaluation of Retrieval Augmented Generation*; Rogan & Gladen (1978), *Estimating Prevalence from the Results of a Screening Test*.


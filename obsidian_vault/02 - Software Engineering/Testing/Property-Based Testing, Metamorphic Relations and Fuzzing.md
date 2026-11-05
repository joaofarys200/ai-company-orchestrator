---
type: concept
domain: software-engineering
difficulty: advanced
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
tags:
  - software-engineering
  - testing
  - property-based-testing
  - hypothesis
  - metamorphic-testing
  - fuzzing
---

# 🧪 Property-Based Testing, Metamorphic Relations and Fuzzing

## 1. Limitações dos Testes Baseados em Exemplos
Testes unitários tradicionais verificam apenas um conjunto finito de pontos $\{(x_i, y_i)\}$ escolhidos pelo autor, falhando sistematicamente em casos extremos (*edge cases*: Unicode `NFD`/`NFC`, floats `NaN`/`Inf`, listas vazias, payloads truncados).

1. **Property-Based Testing (PBT — QuickCheck / Hypothesis)**:
   - Em vez de exemplos fixos, declara-se um quantificador universal $\forall x \in \mathcal{D}: P(f(x))$ sobre geradores estruturados.
   - Ao encontrar um contraexemplo $x^*$, o motor executa **Shrinking** (redução determinística na árvore de geração) até isolar o input mínimo reprodutível.
2. **Metamorphic Testing (Solução para o *Oracle Problem*)**:
   - Quando o output exato $f(x)$ é difícil de calcular a priori (compiladores, motores de busca/RAG, síntese multimodal), testam-se **Relações Metamórficas** entre pares de inputs transformados $T(x)$:
     - *Invariância por Permutação*: reordenar documentos num índice não altera o conjunto recuperado.
     - *Monotonicidade*: adicionar um documento relevante com correspondência exata não pode reduzir o score top-1.
3. **Coverage-Guided Fuzzing (Atheris / LibFuzzer)**:
   - Instrumenta ramos de bytecode/CFG para mutar inputs que descubram novos caminhos de execução, detetando exceções não tratadas, *ReDoS* e falhas de memória.

---

## 2. Taxonomia de Propriedades Algébricas Universais

| Padrão de Propriedade | Fórmula Invariante | Exemplo Prático no JARVIS OS |
|---|---|---|
| **Round-Trip (Codec)** | $\text{decode}(\text{encode}(x)) = x$ | Serialização JSON/YAML de checkpoints de missão |
| **Idempotência** | $f(f(x)) = f(x)$ | Normalização de paths, desduplicação de OCR, `strip_thinking` |
| **Oráculo Simplificado** | $f_{\text{fast}}(x) = f_{\text{naive}}(x)$ | Índice HNSW/cache vs varredura linear exata |
| **Invariante Estrutural** | $\text{inv}(f(x)) = \text{True}$ | Grafo Obsidian com `0` links quebrados após mutação |

---

## 3. Implementação de Referência (Hypothesis em Python)

```python
from hypothesis import given, strategies as st
import json

@given(st.dictionaries(st.text(min_size=1), st.one_of(st.integers(), st.text(), st.booleans())))
def test_atomic_state_roundtrip_and_idempotence(payload: dict) -> None:
    serialized_once = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    restored = json.loads(serialized_once)
    serialized_twice = json.dumps(restored, sort_keys=True, ensure_ascii=False)
    assert restored == payload
    assert serialized_once == serialized_twice
```

---

## 4. Conceitos Relacionados & Fontes
- [[Unit Tests vs End-to-End Tests in Agent Validation]]
- [[Idempotency in Software Systems]]
- [[Compiler Feedback and Test-Driven Self-Repair]]
- [[LLM Evaluation Rigor - LLM-as-a-Judge, Calibration and Regression Gates]]
- **Fontes**: Claessen & Hughes (2000), *QuickCheck: A Lightweight Tool for Random Testing of Haskell Programs* (ICFP); Chen et al. (2018), *Metamorphic Testing: A Review of Challenges and Opportunities* (ACM Computing Surveys); MacIver et al. (2019), *Hypothesis*.


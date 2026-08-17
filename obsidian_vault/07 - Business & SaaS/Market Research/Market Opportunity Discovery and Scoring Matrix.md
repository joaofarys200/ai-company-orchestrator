---
type: concept
domain: business-economics
difficulty: intermediate
tags:
  - business
  - market-research
  - scoring
  - rice-framework
  - product-validation
status: verified
---

# 🎯 Market Opportunity Discovery and Scoring Matrix

## 1. O Framework de Priorização RICE / ICE

Para agentes autónomos que realizam descoberta de oportunidades de mercado e avaliação de viabilidade de software:

### 1.1. Formulação RICE
$$\text{RICE Score} = \frac{\text{Reach (Alcance)} \times \text{Impact (Impacto)} \times \text{Confidence (Confiança)}}{\text{Effort (Esforço de Engenharia)}}$$

Onde:
- **Reach**: Número de potenciais utilizadores/clientes impactados por trimestre.
- **Impact**: Multiplicador de valor ($3 = \text{Massivo}$, $2 = \text{Alto}$, $1 = \text{Médio}$, $0.5 = \text{Baixo}$).
- **Confidence**: Grau de evidência factual comprovada ($1.0 = 100\% \text{ Dados Reais de Vendas}$, $0.8 = \text{Testes de Fumaça Positivos}$, $0.5 = \text{Apenas Pesquisa Teórica}$, $<0.3 = \text{Suposição/Especulação}$).
- **Effort**: Esforço em semanas-pessoa ou missões de agentes.

---

## 2. Matriz de Avaliação de Oportunidades no JARVIS OS

```python
from dataclasses import dataclass

@dataclass
class MarketOpportunity:
    name: str
    reach: int          # Ex: 5000 clientes
    impact: float       # 0.5 a 3.0
    confidence: float   # 0.1 a 1.0
    effort_days: float  # Dias de desenvolvimento do agente

    @property
    def rice_score(self) -> float:
        if self.effort_days <= 0:
            return 0.0
        return (self.reach * self.impact * self.confidence) / self.effort_days

    @property
    def is_viable_for_mvp(self) -> bool:
        # Critério: Alta confiança (>0.7) e score competitivo
        return self.confidence >= 0.7 and self.rice_score >= 100.0
```

---

## 3. Diretriz para Agentes Autónomos
Agentes NUNCA devem recomendar o desenvolvimento de um produto completo baseado em `Confidence < 0.5`. O primeiro passo mandatório é sempre a validação via teste de baixa fidelidade ([[How to Validate Product Ideas with Low-Cost Experiments]]).

---

## 4. Related Concepts
- [[Distinguishing Real vs Synthetic Market Evidence]]
- [[How to Validate Product Ideas with Low-Cost Experiments]]
- [[SaaS Unit Economics - CAC, LTV and Magic Number]]

---

## 5. Sources
- *Sean McBride - RICE: Simple prioritization for product managers (Intercom)*: https://www.intercom.com/blog/rice-simple-prioritization-for-product-managers/
- *The Mom Test: How to talk to customers & learn if your business is a good idea (Rob Fitzpatrick)*

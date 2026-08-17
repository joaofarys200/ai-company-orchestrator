---
type: troubleshooting
domain: business-economics
difficulty: intermediate
tags:
  - business
  - troubleshooting
  - experiments
  - product-validation
  - pretotyping
status: verified
---

# 🛠️ Como Validar Ideias de Produto com Experimentos de Baixo Custo e Smoke Tests

## 1. Critérios de Sucesso e Falha
- **Critério de Sucesso**: O experimento de baixo custo e smoke test mede a taxa de conversão real com evidência externa verificada antes de alocar recursos de engenharia. de software ou funcionalidade comercial de grande porte.

---

## 2. O Método Pretótipo / Smoke Test em 5 Passos

```
[ Ideia / Hipótese de Produto ]
               |
               v
[ Passo 1: Definição da Métrica de Compromisso (*Skin-in-the-Game Metric*) ]
  - Ex: Pelo menos 20 inscrições com email profissional em 100 visitas (20% conv)
               |
               v
[ Passo 2: Construção da Landing Page de Teste (1 Dia) ]
  - Proposta de valor clara, screenshots/mockups realistas e botão "Solicitar Acesso"
               |
               v
[ Passo 3: Geração de Tráfego Inicial Controlado ]
  - Publicação em comunidades de nicho (Reddit, Hacker News, Twitter) ou $30 em Google Ads
               |
               v
[ Passo 4: Coleta e Auditoria de Métricas Reais ]
  - Taxa de rejeição, tempo na página, cliques no botão de checkout
               |
               v
[ Passo 5: Decisão Go / No-Go ]
  - Se meta atingida -> Iniciar desenvolvimento do MVP
  - Se meta falhou -> Pivotar proposta de valor ou abandonar a ideia
```

---

## 3. Padrão de Análise Estatística de Resultados

```python
import math

def calculate_conversion_confidence(visitors: int, conversions: int) -> dict:
    if visitors <= 0:
        return {"error": "Sem visitantes"}

    p_hat = conversions / visitors
    # Intervalo de confiança de 95% (z = 1.96)
    margin_of_error = 1.96 * math.sqrt((p_hat * (1 - p_hat)) / visitors)
    
    ci_lower = max(0.0, p_hat - margin_of_error)
    ci_upper = min(1.0, p_hat + margin_of_error)

    return {
        "visitors": visitors,
        "conversions": conversions,
        "conversion_rate_pct": round(p_hat * 100, 2),
        "ci_95_pct": [round(ci_lower * 100, 2), round(ci_upper * 100, 2)],
        "statistically_significant": visitors >= 100 and (ci_lower > 0.02)
    }
```

---

## 4. Related Concepts
- [[Distinguishing Real vs Synthetic Market Evidence]]
- [[Market Opportunity Discovery and Scoring Matrix]]
- [[SaaS Unit Economics - CAC, LTV and Magic Number]]

---

## 5. Sources
- *Alberto Savoia - Pretotyping: Make Sure You Are Building The Right It Before You Build It Right*
- *Eric Ries - The Lean Startup: How Constant Innovation Creates Radically Successful Businesses*

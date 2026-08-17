---
type: concept
domain: devops
difficulty: intermediate
tags:
  - devops
  - sre
  - sli
  - slo
  - error-budgets
  - observability
status: verified
---

# 📊 SLI-SLO Metrics and Error Budgets

## 1. Definições Formais (Google SRE Framework)

- **SLI (Service Level Indicator)**: Uma medida quantitativa do nível de serviço prestado aos utilizadores em tempo real.
  $$\text{SLI} = \frac{\text{Eventos Bons}}{\text{Total de Eventos Válidos}} \times 100\%$$
- **SLO (Service Level Objective)**: A meta interna de confiabilidade que o serviço deve atingir durante uma janela temporal móvel (ex: 30 dias). Exemplo: $\text{SLO} = 99.5\%$.
- **Error Budget (Orçamento de Erro)**: A margem de falha tolerada pelo SLO:
  $$\text{Error Budget} = 100\% - \text{SLO} = 100\% - 99.5\% = 0.5\%$$

```
+----------------------------------------------------------------+
|                   TOTAL DE REQUISIÇÕES (100%)                  |
+----------------------------------------------------------------+
|       Meta de Sucesso do SLO (99.5%)       | Error Budget (0.5%)|
+--------------------------------------------+-------------------+
                                             | Margem para Deploys,
                                             | Experiências e Falhas
```

---

## 2. Taxa de Queima de Orçamento (Burn Rate)
A **Burn Rate** mede a velocidade com que o sistema consome o seu Error Budget:
- **Burn Rate = 1**: Consome 100% do orçamento de erro exatamente na janela de 30 dias (situação estável).
- **Burn Rate = 14.4**: Consome 100% do orçamento em apenas 2 dias (incidente crítico que exige alerta imediato).

$$\text{Burn Rate} = \frac{1 - \text{SLI}_{\text{janela_curta}}}{1 - \text{SLO}}$$

---

## 3. Política de Resposta a Esgotamento do Error Budget
1. **Se Error Budget > 0%**: A equipa e os agentes têm liberdade para fazer deploys rápidos de novas features e refatorações complexas.
2. **Se Error Budget $\le$ 0%**: *Feature Freeze*. Todos os agentes focam-se exclusivamente em estabilidade, testes, mitigação de bugs e fiabilidade da infraestrutura.

---

## 4. Related Concepts
- [[Healthchecks and Circuit Breakers]]
- [[Structured Logging and Distributed Trace Context]]
- [[SRE_Site_Reliability_Engineering_Body_of_Knowledge]]

---

## 5. Sources
- *Site Reliability Engineering: How Google Runs Production Systems (Beyer et al.)*: https://sre.google/sre-book/service-level-objectives/
- *Google Cloud - Developing SLIs and SLOs*: https://cloud.google.com/architecture/devops/devops-measurement-sli-slo-error-budgets

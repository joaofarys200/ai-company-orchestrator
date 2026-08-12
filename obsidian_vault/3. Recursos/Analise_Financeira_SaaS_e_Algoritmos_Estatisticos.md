# 📊 Tratado Avançado de Análise Financeira SaaS & Algoritmos Estatísticos

## 📌 1. Visão Geral
Este tratado fornece o enquadramento teórico e prático para o cálculo de métricas de SaaS, simulações estatísticas Monte Carlo e deteção estatística de anomalias em séries temporais no **JARVIS OS**.

---

## 📈 2. Economia Unitária & Métricas Financeiras SaaS

### 2.1. Métricas de Receita Recorrente
- **MRR (Monthly Recurring Revenue)**: Receita mensal recorrente contratada.
- **ARR (Annual Recurring Revenue)**: Run-rate de receita anualizada:
  $$\text{ARR} = \text{MRR} \times 12$$

### 2.2. Avaliação da Eficiência Comercial (LTV & CAC)
- **CAC (Customer Acquisition Cost)**: Custo total de vendas e marketing por cada cliente adquirido:
  $$\text{CAC} = \frac{\text{Custos de Vendas + Marketing}}{\text{Novos Clientes Adquiridos}}$$
- **LTV (Lifetime Value)**: Valor líquido que um cliente gera durante todo o seu tempo de permanência:
  $$\text{LTV} = \frac{\text{ARPU} \times \text{Margem Bruta \%}}{\text{Taxa de Churn Mensal \%}}$$
- **Rácio LTV:CAC**: Medida de sustentabilidade de crescimento. O padrão de excelência de mercado exige um rácio $\ge 3.0\text{x}$.

---

## 🎲 3. Simulação Estatística Monte Carlo (Movimento Browniano Geométrico)

### 3.1. Formulação Matemática
Para projetar a trajetória de crescimento do MRR ao longo de $T$ meses sob incerteza de mercado, utiliza-se a Equação Diferencial Estocástica do Movimento Browniano Geométrico (GBM):
$$S_t = S_{t-1} \times \exp\left( \left(\mu - \frac{\sigma^2}{2}\right) \Delta t + \sigma \sqrt{\Delta t} \, Z \right)$$

Onde:
- $S_t$: MRR no mês $t$.
- $\mu$: Taxa média esperada de crescimento mensal.
- $\sigma$: Volatilidade ou desvio padrão da taxa de crescimento.
- $Z \sim \mathcal{N}(0, 1)$: Variável aleatória gaussiana com média 0 e variância 1.

### 3.2. Análise por Percentis Executivos
Após executar $N = 500$ simulações independentes:
- **Percentil 10 (P10)**: Cenário conservador/pessimista (apenas 10% de hipóteses de ficar abaixo).
- **Percentil 50 (P50)**: Mediana esperada do crescimento.
- **Percentil 90 (P90)**: Cenário otimista.

---

## 📉 4. Deteção Estatística de Anomalias em Séries Temporais (Sliding Window Z-Score)

### 4.1. Algoritmo de Janela Deslizante
Para detetar picos anormais de CPU, memória ou churn sem alarmes falsos, o sistema calcula a pontuação Z móvel (*Z-Score*) sobre uma janela temporal deslizante de tamanho $W$:
$$\mu = \frac{1}{W} \sum_{i=1}^{W} x_i$$
$$\sigma = \sqrt{\frac{1}{W} \sum_{i=1}^{W} (x_i - \mu)^2}$$
$$Z = \frac{x_{\text{atual}} - \mu}{\max(\sigma, \epsilon)}$$

### 4.2. Classificação de Gravidade de Incidentes
- **Sem Anomalia**: $|Z| < 2.0$
- **Alerta WARNING**: $2.0 \le |Z| < 3.0$
- **Alerta CRITICAL**: $|Z| \ge 3.0$ (dispara publicação imediata de evento Pub/Sub via `AsyncEventBus`).

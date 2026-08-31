# 📈 Sistema de Suporte à Decisão: Previsão de Séries Temporais & Otimização Metaheurística

<p align="center">
  <img src="https://img.shields.io/badge/Linguagem-Python_3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Previs%C3%A3o-SARIMAX_%7C_VAR_%7C_XGBoost-blue?style=for-the-badge" alt="Previsão" />
  <img src="https://img.shields.io/badge/Otimiza%C3%A7%C3%A3o-NSGA--II_%7C_GA_%7C_Simulated_Annealing-darkgreen?style=for-the-badge" alt="Otimização" />
  <img src="https://img.shields.io/badge/Interface-Streamlit_%2B_Plotly-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit" />
  <img src="https://img.shields.io/badge/Unidade_Curricular-Previs%C3%A3o_%26_Otimiza%C3%A7%C3%A3o-orange?style=for-the-badge" alt="TIAPO" />
</p>

> Sistema de Suporte à Decisão (DSS) que integra modelos econométricos e de machine learning para previsão multivariada de procura com algoritmos evolutivos de otimização metaheurística multiobjetivo para alocação de recursos em redes de retalho.

---

## 🎯 Contextualização e Objetivo

As redes de distribuição e retalho enfrentam dois desafios operacionais interligados:
1. **Incerteza da Procura**: Prever o fluxo de clientes e volume de vendas em múltiplas lojas regionais considerando sazonalidade temporal, fatores meteorológicos e eventos turísticos exógenos.
2. **Alocação Restrita de Recursos**: Resolver problemas complexos de escalonamento não linear com 84 variáveis de decisão, sujeitos a limites físicos de stock, restrições laborais e múltiplos objetivos em conflito (minimização de custos operacionais vs. maximização do nível de serviço).

Este projeto desenvolve uma solução completa em duas fases, complementada por um painel de controlo executivo em **Streamlit**.

---

## 🏛️ Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          INGESTÃO DE DADOS TEMPORAIS                        │
│  Séries por Loja: Baltimore • Lancaster • Filadélfia • Richmond             │
│  Variáveis Exógenas: Eventos Turísticos • Precipitação • Temperatura        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 FASE 1: PREVISÃO MULTIVARIADA DE PROCURA                    │
│  • Modelos Econométricos: SARIMAX (Sazonal com Exógenas) e VAR              │
│  • Modelos de Machine Learning: XGBoost, Random Forest e Ridge              │
│  • Validação Temporal com Backtesting de 12 janelas (Horizontes h ∈ [1, 7]) │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Matriz de Procura Estimada
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 FASE 2: OTIMIZAÇÃO METAHEURÍSTICA EVOLUTIVA                 │
│  • Espaço de Procura: 84 Variáveis ([PR, X, J] × 4 Lojas × 7 Dias)          │
│  • Algoritmos: Pymoo NSGA-II (Multiobjetivo), Pymoo GA e Scipy Annealing    │
│  • Operadores Customizados: Mutação multiplicativa e projeção/reparação     │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Escalonamento Ótimo de Recursos
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 DASHBOARD INTERATIVO EXECUTIVO (STREAMLIT)                  │
│  Curvas de Procura • Fronteiras de Pareto • Tabelas de Turnos • Gráficos    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔬 Metodologia Técnica

### 1. Pipeline de Previsão de Séries Temporais (`forecast_multivariate.py`)
- Avaliação comparativa de modelos estatísticos clássicos (`SARIMAX`, `VAR`) contra ensembles baseados em árvores de decisão (`XGBoost`, `RandomForestRegressor`).
- Enriquecimento com variáveis exógenas (temperatura diária, chuva, feriados, eventos locais).
- Métricas de erro computadas sobre validação temporal estrita: **RMSE**, **MAE** e **sMAPE**.

### 2. Otimização Metaheurística Multiobjetivo (`otimizacao_metaheuristica_bibliotecas.py`)
- Vetor de decisão $\mathbf{x} \in \mathbb{R}^{84}$ que define os recursos alocados para 3 linhas de produto $[PR, X, J]$ em 4 lojas durante o horizonte de planeamento semanal de 7 dias.
- **Algoritmos Avaliados**:
  - **NSGA-II (*Non-dominated Sorting Genetic Algorithm II*)**: Mapeia a Fronteira de Pareto entre custo operacional e taxa de atendimento ao cliente.
  - **Algoritmo Genético (GA) mono-objetivo**.
  - **Simulated Annealing (Scipy)**: Refinamento por arrefecimento simulado.
  - **Hill Climbing & Monte Carlo (Nevergrad)**.
- **Operador de Reparação Personalizado (`Repair`)**: Garante que soluções geradas por mutação cumprem as restrições físicas de capacidade sem descartar indivíduos viáveis.

### 3. Painel de Visualização e Simulação (`app.py`)
- Interface desenvolvida em **Streamlit** com gráficos interativos em **Plotly**.
- Permite a simulação de cenários operacionais "what-if" com ajuste de parâmetros e visualização da fronteira de compromisso entre custo e serviço.

---

## 🛠️ Tecnologias Utilizadas

- **Linguagem**: Python 3.10+
- **Econometria e Previsão**: `statsmodels`, `xgboost`, `scikit-learn`, `scipy`
- **Otimização e Algoritmos Genéticos**: `pymoo`, `nevergrad`, `scipy.optimize`
- **Engenharia de Dados**: `pandas`, `numpy`
- **Interface e Gráficos**: `streamlit`, `plotly`, `matplotlib`, `seaborn`

---

## 🚀 Instalação e Execução

```bash
# Clonar o repositório
git clone https://github.com/joaofarys200/Tiapose2026.git
cd Tiapose2026

# Criar e ativar ambiente virtual
python -m venv venv
source venv/bin/activate  # No Windows: .\venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

# Executar a validação de previsão
python forecast_multivariate.py

# Iniciar o dashboard interativo
streamlit run app.py
```

---

## 👥 Contexto Académico

Desenvolvido no âmbito da unidade curricular de **Teoria da Informação e Algoritmos de Previsão e Otimização** na **Universidade do Minho**.

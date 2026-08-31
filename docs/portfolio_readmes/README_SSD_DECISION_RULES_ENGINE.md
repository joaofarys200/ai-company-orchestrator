# 🛒 Motor de Regras de Suporte à Decisão para E-Commerce

<p align="center">
  <img src="https://img.shields.io/badge/Linguagem-Python_3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Motor-Regras_JSON_%7C_DecisionRules.io-008080?style=for-the-badge" alt="Motor de Regras" />
  <img src="https://img.shields.io/badge/Interface-Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit" />
  <img src="https://img.shields.io/badge/Unidade_Curricular-Sistemas_de_Suporte_%C3%A0_Decis%C3%A3o-darkgreen?style=for-the-badge" alt="SSD" />
</p>

> Sistema de Suporte à Decisão (DSS) para comércio eletrónico que avalia a composição do carrinho de compras em tempo real e dispara recomendações dinâmicas de upsell e cross-sell baseadas em regras de negócio declarativas, com cálculo de margens e integração à API do DecisionRules.io.

---

## 🎯 Contextualização e Objetivo

Algoritmos tradicionais de recomendação baseados em "caixa negra" muitas vezes não oferecem a transparência e o controlo necessários para campanhas comerciais dirigidas. Plataformas de e-commerce necessitam de motores de decisão explicáveis onde regras de negócio (valor mínimo no carrinho, categoria de produto, segmento de cliente) determinem descontos e sugestões de produtos com justificações claras para o consumidor.

Este projeto implementa uma arquitetura desacoplada de avaliação de regras de negócio com suporte híbrido (execução local ou via serviço na nuvem) e um simulador interativo em **Streamlit**.

---

## 🏛️ Arquitetura da Solução

```
┌────────────────────────────────────────────────────────┐
│            Simulador Interativo em Streamlit           │ (Construção do carrinho e catálogo)
└───────────────────────────┬────────────────────────────┘
                            │ Carrinho ativo e Tipo de Cliente
                            ▼
┌────────────────────────────────────────────────────────┐
│            RulesEngine (rules_engine.py)               │
│  - Avalia produtos, categorias, totais e margens       │
│  - Executa regras de negócio declarativas locais       │
│  - Suporta integração via API REST (DecisionRules.io)  │
└───────────────────────────┬────────────────────────────┘
                            │
               ┌────────────┴────────────┐
               ▼                         ▼
┌───────────────────────────┐ ┌──────────────────────────┐
│   catalog.json (Produtos) │ │   rules.json (Regras)    │
│  - SKUs, preços e margens │ │  - Condições e ações     │
└───────────────────────────┘ └──────────────────────────┘
```

---

## 🔬 Capacidades Chave

1. **Regras de Negócio Declarativas (`rules.json`)**:
   - Condições flexíveis: `min_cart_total`, `has_product_in_cart`, `has_category_in_cart`, `client_type`.
   - Ações estruturadas: ID do produto recomendado, percentagem de desconto aplicada, pontuação de prioridade e justificação em linguagem natural.
2. **Avaliação Híbrida**:
   - Avaliação local de baixa latência em Python.
   - Suporte a chamadas remotas de governação de regras via **DecisionRules.io**.
3. **Painel de Simulação (`app.py`)**:
   - Simulador visual de compras com cálculo instantâneo do impacto na margem de lucro e exibição imediata do motivo da recomendação.

---

## 🛠️ Tecnologias Utilizadas

- **Backend**: Python 3.10+, `requests`
- **Gestão de Dados**: `pandas`, `json`
- **Interface Gráfica**: Streamlit, Plotly
- **Governação de Regras**: DecisionRules.io API & Schemas JSON

---

## 🚀 Instalação e Execução

```bash
# Clonar o repositório
git clone https://github.com/joaofarys200/SSD.git
cd SSD

# Instalar dependências
pip install streamlit pandas requests plotly

# Iniciar o painel de suporte à decisão
streamlit run app.py
```

---

## 👥 Contexto Académico

Desenvolvido no âmbito da unidade curricular de **Sistemas de Suporte à Decisão** na **Universidade do Minho**.

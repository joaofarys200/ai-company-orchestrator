# 🚨 SRE BOK — Site Reliability Engineering & Observability (Google SRE Manual)

## 📌 1. Visão Geral
Este manual compila as práticas e disciplinas do **Google Site Reliability Engineering (SRE)** e Observabilidade Industrial para governar a operação, monitorização e resiliência das aplicações geridas pelo **JARVIS OS**.

---

## 📐 2. Os Três Pilares dos Atributos de Serviço (SLI, SLO e SLA)

### 2.1. SLI (Service Level Indicator)
- **Definição**: Uma métrica quantitativa medida em tempo real sobre o comportamento do serviço.
- **Exemplo**: Rácio de pedidos HTTP respondidos com sucesso (`status < 500`) divididos pelo total de pedidos recebidos:
  $$\text{SLI}_{\text{disponibilidade}} = \frac{\text{Pedidos com Status } < 500}{\text{Total de Pedidos HTTP}} \times 100\%$$

### 2.2. SLO (Service Level Objective)
- **Definição**: A meta interna definida para um SLI, estabelecendo o limite aceitável de disponibilidade ou latência.
- **Exemplo**: A latência do endpoint `/api/ingest` deve ser inferior a `200ms` para `99.0%` dos pedidos durante um mês rolling.

### 2.3. SLA (Service Level Agreement)
- **Definição**: O contrato comercial formal com os clientes que define as consequências financeiras/penalidades caso o SLO não seja atingido.

---

## 💸 3. Gestão de Orçamento de Erro (Error Budget)

- **Orçamento de Erro**: O limite máximo de indisponibilidade permitida:
  $$\text{Error Budget} = 100\% - \text{SLO}$$
- **Exemplo**: Se o SLO é 99.9% num mês, o Error Budget é 0.1% (~43 minutos de indisponibilidade).
- **Regra de Ouro do SRE**:
  - Enquanto o **Error Budget for positivo (> 0)**, a equipa e os agentes têm luz verde para lançar novas funcionalidades e refatorações.
  - Se o **Error Budget for esgotado (= 0)**, a publicação de novas funcionalidades é bloqueada e 100% da capacidade de engenharia é redirecionada para a estabilidade, testes e resiliência da infraestrutura.

---

## 👁️ 4. Os Três Pilares da Observabilidade (Metrics, Logs & Traces)

```
                       ┌─────────────────────────┐
                       │    OBSERVABILIDADE     │
                       └────────────┬────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
   ┌──────────┐               ┌──────────┐               ┌──────────┐
   │ MÉTRIBAS │               │   LOGS   │               │ TRACES   │
   │(Metrics) │               │          │               │ (Spans)  │
   └──────────┘               └──────────┘               └──────────┘
```

1. **Métricas (Metrics)**: Valores numéricos agregados ao longo do tempo (CPU, RAM, RPS, Latência). Ideais para dashboards e alertas automatizados.
2. **Logs Estruturados**: Registos de eventos em formato JSON contendo contexto detalhado (`timestamp`, `logger`, `level`, `correlation_id`, `trace_id`).
3. **Traces Distribuídos (OpenTelemetry / Spans)**: Acompanham a jornada exata de um pedido através de múltiplos microserviços e processos em background, identificando gargalos e latência acumulada em cada etapa.

---

## ⚡ 5. Análise de Causa-Raiz & Postmortems Sem Culpados (Blameless Postmortems)

Após a resolução de qualquer incidente grave em produção:
1. **Cronologia dos Eventos**: Registo exato com marcas temporais da deteção, mitigação e resolução.
2. **Causa Raiz (Root Cause Analysis)**: Aplicação dos "5 Porquês" até identificar a falha arquitetural subjacente.
3. **Ações Corretivas Preventivas**: Criação imediata de tarefas prioritárias (ex: adicionar um teste unitário que reproduza o erro, configurar um alarme prévio ou adicionar um *Circuit Breaker*).

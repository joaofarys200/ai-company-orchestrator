---
type: concept
domain: devops
difficulty: advanced
tags:
  - devops
  - sre
  - google-sre
status: verified
---

# ðŸš¨ SRE BOK â€” Site Reliability Engineering & Observability (Google SRE Manual)

## ðŸ“Œ 1. VisÃ£o Geral
Este manual compila as prÃ¡ticas e disciplinas do **Google Site Reliability Engineering (SRE)** e Observabilidade Industrial para governar a operaÃ§Ã£o, monitorizaÃ§Ã£o e resiliÃªncia das aplicaÃ§Ãµes geridas pelo **JARVIS OS**.

---

## ðŸ“ 2. Os TrÃªs Pilares dos Atributos de ServiÃ§o (SLI, SLO e SLA)

### 2.1. SLI (Service Level Indicator)
- **DefiniÃ§Ã£o**: Uma mÃ©trica quantitativa medida em tempo real sobre o comportamento do serviÃ§o.
- **Exemplo**: RÃ¡cio de pedidos HTTP respondidos com sucesso (`status < 500`) divididos pelo total de pedidos recebidos:
  $$\text{SLI}_{\text{disponibilidade}} = \frac{\text{Pedidos com Status } < 500}{\text{Total de Pedidos HTTP}} \times 100\%$$

### 2.2. SLO (Service Level Objective)
- **DefiniÃ§Ã£o**: A meta interna definida para um SLI, estabelecendo o limite aceitÃ¡vel de disponibilidade ou latÃªncia.
- **Exemplo**: A latÃªncia do endpoint `/api/ingest` deve ser inferior a `200ms` para `99.0%` dos pedidos durante um mÃªs rolling.

### 2.3. SLA (Service Level Agreement)
- **DefiniÃ§Ã£o**: O contrato comercial formal com os clientes que define as consequÃªncias financeiras/penalidades caso o SLO nÃ£o seja atingido.

---

## ðŸ’¸ 3. GestÃ£o de OrÃ§amento de Erro (Error Budget)

- **OrÃ§amento de Erro**: O limite mÃ¡ximo de indisponibilidade permitida:
  $$\text{Error Budget} = 100\% - \text{SLO}$$
- **Exemplo**: Se o SLO Ã© 99.9% num mÃªs, o Error Budget Ã© 0.1% (~43 minutos de indisponibilidade).
- **Regra de Ouro do SRE**:
  - Enquanto o **Error Budget for positivo (> 0)**, a equipa e os agentes tÃªm luz verde para lanÃ§ar novas funcionalidades e refatoraÃ§Ãµes.
  - Se o **Error Budget for esgotado (= 0)**, a publicaÃ§Ã£o de novas funcionalidades Ã© bloqueada e 100% da capacidade de engenharia Ã© redirecionada para a estabilidade, testes e resiliÃªncia da infraestrutura.

---

## ðŸ‘ï¸ 4. Os TrÃªs Pilares da Observabilidade (Metrics, Logs & Traces)

```
                       â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                       â”‚    OBSERVABILIDADE     â”‚
                       â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                    â”‚
         â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
         â–¼                          â–¼                          â–¼
   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”               â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”               â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
   â”‚ MÃ‰TRIBAS â”‚               â”‚   LOGS   â”‚               â”‚ TRACES   â”‚
   â”‚(Metrics) â”‚               â”‚          â”‚               â”‚ (Spans)  â”‚
   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜               â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜               â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

1. **MÃ©tricas (Metrics)**: Valores numÃ©ricos agregados ao longo do tempo (CPU, RAM, RPS, LatÃªncia). Ideais para dashboards e alertas automatizados.
2. **Logs Estruturados**: Registos de eventos em formato JSON contendo contexto detalhado (`timestamp`, `logger`, `level`, `correlation_id`, `trace_id`).
3. **Traces DistribuÃ­dos (OpenTelemetry / Spans)**: Acompanham a jornada exata de um pedido atravÃ©s de mÃºltiplos microserviÃ§os e processos em background, identificando gargalos e latÃªncia acumulada em cada etapa.

---

## âš¡ 5. AnÃ¡lise de Causa-Raiz & Postmortems Sem Culpados (Blameless Postmortems)

ApÃ³s a resoluÃ§Ã£o de qualquer incidente grave em produÃ§Ã£o:
1. **Cronologia dos Eventos**: Registo exato com marcas temporais da deteÃ§Ã£o, mitigaÃ§Ã£o e resoluÃ§Ã£o.
2. **Causa Raiz (Root Cause Analysis)**: AplicaÃ§Ã£o dos "5 PorquÃªs" atÃ© identificar a falha arquitetural subjacente.
3. **AÃ§Ãµes Corretivas Preventivas**: CriaÃ§Ã£o imediata de tarefas prioritÃ¡rias (ex: adicionar um teste unitÃ¡rio que reproduza o erro, configurar um alarme prÃ©vio ou adicionar um *Circuit Breaker*).


# 🔍 ECONOMIC GATEWAY REALITY AUDIT

**Data**: 2026-08-13  
**Objetivo**: Auditoria read-only rigorosa sobre a realidade operacional vs. simulação local no `EconomicExecutionGateway` e nos cenários E01 a E10.

---

## 1. 🏗️ Arquitetura Atual do Gateway

A arquitetura atual do `backend/gateway/` é composta por 4 subsistemas em Python que interagem com o sistema operativo local e bases de dados SQLite:

```
[EconomicMissionRunner]
         │
         ├──► [LeadCaptureGateway]       ──► config/leads.sqlite (Local DB)
         ├──► [WebDeploymentGateway]     ──► sandbox_dir/ + http://127.0.0.1:8080 (Localhost Server)
         ├──► [MonetizationGateway]      ──► config/payments.sqlite (Local DB)
         └──► [EvidenceGateway]          ──► SHA-256 Hashes sobre strings/JSON locais
```

---

## 2. 🕵️ Origem e Natureza de Cada Evento Económico

| Evento / Fluxo | Origem Real | Mecanismo de Inserção | Classificação de Realidade |
|---|---|---|---|
| **E01: Oportunidade** | Local (Memória/Prompt) | String instanciada no `EconomicMission` | `LOCAL_REAL` (Processo Local) |
| **E02: Pesquisa** | Externa / Local | `run_local_scrape` / Playwright / HTTPX | `EXTERNAL_UNVERIFIED` (Scrape Web Real) |
| **E03: Concorrentes** | Externa / Local | `run_local_scrape` / Obsidian RAG | `EXTERNAL_UNVERIFIED` (Scrape Web Real) |
| **E04: Scoring EV** | Local | `FinancialAnalyzer.calculate_metrics()` | `LOCAL_REAL` (Cálculo Algorítmico Real) |
| **E05: Build MVP** | Local (Disco) | `write_project_files()` no `sandbox_dir/` | `LOCAL_REAL` (I/O de Ficheiro Real) |
| **E06: Landing Page** | Local (Disco) | Escrita de `index.html` no `sandbox_dir/` | `LOCAL_REAL` (I/O de Ficheiro Real) |
| **E07: Publicação** | Localhost | `http://127.0.0.1:8080` (HTTP Server local) | `LOCAL_REAL` (Servidor Local, Não Público) |
| **E08: Leads** | Local (SQLite) | Chamada interna a `gateway.leads.capture_lead()` | `LOCAL_SYNTHETIC` (Sem Humano / Tráfego Externo) |
| **E09: Receita / ROI** | Local (SQLite) | Chamada interna a `gateway.monetization.process_payment_event()` | `LOCAL_SYNTHETIC` (Sem Transação Bancária / Stripe) |
| **E10: Iteração** | Local (Memória) | Verificação interna de saldo na base SQLite local | `LOCAL_SYNTHETIC` (Loop Fechado no Processo) |

---

## 3. ⛓️ Cadeia Completa de Evidência & Pontos de Fabricação

### A Cadeia Atual:
$$\text{Script Local} \xrightarrow{\text{dados injetados}} \text{SQLite Local} \xrightarrow{\text{consulta SQL}} \text{Runner} \xrightarrow{\text{hash SHA-256}} \text{EvidenceArtifact}$$

### ⚠️ Pontos Críticos Onde o Próprio Sistema Fabrica Evidência:
1. **Injeção Direta de Leads**: O método `capture_lead()` pode ser chamado por qualquer script Python local sem provir de um browser externo ou de um utilizador real.
2. **Injeção Direta de Transações**: O método `process_payment_event()` insere registos em `payments.sqlite` sem assinatura criptográfica de um webhook de um processador de pagamentos externo (e.g. Stripe/PayPal).
3. **Falsa Validade do SHA-256**: O hash SHA-256 prova **estritamente a integridade da string gravada**, mas **NÃO prova a veracidade da sua origem externa**. O sistema pode gerar o hash perfeito de uma transação financeira fabricada em memória.
4. **Isolamento do Sandbox**: O estado `PUBLISHED` apenas valida que o servidor escuta em `127.0.0.1:8080`, sendo completamente invisível para a Internet e utilizadores externos.

---

## 4. 📊 Classificação Individual dos Cenários E01 a E10

- **E01 (Opportunity Discovery)**: `LOCAL_REAL` (Processamento de linguagem e dados locais).
- **E02 (Market Research)**: `EXTERNAL_UNVERIFIED` (Scrape de páginas web públicas reais sem validação formal de autoridade).
- **E03 (Competitor Analysis)**: `EXTERNAL_UNVERIFIED` (Extração real de dados web públicos).
- **E04 (Opportunity Scoring)**: `LOCAL_REAL` (Cálculo matemático determinístico no motor local).
- **E05 (MVP Construction)**: `LOCAL_REAL` (Escrita real de ficheiros e código no disco).
- **E06 (Landing Page Creation)**: `LOCAL_REAL` (Geração de assets web reais locais).
- **E07 (Publishing Sandbox)**: `LOCAL_REAL` (Servidor HTTP real local com resposta 200 OK via loopback).
- **E08 (Lead Acquisition)**: `LOCAL_SYNTHETIC` (Leads inseridos programmaticamente na base de dados SQLite local, sem tráfego real).
- **E09 (Monetization Metrics)**: `LOCAL_SYNTHETIC` (Valores monetários inseridos por código Python local sem gateway de pagamentos externa).
- **E10 (Autonomous Iteration)**: `LOCAL_SYNTHETIC` (Avaliação baseada em métricas financeiras sintéticas locais).

---

## 5. 🧱 A Primeira Fronteira: Execução Local vs. Mundo Externo

A fronteira exata entre o ambiente isolado do JARVIS e o mundo externo situa-se em:

```
[AMBIENTE LOCAL DO JARVIS]                   [MUNDO EXTERNO REAL]
  - Subprocessos PowerShell / Python           - Redes Públicas / Internet
  - Bases de dados SQLite locais               - Utilizadores Humanos Reais
  - Servidor Sandbox (127.0.0.1)               - Processadores de Pagamento (Stripe/Banco)
  - Ficheiros no Disco                         - Domínios Públicos DNS / Cloud Hosting
```

---

## 6. 🛠️ Componentes que Faltam para Externalização Real

1. **Gateway de Publicação Pública (Tunneling / Cloud Deploy)**:
   - Exposição segura do sandbox local à Internet através de túnel seguro (e.g. Cloudflare Tunnels / ngrok) ou deploy estático (GitHub Pages / Cloudflare Pages / Vercel CLI).
2. **Gateway de Tráfego & Aquisição Real**:
   - URL público partilhável para utilizadores reais interagirem com a landing page.
3. **Endpoint de Webhook com Autenticação Criptográfica**:
   - Servidor HTTP com validação HMAC-SHA256 da assinatura de webhooks de pagamento (e.g. Stripe `stripe-signature` header).
4. **Verificação de Identidade / Origem do Lead**:
   - Validação de endereço IP externo, cabeçalhos de requisição HTTP e envio de email de confirmação (Double Opt-In).

---

## 7. 🛡️ Riscos de Segurança & Fronteiras de Controlo

1. **Risco de Auto-Ilusão (Self-Delusion Loop)**:
   - O agente pode entrar num ciclo fechado onde cria o lead, cria a transação de pagamento fictícia e declara vitória económica (`SUCCESS`) sem gerar 1 cêntimo real.
2. **Risco de Ações Externas Irreversíveis Não-Autorizadas**:
   - Publicações acidentais em contas públicas ou despesas em serviços cloud sem aprovação prévia.
3. **Regra Fundamental**: A transição para `MONETIZED` ou `SUCCESS` **nunca pode depender apenas de registos locais na SQLite**. Exige obrigatoriamente um payload assinado de um provedor financeiro externo ou validação humana explícita.

---

## 8. 🎯 Menor Próxima Alteração Necessária

Criar o **`ExternalVerificationGate`**:
- Uma camada de validação que separa explicitamente os dados de teste (`TEST_MODE = True`) dos eventos verificados pelo mundo exterior (`EXTERNAL_VERIFIED`).
- Proibir que um benchmark local consiga colocar o estado de uma missão em `SUCCESS` económico sem a flag explícita `EXTERNAL_VERIFIED`.

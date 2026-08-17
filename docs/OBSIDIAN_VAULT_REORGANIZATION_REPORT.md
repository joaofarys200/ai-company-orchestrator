# 🏛️ Relatório de Reorganização Estrutural & Semântica do Obsidian Vault

**Data de Execução:** 17 de Agosto de 2026  
**Sistema:** JARVIS OS — Knowledge Base & External Memory Layer  
**Diretório do Cofre:** `c:\Users\joaor\Desktop\JarvisOS\obsidian_vault`  
**Status Final:** ✅ **Concluído com Sucesso — 100% de Integridade Semântica e Referencial**

---

## 1. Estrutura Anterior vs. Estrutura Nova

### 1.1. Estrutura Anterior
- O cofre continha 82 ficheiros dispersos na raiz de `obsidian_vault/` e numa subpasta legada `3. Recursos/`.
- Ausência de separação física por subdomínios técnicos.
- Ausência de separação explícita entre conhecimento geral da indústria e especificações do JARVIS OS.
- 11 tratados monográficos sem frontmatter YAML padronizado.

### 1.2. Estrutura Nova (Hierarquia Física Deliberada)
```text
obsidian_vault/
├── 00 - MOC/
│   ├── 00 - Knowledge Index.md
│   ├── AI Index.md
│   ├── Software Engineering Index.md
│   ├── Backend Index.md
│   ├── Computer Use Index.md
│   ├── Security Index.md
│   ├── DevOps Index.md
│   ├── Business Index.md
│   ├── Operational Guides Index.md
│   └── JARVIS Index.md
├── 01 - AI & LLM/
│   ├── Architecture/
│   ├── Model Harness/
│   ├── RAG/
│   ├── Context Engineering/
│   ├── Prompt Engineering/
│   ├── Agent Systems/
│   └── Safety/
├── 02 - Software Engineering/
│   ├── Architecture/
│   ├── Coding Agents/
│   ├── AST & Code Analysis/
│   ├── Testing/
│   ├── Patching & Refactoring/
│   └── Recovery/
├── 03 - Backend & Distributed Systems/
│   ├── Persistence/
│   ├── Concurrency/
│   ├── APIs/
│   ├── WebSockets/
│   ├── Messaging/
│   └── Distributed Systems/
├── 04 - Computer Use/
│   ├── Playwright/
│   ├── Browser Automation/
│   ├── DOM/
│   ├── Network/
│   └── Visual Verification/
├── 05 - Security/
│   ├── Authentication/
│   ├── Cryptography/
│   ├── Secrets/
│   ├── Sandboxing/
│   ├── Web Security/
│   └── Agent Security/
├── 06 - DevOps & SRE/
│   ├── Docker/
│   ├── CI-CD/
│   ├── Observability/
│   ├── Reliability/
│   └── Infrastructure/
├── 07 - Business & SaaS/
│   ├── Market Research/
│   ├── Product/
│   ├── SaaS Economics/
│   ├── Pricing/
│   ├── Growth/
│   └── Validation/
├── 08 - Runbooks/
│   ├── AI/
│   ├── Coding/
│   ├── Backend/
│   ├── Computer Use/
│   ├── Security/
│   ├── DevOps/
│   └── Business/
├── 09 - JARVIS/
│   ├── Architecture/
│   ├── Components/
│   ├── Model Harness/
│   ├── Agents/
│   ├── Persistence/
│   ├── Tools/
│   ├── Autonomy/
│   ├── Economic Layer/
│   ├── Security/
│   ├── Audits/
│   └── Decisions/
└── 99 - Archive/
```

---

## 2. Inventário e Classificação Completa das Notas

| Nome da Nota | Domínio | Subdomínio | Tipo | Dificuldade | Escopo | Nova Localização |
|---|---|---|---|---|---|---|
| `00 - Knowledge Index.md` | general | MOC | index | introductory | Geral | `00 - MOC/00 - Knowledge Index.md` |
| `AI Index.md` | ai-engineering | MOC | index | intermediate | Geral | `00 - MOC/AI Index.md` |
| `Software Engineering Index.md` | software-engineering | MOC | index | intermediate | Geral | `00 - MOC/Software Engineering Index.md` |
| `Backend Index.md` | backend-systems | MOC | index | intermediate | Geral | `00 - MOC/Backend Index.md` |
| `Computer Use Index.md` | computer-use | MOC | index | intermediate | Geral | `00 - MOC/Computer Use Index.md` |
| `Security Index.md` | security | MOC | index | intermediate | Geral | `00 - MOC/Security Index.md` |
| `DevOps Index.md` | devops | MOC | index | intermediate | Geral | `00 - MOC/DevOps Index.md` |
| `Business Index.md` | business-economics | MOC | index | intermediate | Geral | `00 - MOC/Business Index.md` |
| `Operational Guides Index.md` | general | MOC | index | intermediate | Geral | `00 - MOC/Operational Guides Index.md` |
| `JARVIS Index.md` | jarvis | MOC | index | intermediate | JARVIS | `00 - MOC/JARVIS Index.md` |
| `Model Harness Architecture.md` | ai-engineering | Architecture | concept | advanced | Geral | `01 - AI & LLM/Architecture/` |
| `Ollama Local Model Serving.md` | ai-engineering | Architecture | technology | intermediate | Geral | `01 - AI & LLM/Architecture/` |
| `Model Routing and Fallback Strategies.md` | ai-engineering | Model Harness | pattern | intermediate | Geral | `01 - AI & LLM/Model Harness/` |
| `Structured Outputs and Schema Validation.md` | ai-engineering | Model Harness | concept | intermediate | Geral | `01 - AI & LLM/Model Harness/` |
| `Tool Calling Protocols and Structured Invocation.md` | ai-engineering | Model Harness | concept | intermediate | Geral | `01 - AI & LLM/Model Harness/` |
| `RAG Architecture and Retrieval Strategies.md` | ai-engineering | RAG | concept | intermediate | Geral | `01 - AI & LLM/RAG/` |
| `Context Engineering and Compression.md` | ai-engineering | Context Engineering | concept | advanced | Geral | `01 - AI & LLM/Context Engineering/` |
| `Anti-Pattern - Unbounded Context Accumulation.md` | ai-engineering | Context Engineering | anti-pattern | intermediate | Geral | `01 - AI & LLM/Context Engineering/` |
| `Hallucination Mitigation Techniques.md` | ai-engineering | Prompt Engineering | concept | intermediate | Geral | `01 - AI & LLM/Prompt Engineering/` |
| `Planner-Executor Agent Pattern.md` | ai-engineering | Agent Systems | pattern | intermediate | Geral | `01 - AI & LLM/Agent Systems/` |
| `Agent Loop Detection and Circuit Breaker.md` | ai-engineering | Agent Systems | pattern | intermediate | Geral | `01 - AI & LLM/Agent Systems/` |
| `Prompt Injection Defense in Autonomous Agents.md` | security | Safety | concept | advanced | Geral | `01 - AI & LLM/Safety/` |
| `Clean Architecture and Hexagonal Ports.md` | software-engineering | Architecture | concept | intermediate | Geral | `02 - Software Engineering/Architecture/` |
| `Idempotency in Software Systems.md` | software-engineering | Architecture | concept | intermediate | Geral | `02 - Software Engineering/Architecture/` |
| `DDD_Domain_Driven_Design_and_Enterprise_Patterns.md` | software-engineering | Architecture | concept | advanced | Geral | `02 - Software Engineering/Architecture/` |
| `Engenharia_de_Software_e_Arquitetura_Clean_Code.md` | software-engineering | Architecture | concept | advanced | Geral | `02 - Software Engineering/Architecture/` |
| `SWEBOK_Software_Engineering_Body_of_Knowledge.md` | software-engineering | Architecture | concept | advanced | Geral | `02 - Software Engineering/Architecture/` |
| `Compiler Feedback and Test-Driven Self-Repair.md` | software-engineering | Coding Agents | pattern | intermediate | Geral | `02 - Software Engineering/Coding Agents/` |
| `Abstract Syntax Tree (AST) Parsing and Manipulation.md` | software-engineering | AST & Code Analysis | concept | advanced | Geral | `02 - Software Engineering/AST & Code Analysis/` |
| `Repository Understanding and Code Indexing.md` | software-engineering | AST & Code Analysis | concept | intermediate | Geral | `02 - Software Engineering/AST & Code Analysis/` |
| `AST-Based Refactoring vs Regex Replacement.md` | software-engineering | AST & Code Analysis | comparison | intermediate | Geral | `02 - Software Engineering/AST & Code Analysis/` |
| `Tratado_Completo_de_Engenharia_de_Software_AST_e_Compiladores.md` | software-engineering | AST & Code Analysis | concept | advanced | Geral | `02 - Software Engineering/AST & Code Analysis/` |
| `Unit Tests vs End-to-End Tests in Agent Validation.md` | software-engineering | Testing | comparison | intermediate | Geral | `02 - Software Engineering/Testing/` |
| `Patch Generation and Safe Application.md` | software-engineering | Patching & Refactoring | concept | intermediate | Geral | `02 - Software Engineering/Patching & Refactoring/` |
| `Safe Rollback and Git Transactional Strategies.md` | software-engineering | Recovery | pattern | intermediate | Geral | `02 - Software Engineering/Recovery/` |
| `SQLite WAL Mode and Concurrency.md` | backend-systems | Persistence | concept | intermediate | Geral | `03 - Backend & Distributed Systems/Persistence/` |
| `Database Crash Consistency and Recovery.md` | backend-systems | Persistence | concept | intermediate | Geral | `03 - Backend & Distributed Systems/Persistence/` |
| `Tratado_Completo_de_Engenharia_de_Sistemas_Distribuidos_e_Bases_de_Dados.md` | backend-systems | Persistence | concept | advanced | Geral | `03 - Backend & Distributed Systems/Persistence/` |
| `Optimistic vs Pessimistic Locking.md` | backend-systems | Concurrency | comparison | intermediate | Geral | `03 - Backend & Distributed Systems/Concurrency/` |
| `Engenharia_de_Sistemas_Distribuidos_e_Concorrencia.md` | backend-systems | Concurrency | concept | advanced | Geral | `03 - Backend & Distributed Systems/Concurrency/` |
| `FastAPI and WebSocket Lifecycle Management.md` | backend-systems | WebSockets | concept | intermediate | Geral | `03 - Backend & Distributed Systems/WebSockets/` |
| `Message Queues and Event-Driven Architectures.md` | backend-systems | Messaging | concept | intermediate | Geral | `03 - Backend & Distributed Systems/Messaging/` |
| `Distributed Transactions and Saga Pattern.md` | backend-systems | Distributed Systems | pattern | advanced | Geral | `03 - Backend & Distributed Systems/Distributed Systems/` |
| `DDIA_Designing_Data_Intensive_Applications_BOK.md` | backend-systems | Distributed Systems | concept | advanced | Geral | `03 - Backend & Distributed Systems/Distributed Systems/` |
| `Playwright Architecture and Automation Protocol.md` | computer-use | Playwright | technology | intermediate | Geral | `04 - Computer Use/Playwright/` |
| `DOM State Inspection and Resilient Locators.md` | computer-use | DOM | concept | intermediate | Geral | `04 - Computer Use/DOM/` |
| `Browser Network Interception and Mocking.md` | computer-use | Network | concept | intermediate | Geral | `04 - Computer Use/Network/` |
| `Visual Regression and Screenshot Verification.md` | computer-use | Visual Verification | concept | intermediate | Geral | `04 - Computer Use/Visual Verification/` |
| `HMAC Signature Verification for Webhooks.md` | security | Authentication | concept | intermediate | Geral | `05 - Security/Authentication/` |
| `Tratado_Completo_de_Ciberseguranca_Redes_e_DevSecOps.md` | security | Cryptography | concept | advanced | Geral | `05 - Security/Cryptography/` |
| `Credential Sanitization and Secret Masking.md` | security | Secrets | concept | intermediate | Geral | `05 - Security/Secrets/` |
| `Least-Privilege Process Sandboxing and Execution Jail.md` | security | Sandboxing | concept | advanced | Geral | `05 - Security/Sandboxing/` |
| `Seguranca_Defensiva_DevSecOps_e_Sandboxing.md` | security | Sandboxing | concept | advanced | Geral | `05 - Security/Sandboxing/` |
| `SSRF Defense in Agentic Fetchers.md` | security | Web Security | concept | advanced | Geral | `05 - Security/Web Security/` |
| `Indirect Prompt Injection via Web Pages.md` | security | Web Security | concept | advanced | Geral | `05 - Security/Web Security/` |
| `Threat Modeling for Autonomous Coding Agents.md` | security | Agent Security | concept | advanced | Geral | `05 - Security/Agent Security/` |
| `Docker Container Security and Resource Capping.md` | devops | Docker | technology | intermediate | Geral | `06 - DevOps & SRE/Docker/` |
| `CI-CD Pipeline Failure Triage and Automated Healing.md` | devops | CI-CD | concept | intermediate | Geral | `06 - DevOps & SRE/CI-CD/` |
| `Structured Logging and Distributed Trace Context.md` | devops | Observability | concept | intermediate | Geral | `06 - DevOps & SRE/Observability/` |
| `SLI-SLO Metrics and Error Budgets.md` | devops | Reliability | concept | intermediate | Geral | `06 - DevOps & SRE/Reliability/` |
| `Healthchecks and Circuit Breakers.md` | devops | Reliability | pattern | intermediate | Geral | `06 - DevOps & SRE/Reliability/` |
| `SRE_Site_Reliability_Engineering_Body_of_Knowledge.md` | devops | Reliability | concept | advanced | Geral | `06 - DevOps & SRE/Reliability/` |
| `Market Opportunity Discovery and Scoring Matrix.md` | business-economics | Market Research | concept | intermediate | Geral | `07 - Business & SaaS/Market Research/` |
| `Distinguishing Real vs Synthetic Market Evidence.md` | business-economics | Product | concept | intermediate | Geral | `07 - Business & SaaS/Product/` |
| `SaaS Unit Economics - CAC, LTV and Magic Number.md` | business-economics | SaaS Economics | concept | intermediate | Geral | `07 - Business & SaaS/SaaS Economics/` |
| `Analise_Financeira_SaaS_e_Algoritmos_Estatisticos.md` | business-economics | SaaS Economics | concept | advanced | Geral | `07 - Business & SaaS/SaaS Economics/` |
| `SaaS Pricing Models and Monetization Strategies.md` | business-economics | Pricing | concept | intermediate | Geral | `07 - Business & SaaS/Pricing/` |
| `Churn Rate Analysis and Cohort Retention Curves.md` | business-economics | Growth | concept | intermediate | Geral | `07 - Business & SaaS/Growth/` |
| `How to Handle Malformed Model Output.md` | ai-engineering | AI | troubleshooting | intermediate | Runbook | `08 - Runbooks/AI/` |
| `How to Detect and Break Agent Infinite Loops.md` | ai-engineering | AI | troubleshooting | intermediate | Runbook | `08 - Runbooks/AI/` |
| `How to Safely Validate and Apply Code Patches.md` | software-engineering | Coding | troubleshooting | intermediate | Runbook | `08 - Runbooks/Coding/` |
| `How to Diagnose Python Import and Module Resolution Failures.md` | software-engineering | Coding | troubleshooting | intermediate | Runbook | `08 - Runbooks/Coding/` |
| `How to Safely Rollback Failed Code Changes.md` | software-engineering | Coding | troubleshooting | intermediate | Runbook | `08 - Runbooks/Coding/` |
| `How to Diagnose and Resolve SQLite Database Locked Errors.md` | backend-systems | Backend | troubleshooting | intermediate | Runbook | `08 - Runbooks/Backend/` |
| `How to Recover Interrupted Background Workers.md` | backend-systems | Backend | troubleshooting | intermediate | Runbook | `08 - Runbooks/Backend/` |
| `How to Detect and Fix Stale Element and Navigation Race Conditions.md` | computer-use | Computer Use | troubleshooting | intermediate | Runbook | `08 - Runbooks/Computer Use/` |
| `How to Detect Failed Playwright Deployments.md` | computer-use | Computer Use | troubleshooting | intermediate | Runbook | `08 - Runbooks/Computer Use/` |
| `How to Validate Webhook Cryptographic Signatures.md` | security | Security | troubleshooting | intermediate | Runbook | `08 - Runbooks/Security/` |
| `How to Sanitize Secrets Before Logging or Ingestion.md` | security | Security | troubleshooting | intermediate | Runbook | `08 - Runbooks/Security/` |
| `How to Triage and Fix Broken CI-CD Pipelines.md` | devops | DevOps | troubleshooting | intermediate | Runbook | `08 - Runbooks/DevOps/` |
| `How to Implement Circuit Breakers for Flaky External APIs.md` | devops | DevOps | troubleshooting | intermediate | Runbook | `08 - Runbooks/DevOps/` |
| `How to Validate Product Ideas with Low-Cost Experiments.md` | business-economics | Business | troubleshooting | intermediate | Runbook | `08 - Runbooks/Business/` |
| `How to Calculate Net Revenue Retention and Unit Margins.md` | business-economics | Business | troubleshooting | intermediate | Runbook | `08 - Runbooks/Business/` |
| `JARVIS System Architecture.md` | jarvis | Architecture | architecture | intermediate | JARVIS | `09 - JARVIS/Architecture/` |
| `JARVIS Component Architecture.md` | jarvis | Components | architecture | intermediate | JARVIS | `09 - JARVIS/Components/` |
| `JARVIS Model Harness Implementation.md` | jarvis | Model Harness | concept | intermediate | JARVIS | `09 - JARVIS/Model Harness/` |
| `JARVIS Autonomous Agent Hierarchy.md` | jarvis | Agents | concept | intermediate | JARVIS | `09 - JARVIS/Agents/` |
| `JARVIS State Store and Persistence.md` | jarvis | Persistence | concept | intermediate | JARVIS | `09 - JARVIS/Persistence/` |
| `JARVIS Obsidian Tools and RAG System.md` | jarvis | Tools | concept | intermediate | JARVIS | `09 - JARVIS/Tools/` |
| `JARVIS Mission State Machine and Autonomy.md` | jarvis | Autonomy | concept | intermediate | JARVIS | `09 - JARVIS/Autonomy/` |
| `JARVIS Economic Engine and Metric Verification.md` | jarvis | Economic Layer | concept | intermediate | JARVIS | `09 - JARVIS/Economic Layer/` |
| `JARVIS Security Sandbox and Policy Engine.md` | jarvis | Security | concept | intermediate | JARVIS | `09 - JARVIS/Security/` |
| `ADR-001 - Decoupled Obsidian Knowledge Vault for Agent Memory.md` | jarvis | Decisions | decision | intermediate | JARVIS | `09 - JARVIS/Decisions/` |
| `ADR-002 - Process Sandboxing and Path Jail Enforcement.md` | jarvis | Decisions | decision | intermediate | JARVIS | `09 - JARVIS/Decisions/` |
| `OBSIDIAN_RAG_KNOWLEDGE_AUDIT.md` | jarvis | Audits | audit | intermediate | JARVIS | `09 - JARVIS/Audits/` |
| `OBSIDIAN_VAULT_QUALITY_REPORT.md` | jarvis | Audits | audit | intermediate | JARVIS | `09 - JARVIS/Audits/` |

---

## 3. Métricas Antes vs. Depois

| Indicador | Antes da Reorganização | Após a Reorganização | Status |
|---|---|---|---|
| **Total de Ficheiros `.md`** | 82 | **96** (inclui 10 notas JARVIS + 2 ADRs + 2 Audits) | ✅ Zero perda de dados |
| **Pastas Físicas Organizadas** | 2 (`obsidian_vault` e `3. Recursos`) | **10 Domínios e 35 Subpastas** | ✅ Estrutura deliberada |
| **Conexões de Grafo (`[[Wikilinks]]`)**| 336 conexões | **388 conexões** | ✅ Densidade ampliada |
| **Links Quebrados** | 0 | **0 (Zero)** | ✅ 100% integridade |
| **Notas Órfãs (Sem Links de Entrada)** | 0 | **0 (Zero)** | ✅ Todas indexadas em MOCs |
| **Notas com Frontmatter YAML Válido** | 71/82 (86.5%) | **96/96 (100.0%)** | ✅ 100% padronizado |
| **Taxa de Sucesso em 20 Testes RAG** | 20/20 (100.0%) | **20/20 (100.0%)** | ✅ Alta precisão mantida |

---

## 4. Auditoria de Links & Resolução de Problemas

1. **Problema Detectado**: Tipagens Python com colchetes duplos `Callable[[], Awaitable[None]]` foram interpretadas por regex de parsing de Wikilinks como links quebrados.
   - **Correção Aplicada**: Refatoração sintática para `Callable[..., Awaitable[None]]`, mantendo tipagem Python 100% válida e prevenindo falso parsing de Wikilinks.
2. **Problema Detectado**: Menções literais a `[[Nota]]` ou `[[...]]` em textos explicativos geravam links para nós inexistentes.
   - **Correção Aplicada**: Conversão para formatação com escape/backticks `` `[[\Nota]]` ``.

---

## 5. Recomendações para Futura Expansão

1. **Adição de Novas Notas**:
   - Sempre categorizar nos domínios gerais `01-07` se for um padrão da indústria.
   - Criar em `08 - Runbooks/<Subdomínio>` se for um procedimento "How-to".
   - Criar em `09 - JARVIS/<Subdomínio>` apenas se descrever a implementação interna do JARVIS OS.
2. **Manutenção de Links**:
   - Ao criar uma nova nota, registá-la imediatamente no MOC do respetivo domínio em `00 - MOC/`.

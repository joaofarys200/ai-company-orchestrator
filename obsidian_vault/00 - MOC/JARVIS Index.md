---
type: index
domain: jarvis
difficulty: intermediate
tags:
  - jarvis
  - index
  - architecture
  - components
  - lessons
  - adrs
  - knowledge-gaps
status: verified
source_type: JARVIS_INTERNAL
confidence: high
freshness: stable
---

# 🤖 JARVIS System Knowledge Index

Este índice centraliza todo o conhecimento técnico específico da implementação, arquitetura de componentes, subsistemas, post-mortems/lessons aprendidas, decisões arquiteturais (ADRs) e registro explícito de lacunas (*Knowledge Gaps*) do **JARVIS OS**.

---

## 🏛️ Arquitetura Global & Componentes Centrais

- [[JARVIS System Architecture]] — Visão global da arquitetura desktop, frontend, backend assíncrono e swarm.
- [[JARVIS Component Architecture]] — Mapeamento detalhado dos módulos (`server.py`, `database.py`, `sandbox.py`, etc.).
- [[JARVIS Autonomous Agent Hierarchy]] — Contratos de papéis de Clara, Devon, Alex e Quinn.
- [[JARVIS Swarm Orchestrator and Agent Turn Arbitrator]] — Gestão hierárquica do swarm, injeção de habilidades e turnos.
- [[JARVIS Mission State Machine and Autonomy]] — Ciclo de vida FSM de missões e autonomia delimitada (*Bounded Autonomy*).
- [[JARVIS MissionStateStore and Persistence Engine]] — Especificação profunda do motor de persistência SQLite WAL.
- [[JARVIS MissionExecutorService and Autonomy Controller]] — Motor de execução de DAG e fiscalização de autonomia.
- [[JARVIS MissionRecoveryWatchdog and Crash Recovery]] — Processo de recuperação de tarefas zumbis e restauração pós-crash.

---

## 🛠️ Subsistemas & Implementações Específicas

- [[JARVIS Voice Service and Audio Streaming Architecture]] — Processamento local de áudio, WebRTC VAD e Whisper STT.
- [[JARVIS Gemini Live Multimodal WebSocket Protocol]] — Protocolo bidirecional de streaming de voz e barge-in.
- [[JARVIS AirLLM Layer-by-Layer Offloading Architecture]] — Servidor de modelos 70B com descarregamento camada por camada.
- [[JARVIS IDE Terminal and ANSI Escape Stripping Pipeline]] — Captura de stdout/stderr sem buffer e higienização ANSI.
- [[JARVIS Desktop Electron IPC Security Bridge]] — Isolamento de contexto no Electron e APIs seguras em `preload.js`.
- [[JARVIS ProjectBuilder Dependency Resolution Engine]] — Análise de imports por AST e resolução de dependências com lockfiles.
- [[JARVIS SQLite WAL Checkpoint Daemon and PRAGMA Tuning]] — Parâmetros de alta concorrência e truncamento WAL.
- [[JARVIS PatchEngine and CodingSession Architecture]] — Infraestrutura de patching atómico e validação sintática pré-escrita.
- [[JARVIS ProjectBuilder and Validation Pipeline]] — Compilação e esteira de validação em sandbox com Flight Recorder.
- [[JARVIS RHO and SHE Self-Healing Architecture]] — Orquestrador de auto-correção reflexiva com circuit breakers.
- [[JARVIS ComputerUseEngine and Playwright Integration]] — Automação de navegador, captura de screenshots e ARIA trees.
- [[JARVIS PermissionPolicyManager and Workspace Policy]] — Regras estritas de path jail e bloqueio de comandos destrutivos.
- [[JARVIS EconomicExecutionGateway and Monetization]] — Motor financeiro, cálculo de unit economics e auditoria de webhooks.
- [[JARVIS EvidenceGateway and Market Verification Gate]] — Barreira epistêmica de validação de mercado e comprovativos de tração.
- [[JARVIS LeadCaptureGateway and Conversion Architecture]] — Captura de formulários, proteção anti-spam e validação de leads.
- [[JARVIS Mission Cost and Token Accounting Engine]] — Rastreamento granular de tokens de prompt/completion e orçamento.
- [[JARVIS WebSocket Telemetry and Dispatcher Protocol]] — Protocolo JSON-RPC de streaming e barreira de saída de segredos.
- [[JARVIS Obsidian Tools and RAG System]] — Ferramentas RAG e integração de memória externa.

---

## 📝 JARVIS Production Lessons & Post-Mortems (09 - JARVIS/Lessons)

- [[Lesson - Unhandled Rate Limits and Context Explosion]] — Explosão de janela de contexto em retentativas HTTP 429.
- [[Lesson - SQLite Lock Starvation from Unclosed Readers]] — Travamento de banco causado por cursores esquecidos abertos.
- [[Lesson - Regex Refactoring Syntax Corruption]] — Corrupção sintática de código gerada por substituições cegas com regex.
- [[Lesson - Hydration Race Condition in Fast Form Submit]] — Submissão prematura de formulário antes do binding de event listeners no Playwright.
- [[Lesson - Bounded Autonomy Escape in Subprocess Invocation]] — Evasão de path jail por encadeamento de comandos com `shell=True`.
- [[Lesson - Accidental Secret Leaks in Telemetry Broadcast]] — Fuga de tokens de autenticação pelo canal de telemetria WebSocket.
- [[Lesson - Synthetic Evidence Hallucination in Market Validation]] — Confusão epistêmica entre personas simuladas e compromisso financeiro real.
- [[Lesson - Stale Preview Port Binding Collision]] — Colisão de portas de preview locais gerando testes em instâncias residuais.
- [[Lesson - Low-Score BM25 Pollution in Short Semantic Queries]] — Contaminação de contexto em queries curtas por falta de bônus de título.
- [[Lesson - Unescaped Wikilink Parsing Collisions in Markdown]] — Colisões entre caminhos físicos de arquivos de código e nós conceituais.

---

## 📋 Decisões Arquiteturais (ADRs)

- [[ADR-001 - Decoupled Obsidian Knowledge Vault for Agent Memory]] — Adoção do cofre Obsidian como memória externa.
- [[ADR-002 - Process Sandboxing and Path Jail Enforcement]] — Isolamento de subprocessos e restrição de sistema de ficheiros.
- [[ADR-003 - Reflective Healing Orchestration (RHO) for Model Harness]] — Auto-cura reflexiva com circuit breakers no harness.
- [[ADR-004 - Strict Exit Barrier Secret Sanitization in WebSocket Telemetry]] — Sanitização obrigatória de segredos no canal de saída.
- [[ADR-005 - Economic Evidence Provenance and Synthetic Data Capping]] — Classificação quadripartite e teto de confiança para dados sintéticos.
- [[ADR-006 - Context Engineering and AST Fallback Paring]] — Poda estrutural de código por AST para economia de tokens.
- [[ADR-007 - Evidence Integrity and External Verification Gate]] — Barreira obrigatória de comprovação real para missões comerciais.
- [[ADR-008 - Computer Use Reality Gate and DOM State Inspection]] — Validação pós-ação de DOM no Playwright.
- [[ADR-009 - RHO and SHE Rule Compaction and Max Turn Quotas]] — Limite de 3 turnos e resumo compacto de erros.
- [[ADR-010 - Untrusted External Data Isolation via Boundary Delimiters]] — Encapsulamento de dados externos contra injeção de prompt.
- [[ADR-011 - Mission Crash Recovery and Git Transactional Reset]] — Checkpoints Git pré-mutação e recuperação pós-queda.
- [[ADR-012 - Context Compression via Structural AST Summarization]] — Esqueletos de AST com corpo de funções omitido.
- [[ADR-013 - Economic Evidence Provenance and Confidence Capping]] — Teto rígido de $0.20$ de confiança para dados sintéticos.

---

## ❓ Registro Explícito de Lacunas (09 - JARVIS/Knowledge Gaps)

- [[Gap - Real-Time WebRTC Audio Latency Bounds in Local Hardware]] — Limites físicos de latência em conversação contínua por voz.
- [[Gap - Multi-Modal Continuous Eye Gaze Tracking for Desktop Actions]] — Rastreamento ocular para inferência de atenção na IDE.
- [[Gap - Formal Verification of Swarm Convergence with TLA+]] — Prova formal de convergência em tempo finito de enxames de IA.
- [[Gap - Quantum-Safe Ciphers for Local State Encryption]] — Criptografia pós-quântica (ML-KEM/ML-DSA) em bases SQLite locais.

---

## 🔍 Auditorias Técnicas

- [[OBSIDIAN_RAG_KNOWLEDGE_AUDIT]] — Auditoria técnica completa do motor RAG do Obsidian.
- [[OBSIDIAN_VAULT_QUALITY_REPORT]] — Relatório de qualidade, validação de links e benchmark de retrieval.

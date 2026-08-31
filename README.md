# 🤖 JARVIS OS — Autonomous Multi-Agent Cognitive Platform

<p align="center">
  <img src="https://img.shields.io/badge/Status-Independent_Engineering_Project-3b82f6?style=for-the-badge&logo=rocket&logoColor=white" alt="Independent Project" />
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/TypeScript-React_18-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript / React 18" />
  <img src="https://img.shields.io/badge/Electron-Desktop_HUD-47848F?style=for-the-badge&logo=electron&logoColor=white" alt="Electron Desktop" />
  <img src="https://img.shields.io/badge/Test_Suites-953_Passed-22c55e?style=for-the-badge&logo=pytest&logoColor=white" alt="953 Pytest Passed" />
  <img src="https://img.shields.io/badge/Architecture-10_SVG_Blueprints-38bdf8?style=for-the-badge" alt="10 Architecture Blueprints" />
  <img src="https://img.shields.io/badge/Privacy-100%25_Offline_Capable-a855f7?style=for-the-badge" alt="100% Offline Capable" />
  <img src="https://img.shields.io/badge/License-MIT-amber?style=for-the-badge" alt="MIT License" />
</p>

> **JARVIS OS** is an independent, deterministic multi-agent cognitive operating system and autonomous orchestration platform designed for reliable software engineering, local host safety monitoring, and long-horizon goal execution.

---

## 🧭 Navigation Table

| Area | Documentation Link | Description |
|---|---|---|
| 🏛️ **Architecture** | [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Deep technical architecture specification & invariants |
| 📊 **Diagrams** | [`docs/diagrams/`](./docs/diagrams/) | 10 high-fidelity standalone SVG architecture blueprints |
| 📐 **JSON Schemas** | [`schemas/README.md`](./schemas/README.md) | Canonical Draft-07 schemas for all internal data contracts |
| 🛡️ **Security Policy** | [`SECURITY.md`](./SECURITY.md) | Sentinel watchdog, vulnerability reporting & sandbox boundaries |
| 🗺️ **Project Map** | [`docs/PROJECT_MAP.md`](./docs/PROJECT_MAP.md) | Physical directory, module, and dependency index |
| ⚖️ **ADRs** | [`docs/decisions/`](./docs/decisions/) | Architecture Decision Records (ADR-001 to ADR-006) |
| 📈 **Benchmarks** | [Benchmark Reports](#-benchmarks--empirical-validation-reports) | 10 empirical validation & capability test reports |
| 🤝 **Contributing** | [`CONTRIBUTING.md`](./CONTRIBUTING.md) | Contribution standards, code style & PR requirements |
| 📜 **Changelog** | [`CHANGELOG.md`](./CHANGELOG.md) | Factual historical release and feature log |

---

## 🌟 Overview & Technical Philosophy

Current LLMs are stochastic and unconstrained when generating code or issuing terminal commands. JARVIS OS addresses this fundamental reliability gap by treating AI models as **stochastic reasoning units operating inside deterministic, mechanical harnesses**.

Every agent interaction is bounded by:
- **Canonical Typed Schemas (Draft-07)** enforcing input/output invariants.
- **AST Symbol Parsers** modifying exact code nodes rather than hallucinating full-file rewrites.
- **Chrome DevTools Autonomous QA** verifying rendered web output, DOM states, and network errors.
- **Host EDR Monitoring (Security Sentinel)** observing Windows process trees, open ports, and filesystem writes with human approval gates.

---

## 🚦 Engineering Status & Validation Matrix

To ensure absolute scientific integrity and avoid exaggerated claims, all platform capabilities are classified into explicit lifecycle states:

| Component | Maturity State | Description & Verification Evidence |
|---|---|---|
| **Multi-Agent Orchestrator** | `IMPLEMENTED & AUTOMATED` | Clara, Alex, Devon, and Quinn personas with DAG WorkPackage scheduling. Verified by 45+ unit tests. |
| **Model Harness & Routing** | `IMPLEMENTED & AUTOMATED` | Multi-provider routing (Ollama local, OpenRouter free, Gemini/Claude/OpenAI cloud) with 7-stage schema validation. |
| **Coding Agent 2.0 Engine** | `VALIDATED IN TRIALS` | AST symbol replacements, cross-file TypeScript aliases, automated rollback. Validated across 4 benchmark suites. |
| **Security Sentinel (EDR)** | `VALIDATED IN TRIALS` | Windows process, port, task, and filesystem telemetry with baseline drift scoring and one-click rollback. |
| **Real Browser DevTools QA** | `VALIDATED IN TRIALS` | Headless/headed Chrome DevTools automation capturing DOM trees and network traces via Playwright. |
| **Knowledge Vault & RAG** | `IMPLEMENTED & AUTOMATED` | SQLite compounding rules engine + Obsidian Markdown Vault with bi-directional epistemic graphs. |
| **Cornell Lecture Audio** | `IMPLEMENTED & AUTOMATED` | Live voice recording + Whisper transcription into Cornell notes and interactive quizzes. |
| **Continuous Self-Improvement**| `EXPERIMENTAL` | ECC error-correction loops recording failure patterns from user corrections to prevent recurring errors. |
| **Self-Driving Enterprise** | `PLANNED` | Long-horizon multi-project budget allocation and fully autonomous multi-repo maintenance. |

---

## 🏛️ System Architecture

JARVIS OS is architected into modular, decoupled layers connecting user interfaces, cognitive agents, execution sandboxes, and host security monitors:

![JARVIS OS System Architecture](./docs/diagrams/01-system-architecture.svg)

---

## ⚡ Core Capabilities

1. **Autonomous Mission Orchestration**: Decomposes high-level natural language goals into atomic WorkPackages resolved via dependency DAGs with deterministic checkpointing.
2. **Multi-Agent Swarm Collaboration**: Four specialized personas (**Clara**, **Alex**, **Devon**, **Quinn**) operating over structured message buses with debate and consensus protocols.
3. **Coding Agent 2.0 Engine**: Replaces fragile text diffs with deterministic AST symbol manipulation, cross-file typed alias resolution, and atomic multi-file patch application.
4. **Hybrid Model Harness**: Multi-provider execution router supporting 100% offline local models (`qwen3.5:9b` via Ollama), zero-cost cloud reasoning (OpenRouter), and commercial cloud failover with 7-stage schema validation.
5. **Continuous Compounding Memory**: SQLite-persisted rules engine learning from human corrections on every turn with ECC self-correction injection.
6. **Bi-Directional Knowledge Vault**: Over 100 structured Markdown notes in an Obsidian vault with vector semantic search and backlink graphs.
7. **Cornell Lecture Synthesis**: Voice-recorded lectures transcribed via Whisper, formatted as Cornell notes with cues, summaries, and self-grading interactive quizzes.
8. **Real Browser QA & DevTools Automation**: Chrome DevTools Protocol automation capturing DOM trees, console exceptions, network traces, and multi-step visual screenshots.
9. **Security Sentinel (EDR Watchdog)**: Real-time host telemetry monitor (process spawn trees, listening ports, Task Scheduler persistence, filesystem writes) with human approval gates.
10. **4-Tier Economic Evidence Taxonomy**: Scientific classification separating synthetic test benchmarks from external observations and real financial transactions.

---

## 👥 Multi-Agent Swarm Architecture

Autonomous tasks are distributed across four specialized agent personas with strict role boundaries:

![Multi-Agent Swarm Architecture](./docs/diagrams/02-agent-architecture.svg)

- **Clara (Executive & Coordinator)**: Decomposes directives into scoped missions, schedules WorkPackage DAGs, and synthesizes executive reports.
- **Alex (Systems Architect)**: Authors Architecture Decision Records (ADRs), maps cross-module dependency graphs, and validates API contracts.
- **Devon (Coding Engineer)**: Performs AST symbol replacements, applies multi-file atomic patches, and operates the build/repair compiler loop.
- **Quinn (QA, Sentinel & Adversary)**: Executes headless Chrome DevTools tests, runs Security Sentinel audits, and enforces code quality gates.

---

## 💻 Coding Agent 2.0 Pipeline

The Coding Agent pipeline replaces full-file rewriting with deterministic AST symbol manipulation:

```
Prompt ──> Specification ──> Artifact Inference ──> Repository Graph
  ──> AST Symbol Graph ──> Coding Session Plan ──> Atomic Patch Engine
  ──> Build Pipeline (tsc / py_compile) ──> Browser DevTools QA ──> Self-Repair Loop
```

![Coding Agent Pipeline](./docs/diagrams/03-coding-agent-pipeline.svg)

- **AST Symbol Replacement**: Targets specific function or class nodes, preventing syntax regressions in surrounding code.
- **Cross-File Type Resolution**: Resolves TypeScript `@/*` path aliases and Python relative imports across monorepos.
- **Automated Checkpoints & Rollback**: Captures pre-modification byte snapshots with instant restoration on test failure.

---

## 🔄 Model Harness & Multi-Provider Routing

The Model Harness (`backend/model_harness/`) provides multi-provider abstraction with deterministic output guarantees:

```
Request ──> Context Builder ──> Profile Router ──> Provider Execution
  ──> 7-Stage Validation Loop ──> Deterministic Recovery ──> Telemetry Recording
```

![Model Harness Architecture](./docs/diagrams/04-model-harness.svg)

- **Profiles**: `default`, `coding`, `fast`, `reasoning`.
- **Supported Providers**: Ollama (local `qwen3.5:9b`), OpenRouter (free tier `nemotron`, `qwen`), Google Gemini, Anthropic Claude, OpenAI.
- **7-Stage Validation**: `parsing` &rarr; `schema` &rarr; `enums` &rarr; `references` &rarr; `preconditions` &rarr; `compatibility` &rarr; `acceptance_criteria`.

---

## 🛡️ Security Sentinel Watchdog (EDR)

Security Sentinel (`security/sentinel/`) continuously guards the host operating system against unauthorized or anomalous agent operations:

```
Windows Host ──> Process/Port/FS Collectors ──> Baseline Drift Analysis
  ──> Temporal Correlation ──> Incident Scoring ──> Human Approval Gate
  ──> Containment Action (Kill/Quarantine) ──> Post-State Verification ──> One-Click Rollback
```

![Security Sentinel Architecture](./docs/diagrams/06-sentinel-architecture.svg)

- **Host Monitoring**: Windows process spawn trees, TCP/UDP listening ports, Task Scheduler persistence, and filesystem writes.
- **Human Approval Mandatory**: High-risk mutations (`TERMINATE_PROCESS`, `QUARANTINE_FILE`, `DISABLE_SCHEDULED_TASK`) require explicit user confirmation.
- **One-Click Reversible Rollback**: Quarantined files and disabled tasks can be restored with a single click.

---

## 📚 Knowledge Vault & Continuous Learning

```
Obsidian Markdown Vault ──> Bi-Directional Epistemic Graph ──> Vector Embeddings / RAG
  ──> Cornell Lecture Audio Recorder ──> Whisper Synthesizer ──> Interactive Quiz Engine
  ──> Compounding Memory (SQLite) ──> Future Mission Context Injection
```

![Knowledge Architecture](./docs/diagrams/07-knowledge-architecture.svg)

- **Obsidian Vault (`obsidian_vault/`)**: Plain-text markdown files organized into MOCs, literature notes, and study guides.
- **Cornell Lectures (`services/`)**: Live audio capture converted into structured Cornell notes and self-grading quizzes.
- **Compounding Rules**: Rules learned from human corrections are persisted in SQLite and injected into subsequent prompts.

---

## ⚖️ 4-Tier Economic Evidence Taxonomy

To ensure scientific honesty and prevent exaggerated claims, JARVIS OS classifies all economic activities into 4 explicit tiers:

![Economic Evidence Taxonomy](./docs/diagrams/08-economic-evidence-flow.svg)

| Tier | Category | Operational Definition | Verification Proof |
|---|---|---|---|
| **Tier 1** | `SYNTHETIC_BENCHMARK` | Simulated coding problem suites and unit trials | Automated test assertion logs & exit codes |
| **Tier 2** | `EXTERNAL_OBSERVED` | Real-world read-only web/paper data extraction | SHA256 content hashes & HTTP headers |
| **Tier 3** | `EXTERNAL_VERIFIED` | Authenticated API calls and live browser automation | Network traces & DevTools DOM snapshots |
| **Tier 4** | `FINANCIAL_TRANSACTION` | Actual monetary exchange or bank transfer | Cryptographic signatures & settlement receipts |

> [!IMPORTANT]
> **No synthetic simulation or test benchmark is ever represented as real financial revenue.**

---

## 📈 Benchmarks & Empirical Validation Reports

Detailed empirical reports documenting capabilities and validation trials:

| Report Document | Focus Area | Key Findings & Metrics |
|---|---|---|
| [`JARVIS_CODING_AGENT_2_REPORT.md`](./docs/JARVIS_CODING_AGENT_2_REPORT.md) | Coding Agent 2.0 | AST symbol parser benchmark suite |
| [`JARVIS_CODING_AGENT_2_2_REAL_REPOSITORY_REPORT.md`](./docs/JARVIS_CODING_AGENT_2_2_REAL_REPOSITORY_REPORT.md) | Real-World Trial | Multi-file refactoring on active repositories |
| [`JARVIS_CODING_AGENT_2_3_LONG_HORIZON_REPORT.md`](./docs/JARVIS_CODING_AGENT_2_3_LONG_HORIZON_REPORT.md) | Long-Horizon Workflows | Multi-package dependencies & rollback recovery |
| [`JARVIS_CODING_AGENT_2_4_TYPED_SEMANTICS_REPORT.md`](./docs/JARVIS_CODING_AGENT_2_4_TYPED_SEMANTICS_REPORT.md) | Typed Semantics | TypeScript `@/*` path alias resolution |
| [`SENTINEL_S5_DETECTION_QUALITY_REPORT.md`](./docs/SENTINEL_S5_DETECTION_QUALITY_REPORT.md) | Sentinel Detection | EDR incident scoring and anomalous spawn detection |
| [`SENTINEL_S6_SHADOW_MODE_REPORT.md`](./docs/SENTINEL_S6_SHADOW_MODE_REPORT.md) | Shadow Mode | Zero-overhead continuous background telemetry |
| [`OBSIDIAN_KNOWLEDGE_GRAPH_AND_EPISTEMIC_REPORT.md`](./docs/OBSIDIAN_KNOWLEDGE_GRAPH_AND_EPISTEMIC_REPORT.md) | Knowledge Engineering | Bi-directional graph topology and RAG search |
| [`JARVIS_REALTIME_BROWSER_VALIDATION_REPORT.md`](./docs/JARVIS_REALTIME_BROWSER_VALIDATION_REPORT.md) | Autonomous QA | Chrome DevTools real-time DOM & console verification |
| [`JARVIS_PHASE7_SELF_IMPROVEMENT_REPORT.md`](./docs/JARVIS_PHASE7_SELF_IMPROVEMENT_REPORT.md) | Self-Improvement | Error-correction compounding memory loops |
| [`JARVIS_PHASE10_REAL_WORLD_VALUE_REPORT.md`](./docs/JARVIS_PHASE10_REAL_WORLD_VALUE_REPORT.md) | Value Validation | Controlled execution of empirical value tasks |

---

## 📁 Repository Structure

```
ai-company-orchestrator/
├── agents/                  # Multi-agent swarm (Clara, Alex, Devon, Quinn), mission executors, tools
├── backend/                 # Core server runtime, Model Harness, WebSocket gateway, lifecycle
├── config/                  # Global system configuration and runtime parameters
├── diagnostics/             # Environment diagnostic tools and system telemetry scripts
├── docs/                    # Architectural specifications, benchmark reports, diagrams, and ADRs
│   ├── decisions/           # Architecture Decision Records (ADR-001 to ADR-006)
│   ├── diagrams/            # Standalone vector SVG architecture diagrams (01 to 10)
│   └── portfolio_readmes/   # Production README templates for academic portfolio repos
├── evidence/                # Verified test run evidence (screenshots, DOM dumps, event logs)
├── frontend/                # React 18 + Tailwind + Monaco Editor desktop workspace HUD
├── intelligence/            # Coding Agent 2.0 (AST repair, repo graph, semantic resolver, build loop)
├── obsidian_vault/          # Plain-text Markdown Knowledge Vault and Cornell study guides
├── persistence/             # SQLite repositories for rules, decisions, projects and messages
├── schemas/                 # Canonical JSON Schemas (Draft-07) for core data contracts
├── security/                # Security Sentinel watchdog, EDR host monitors, safety classifier
├── sentinel/                # Sentinel quarantine store and response history audit log
├── services/                # Specialized background services (Lecture recorder, synthesizer, AirLLM)
├── tests/                   # 38+ automated pytest test suites (953 passed tests)
└── workspace/               # Isolated project code sandboxes and AST metadata (.jarvis/)
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **OS**: Windows 10/11, macOS, or Linux (Windows recommended for full Sentinel EDR collectors)
- **Python**: 3.11 or higher
- **Node.js**: v20+ and `npm`
- **Ollama** *(optional)*: For 100% offline, private model execution (`qwen3.5:9b`)

### 2. Backend Setup
```powershell
# Create and activate Python virtual environment
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m playwright install chromium

# Configure environment variables
Copy-Item .env.example .env
```

### 3. Frontend & Desktop HUD Setup
```powershell
npm install
npm install --prefix frontend
```

### 4. Running JARVIS OS
```powershell
# Launch Desktop Application (Electron + React HUD + Backend Server)
npm start

# Or launch development mode (Vite Dev Server + Server)
npm run dev

# Or run standalone Python backend server
.\venv\Scripts\python.exe server.py
```

---

## 🧪 Testing & Verification

JARVIS OS maintains a comprehensive automated testing suite:

```powershell
# Run the complete test suite (953 tests)
.\venv\Scripts\python.exe -m pytest tests/ -q

# Run documentation & schema integrity tests
.\venv\Scripts\python.exe -m pytest tests/test_documentation_integrity.py -q

# Run Security Sentinel EDR test suites
.\venv\Scripts\python.exe -m pytest tests/test_sentinel.py tests/test_sentinel_response_actions.py -q

# Run Coding Agent 2.0 benchmarks
.\venv\Scripts\python.exe -m pytest tests/test_coding_agent_2_benchmark.py tests/test_repository_graph.py -q

# Validate frontend TypeScript zero-error build
npm run build --prefix frontend
```

---

## 🔒 Security

For vulnerability disclosures, Sentinel EDR architecture details, and sandbox boundaries, please consult [`SECURITY.md`](./SECURITY.md).

---

## 📜 License

Developed as an independent research and engineering project on **Autonomous Multi-Agent Cognitive Systems & Software Engineering Automation**. Distributed under the **MIT License**. Engineering skills based on specifications by [Addy Osmani (`agent-skills`)](https://github.com/addyosmani/agent-skills).

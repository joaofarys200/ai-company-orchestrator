# ADR-001: Hybrid Dual-Model Routing in Model Harness

## Context
JARVIS OS operates across diverse workloads: high-level mission planning, complex multi-file code refactoring, rapid conversational voice responses, and private on-device automation. Relying on a single commercial model for all requests results in high API costs, privacy exposure for local code, and vendor lock-in. Conversely, relying solely on local consumer hardware models can limit complex cross-repository reasoning.

## Decision
We implemented a **Hybrid Dual-Model Harness** (`backend/model_harness/`) with dynamic profile routing:
1. **Local Offline Provider (Ollama / `qwen3.5:9b` / AirLLM)**: Used for private operations, local file editing, and low-latency routine tasks.
2. **Cloud Zero-Cost & Reasoning Provider (OpenRouter)**: Used for complex tool-calling and mission decomposition (`openrouter/free`, `nvidia/nemotron-3-super-120b-a12b:free`).
3. **Cloud Fallback (Gemini / Claude / OpenAI)**: Activated as graceful degradation if free endpoints encounter rate-limits (`429`) or service degradation (`503`).
4. **Strict Schema & Recovery Envelopes**: All model outputs pass through a 7-stage deterministic validation loop (`parsing`, `schema`, `enums`, `references`, `preconditions`, `compatibility`, `acceptance_criteria`) with automatic mechanical repair.

## Alternatives Considered
- *Single Cloud Provider (OpenAI GPT-4o only)*: Rejected due to recurring token costs, reliance on external network connectivity, and privacy concerns.
- *Local Models Only*: Rejected due to high VRAM demands when running 70B+ parameter reasoning models on standard consumer developer machines.

## Consequences
- **Positive**: Zero cost for standard development loops; 100% privacy when local mode is selected; automatic recovery from malformed JSON.
- **Negative**: Requires handling different context window sizes and formatting peculiarities across multiple model families.

## Status
**ACCEPTED** (Implemented in `backend/model_harness/`).

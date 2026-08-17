---
type: index
domain: ai-engineering
difficulty: intermediate
tags:
  - ai-engineering
  - llm
  - agents
  - model-harness
  - rag
  - moc
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
---

# 🤖 AI & LLM Engineering Knowledge Index

Este MOC organiza o conhecimento sobre inferência autoregressiva, infraestrutura de serving, engenharia de contexto, decodificação restrita, compilação de kernels GPU e sistemas agênticos de auto-cura.

---

## 🏛️ Architecture, Serving & GPU Optimization
- [[Model Harness Architecture]] — Abstração de execução resiliente, timeouts e políticas de retry para LLMs.
- [[Ollama Local Model Serving]] — Execução local de modelos de código aberto com baixa latência e controle de recursos.
- [[KV-Cache Dynamics and Memory Optimization in Agent Workloads]] — PagedAttention, Prefix Caching e otimização de VRAM.
- [[GPU Kernel Compilation - CUDA, Triton and Memory Bandwidth]] — Roofline model, intensidade operacional e fusão de kernels em Triton.
- [[Speculative Decoding and Draft-Verification Dynamics]] — Aceleração de inferência via modelos draft rápidos e verificação paralela.
- [[Model Quantization Dynamics - GGUF, AWQ, GPTQ and KV-Cache Impact]] — Compressão de pesos e quantização de KV-cache (FP8/INT4).

## ⚙️ Model Harness & Constrained Decoding
- [[Constrained Decoding and Grammar-Based Generation]] — Máscara de logits via autômatos DFA/PDA e saídas JSON garantidas.
- [[Structured Outputs and Schema Validation]] — Constrained decoding e validação determinística com Pydantic v2.
- [[Deterministic vs Stochastic Inference in Coding Pipelines]] — Calibração de temperatura e top_p para pipelines de código vs ideação.
- [[Model Routing and Fallback Strategies]] — Padrões de cascata entre modelos locais rápidos e modelos frontier na nuvem.
- [[Tool Calling Protocols and Structured Invocation]] — Especificações OpenAPI / Function Calling e tratamento de saídas de ferramentas.
- [[Tool-Result Isolation and Epistemic Separation]] — Isolamento de saídas de ferramentas contra injeção indireta de prompts.

## 📚 Retrieval-Augmented Generation (RAG) & Vector Indexes
- [[RAG Architecture and Retrieval Strategies]] — Chunking semântico, busca híbrida (BM25 + Vetorial) e re-ranking.
- [[Vector Indexes - HNSW and Approximate Nearest Neighbor Partitioning]] — Grafos multicamadas HNSW e complexidade $O(\log N)$.
- [[Semantic Caching for LLM Responses and Invalidation Strategies]] — Cache semântico por embeddings e invalidação por hash de commit.
- [[Comparison - Lexical BM25 vs Dense Vector Embeddings vs Hybrid RAG]] — Análise comparativa entre métodos de busca e fusão RRF.

## 🧠 Context Engineering
- [[Context Engineering and Compression]] — Gestão de janelas de contexto, token budgeting e poda por AST.
- [[Anti-Pattern - Unbounded Context Accumulation]] — Degradação de atenção e poluição do histórico de mensagens.

## 🎯 Prompt Engineering & Grounding
- [[Hallucination Mitigation Techniques]] — Grounding com RAG, citações obrigatórias e validação externa de código.

## 👥 Agent Systems & Self-Healing
- [[Planner-Executor Agent Pattern]] — Desacoplamento entre planeamento estratégico (DAG) e execução tática.
- [[Self-Healing Prompt Loops and Reflective Orchestration (RHO-SHE)]] — Arquitetura de reflexão e auto-correção delimitada.
- [[Agent Loop Detection and Circuit Breaker]] — Deteção de oscilações, repetição de ferramentas e circuit breaking.

## 🛡️ Safety & Alignment
- [[Prompt Injection Defense in Autonomous Agents]] — Separação estrita de dados e instruções e guardrails em tempo de execução.

---

## 🛠️ Runbooks Relacionados em 08 - Runbooks/AI
- [[How to Handle Malformed Model Output]] — Procedimento de recuperação de JSON truncado.
- [[How to Detect and Break Agent Infinite Loops]] — Protocolo de intervenção em impasses de agentes.
- [[Runbook - How to Recover from RHO Rule Explosion and Saturated Context]] — Poda estrutural e compactação de reflexões.

## 📝 Lições de Produção em 09 - JARVIS/Lessons
- [[Lesson - Unhandled Rate Limits and Context Explosion]] — Explosão de janela de contexto em retentativas HTTP 429.
- [[Lesson - Low-Score BM25 Pollution in Short Semantic Queries]] — Contaminação de contexto por casamento léxico bruto.

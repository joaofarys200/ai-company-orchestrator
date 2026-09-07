# JARVIS OS — Phase 15 & 15.2 Autonomous Multi-Agent Collaboration & Conflict Resolution

## 1. Executive Summary & Architectural Overview

Phase 15 and Phase 15.2 evolve JARVIS OS from **Multi-Agent Task Distribution** (Phase 14) to **Autonomous Multi-Agent Collaborative Execution**. Instead of assigning work units strictly in isolation, specialized autonomous agents (`CodingAgent`, `TestingAgent`, `ReviewAgent`, `ArchitectureAgent`, `ResearchAgent`, `BrowserAgent`) collaborate concurrently on shared tasks, projects, and critical modules.

The core engine guarantees deterministic conflict detection across 7 dimensions, deterministic arbitration governed by an unshakeable evidence hierarchy (where confidence never replaces objective proof), non-destructive disjoint auto-merge with AST awareness, anti-loop safeguards, crash-resilient session checkpointing, and seamless integration with the Satisfaction Barrier.

```
                  ┌─────────────────────────────────────────────────────────┐
                  │               MISSION LIFECYCLE ORCHESTRATOR           │
                  └───────────────────────────┬─────────────────────────────┘
                                              │ Collaborative Node Dispatch
                                              ▼
                  ┌─────────────────────────────────────────────────────────┐
                  │                 COLLABORATION COORDINATOR               │
                  │   - Session Lifecycle (OPEN -> MERGED / RESOLVED)      │
                  │   - Deduplication & Anti-Loop Safeguards                │
                  │   - Checkpointing & Recovery Engine                     │
                  └─────────────┬───────────────────────────┬───────────────┘
                                │                           │
             ┌──────────────────┴───────────────┐           │
             ▼                                  ▼           ▼
┌───────────────────────────┐     ┌───────────────────────────┐     ┌─────────────────────────┐
│     CONFLICT DETECTOR     │     │  AGENT CONFLICT ARBITRATOR│     │   PATCH MERGE ENGINE    │
│  - Hierarchical Index     │     │  - Strict Evidence Score  │     │  - Python AST Merge     │
│  - Candidate Conflict Gr. │     │  - Security Sandbox Gate  │     │  - TS/JS Regex Merge    │
│  - 7D Taxonomy Detection  │     │  - Economic Bypass Denied │     │  - Windowed Block Merge │
│  - Connected Components   │     │  - Deterministic Winners  │     │  - 3-Way Disjoint Match │
└───────────────────────────┘     └───────────────────────────┘     └─────────────────────────┘
             │                                  │                               │
             └──────────────────────────────────┼───────────────────────────────┘
                                                ▼
                                  ┌───────────────────────────┐
                                  │   SATISFACTION BARRIER    │
                                  │  - 100% Verified Evidence │
                                  │  - Zero False Positives   │
                                  └───────────────────────────┘
```

---

## 2. 7-Dimensional Conflict Taxonomy

The `ConflictDetector` detects conflicts across 7 orthogonal dimensions deterministically using SHA-256 content addressing:

| Dimension | Conflict Type Enum | Detection Mechanism | Resolution Strategy |
| :--- | :--- | :--- | :--- |
| **1. File Overlap** | `FILE_CONFLICT` | Overlapping file modifications without declared disjoint symbol boundaries | PatchMergeEngine disjoint auto-merge; if overlapping lines, arbitrate via evidence hierarchy |
| **2. Symbol AST** | `SYMBOL_CONFLICT` | AST parsing (`ast.parse`) reveals concurrent modifications to same function, class, or async method | Deterministic evidence score comparison; highest verified evidence wins |
| **3. Semantic** | `SEMANTIC_CONFLICT` | Divergent behavioral intents (e.g., safe workspace sandbox vs unrestricted shell execution) | Security rules applied first; sandbox strictly prioritized; unverified actions blocked |
| **4. Architectural** | `ARCHITECTURAL_CONFLICT`| Incompatible architectural patterns (e.g., RESTful HTTP endpoints vs GraphQL schema) | Trigger `REPLAN` or `REPAIR` through Dynamic Sub-DAG expansion and Adaptive Planning Engine |
| **5. Contract** | `CONTRACT_CONFLICT` | Consumer (Frontend) / Producer (Backend) API route mismatch or parameter type divergence | Backend/Contract authority with regression tests prioritized; route alignment enforced |
| **6. Test Verdict** | `TEST_CONFLICT` | Conflicting assertions or execution verdicts between test suites | Empirical execution priority: higher test pass count and exit code 0 wins |
| **7. Requirement** | `REQUIREMENT_CONFLICT` | Ambiguity in user requirements (e.g., case-sensitivity divergence in search) | ReviewAgent consultation, prompt clarification, or test-backed specification |

---

## 3. Evidence Hierarchy & Scoring Rules

Confidence is strictly segregated from correctness. An agent asserting `0.99` confidence with no test evidence will always lose to an agent with `0.50` confidence backed by a passing test.

```
Hard Validation / Sandbox (1000 pts)
  > Real Test Suite Execution (500 pts + 10 pts/test, max 700 pts)
    > Clean Build (300 pts)
      > Runtime Verification (200 pts)
        > Real Browser / Playwright (150 pts)
          > Contract Conformance (100 pts)
            > Architecture Compatibility (80 pts)
              > Agent Confidence (max 10 pts)
                > Textual Rationale (1 pt)
```

### Security & Economic Invariants
1. **Economic Safeguards:** In tasks involving funds, payments, or ledger operations, consensus between collaborating agents *cannot* bypass external gateway validation. Any agreement to skip validation produces `ArbitrationDecision.BLOCK`.
2. **Security Sandbox:** Proposing commands outside the workspace or privilege escalation triggers automatic `BLOCK`, selecting the sandboxed proposal regardless of confidence.
3. **Role Privileges:** Agents without code modification capabilities (e.g. `RESEARCH`) cannot emit `PATCH` proposals; attempts are dropped or blocked.

---

## 4. Disjoint Auto-Merge Engines (Phase 15.2)

Blind textual merges are strictly forbidden. The system applies a multi-layered merge pipeline:

1. **Python AST Structural Merge:** Parses both proposals using `ast.parse`. When changes touch disjoint top-level or class functions, AST nodes are merged losslessly and compiled to check syntax integrity.
2. **TypeScript / JavaScript Regex Structural Merge:** Tokenizes function, class, and interface declarations to merge disjoint symbol blocks.
3. **Windowed Block Merge:** For large artifacts (>10,000 lines), slices source into diff windows with 50-line padding to prevent parser stalls and memory spikes.
4. **SequenceMatcher 3-Way Auto-Merge:** Validates clean offsets against original base text, verifying that no hunk boundaries collide.
5. **Merge Failure Memory:** If an AST or 3-way merge fails, diagnostic details are recorded to `MergeFailureMemory` and an adaptive fallback is selected without data loss.

---

## 5. Hierarchical Indexing & Connected Components (Phase 15.2)

To avoid $O(N^2)$ candidate comparisons in dense multi-agent sessions:
1. **Hierarchical Index (`HierarchicalConflictIndex`):** Organizes proposals progressively across:
   - Package / Directory Level
   - File Path Level
   - Symbol & AST Range Level
   - API Endpoint & Contract Level
   - Requirement Tag Level
2. **Connected Component Decomposition:** Partitions proposals into disjoint connected components. Non-interfering sub-graphs are arbitrated in parallel.
3. **Adaptive Density Strategy:**
   - Sparse (<35% density): `PAIRWISE` evaluation.
   - Dense (>=35% density, >=8 agents): `CONNECTED_COMPONENTS` or `BUCKETED_COMPARISON`.
   - Guaranteed Invariant: **Zero False Negatives** verified empirically against exhaustive reference matrix.

---

## 6. WebSocket Protocol & UI Integration

Two real-time WebSocket contracts are implemented:
- `mission_collaboration_status`: Queries active session state, participating agents, conflicts, arbitrations, and auto-merge metrics.
- `mission_collaboration_arbitrate`: Triggers manual or automated arbitration on an existing conflict.

The frontend (`MissionPlanner.tsx`) features:
- Live 7D Conflict Taxonomy indicator with real-time badges
- Winning proposal visualization with evidence score breakdown
- Auto-merge telemetry and active lease monitoring
- Real-time arbitration trigger buttons

---

## 7. Performance & Scalability Benchmarks

Empirically measured via `scripts/collaboration_performance_benchmark.py`:

| Benchmark Metric | Measured Result | Throughput / Efficiency |
| :--- | :--- | :--- |
| **Hierarchical Graph (2 Proposals)** | 0.20 ms | Instant O(1) fast-path |
| **Hierarchical Graph (50 Proposals)** | 1.51 ms | 225 pairs evaluated vs 1,225 combinatorial |
| **Hierarchical Graph (100 Proposals)** | 2.86 ms | Sub-3ms for massive fleet |
| **Arbitration Latency (Microbench)** | 6.67 µs – 13.24 µs / op | 75,000 – 150,000 ops/second |
| **Auto-Merge Latency (5,000 lines)** | 2.09 ms | Sub-5ms lossless merge |
| **Zero False Negatives Invariant** | 100% match | 0 missed conflicts vs $O(N^2)$ exhaustive |

### `FIRST_REAL_LIMIT`
- **Proposal Density Threshold:** Beyond 50 concurrent proposals on a single task node, graph density exceeds 35%, triggering `CONNECTED_COMPONENTS` clustering.
- **AST Parsing Scale Threshold:** At 10,000 lines per source file, the engine automatically switches to `Windowed Block Merge` to avoid Python compiler recursion depth limits while keeping response time under 10ms.
- **Lease Concurrency Ceiling:** Maximum 8 concurrent agent leases per file resource under `HierarchicalQuotaManager` to prevent lease thrashing.

# Architecture & System Design — Phase 79: Autonomous Adaptive Experimentation & Scientific Hypothesis Validation

**Author**: Antigravity Assistant (Google DeepMind)  
**Date**: 2026-10-25  
**Target Subsystems**: `backend/agents/adaptive_experimentation/` & `agents/adaptive_experimentation/`  
**Status**: APPROVED FOR IMPLEMENTATION  

---

## 1. Architectural Mission & Principles

Phase 79 establishes the **Autonomous Adaptive Experimentation & Scientific Hypothesis Validation Engine** for JARVIS OS. Its purpose is to guide autonomous investigations by quantitatively determining *which observation or experiment to perform next*, updating beliefs probabilistically from actual evidence, and applying evidence-based stopping criteria.

### The 11-Stage Closed-Loop Lifecycle

```mermaid
graph TD
    S1[1. INTAKE QUESTION: Diagnostic problem & competing hypotheses] --> S2[2. ESTIMATE PRIORS: Normalize prior probability distribution]
    S2 --> S3[3. GENERATE CANDIDATES: Compile candidate diagnostic experiments pool]
    S3 --> S4[4. INFORMATION VALUE: Compute prior entropy & Expected Information Gain EIG]
    S4 --> S5[5. COST & RISK UTILITY: Score net utility factoring cost, risk, & latency]
    S5 --> S6[6. SELECT OPTIMAL: Select experiment maximizing EIG per unit of cost/risk]
    S6 --> S7[7. PREFLIGHT & AUTH: Verify read-only safety, block destructive ops]
    S7 --> S8[8. EXECUTE & RECORD: Execute probe, record observation with SHA-256 hash]
    S8 --> S9[9. BAYESIAN UPDATE: Calculate posterior distribution P Hi | o]
    S9 --> S10[10. STOPPING EVALUATION: Evaluate stopping rules e.g. certainty, EVOI, budget]
    S10 --> S11[11. REPORT & AUDIT: Formulate auditable scientific report with audit trail]
    S10 -- Not Stopped --> S3
```

---

## 2. Mathematical Foundation: Information Gain & Utility

### Prior Shannon Entropy
For a hypothesis space of $K$ mutually exclusive and exhaustive hypotheses $\{H_1, \dots, H_K\}$ with probabilities $p_i = P(H_i)$:
$$H(H) = -\sum_{i=1}^K p_i \log_2(p_i)$$
where $0 \log_2(0) \equiv 0$.

### Conditional Entropy & Expected Information Gain (EIG)
An experiment $E$ can yield discrete outcomes $O = \{o_1, \dots, o_J\}$.
The expected probability of observing outcome $o_j$ is:
$$P(o_j) = \sum_{i=1}^K P(o_j \mid H_i) P(H_i)$$
The posterior probability of hypothesis $H_i$ given outcome $o_j$ is:
$$P(H_i \mid o_j) = \frac{P(o_j \mid H_i) P(H_i)}{P(o_j)}$$
The conditional entropy after observing $o_j$ is:
$$H(H \mid o_j) = -\sum_{i=1}^K P(H_i \mid o_j) \log_2 P(H_i \mid o_j)$$
The Expected Information Gain (mutual information $I(H; E)$) is:
$$\text{EIG}(E) = H(H) - \sum_{j=1}^{|O|} P(o_j) H(H \mid o_j)$$

### Cost and Risk Penalized Utility
To prevent running unnecessarily expensive or risky experiments, the engine ranks candidates by Net Expected Utility:
$$U(E) = \frac{\text{EIG}(E)}{1.0 + \lambda_c C(E) + \lambda_r R(E)}$$
where:
- $C(E) \in [0.0, 1.0]$: Normalized execution cost (time and compute resource consumption).
- $R(E) \in [0.0, 1.0]$: Operational risk (e.g. read-only probe $R=0.0$; heavy network scan $R=0.6$).
- $\lambda_c, \lambda_r \ge 0$: Tuning weights for cost and risk penalties.
- Tie-breaking: If two experiments have equal utility ($|\Delta U| < 10^{-4}$), prefer the lower risk, then lower cost experiment.

---

## 3. Bayesian Belief Updating

Upon executing experiment $E$ and observing actual outcome $o^*$:
1. **Likelihood Retrieval**: Look up $P(o^* \mid H_i)$ for each hypothesis.
2. **Contradiction Penalty**: If an outcome is mathematically incompatible ($P(o^* \mid H_i) = 0$), $H_i$ is refuted.
3. **Posterior Computation**:
   $$P_{\text{new}}(H_i) = \frac{P(o^* \mid H_i) P_{\text{prior}}(H_i)}{\sum_{j=1}^K P(o^* \mid H_j) P_{\text{prior}}(H_j)}$$
4. **Laplace Smoothing**: Apply minimal smoothing $\epsilon = 10^{-4}$ to avoid permanent zero-lock from noisy observations.
5. **Synthetic Caveat**: If the experiment was executed against synthetic mock fixtures, posterior updates are capped and tagged `SYNTHETIC_FIXTURE_EVIDENCE`.

---

## 4. Evidence-Based Stopping Criteria

The adaptive investigation loop terminates when any of the following stopping criteria are satisfied:
1. `HYPOTHESIS_CONFIRMED`: A leading hypothesis reaches $\max_i P(H_i) \ge \tau_{\text{confirm}}$ (default 0.85).
2. `MINIMAL_UNCERTAINTY`: Remaining entropy $H(H) \le \epsilon_H$ (default 0.25 bits).
3. `DIMINISHING_INFORMATION_GAIN`: The maximum $\text{EIG}(E)$ among all remaining safe experiments is below threshold $\text{EIG}_{\min}$ (default 0.05 bits).
4. `BUDGET_EXHAUSTED`: Accumulated experiment cost exceeds the allocated budget $B_{\text{cost}}$.
5. `NO_SAFE_EXPERIMENTS_REMAIN`: All remaining candidate experiments are either destructive, rejected by policy, or require ungranted authorization.
6. `CONTRADICTED_INCONCLUSIVE`: All hypotheses have been refuted or mutually contradict available observations.

---

## 5. Security & Safety Governance

1. **Non-Destructive by Default**: Only read-only or sandbox experiments are permitted automatically.
2. **Destructive Guard**: Experiments containing destructive commands (`rm`, `kill`, `drop`, `truncate`, `delete`) are blocked immediately.
3. **Authorization Boundary**: Tier 4 experiments require an authentic Phase 77 `HUMAN_APPROVAL_RECORD`.
4. **Traceable Persistence**: All experiments, observations, priors, posteriors, and stopping decisions are atomically recorded in `.jarvis/adaptive_experimentation/`.

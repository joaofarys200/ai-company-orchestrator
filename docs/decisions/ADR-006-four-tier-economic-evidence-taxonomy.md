# ADR-006: Four-Tier Economic Evidence Taxonomy and Factuality Gate

## Context
Many AI agent projects claim "autonomous economic value" or "revenue generation" based on simulated test suites or mock client interactions. To maintain scientific integrity and engineering factuality, JARVIS OS requires an unambiguous classification system that prevents confusing in-memory benchmark tests with real-world financial transactions.

## Decision
We established a strict **Four-Tier Economic Evidence Taxonomy** (`agents/controlled_real_world_value_agent.py` & `schemas/economic-mission.schema.json`):
- **Tier 1: `SYNTHETIC_BENCHMARK`**: Local unit tests, mock scenarios, synthetic coding benchmark runs. Verified purely by test assertions and exit codes.
- **Tier 2: `EXTERNAL_OBSERVED`**: Real-world read-only observation (e.g. arXiv paper extraction, live website scraping). Verified by SHA256 digest and HTTP response headers.
- **Tier 3: `EXTERNAL_VERIFIED`**: Live authenticated external interactions (e.g. Chrome DevTools browser actions, git remote pushes, authenticated API responses). Verified by network traces and DOM screenshots.
- **Tier 4: `FINANCIAL_TRANSACTION_VERIFIED`**: Actual financial exchange (e.g. bank transfer receipts, blockchain transaction hashes, payment gateway webhooks). Verified by cryptographic signatures and external settlement receipts.

## Invariant Rule
**No synthetic simulation or test trial shall ever be presented as financial revenue or real money.** All reports and benchmarks must explicitly state the exact evidence tier.

## Alternatives Considered
- *Single "Verified" Status*: Rejected because it conceals whether verification occurred in a mock test environment or on live networks.

## Consequences
- **Positive**: Absolute transparency; builds trust with researchers and engineers; prevents hallucinated revenue metrics.
- **Negative**: Requires explicit tier labeling across economic agent tasks.

## Status
**ACCEPTED** (Implemented across `docs/`, `agents/`, and `schemas/`).

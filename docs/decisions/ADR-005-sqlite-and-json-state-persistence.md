# ADR-005: Hybrid SQLite and JSON State Persistence Architecture

## Context
JARVIS OS manages both structured relational entities (user rules, architecture decisions, message history, Kanban cards) and hierarchical, document-centric graphs (AST indices, monorepo dependency DAGs, coding session checkpoints, Obsidian notes).

## Decision
We implemented a **Hybrid Persistence Architecture**:
1. **SQLite Database (`database.db`)**: Used for relational data requiring fast indexing, filtering, and ACID transactions (`rules`, `architecture`, `decisions`, `messages`, `kanban_cards`). Operates with Write-Ahead Logging (WAL) enabled for high concurrent throughput.
2. **Project Metadata JSON Stores (`workspace/.jarvis/`)**: Stores project-specific symbol trees (`ast_index.json`), coding session proposals, and pre-modification checkpoints (`session.json`, `checkpoint.json`).
3. **Plain-Text Markdown Knowledge Vault (`obsidian_vault/`)**: Human-readable and human-editable substrate for long-term knowledge, literature notes, Cornell study guides, and system documentation.

## Alternatives Considered
- *All in JSON Files*: Rejected due to lack of indexing, race conditions on concurrent reads/writes, and slow query performance for chat history.
- *All in Heavy External DB (PostgreSQL / MongoDB)*: Rejected to avoid imposing complex daemon dependencies on developer desktop machines.

## Consequences
- **Positive**: Zero external database configuration required; single-file portability (`database.db`); human-inspectable code trees and checkpoints in JSON.
- **Negative**: Requires maintaining separate repositories for SQLite models and filesystem JSON schemas.

## Status
**ACCEPTED** (Implemented in `database.py`, `persistence/`, and `intelligence/project_context.py`).

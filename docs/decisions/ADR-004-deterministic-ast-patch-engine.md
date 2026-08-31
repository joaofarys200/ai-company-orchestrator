# ADR-004: Deterministic AST Symbol Patch Engine vs Whole-File Rewriting

## Context
Standard LLM code modification often relies on rewriting entire files or executing fuzzy unified diff replacements. On large files (&gt;500 lines), full-file rewriting is slow, consumes large token budgets, frequently introduces subtle regressions in untouched functions, and often fails due to output token truncation.

## Decision
We implemented a **Deterministic AST Symbol Patch Engine** (`intelligence/coding_session.py` & `agents/patch_engine.py`):
1. **AST Node Indexing (`project_context.py`)**: Parses Python and JavaScript/TypeScript source files into Abstract Syntax Trees, indexing top-level and nested functions, classes, and exported symbols along with byte offsets and SHA256 hashes.
2. **Atomic Symbol Replacement (`replace_symbol`)**: When modifying a function or class, Devon extracts and replaces only the exact AST symbol span, preserving the surrounding file intact.
3. **Automated Pre-Modification Checkpointing**: Before applying changes, byte-level snapshots are recorded to `workspace/.jarvis/projects/<project_id>/coding_sessions/<session_id>/checkpoint.json`.
4. **Autonomous Self-Repair Loop (`autonomous_repair_loop.py`)**: If `py_compile`, `tsc`, or unit tests fail post-patch, the repair engine analyzes the compiler error and performs localized fixes or rolls back cleanly.

## Alternatives Considered
- *Search-and-Replace Regular Expressions*: Fragile when whitespace, comments, or variable formatting shift slightly.
- *Blind Whole-File Overwrites*: Discarded due to token overhead and regression frequency.

## Consequences
- **Positive**: Blazing fast patches; minimal token usage; zero accidental deletions of surrounding functions; deterministic recovery on syntax errors.
- **Negative**: Requires AST parser support for each target programming language.

## Status
**ACCEPTED** (Implemented in `intelligence/` and `agents/patch_engine.py`).

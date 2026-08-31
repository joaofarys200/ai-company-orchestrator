# Contributing to JARVIS OS

Thank you for your interest in contributing to **JARVIS OS**! We welcome contributions that uphold the highest standards of engineering rigor, architectural cleanliness, type safety, and factuality.

---

## 1. Development Philosophy

1. **Factuality Over Hype**: All claims, benchmarks, and architectural documentation must reflect verified code in the repository. Never claim synthetic simulations as financial revenue.
2. **Deterministic Quality Gates**: Every code modification must pass static analysis, type checking, unit tests, and schema validation.
3. **Defensive by Default**: All new tools or features must respect sandbox boundaries and declare explicit permission levels in the Security Sentinel catalog.

---

## 2. Setting Up the Development Environment

### Prerequisites
- Windows 10/11, macOS, or Linux
- Python 3.11+
- Node.js v20+ and `npm`

### Local Setup
```bash
# 1. Clone repository
git clone https://github.com/joaofarys200/ai-company-orchestrator.git
cd ai-company-orchestrator

# 2. Setup Python environment
python -m venv venv
./venv/Scripts/python.exe -m pip install --upgrade pip
./venv/Scripts/python.exe -m pip install -r requirements.txt
./venv/Scripts/python.exe -m playwright install chromium

# 3. Setup Frontend dependencies
npm install
npm install --prefix frontend

# 4. Copy environment template
cp .env.example .env
```

---

## 3. Testing Standards

Before submitting a pull request, all automated test suites must pass:

```bash
# Run backend Python tests
./venv/Scripts/python.exe -m pytest tests/ -q

# Run documentation integrity tests
./venv/Scripts/python.exe -m pytest tests/test_documentation_integrity.py -q

# Build frontend to ensure TypeScript zero-error compliance
npm run build --prefix frontend
```

---

## 4. Code Style &amp; Conventions

- **Python**: PEP 8 compliance, explicit type annotations, dataclasses with slots where appropriate, context managers for transactions.
- **TypeScript**: Strict mode enabled (`tsconfig.json`), no `any` where a concrete interface can be defined, functional React components with custom hooks.
- **JSON Schemas**: Draft-07 compliance with `$id`, `required`, and `additionalProperties: false` where strict contracts are needed.
- **Git Commits**: Conventional commit format (`feat: ...`, `fix: ...`, `docs: ...`, `chore: ...`).

---

## 5. Pull Request Checklist

- [ ] Code follows project conventions and passes linters.
- [ ] Added or updated automated unit tests in `tests/`.
- [ ] Validated with `npm run build --prefix frontend`.
- [ ] Updated corresponding JSON Schemas in `schemas/` if data contracts changed.
- [ ] Updated `CHANGELOG.md` with concise description of changes.

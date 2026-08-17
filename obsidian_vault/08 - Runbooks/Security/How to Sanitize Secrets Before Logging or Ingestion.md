---
type: troubleshooting
domain: security
difficulty: intermediate
tags:
  - security
  - troubleshooting
  - secrets
  - sanitization
  - privacy
status: verified
---

# ðŸ› ï¸ How to Sanitize Secrets Before Logging or Ingestion

## 1. Sintomas & DiagnÃ³stico
- Tokens de autenticaÃ§Ã£o (`ghp_...`, `sk-...`, `Bearer eyJ...`) aparecem visÃ­veis nos ficheiros de log (`.log`), traces do console ou histÃ³rico de conversas do Obsidian.
- Alertas de seguranÃ§a emitidos por scanners automÃ¡ticos de repositÃ³rio (ex: GitHub Secret Scanning).

---

## 2. ImplementaÃ§Ã£o do Filtro de Logging Customizado (Python)

```python
import logging
import re

class SensitiveDataRedactionFilter(logging.Filter):
    PATTERNS = [
        re.compile(r"ghp_[A-Za-z0-9]{36}"),
        re.compile(r"sk-[A-Za-z0-9]{32,}"),
        re.compile(r"sk-proj-[A-Za-z0-9_-]{40,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"(api[-_]?key|secret|password|token)\s*[:=]\s*['\"]?([^\s'\",]+)", re.IGNORECASE)
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact(str(arg)) for arg in record.args)
        return True

    def _redact(self, text: str) -> str:
        for pattern in self.PATTERNS:
            text = pattern.sub("[REDACTED_SECRET]", text)
        return text

# ConfiguraÃ§Ã£o global no logger
logger = logging.getLogger("jarvis")
redactor = SensitiveDataRedactionFilter()
logger.addFilter(redactor)
```

---

## 3. VerificaÃ§Ã£o Automatizada em CI/CD
Antes de qualquer merge, executar scanner de segredos no repositÃ³rio:

```powershell
# Executar verificaÃ§Ã£o local de segredos
git diff HEAD~1 | Select-String -Pattern "ghp_", "sk-", "AKIA"
```

---

## 4. Related Concepts
- [[Credential Sanitization and Secret Masking]]
- [[Least-Privilege Process Sandboxing and Execution Jail]]
- [[Threat Modeling for Autonomous Coding Agents]]

---

## 5. Sources
- *OWASP Secrets Management Cheat Sheet*: https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html
- *Python logging documentation - Filter Objects*: https://docs.python.org/3/library/logging.html#filter-objects

## Query Relevance
Como sanitizar credenciais e segredos antes de logs ou ingestão em telemetria.


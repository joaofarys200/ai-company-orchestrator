---
type: concept
domain: security
difficulty: intermediate
tags:
  - security
  - secrets-management
  - sanitization
  - privacy
  - logging
status: verified
---

# ðŸ™ˆ Credential Sanitization and Secret Masking

## 1. O Risco de Fuga de Credenciais em Agentes
Agentes de IA operam com ficheiros `.env`, tokens de autenticaÃ§Ã£o (GitHub PATs, chaves OpenAI/Gemini, senhas de banco de dados) e variÃ¡veis de ambiente.

Se esses segredos forem impressos em logs de terminal, enviados para provedores de modelos de terceiros no histÃ³rico do prompt ou persistidos em relatÃ³rios pÃºblicos Markdown, ocorre **vazamento de credenciais (Credential Leak)**.

---

## 2. PadrÃµes de DeteÃ§Ã£o de Segredos (Shannon Entropy & Regex)

1. **Regex de Prefixo Conhecido**:
   - Chaves GitHub: `ghp_[a-zA-Z0-9]{36}`, `github_pat_[a-zA-Z0-9_]{82}`
   - Chaves OpenAI: `sk-[a-zA-Z0-9]{48}`, `sk-proj-[a-zA-Z0-9_-]{80,}`
   - Chaves AWS: `AKIA[0-9A-Z]{16}`
   - Chaves GenÃ©ricas / JWTs: `Bearer\s+[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*`
2. **Entropia de Shannon para Tokens AleatÃ³rios**:
   - Strings com alta densidade de informaÃ§Ã£o aleatÃ³ria ($H \ge 3.5$) em blocos alfanumÃ©ricos sem palavras de dicionÃ¡rio.

---

## 3. ImplementaÃ§Ã£o do Sanitizador de Segredos

```python
import re
from typing import List

SECRET_REGEX_PATTERNS = [
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"github_pat_[a-zA-Z0-9_]{82}"),
    re.compile(r"sk-[a-zA-Z0-9]{32,}"),
    re.compile(r"sk-proj-[a-zA-Z0-9_-]{40,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(password|passwd|secret|api_key|token)\s*[:=]\s*['\"]?([^\s'\"]+)['\"]?", re.IGNORECASE)
]

def mask_secrets_in_text(text: str) -> str:
    """
    Substitui tokens sensÃ­veis por mÃ¡scaras de seguranÃ§a redigidas.
    """
    if not text:
        return ""

    sanitized = text
    for pattern in SECRET_REGEX_PATTERNS:
        def redact_match(match):
            # Se tiver grupos de captura (ex: key=value), redigir apenas o valor
            if match.groups():
                full = match.group(0)
                secret_val = match.group(2) if len(match.groups()) >= 2 else match.group(1)
                return full.replace(secret_val, "[REDACTED_SECRET]")
            return "[REDACTED_SECRET]"
            
        sanitized = pattern.sub(redact_match, sanitized)

    return sanitized
```

---

## 4. IntegraÃ§Ã£o no Pipeline de Logging e Prompting
- **No Logger (`logging.Formatter`)**: Toda a linha enviada para ficheiros de log passa pelo filtro `mask_secrets_in_text`.
- **No Exportador de RelatÃ³rios / Walkthrough**: Antes de salvar qualquer ficheiro markdown, os tokens sÃ£o sanitizados.

---

## 5. Related Concepts
- [[How to Sanitize Secrets Before Logging or Ingestion]]
- [[HMAC Signature Verification for Webhooks]]
- [[Least-Privilege Process Sandboxing and Execution Jail]]
- [[Seguranca_Defensiva_DevSecOps_e_Sandboxing]]

---

## 6. Sources
- *OWASP Secrets Management Cheat Sheet*: https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html
- *TruffleHog & detect-secrets Rulesets*: https://github.com/trufflesecurity/trufflehog

## Query Relevance
Mascaramento preventivo de credenciais e tokens em telemetria e logs.


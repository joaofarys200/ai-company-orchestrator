---
type: concept
domain: security
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: advanced
tags:
  - security
  - secrets
  - shannon-entropy
  - regex
  - sanitization
prerequisites:
  - "[[Credential Sanitization and Secret Masking]]"
related:
  - "[[How to Sanitize Secrets Before Logging or Ingestion]]"
  - "[[Structured Logging and Distributed Trace Context]]"
used_by:
  - "[[JARVIS Security Sandbox and Policy Engine]]"
failure_modes:
  - "[[Lesson - Accidental Secret Leaks in Telemetry Broadcast]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: A Mathematical Theory of Communication (Claude E. Shannon, 1948)
    type: PRIMARY_SOURCE
    url: https://ieeexplore.ieee.org/document/6773024
  - title: TruffleHog - High Entropy and Regex Secret Detection Engine
    type: PRIMARY_SOURCE
    url: https://github.com/trufflesecurity/trufflehog
---

# 🔑 Shannon Entropy and Heuristic Secret Scanners

## 1. Pergunta Central
> *Como detectar chaves de API, senhas e tokens criptográficos desconhecidos em strings de texto e código sem depender de prefixos conhecidos (como `ghp_` ou `sk-`)?*

---

## 2. Entropia de Shannon para Cadeias de Caracteres
A Entropia de Shannon mede a aleatoriedade e densidade de informação numa sequência de caracteres.
Para uma string $S$ com conjunto de caracteres únicos $C$, a entropia $H(S)$ em bits por caractere é:

$$H(S) = -\sum_{c \in C} p(c) \log_2 p(c)$$
- $p(c)$: Frequência relativa do caractere $c$ na string.

### 2.1. Calibração de Limiares de Entropia
- **Texto em Linguagem Natural**: $H(S) \approx 2.5 - 3.5\text{ bits/char}$
- **Nomes de Variáveis em Código**: $H(S) \approx 3.0 - 3.8\text{ bits/char}$
- **Chaves Criptográficas Hexadecimais**: $H(S) \ge 3.8\text{ bits/char}$ (base 16)
- **Tokens Base64 (JWT, AWS Secret Keys)**: $H(S) \ge 4.5\text{ bits/char}$ (base 64)

---

## 3. Algoritmo Híbrido de Redação no JARVIS

```python
import math
from collections import Counter

def calculate_shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    entropy = 0.0
    length = len(text)
    counts = Counter(text)
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy

def is_potential_high_entropy_secret(token: str) -> bool:
    if len(token) < 16:
        return False
    entropy = calculate_shannon_entropy(token)
    # Se comprimento >= 16 e entropia > 4.2 -> Alto risco de segredo
    return entropy > 4.2
```

---

## 4. Related Concepts
- [[Credential Sanitization and Secret Masking]]
- [[How to Sanitize Secrets Before Logging or Ingestion]]
- [[Lesson - Accidental Secret Leaks in Telemetry Broadcast]]

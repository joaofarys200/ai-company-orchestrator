---
type: concept
domain: security
status: verified
source_type: PRIMARY_SOURCE
confidence: high
difficulty: advanced
tags:
  - security
  - authentication
  - webhooks
  - replay-attacks
  - nonce
  - timestamp
prerequisites:
  - "[[HMAC Signature Verification for Webhooks]]"
related:
  - "[[Credential Sanitization and Secret Masking]]"
  - "[[Zero Trust Architecture and Microsegmentation]]"
used_by:
  - "[[JARVIS Security Sandbox and Policy Engine]]"
failure_modes:
  - "[[Lesson - Accidental Secret Leaks in Telemetry Broadcast]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: RFC 2104 - HMAC - Keyed-Hashing for Message Authentication
    type: PRIMARY_SOURCE
    url: https://datatracker.ietf.org/doc/html/rfc2104
  - title: Stripe Webhook Signatures and Replay Attack Prevention
    type: PRIMARY_SOURCE
    url: https://docs.stripe.com/webhooks/signatures
---

# 🛡️ Replay Attack Prevention with Nonce and Timestamp Windows

## 1. Pergunta Central
> *Como impedir que um atacante que intercepte um payload de webhook legítimo e assinado com HMAC consiga reenviar a mesma requisição múltiplas vezes para duplicar transações ou comandos de missão?*

---

## 2. O Mecanismo da Janela de Tolerância e Armazenamento de Nonce

A validação de webhooks segura opera sob um esquema de duas camadas:

```
[ Webhook Request ] -> Headers: `X-Signature`, `X-Timestamp`, `X-Nonce`
                            |
                            v
[ 1. Verificação da Janela Temporal ]
     - Se |Current_Time - Timestamp| > 300 segundos -> REJEITA (Timestamp Expirado!)
                            |
                            v (Dentro da Janela de 5 min)
[ 2. Verificação de Unicidade do Nonce ]
     - Consulta Cache/Redis: `EXISTS nonce:{X-Nonce}`
     - Se existe -> REJEITA (Ataque de Replay Detectado!)
     - Se não existe -> Grava `SETEX nonce:{X-Nonce} 300 "1"`
                            |
                            v
[ 3. Validação Criptográfica do HMAC ]
     - HMAC-SHA256(Secret, Timestamp + "." + Nonce + "." + Body) == Signature
```

---

## 3. Implementação em Python

```python
import hmac
import hashlib
import time
from typing import Set

SEEN_NONCES: Set[str] = set()
TOLERANCE_SECONDS = 300

def verify_webhook_request(payload: bytes, signature: str, timestamp_str: str, nonce: str, secret: bytes) -> bool:
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        return False

    # 1. Validar janela temporal
    now = int(time.time())
    if abs(now - timestamp) > TOLERANCE_SECONDS:
        return False  # Rejeitado por atraso temporal

    # 2. Validar Nonce
    if nonce in SEEN_NONCES:
        return False  # Rejeitado por duplicação de nonce
    SEEN_NONCES.add(nonce)

    # 3. Validar assinatura criptográfica com compare_digest
    signed_payload = f"{timestamp}.{nonce}.".encode("utf-8") + payload
    expected_sig = hmac.new(secret, signed_payload, hashlib.sha256).hexdigest()
    
    return hmac.compare_digest(expected_sig, signature)
```

---

## 4. Related Concepts
- [[HMAC Signature Verification for Webhooks]]
- [[Idempotency in Software Systems]]
- [[Zero Trust Architecture and Microsegmentation]]

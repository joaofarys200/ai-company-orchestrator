---
type: troubleshooting
domain: security
difficulty: intermediate
tags:
  - security
  - troubleshooting
  - webhooks
  - hmac
  - signatures
  - runbook
status: verified
---

# 🛠️ How to Validate Webhook Cryptographic Signatures

## 1. Objetivo & Sintomas de Erro
- Webhooks legítimos de parceiros estão a ser rejeitados com `401 Unauthorized` ou `403 Forbidden`.
- Mensagem de erro: `Signature verification failed: computed hash does not match header`.
- Risco de aceitar payloads falsificados se a validação estiver desativada ou com bypass.

---

## 2. Causas Comuns de Falha na Verificação
1. **JSON Body Re-serializado**: Fazer `json.loads()` e depois `json.dumps()` antes de calcular o hash altera a ordem das chaves e espaços em branco, invalidando a assinatura. O hash deve ser calculado estritamente sobre os **bytes brutos originais** (`request.body()`).
2. **Charset / Encoding**: Usar encoding diferente de `utf-8` na chave secreta.
3. **Prefixo do Header**: Esquecer de remover prefixos como `sha256=` ou `v1=` do valor do cabeçalho.

---

## 3. Procedimento de Diagnóstico e Implementação Segura

```python
import hmac
import hashlib
from fastapi import Request, HTTPException

async def validate_raw_webhook_payload(request: Request, webhook_secret: str) -> bytes:
    # 1. Obter os bytes brutos antes de qualquer parsing
    raw_payload: bytes = await request.body()
    
    # 2. Obter o cabeçalho de assinatura
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not signature_header:
        raise HTTPException(status_code=401, detail="Cabeçalho de assinatura ausente.")

    # 3. Tratar prefixo
    expected_hex = signature_header.split("=")[-1].strip()

    # 4. Calcular HMAC-SHA256
    secret_bytes = webhook_secret.encode("utf-8")
    mac = hmac.new(secret_bytes, msg=raw_payload, digestmod=hashlib.sha256)
    computed_hex = mac.hexdigest()

    # 5. Comparação em tempo constante
    if not hmac.compare_digest(expected_hex, computed_hex):
        raise HTTPException(status_code=401, detail="Assinatura HMAC inválida.")

    return raw_payload
```

---

## 4. Teste de Validação Unitária

```python
def test_hmac_verification_logic():
    secret = "segredo_super_seguro_123"
    payload = b'{"event": "mission.created", "mission_id": "102"}'
    
    # Gerar assinatura válida
    valid_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    
    # Testar que payload idêntico passa
    assert hmac.compare_digest(valid_sig, hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest())
    
    # Testar que payload com 1 espaço a mais falha
    tampered_payload = b'{"event": "mission.created",  "mission_id": "102"}'
    assert not hmac.compare_digest(valid_sig, hmac.new(secret.encode("utf-8"), tampered_payload, hashlib.sha256).hexdigest())
```

---

## 5. Related Concepts
- [[HMAC Signature Verification for Webhooks]]
- [[Credential Sanitization and Secret Masking]]
- [[FastAPI and WebSocket Lifecycle Management]]

---

## 6. Sources
- *RFC 2104 - HMAC Specification*: https://datatracker.ietf.org/doc/html/rfc2104
- *GitHub Webhook Documentation*: https://docs.github.com/en/webhooks

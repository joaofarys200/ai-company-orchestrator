---
type: concept
domain: security
difficulty: intermediate
tags:
  - security
  - cryptography
  - hmac
  - webhooks
  - authentication
status: verified
---

# 🔐 HMAC Signature Verification for Webhooks

## 1. Definição & O Problema de Autenticidade
Em integrações HTTP via Webhooks (como Stripe, GitHub, Slack ou parceiros de API), o servidor anfitrião recebe requisições em endpoints públicos. Sem validação criptográfica, atacantes podem forjar eventos maliciosos (ex: fingir um webhook de pagamento aprovado ou trigger de deploy).

O **HMAC (Hash-based Message Authentication Code - RFC 2104)** combina uma chave secreta partilhada com o payload bruto da mensagem através de uma função de hash criptográfica (ex: SHA-256), garantindo simultaneamente:
- **Autenticidade da Origem** (apenas quem possui o segredo pode gerar a assinatura).
- **Integridade dos Dados** (qualquer byte alterado no payload invalida a assinatura).

```
Remetente (GitHub / Stripe):
[ Raw Payload Bytes ] + [ Shared Secret ] ---> [ HMAC-SHA256 ] ---> Header: `X-Signature-SHA256: 7a8b...`
                                                                                    |
                                                                                    v (HTTP POST)
Receptor (JARVIS OS Server):                                                        |
[ Raw Payload Bytes ] + [ Shared Secret ] ---> [ HMAC-SHA256 ] ---> Compara com Header via `compare_digest`
                                                                          |
                                                      +-------------------+-------------------+
                                                      |                                       |
                                                  (Match!)                                (Mismatch!)
                                                      v                                       v
                                              [ 200 OK: Processa ]                   [ 401 Unauthorized ]
```

---

## 2. Vulnerabilidade Crítica: Ataques de Tempo (Timing Attacks)
Se a comparação entre a assinatura recebida e a assinatura calculada for feita com o operador padrão `if signature_a == signature_b:`, a execução termina no primeiro byte discrepante.

Atacantes conseguem medir as variações de microssegundos no tempo de resposta do servidor para deduzir a assinatura byte a byte.
**Regra Inviolável**: Utilizar SEMPRE funções de comparação em tempo constante (`hmac.compare_digest` em Python ou `crypto.timingSafeEqual` em Node.js).

---

## 3. Implementação Canónica em Python / FastAPI

```python
import hmac
import hashlib
import time
from fastapi import Request, HTTPException, status

async def verify_github_webhook_signature(request: Request, secret: str) -> bytes:
    # 1. Ler o payload bruto (raw bytes) ANTES de qualquer parse JSON
    raw_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")
    
    if not signature_header or not signature_header.startswith("sha256="):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Assinatura HMAC ausente ou malformada."
        )

    expected_signature = signature_header.replace("sha256=", "").strip()
    
    # 2. Calcular o hash HMAC-SHA256 localmente
    computed_signature = hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).hexdigest()

    # 3. Comparação em tempo constante para mitigar timing attacks
    if not hmac.compare_digest(expected_signature, computed_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Assinatura HMAC inválida."
        )

    return raw_body
```

---

## 4. Mitigação de Ataques de Repetição (Replay Attacks)
Além do hash, webhooks robustos (como Stripe) incluem um timestamp no cabeçalho (ex: `t=1710000000`).
Se $|T_{\text{atual}} - T_{\text{header}}| > 300\text{ segundos}$, a requisição deve ser sumariamente rejeitada mesmo que a assinatura seja válida.

---

## 5. Related Concepts
- [[How to Validate Webhook Cryptographic Signatures]]
- [[Credential Sanitization and Secret Masking]]
- [[FastAPI and WebSocket Lifecycle Management]]
- [[Tratado_Completo_de_Ciberseguranca_Redes_e_DevSecOps]]

---

## 6. Sources
- *RFC 2104 - HMAC: Keyed-Hashing for Message Authentication*: https://datatracker.ietf.org/doc/html/rfc2104
- *GitHub Webhook Security Best Practices*: https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
- *Stripe Webhook Signatures Verification*: https://stripe.com/docs/webhooks/signatures

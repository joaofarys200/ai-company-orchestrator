---
type: comparison
domain: security
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
difficulty: advanced
tags:
  - security
  - cryptography
  - comparison
  - hmac
  - asymmetric-signatures
  - rsa
  - ed25519
prerequisites:
  - "[[HMAC Signature Verification for Webhooks]]"
  - "[[Replay Attack Prevention with Nonce and Timestamp Windows]]"
related:
  - "[[Zero Trust Architecture and Microsegmentation]]"
  - "[[Credential Sanitization and Secret Masking]]"
used_by:
  - "[[JARVIS Economic Engine and Metric Verification]]"
failure_modes:
  - "[[Lesson - Accidental Secret Leaks in Telemetry Broadcast]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: RFC 2104 - HMAC - Keyed-Hashing for Message Authentication
    type: PRIMARY_SOURCE
    url: https://datatracker.ietf.org/doc/html/rfc2104
  - title: RFC 8032 - Edwards-Curve Digital Signature Algorithm (Ed25519)
    type: PRIMARY_SOURCE
    url: https://datatracker.ietf.org/doc/html/rfc8032
---

# ⚖️ Comparison: HMAC Signatures vs Asymmetric Public-Key Signatures

## 1. Tabela Comparativa de Primitivas Criptográficas

| Dimensão | HMAC Simétrico (HMAC-SHA256) | Assinatura Assimétrica (Ed25519 / RSA) |
|---|---|---|
| **Chaves Necessárias** | **Uma chave secreta compartilhada ($K$)** | Par de chaves: Privada ($SK$) e Pública ($PK$) |
| **Custo Computacional** | **Ultrarrápido ($< 1\mu\text{s}$)** | Mais lento ($50 - 500\mu\text{s}$) |
| **Não-Repúdio (Non-Repudiation)** | Não (Ambas as partes conhecem a chave e podem forjar) | **Sim (Apenas o detentor da chave privada pode assinar)** |
| **Distribuição de Chaves** | Requer canal seguro para compartilhar o segredo | **Chave pública pode ser distribuída abertamente** |

---

## 2. Decisão de Engenharia para o JARVIS

### When should JARVIS choose HMAC?
- Para validação de webhooks de pagamento de terceiros (Stripe, LemonSqueezy, GitHub) e tokens de comunicação interna entre microsserviços locais.

### When should JARVIS choose Asymmetric Signatures (Ed25519)?
- Para emissão de certificados de proveniência de código e artefatos de build que serão verificados publicamente por clientes externos sem expor a chave de assinatura.

### What failure mode does each introduce?
- **HMAC**: Vazamento da chave compartilhada compromete todo o sistema de validação bidirecional.
- **Asymmetric**: Complexidade no gerenciamento de revogação de chaves públicas e consumo adicional de CPU.

---

## 3. Related Concepts
- [[HMAC Signature Verification for Webhooks]]
- [[Replay Attack Prevention with Nonce and Timestamp Windows]]
- [[Zero Trust Architecture and Microsegmentation]]

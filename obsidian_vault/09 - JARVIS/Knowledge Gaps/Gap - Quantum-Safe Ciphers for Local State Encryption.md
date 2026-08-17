---
type: concept
domain: jarvis
status: knowledge_gap
source_type: UNVERIFIED
confidence: low
freshness: evolving
difficulty: advanced
tags:
  - knowledge-gap
  - jarvis
  - security
  - post-quantum
  - ml-kem
  - cryptography
prerequisites:
  - "[[Replay Attack Prevention with Nonce and Timestamp Windows]]"
  - "[[HMAC Signature Verification for Webhooks]]"
related:
  - "[[Zero Trust Architecture and Microsegmentation]]"
used_by:
  - "[[JARVIS Security Sandbox and Policy Engine]]"
failure_modes:
  - "[[Lesson - Accidental Secret Leaks in Telemetry Broadcast]]"
implementation:
  - "[[JARVIS SQLite WAL Checkpoint Daemon and PRAGMA Tuning]]"
sources:
  - title: NIST Post-Quantum Cryptography Standards (FIPS 203 ML-KEM, FIPS 204 ML-DSA)
    type: PRIMARY_SOURCE
    url: https://csrc.nist.gov/projects/post-quantum-cryptography
---

# â“ Gap - Quantum-Safe Ciphers for Local State Encryption

## Question
*Qual o overhead de performance de substituir o AES-256-GCM e HMAC-SHA256 atuais por algoritmos de criptografia pÃ³s-quÃ¢ntica padronizados pelo NIST (como ML-KEM / Kyber e ML-DSA / Dilithium) na encriptaÃ§Ã£o de banco de dados SQLite local em tempo real?*

---

## Why It Matters
Garante que credenciais de longo prazo, dados proprietÃ¡rios de usuÃ¡rios e checkpoints de missÃµes persistidos no cofre local permaneÃ§am protegidos contra ataques do tipo *Harvest Now, Decrypt Later* (HNDL).

---

## What Is Known
- O NIST padronizou oficialmente o FIPS 203 (ML-KEM) e FIPS 204 (ML-DSA) em 2024.
- As chaves pÃºblicas e assinaturas sÃ£o significativamente maiores (ex: 2.4 KB para ML-DSA vs 64 bytes para Ed25519).

---

## What Is Unknown
- A degradaÃ§Ã£o de throughput de I/O de disco em SQLite quando blocos WAL sÃ£o cifrados com primitivas pÃ³s-quÃ¢nticas em CPUs sem extensÃµes AVX-512 dedicadas.

---

## Evidence Required
Benchmark comparativo medindo latÃªncia de gravaÃ§Ã£o de checkpoints em `database.py` com `liboqs` / `pqcrypto` em Python vs AES-256 nativo.

---

## Potential Sources
- NIST CSRC Post-Quantum Cryptography Standardization.
- Open Quantum Safe (OQS) Project.

---

## Implementation Status
`status: "knowledge_gap"` (Planejado para avaliaÃ§Ã£o futura).

---

## Priority
`P3 (Pesquisa de Longo Prazo)`


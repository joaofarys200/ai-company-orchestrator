---
type: concept
domain: security
difficulty: advanced
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
tags:
  - security
  - cryptography
  - post-quantum
  - ml-kem
  - ml-dsa
  - nist
---

# 🛡️ Post-Quantum Cryptography Migration - Hybrid ML-KEM (FIPS 203) and ML-DSA (FIPS 204)

## 1. Modelo de Ameaça HNDL e Padronização NIST
Computadores quânticos criptograficamente relevantes (CRQCs) quebram RSA, Diffie-Hellman e curvas elípticas (`ECDH`/`ECDSA`/`Ed25519`) em tempo polinomial via o **Algoritmo de Shor**, enquanto o **Algoritmo de Grover** reduz apenas quadradicamente a segurança simétrica (tornando `AES-256` e `SHA-384/512` resistentes).

A urgência imediata decorre de ataques **Harvest Now, Decrypt Later (HNDL)**: tráfego TLS ou backups cifrados capturados hoje podem ser decifrados anos mais tarde se a troca de chaves assétrica inicial não for resistente a quântica.

---

## 2. Primitivas Padronizadas pelo NIST (Redes Euclidianas / Module-LWE)

| Norma NIST | Algoritmo (Origem) | Finalidade | Tamanhos (Nível 3: `ML-KEM-768` / `ML-DSA-65`) |
|---|---|---|---|
| **FIPS 203** | **ML-KEM** (CRYSTALS-Kyber) | Encapsulamento de chave (KEM / TLS) | PubKey: `1,184 B` · Ciphertext: `1,088 B` · Segredo: `32 B` |
| **FIPS 204** | **ML-DSA** (CRYSTALS-Dilithium) | Assinaturas digitais de código/tokens | PubKey: `1,952 B` · Assinatura: `3,309 B` |
| **FIPS 205** | **SLH-DSA** (SPHINCS+) | Assinaturas *stateless* baseadas em hash | PubKey: `32–64 B` · Assinatura: `7.8–49.8 KB` (conservador) |

---

## 3. Padrão de Transição Híbrida e Encriptação Local
Para evitar regressão caso uma suposição algébrica de reticulados sofra criptoanálise clássica inesperada, a migração de produção utiliza **KEMs Híbridos** (`X25519MLKEM768` em TLS 1.3):

$$K_{\text{session}} = \text{HKDF-SHA256}\left(Z_{\text{X25519}} \,\|\, Z_{\text{ML-KEM-768}}, \text{context}\right)$$

A sessão permanece segura desde que **pelo menos um** dos dois problemas matemáticos (ECDLP ou Module-LWE) permaneça intratável. Para bases de dados locais (como SQLite WAL), o caminho simétrico de blocos mantém `AES-256-GCM` (acelerado por AES-NI), aplicando `ML-KEM-768` apenas no *key wrapping* da Data Encryption Key (DEK), mantendo o overhead de I/O de disco virtualmente nulo.

---

## 4. Conceitos Relacionados & Fontes
- [[Gap - Quantum-Safe Ciphers for Local State Encryption]]
- [[Comparison - HMAC Signatures vs Asymmetric Public-Key Signatures]]
- [[TCP Handshake and BBR Congestion Control]]
- [[Zero-Knowledge Proofs and zk-SNARKs in Autonomous Verification]]
- **Fontes**: NIST FIPS 203 (*Module-Lattice-Based Key-Encapsulation Mechanism Standard*, 2024); NIST FIPS 204 (*ML-DSA*, 2024); NIST FIPS 205 (*SLH-DSA*, 2024); IETF Draft `draft-ietf-tls-ecdhe-mlkem`.


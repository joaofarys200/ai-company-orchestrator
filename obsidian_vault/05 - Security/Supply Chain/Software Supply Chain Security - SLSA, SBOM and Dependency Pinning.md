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
  - supply-chain
  - slsa
  - sbom
  - dependencies
  - devsecops
---

# 🔗 Software Supply Chain Security - SLSA, SBOM and Dependency Pinning

## 1. Superfície de Ataque na Cadeia de Suprimentos de Software
Agentes autónomos de código que instalam pacotes sugeridos por LLMs enfrentam quatro vetores críticos de ataque:
1. **Slopsquatting / Typosquatting**: Um atacante regista no PyPI/npm o nome exato de um pacote frequentemente alucinado por LLMs ou com erro tipográfico de 1 carácter.
2. **Dependency Confusion**: Um pacote interno privado `@corp/utils` sem namespace reservado é substituído por uma versão pública superior num registo externo.
3. **Malicious Install Hooks**: Scripts `setup.py` / `postinstall` executam código arbitrário no momento da instalação antes mesmo de qualquer `import`.
4. **Comprometimento Transitivo**: Uma sub-dependência de 3.º nível sofre *account takeover* e publica uma patch version maliciosa dentro de intervalos semânticos abertos (`^1.2.0` ou `>=2.0`).

---

## 2. Controles Defensivos Obrigatórios e Níveis SLSA

| Controle | Implementação Técnica | Risco Mitigado |
|---|---|---|
| **Autorização Explícita por Projeto** | Gate de aprovação humana + instalação restrita ao `venv`/`node_modules` local | Impede poluição global do sistema operativo e instalações silenciosas |
| **Hash-Locked Pinning** | `pip install --require-hashes -r requirements.lock` / `npm ci --ignore-scripts` | Garante integridade bit-a-bit (SHA-256) e bloqueia hooks `postinstall` |
| **SBOM (CycloneDX / SPDX)** | Inventário legível por máquina de toda a árvore transitiva + scan OSV | Resposta imediata a CVEs zero-day (ex.: `pip-audit`, `osv-scanner`) |
| **SLSA Build Provenance (L2–L3)** | Atestados assinados (`Sigstore` / `cosign`) ligando binário ao commit/CI exato | Impede adulteração entre repositório fonte e registo de pacotes |

---

## 3. Regra Operacional para Agentes Autónomos
Nenhum agente deve invocar `pip install` ou `npm install` globalmente, com privilégios administrativos, ou com intervalos flutuantes sem lockfile auditado e consentimento explícito do operador para o projeto alvo.

---

## 4. Conceitos Relacionados & Fontes
- [[Threat Modeling for Autonomous Coding Agents]]
- [[Least-Privilege Process Sandboxing and Execution Jail]]
- [[JARVIS ProjectBuilder Dependency Resolution Engine]]
- [[JARVIS Phase 24-25 Durable Mission Lifecycle, Leases and Authorization]]
- [[Runbook - How to Audit and Quarantine Untrusted Third-Party Dependencies]]
- **Fontes**: SLSA Specification v1.0 (`slsa.dev`); NIST SP 800-218 (*SSDF*); CycloneDX / SPDX SBOM Standards; Birsan (2021), *Dependency Confusion*.


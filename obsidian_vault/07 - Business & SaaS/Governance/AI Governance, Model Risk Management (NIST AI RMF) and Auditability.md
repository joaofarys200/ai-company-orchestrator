---
type: concept
domain: business-economics
difficulty: advanced
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
tags:
  - business
  - governance
  - nist-ai-rmf
  - iso-42001
  - compliance
  - auditability
---

# ⚖️ AI Governance, Model Risk Management (NIST AI RMF) and Auditability

## 1. Enquadramento Operacional de Governação de IA
Para além da conformidade legal estrita (EU AI Act e RGPD/GDPR), organizações que operam agentes autónomos necessitam de **Model Risk Management (MRM)** contínuo para prevenir danos financeiros, fugas de dados, ações não autorizadas e deriva silenciosa de comportamento (*model drift*). O padrão internacional de referência é o **NIST AI Risk Management Framework (AI RMF 1.0)** aliado à norma **ISO/IEC 42001**.

---

## 2. As 4 Funções Nucleares do NIST AI RMF Aplicadas a Agentes

| Função NIST | Objetivo Operacional | Implementação Concreta em Sistemas Agênticos |
|---|---|---|
| **1. GOVERN** | Políticas, papéis, limites de autonomia e responsabilização | Matriz explícita de *Bounded Autonomy* (ações livres vs ações que exigem aprovação humana) |
| **2. MAP** | Mapeamento de contexto, impacto, dados sensíveis e dependências | Inventário de modelos (locais e externos), classificação de risco por ferramenta e ameaças STRIDE |
| **3. MEASURE** | Avaliação quantitativa pré e pós-deploy | Suites de regressão, métricas de fidelidade/alucinação, calibração de juízes e monitorização de drift |
| **4. MANAGE** | Resposta a incidentes, contenção e recuperação | *Kill switches* imediatos, *circuit breakers*, rollback transacional e auditoria pós-incidente |

---

## 3. Requisitos de Trilho de Auditoria Imutável (*Decision Provenance*)
Para que qualquer ação autónoma seja defensável perante auditoria técnica ou regulatória, cada efeito externo deve registar um envelope de proveniência contendo:
1. **Identidade & Versão**: `mission_id`, `model_provider`, `model_version`, hash do template/política ativa.
2. **Base Epistêmica**: IDs das fontes/documentos consultados (separando `OBSERVED` de `INFERRED`) sem gravar segredos em texto limpo.
3. **Cadeia de Autorização**: Registo criptográfico/timestamp de quem aprovou permissões elevadas (ex.: instalação de dependências, escrita fora da sandbox ou transações externas) e resultado observável da verificação final.

---

## 4. Conceitos Relacionados & Fontes
- [[EU AI Act and GDPR Compliance for Autonomous Agent Systems]]
- [[Economic Evidence Provenance - Real vs Synthetic vs Unverified]]
- [[Threat Modeling for Autonomous Coding Agents]]
- [[Credential Sanitization and Secret Masking]]
- [[JARVIS Phase 24-25 Durable Mission Lifecycle, Leases and Authorization]]
- **Fontes**: NIST (2023), *Artificial Intelligence Risk Management Framework (AI RMF 1.0)* & *NIST AI 600-1 (Generative AI Profile, 2024)*; ISO/IEC 42001:2023 (*AI Management System*).


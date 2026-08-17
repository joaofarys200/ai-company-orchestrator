---
type: concept
domain: business-economics
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: evolving
difficulty: advanced
tags:
  - business
  - legal
  - eu-ai-act
  - gdpr
  - compliance
  - governance
  - provenance
prerequisites:
  - "[[Economic Evidence Provenance - Real vs Synthetic vs Unverified]]"
related:
  - "[[Threat Modeling for Autonomous Coding Agents]]"
  - "[[Structured Logging and Distributed Trace Context]]"
used_by:
  - "[[JARVIS Economic Engine and Metric Verification]]"
failure_modes:
  - "[[Lesson - Accidental Secret Leaks in Telemetry Broadcast]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: EU Artificial Intelligence Act (Regulation (EU) 2024/1689 of the European Parliament and of the Council)
    type: PRIMARY_SOURCE
    url: https://eur-lex.europa.eu/eli/reg/2024/1689/oj
  - title: General Data Protection Regulation (Regulation (EU) 2016/679 - GDPR)
    type: PRIMARY_SOURCE
    url: https://gdpr-info.eu/
---

# ⚖️ EU AI Act and GDPR Compliance for Autonomous Agent Systems

## 1. Pergunta Central
> *Quais requisitos legais e de governança técnica o Regulamento de Inteligência Artificial da UE (EU AI Act) e o GDPR impõem a agentes de código autónomos que geram aplicações, tomam decisões económicas e processam dados de utilizadores?*

---

## 2. As Obrigações Chave do EU AI Act para Agentes Autónomos

1. **Rastreabilidade e Logs de Auditoria Contínua (Artigo 12)**:
   - Todo agente que executa ações com impacto no mundo real deve persistir logs imutáveis registando: prompt original, versão do modelo, temperatura, saídas intermediárias de ferramentas e aprovação humana.
2. **Supervisão Humana / Human-in-the-Loop (Artigo 14)**:
   - A arquitetura deve fornecer mecanismos de paragem de emergência (*Kill Switch* / `PAUSED_WAITING_HUMAN`) e revisão obrigatória antes de operações irreversíveis (ex: cobrança financeira, exclusão em massa).
3. **Transparência e Marca d'Água de Dados Sintéticos (Artigo 50)**:
   - Todo conteúdo e código gerado por IA deve ser explicitamente etiquetado como tal nos metadados.

---

## 3. Conformidade com o GDPR no Contexto de Memória de Agentes
- **Direito ao Esquecimento (Artigo 17)**: Vetores de embeddings e bancos de memória RAG devem suportar exclusão pontual de dados pessoais (*Selective Deletion*) sem necessidade de retreinar o modelo ou reconstruir o cofre inteiro.

---

## 4. Related Concepts
- [[Economic Evidence Provenance - Real vs Synthetic vs Unverified]]
- [[Threat Modeling for Autonomous Coding Agents]]
- [[Structured Logging and Distributed Trace Context]]

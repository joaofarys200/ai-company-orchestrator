# 5. EPISTEMIC GROUNDING VALIDATION

**Status:** IMPLEMENTED | INTEGRATED | UNIT_TESTED | INTEGRATION_TESTED | INDEPENDENTLY_VALIDATED  
**Data:** 2026-11-05  

---

## 5.1 Eliminação da Promoção Cega de Frontmatter

Na versão anterior, quando uma nota não possuía cabeçalho YAML, eram atribuídos automaticamente os campos:
`status: verified`, `confidence: high`.
Este comportamento violava o princípio do rigor epistémico.

**Correção Implementada:**
Quando uma nota não tem frontmatter, o motor atribui valores estritamente conservadores:
```yaml
---
type: atomic_note
domain: <pasta_da_nota>
status: needs_review
provenance: UNDECLARED
confidence: unknown
tags:
  - <pasta>
---
```
Nenhum valor adicionado automaticamente tem autorização para elevar a confiança epistémica de uma nota.

---

## 5.2 Níveis Epistémicos Rigorosamente Distintos

1. `VERIFIED_PRIMARY_SOURCE`: Normas formais (RFC, FIPS, ISO) com marcadores textuais e citações `[E#]`.
2. `GROUNDED_STUDY_SYNTHESIS`: Sínteses multimédia geradas por modelo ancoradas em diapositivos/aulas.
3. `INTERNAL_ENGINEERING_SPEC`: Especificações internas do JARVIS OS (nunca promovidas a fontes primárias).
4. `EXTRACTIVE_TRANSCRIPTION`: Transcrições puras de áudio ou OCR de diapositivos.
5. `UNVERIFIED_HEURISTIC`: Conteúdo sem proveniência ou notas heurísticas em análise.

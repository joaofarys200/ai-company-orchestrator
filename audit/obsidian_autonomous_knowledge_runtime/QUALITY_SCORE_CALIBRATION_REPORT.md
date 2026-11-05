# 8. QUALITY SCORE CALIBRATION REPORT

**Status:** IMPLEMENTED | INTEGRATED | UNIT_TESTED | INTEGRATION_TESTED | INDEPENDENTLY_VALIDATED  
**Data:** 2026-11-05  

---

## 8.1 Transparência da Fórmula Heurística

As pontuações determinísticas são agora expressamente declaradas como `HEURISTIC` e a fórmula de cálculo é divulgada no payload:
`Pontuação = (Qualidade Estrutural * 0.25) + (Qualidade de Conhecimento * 0.30) + (Qualidade de Evidência * 0.25) + (Qualidade do Grafo * 0.20)`

- **Isolamento de Código:** Os blocos de código Markdown (` ``` `) são completamente removidos antes de contar parágrafos ou densidade textual de prosa.
- **Parsing de Datas:** As datas são processadas através de formatos ISO e normalizadas para contagem de dias reais transcorridos. Quando ausentes ou inválidas, a frescura é reportada como `UNKNOWN`.
- **Deteção de Quase-Duplicados:** Algoritmo SequenceMatcher aplicado a títulos e assinaturas do cofre para sinalizar potenciais fragmentações de conhecimento.

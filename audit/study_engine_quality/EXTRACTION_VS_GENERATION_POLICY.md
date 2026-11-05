# JARVIS OS — Extraction vs. Generation Policy (`EXTRACTION_VS_GENERATION_POLICY.md`)

**Data:** 2026-11-04  
**Objetivo:** Garantir transparência absoluta entre síntese gerada pelo modelo (`qwen3.5:9b`), extração determinística local e indisponibilidade de geração.

---

## 1. Taxonomia Oficial de Modos (`generation_mode`)

Cada documento e cada artefacto individual (`artifact_modes`) declara obrigatoriamente um dos 4 estados contratuais:

| `generation_mode` | Significado Técnico | Quando Ocorre | Apresentação na Interface (Frontend) |
|---|---|---|---|
| `LLM_GROUNDED` | Síntese produzida pelo `qwen3.5:9b` (Ollama local), validada estruturalmente e ancorada nas unidades de evidência do documento (`grounding_ratio >= 0.5`). | Execução normal com Ollama ativo e validação aprovada. | Badge Esmeralda: **`IA Fundamentada • qwen3.5:9b`** + métricas de latência, tokens/s e ratio de fundamentação. |
| `PARTIAL` | Parte dos artefactos foi gerada e validada pelo `qwen3.5:9b`, mas pelo menos uma secção exigiu complemento extrativo determinístico ou teve avisos de validação. | Resposta parcial do modelo ou documento com secções heterogéneas. | Badge Âmbar: **`Síntese Parcial • qwen3.5:9b`** + lista de avisos de validação. |
| `EXTRACTIVE_GROUNDED` | Conteúdo extraído deterministicamente das frases e secções mais salientes do documento, **sem intervenção generativa do LLM**. | Quando o Ollama/`qwen3.5:9b` está offline, excede timeout ou em execução rápida de testes determinísticos. | Badge Ciano: **`Extração Local sem Modelo`** + aviso explícito das funcionalidades generativas indisponíveis (`unavailable_generative_features`). |
| `UNAVAILABLE` | Não foi possível extrair texto, fala ou OCR legível do ficheiro de origem. | Áudio silencioso sem fala, vídeo vazio ou ficheiro corrompido sem texto. | Badge Vermelho: **`Indisponível — Sem Conteúdo Extraível`** + motivo técnico detalhado. |

---

## 2. Regras de Honestidade no Fallback Extrativo (`EXTRACTIVE_GROUNDED`)

Quando o sistema opera em modo `EXTRACTIVE_GROUNDED`:
1. **Proibição de Simular Síntese do Modelo:** O sistema nunca rotula excertos extraídos como `LLM_GROUNDED` nem preenche `generation_telemetry.status` como `"COMPLETED"`.
2. **Declaração de Funcionalidades Generativas Indisponíveis:** O campo `unavailable_generative_features` lista explicitamente `["AbstractGenerativeSynthesis", "InferentialArgumentMapping", "GenerativeConceptualSynthesis"]`.
3. **Mapa de Argumentos Honesto:** Se o texto não contiver marcadores argumentativos explícitos (`detect_argumentative_structure()`), `structure.is_argumentative` é `False` e `structure.argumentative_limitation` informa claramente o utilizador em vez de fabricar teses ou conclusões artificiais.
4. **Rastreabilidade Mantida:** Mesmo em modo extrativo, todas as frases selecionadas por `rank_salient_sentences()` conservam `source_refs` apontando para os `evidence_id`s exatos (página/parágrafo/slide/timestamp).


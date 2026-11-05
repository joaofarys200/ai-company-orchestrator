# JARVIS OS — Grounded Generation Design (`GROUNDED_GENERATION_DESIGN.md`)

**Data:** 2026-11-04  
**Modelo de Síntese:** Local Ollama `qwen3.5:9b` (`services/study_ai_engine.py` + `services/model_execution_service.py`)

---

## 1. Princípio Arquitetural Central

> **Nenhuma afirmação factual pode ser apresentada como resultado do documento sem uma base identificável nas unidades de evidência do documento de origem.**

---

## 2. Pipeline de Geração Fundamentada (`qwen3.5:9b`)

1. **Construção de Unidades de Evidência (`build_document_evidence_units`):**
   - Cada parágrafo, slide, elemento de texto, segmento de transcrição ou slide OCR recebe um identificador único `evidence_id` (ex.: `doc_abc:p2:par1` ou `doc_vid:t12000-18500:ASR_SPEECH:1`).
2. **Preparação do Dossier de Evidências (`prepare_evidence_dossier`):**
   - O documento não é truncado cegamente aos primeiros caracteres.
   - `prepare_evidence_dossier()` seleciona unidades de evidência estratificadas ao longo de **todas** as secções do documento, formatando cada bloco como:
     ```text
     [doc_abc:p1:par1] (Secção: Introdução | Pág. 1)
     Texto integral do excerto...
     ```
3. **Execução Observável no `qwen3.5:9b` (`invoke_study_llm_observable`):**
   - Invoca `ModelExecutionService.execute("study_synthesis", ...)` estritamente com `provider="ollama"` e `model="qwen3.5:9b"`.
   - Regista `StudyLLMTelemetry` por operação e documento:
     - `provider`: `"ollama"`
     - `model`: `"qwen3.5:9b"`
     - `generation_id`: UUID único da geração (`gen_...`)
     - `input_tokens`, `output_tokens`, `ttft_ms`, `total_ms`, `tokens_per_sec`, `context_used`
     - `status`: `"COMPLETED"` | `"PARTIAL"` | `"MODEL_UNAVAILABLE"` | `"PARSE_FAILED"` | `"CANCELLED"`
     - `validation_errors`: lista detalhada de falhas de esquema ou grounding
     - `attempts`: número real de tentativas efetuadas
4. **Higiene e Validação Pós-Geração:**
   - **Remoção de Raciocínio Interno:** `strip_think_tags()` remove todos os blocos `<think>...</think>` ou marcadores órfãos antes do parsing e em todos os campos de saída.
   - **Verificação de Evidências (`match_claim_to_evidence_units` / `match_claim_evidence_ids`):**
     - Cada afirmação gerada pelo modelo é validada contra as unidades de evidência reais do documento através de sobreposição léxico-semântica ponderada (excluindo stopwords) e verificação de `source_refs` devolvidos pelo modelo.
     - Se uma afirmação não tiver suporte suficiente nas unidades de evidência (`status == "UNCONFIRMED"`), `match_claim_evidence_ids(..., allow_fallback=False)` devolve `[]` e a afirmação não recebe citação falsa.

---

## 3. Especificação dos 7 Artefactos de Estudo Melhorados

| Artefacto | Requisitos Implementados | Rastreabilidade (`source_refs`) |
|---|---|---|
| **A. Quick Summary** | Identifica tema central, objetivo do conteúdo, conceitos essenciais e conclusões principais específicas do documento. | `summaries.quick_refs` mapeado para `evidence_id`s reais. |
| **B. Study Summary** | Organizado pelas secções reais do documento (`heading`, `content`, `key_points`), preservando a estrutura original sem misturar secções. | Cada secção contém `source_refs: List[str]`. |
| **C. Detailed Summary** | Aprofunda definições, mecanismos técnicos, relações entre conceitos, pressupostos e exemplos presentes na fonte (nunca é cópia do Quick Summary). | Cada bloco contém `source_refs: List[str]`. |
| **D. Exam Summary** | Destaca `high_yield_concepts` (conceito + definição/processo), `formulas_and_rules` e `likely_questions` com `answer_guide` estritamente baseados na matéria presente. | Cada conceito e pergunta contém `source_refs: List[str]`. |
| **E. Cornell Notes** | Produz `cue_column` (conceito/pergunta + explicação fundamentada), `detailed_notes` estruturadas por secção e `executive_summary` final. | Cada item de `cue_column` possui `source_refs: List[str]`. |
| **F. Argument Map** | Representa `problem`/`thesis`, `method`, `results`, `limitations`, `conclusion` e `relations`. Deteta via `detect_argumentative_structure()` se o documento é descritivo (`is_argumentative: false`) e declara `argumentative_limitation` em vez de inventar premissas. | Cada nó possui `status` (`OBSERVED`/`INFERRED`/`UNKNOWN`) e `source_refs`. |
| **G. Flashcards & Quizzes** | Gerados a partir de conceitos high-yield, secções reais, glossário e factos verificados, com distratores plausíveis do próprio domínio e zero perguntas genéricas pré-fabricadas. | Cada questão e flashcard possui `source_ids` com `evidence_id`s reais. |


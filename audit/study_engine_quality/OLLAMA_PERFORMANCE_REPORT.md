# JARVIS OS — Ollama & `qwen3.5:9b` Performance Report (`OLLAMA_PERFORMANCE_REPORT.md`)

**Data:** 2026-11-04  
**Modelo Local:** `qwen3.5:9b` via Ollama (`http://127.0.0.1:11434`)  
**Configuração Ativa:** `OLLAMA_MODEL=qwen3.5:9b`, `OLLAMA_NUM_CTX=16384`, `OLLAMA_KEEP_ALIVE=60m`, `thinking=False` (`OutputFormat.JSON`)

---

## 1. Diagnóstico Forense das Causas de Lentidão e Falhas Antes da Otimização

Na primeira medição de referência sobre o pipeline não otimizado (`task-2553`), foram identificadas 3 causas concretas:

1. **Excesso de Tokens de Saída num Único Pedido JSON (`max_output_tokens=2800` com esquema verboso):**
   - O prompt pedia simultaneamente `detailed_summary` e `cornell_notes.detailed_notes` (duplicando o texto explicativo), além de 11 chaves obrigatórias em `structure` (obrigando o modelo a emitir repetidamente `"Não especificado diretamente no documento."`).
   - Resultado antes da otimização: no vídeo `doc_vid_f76259cd5c4e`, o `qwen3.5:9b` gerou exatamente `2800` tokens em `173.96s` (`16.1 tok/s`) e truncou a resposta a meio de uma string (`Unterminated string starting at...`), falhando na validação JSON e disparando uma 2.ª tentativa desnecessária.
2. **Dossier de Entrada Excessivamente Longo (`max_chars=7500`, ~3000–4000 tokens):**
   - Aumentava o tempo de *prompt eval* (prefill) e penalizava a atenção em cada token gerado.
3. **Cold Start da VRAM + Timeout Rígido de 95s:**
   - Na primeira chamada a frio (`doc_a3b336f4295d`), o tempo de carregamento do modelo em VRAM somado ao prefill de 2903 tokens e geração longa atingiu `100.08s`, causando `ReadTimeout`.

---

## 2. Otimizações Implementadas em `services/study_ai_engine.py`

1. **Dossier de Evidências Estratificado e Compacto (`max_chars=4500`):**
   - `prepare_evidence_dossier()` seleciona de forma estratificada as unidades de evidência de todas as secções do documento em ~2200–2800 tokens de entrada (redução de ~30% no prefill sem perda de cobertura estrutural).
2. **Eliminação de Redundância no Esquema JSON da Chamada Única:**
   - O modelo gera apenas os campos de alto valor cognitivo (`quick_summary`, `study_sections`, `detailed_summary`, `exam_summary`, `cornell_notes.executive_summary` + `cue_column`, e os 5 eixos nucleares de `structure`).
   - `_normalize_llm_bundle()` reutiliza automaticamente `detailed_summary` para compor as notas detalhadas de Cornell quando omitidas e preenche deterministicamente chaves `UNKNOWN` não especificadas na fonte.
3. **Orçamento de Saída Seguro (`max_output_tokens=3600`, `timeout_seconds=135.0`):**
   - Como a resposta compacta consome apenas **1344 a 1630 tokens**, o limite de `3600` tokens garante uma margem superior a 2x, eliminando por completo erros de JSON truncado (`Unterminated string`) logo na 1.ª tentativa (`attempts: 1`).

---

## 3. Comparação de Desempenho Antes vs. Depois (`qwen3.5:9b`)

| Métrica | Antes da Otimização (`doc_a3b336f4295d` PDF) | Depois da Otimização (`doc_a3b336f4295d` PDF) | Antes da Otimização (`doc_vid_f76259cd5c4e` Vídeo) | Depois da Otimização (`doc_vid_f76259cd5c4e` Vídeo) |
|---|---|---|---|---|
| **Estado Final (`status`)** | `TIMEOUT` (`ReadTimeout`) | **`COMPLETED`** | `FAILED_VALIDATION` (JSON truncado) | **`COMPLETED`** |
| **Modo de Geração** | Fallback `EXTRACTIVE_GROUNDED` | **`LLM_GROUNDED`** | Fallback `EXTRACTIVE_GROUNDED` | **`LLM_GROUNDED` (6/6 artefactos)** |
| **Tentativas (`attempts`)** | 1 (abortada aos 100s) | **1** | 2 (ambas truncadas) | **1** |
| **Tokens de Entrada (`input_tokens`)** | 2903 | **2281** (-21.4%) | 4000 | **2826** (-29.4%) |
| **Tokens de Saída (`output_tokens`)** | 0 (timeout) | **1344** | 2800 (truncado) | **1630** (-41.8%) |
| **Velocidade (`tokens_per_sec`)** | 0.0 tok/s | **20.32 tok/s** | 16.10 tok/s | **32.61 tok/s** (+102.5%) |
| **Tempo Total (`total_ms`)** | 100,084.4 ms | **66,145.3 ms** (-33.9%) | 173,957.9 ms | **49,986.0 ms** (**-71.3% / 3.5x mais rápido**) |
| **Grounding Ratio** | N/A | **82.4%** (14 claims verificadas) | N/A | **95.2%** (20 claims verificadas) |


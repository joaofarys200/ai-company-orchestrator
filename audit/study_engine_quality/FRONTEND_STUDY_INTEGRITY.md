# JARVIS OS — Frontend Study Integrity & Spatial Board HUD (`FRONTEND_STUDY_INTEGRITY.md`)

**Data:** 2026-11-04  
**Ficheiros Auditados e Atualizados:**
- [`frontend/src/features/study/StudySummaryView.tsx`](file:///c:/Users/joaor/Desktop/JarvisOS/frontend/src/features/study/StudySummaryView.tsx)
- [`frontend/src/features/study/StudyNotesView.tsx`](file:///c:/Users/joaor/Desktop/JarvisOS/frontend/src/features/study/StudyNotesView.tsx)
- [`frontend/src/features/study/StudyContainer.tsx`](file:///c:/Users/joaor/Desktop/JarvisOS/frontend/src/features/study/StudyContainer.tsx)
- [`frontend/src/features/board/SpatialBoard.tsx`](file:///c:/Users/joaor/Desktop/JarvisOS/frontend/src/features/board/SpatialBoard.tsx)
- [`frontend/src/features/workspace/HologramCore.tsx`](file:///c:/Users/joaor/Desktop/JarvisOS/frontend/src/features/workspace/HologramCore.tsx)
- [`frontend/src/context/WebSocketContext.tsx`](file:///c:/Users/joaor/Desktop/JarvisOS/frontend/src/context/WebSocketContext.tsx)
- [`frontend/src/protocol/websocket.ts`](file:///c:/Users/joaor/Desktop/JarvisOS/frontend/src/protocol/websocket.ts)

---

## 1. Transparência e Estados Visuais na Interface de Estudos

1. **Distinção Clara entre Modos de Geração (`StudySummaryView.tsx` & `StudyNotesView.tsx`):**
   - **`LLM_GROUNDED`:** Exibe badge `IA Fundamentada • qwen3.5:9b`, velocidade em `tok/s`, latência total (`total_ms`), TTFT (`ttft_ms`) e percentagem de afirmações ancoradas (`grounding_ratio`).
   - **`PARTIAL`:** Exibe badge `Síntese Parcial • qwen3.5:9b` com indicação de que partes foram complementadas por extração determinística.
   - **`EXTRACTIVE_GROUNDED`:** Exibe badge `Extração Local sem Modelo` e banner informativo listando `unavailable_generative_features` e a causa técnica registada em `generation_telemetry.status`.
   - **`UNAVAILABLE`:** Exibe estado de erro claro quando o documento não possui texto ou fala extraível.

2. **Rastreabilidade de Evidências (`source_refs`):**
   - Cada secção do Study Summary, cada bloco do Detailed Summary, cada conceito/pergunta do Exam Summary e cada entrada da coluna de tópicos das Cornell Notes exibe chips clicáveis/visuais com as coordenadas de origem (`doc_id:p2:par1`, `slide3:el2`, `t12000-18000`).

3. **Avisos de Limitação Argumentativa e Multimodal:**
   - Quando `structure.is_argumentative === false`, o separador de Mapa de Argumentos apresenta o banner de `argumentative_limitation` explicando que o material é predominantemente descritivo/expositivo.
   - Quando `metadata.audio_analysis_incomplete === true` ou `transcription_warning` está presente, a vista exibe o alerta de transcrição/OCR multimodal.

4. **Progresso Detalhado e Cancelamento em Tempo Real (`study_cancel_generation`):**
   - `WebSocketContext.tsx` expõe `studyPipelineStage` (`UPLOADED`, `EXTRACTING`, `TRANSCRIBING`, `ANALYZING_VIDEO`, `GENERATING`, `VALIDATING`, `READY`, `CANCELLED`, `FAILED`) e `cancelStudyGeneration(documentId)`.
   - `StudySummaryView.tsx` inclui botão **Cancelar** ativo durante a síntese, enviando `{ type: "study_cancel_generation", document_id, request_id }`.

---

## 2. Rose-Style Spatial Board HUD (`SpatialBoard.tsx` + `HologramCore.tsx`)

Inspirado no conceito de interface modular espacial:
- **Estado de Repouso:** `HologramCore.tsx` permanece centrado no ecrã (`360x360`).
- **Estado Spatial Board Ativo:** Quando o utilizador pede por voz/texto ou clica no botão **Quadro Espacial**:
  - *"Jarvis, abre o quadro do tema X que estudei"* → abre o quadro espacial do documento de estudo correspondente (resumo executivo, métricas de cobertura/evidências, vídeo/media da aula, notas Cornell e ligações Obsidian).
  - *"Jarvis, abre o quadro do projeto dina"* → abre o quadro espacial do projeto com ficheiros, estatísticas LOC e estado de execução.
  - *"Jarvis, abre o quadro do vault"* / *"abre o quadro do Sentinel"* → monta os cartões respetivos.
  - *"Maximiza o gráfico / cartão X"* → foca o cartão no centro (`focusedCardId`) e reduz a opacidade do fundo.
  - *"Podes descansar"* → fecha o quadro e desliza o orbe holográfico suavemente do canto inferior direito (`docked`) de volta para o centro (`layoutId="jarvis-hologram-orb"`).

---

## 3. Verificação de Compilação Frontend

- Comando executado: `npm --prefix frontend run build` (`tsc -b && vite build`)
- Resultado: **PASSOU com 0 erros de TypeScript** (`✓ built in 3.96s`).


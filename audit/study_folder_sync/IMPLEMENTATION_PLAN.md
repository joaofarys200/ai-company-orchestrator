# PLANO DE IMPLEMENTAÇÃO — ÁREA DE ESTUDO DO JARVIS OS
## MATERIAIS DE ESTUDO BASEADOS EM PASTAS & SINCRONIZAÇÃO AUTOMÁTICA

### 1. OBJETIVO & CONTEXTO
Evoluir a área de Estudo existente do JARVIS OS (`services/study_service.py`, `backend/websocket/handlers/study.py`, `frontend/src/features/study/*`) para suportar:
- Organização unificada de materiais por disciplina ou curso (reutilizando e estendendo `StudyCollection`).
- Associação de pastas locais nativas a cursos (`dialog.showOpenDialog` em Electron com fallback Web).
- Sincronização automática contínua (monitorização de sistema de ficheiros + varrimento de reconciliação para ficheiros novos, modificados, renomeados ou eliminados, incluindo alterações offline enquanto o JARVIS esteve desligado).
- Processamento real dos materiais através dos pipelines existentes (PyMuPDF para PDFs, python-docx para DOCX, VideoIntelligenceService com áudio, Whisper e keyframes para vídeos).
- Consulta contextual e RAG restrito ao curso com citações rigorosas.
- Interface enriquecida na área de Estudo respeitando o design system existente.
- Garantia absoluta de preservação de ficheiros: o JARVIS NUNCA elimina ficheiros originais no disco ao desvincular pastas ou gerir o catálogo de estudo.

### 2. AUDITORIA DA ARQUITETURA EXISTENTE
- **Modelos:**
  - `StudyDocument`: Metadados, seções, parágrafos, argument map, glossário, progresso, hash SHA-256.
  - `StudyCollection`: `collection_id`, `name`, `subject`, `document_ids`, `created_at`.
- **Pipelines:**
  - `ingest_document`: Processa PDF, DOCX, TXT, MD, Áudio, Imagens.
  - `ingest_video`: Pipeline multimodal completo (áudio WAV, transcrição Whisper com timestamps granulares, keyframes, slides, capítulos).
- **Persistência:**
  - JSON atómico (`documents.json`, `collections.json`, `quizzes.json`, etc.) com deteção de alterações externas via `mtime` e `size`.
- **Electron:**
  - `main.js` + `preload.js` com contexto isolado. Necessita de endpoints para diálogo nativo de pasta (`select-folder`) e abertura no SO (`open-path`).

### 3. FASES DE EXECUÇÃO
1. **Fase 1 — Serviço de Sincronização & Modelos:**
   - Criar `services/folder_sync_service.py` com validação de caminhos seguros, varrimento de reconciliação, monitorização em background com debounce, deteção de alterações e suporte a recuperação pós-reinício.
   - Atualizar `StudyCollection` e `StudyDocument` em `services/study_service.py` com `linked_folders`, `sync_preferences`, `source_origin`, `linked_folder_path`, `rel_path` e `sync_status`.
   - Adicionar métodos de curso/pasta: `link_folder_to_collection`, `unlink_folder_from_collection`, `sync_collection_folder`, `ask_course`.
2. **Fase 2 — WebSocket & Electron IPC:**
   - Adicionar handlers WebSocket em `backend/websocket/handlers/study.py`: `study_link_folder`, `study_unlink_folder`, `study_sync_folder`, `study_ask_course`, etc.
   - Adicionar `ipcMain.handle('select-folder')` e `ipcMain.handle('open-path')` em `main.js`.
   - Expor métodos seguros em `preload.js`.
3. **Fase 3 — Interface de Utilizador (Frontend):**
   - Atualizar `types.ts` com tipos de pastas vinculadas e metadados de sincronização.
   - Atualizar `StudyLibraryView.tsx` e `StudyContainer.tsx`:
     - Barra de disciplinas/cursos.
     - Painel de pastas vinculadas (caminho, status de sincronização, botão sincronizar, botão desvincular, botão abrir pasta).
     - Badges de origem nos cartões (`📁 Pasta: ...` vs `☁️ Upload`).
     - Badges de estado de processamento (`Pronto`, `A Processar`, `Falha`, `Não Suportado`).
     - Diálogo para vincular pasta (nativo Electron com fallback modal Web).
   - Atualizar `WebSocketContext.tsx` para ligar as mensagens WebSocket.
4. **Fase 4 — Testes End-to-End (Cenários A a N):**
   - Desenvolver `tests/test_study_folder_sync.py` cobrindo rigorosamente todos os 14 cenários exigidos no caderno de encargos.
   - Executar regressão total (`test_study_reading_experience.py`).
5. **Fase 5 — Documentação e Auditoria:**
   - Elaborar os 6 relatórios exigidos em `audit/study_folder_sync/`.

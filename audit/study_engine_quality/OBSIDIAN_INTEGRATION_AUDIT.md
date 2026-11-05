# JARVIS OS — Obsidian Integration Audit (`OBSIDIAN_INTEGRATION_AUDIT.md`)

**Data:** 2026-11-04  
**Ficheiros Auditados:**
- [`services/study_service.py::save_to_knowledge_vault`](file:///c:/Users/joaor/Desktop/JarvisOS/services/study_service.py)
- [`services/lecture_synthesizer.py::CornellNoteSynthesizer`](file:///c:/Users/joaor/Desktop/JarvisOS/services/lecture_synthesizer.py)
- [`backend/websocket/handlers/study.py::save_to_knowledge`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/websocket/handlers/study.py)

---

## 1. Preservação das Notas Existentes no Cofre Obsidian

- As **24 notas de conhecimento de fronteira** previamente criadas no Obsidian Vault foram **100% preservadas** e não sofreram qualquer modificação destrutiva ou reescrita em lote.
- A sincronização de pastas e exportação de notas respeita integralmente a regra não-destrutiva: nenhum ficheiro do utilizador é apagado.

---

## 2. Frontmatter YAML com Proveniência Completa e Estado de Validação Honesto

Ao executar `study_save_to_vault` / `save_to_knowledge_vault()`, cada nota exportada para `obsidian_vault/10 - Lectures/<Disciplina>/<YYYY-MM-DD> - <Título>.md` inclui obrigatoriamente o seguinte cabeçalho YAML:

```yaml
---
type: study_note
domain: academic
status: llm_grounded_verified # ou llm_partial_verified / extractive_unverified
source_document_id: "doc_..."
source_title: "Título Real do Documento"
synthesis_type: "cornell_study_note"
generated_at: "2026-11-04T01:17:45.123456"
model_used: "qwen3.5:9b" # ou deterministic_extractor se fallback extrativo
generation_mode: "LLM_GROUNDED" # ou PARTIAL / EXTRACTIVE_GROUNDED
validation_status: "PASSED" # ou PARTIAL_VALIDATED / EXTRACTIVE_FALLBACK
subject: "Disciplina"
date: "2026-11-04"
sources:
  - doc_...
source_refs:
  - "doc_...:p1:par1"
  - "doc_...:p2:par3"
tags:
  - study-vault
  - knowledge-retrieval
  - disciplina
---
```

### Regra de Integridade do Campo `status`
- `status: llm_grounded_verified` **só** é atribuído quando `generation_mode == "LLM_GROUNDED"` e `validation_status == "PASSED"`.
- Se a nota tiver sido gerada em modo extrativo (`EXTRACTIVE_GROUNDED`), recebe `status: extractive_unverified` e `model_used: "deterministic_extractor"`, nunca enganando o utilizador quanto à sua origem.

---

## 3. Proteção contra Sobrescrita Silenciosa (`.archive/`)

- Sempre que o ficheiro de destino `dest_file` já existe em `obsidian_vault/10 - Lectures/<Disciplina>/`, `save_to_knowledge_vault()` copia automaticamente a versão anterior para:
  `obsidian_vault/10 - Lectures/<Disciplina>/.archive/<nome_da_nota>_<YYYYMMDD_HHMMSS_ffffff>.md`
  antes de gravar a nova versão.
- Validado pelo teste automático `test_23_save_to_vault_preserves_provenance_and_archives_existing_file` em [`tests/test_study_engine_forensic_qa.py`](file:///c:/Users/joaor/Desktop/JarvisOS/tests/test_study_engine_forensic_qa.py).


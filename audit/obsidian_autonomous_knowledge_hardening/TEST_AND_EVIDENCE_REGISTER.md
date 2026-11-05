# REGISTO DE TESTES E EVIDÊNCIAS DE EXECUÇÃO
## JARVIS OS — Verificação Automatizada e Caracterização

### 1. Resumo Executivo das Suítes de Teste
Todas as suítes de teste de integração, segurança, contratos WebSocket, motor de estudo e avaliação de grafos de conhecimento foram executadas no ambiente real.

| Suíte de Testes | Ficheiro de Teste | Itens | Duração | Código de Saída | Status |
|---|---|---|---|---|---|
| **Segurança e Hardening de Conhecimento** | `tests/test_obsidian_knowledge_hardening.py` | 12 | 0.29s | 0 | **PASS (100%)** |
| **Motor de Grafo e Avaliação de Notas** | `tests/test_obsidian_graph_engine.py` | 6 | 0.29s | 0 | **PASS (100%)** |
| **Contrato do Dispatcher WebSocket** | `tests/test_websocket_dispatcher_contract.py` | 9 | 1.73s | 0 | **PASS (100%)** |
| **Caracterização do Servidor WebSocket** | `tests/test_server_websocket_characterization.py` | 8 | 4.98s | 0 | **PASS (100%)** |
| **QA Forense do Motor de Estudo & PDF** | `tests/test_study_engine_forensic_qa.py` | 25 | 0.91s | 0 | **PASS (100%)** |
| **Compilação do Frontend (TypeScript + Vite)** | `npm run build --prefix frontend` | 3.506 módulos | 4.14s | 0 | **PASS (100%)** |

**Total de Testes Unitários e de Integração:** **60 testes executados, 60 aprovados (0 falhas).**

---

### 2. Detalhe dos Testes de Hardening (`test_obsidian_knowledge_hardening.py`)

1. `test_path_traversal_note_path_rejected`: Valida que sequências `../` no caminho de notas disparam `ObsidianSecurityError`.
2. `test_absolute_path_outside_vault_rejected`: Valida que caminhos absolutos como `C:/Windows/System32/...` são travados imediatamente.
3. `test_null_byte_in_path_rejected`: Valida rejeição de caminhos com bytes nulos (`\x00`).
4. `test_snapshot_path_must_be_inside_history_dir`: Valida que caminhos de snapshot fora do diretório `.history` são rejeitados.
5. `test_snapshot_file_identity_mismatch_rejected_on_rollback`: Valida que restaurar um snapshot de `Nota A` sobre `Nota B` é barrado por incompatibilidade de identidade nos metadados.
6. `test_snapshot_high_resolution_collision_free`: Cria snapshots repetidos no mesmo milissegundo e valida que os nomes e IDs de snapshot são 100% únicos com carimbos em nanossegundos e UUIDs.
7. `test_atomic_write_and_optimistic_concurrency`: Valida que a escrita atómica CAS detecta conflitos concorrentes se o hash original tiver mudado.
8. `test_quality_scoring_four_categories_no_fixed_scores`: Valida que o auditor de qualidade expõe as 4 categorias factuais (`structural`, `knowledge`, `evidence`, `graph`) sem notas pré-fabricadas.
9. `test_jarvis_internal_never_promoted_to_verified_primary_source`: Comprova que notas com `source_type: JARVIS_INTERNAL` recebem estritamente `INTERNAL_ENGINEERING_SPEC` (score 65-75).
10. `test_markdown_aware_link_parser_ignores_code_fences`: Comprova que código contendo `Callable[[], Awaitable[T]]` não gera falsos links quebrados.
11. `test_queue_worker_pause_and_resume_controls`: Valida que `pause_queue_worker()` e `resume_queue_worker()` persistem no disco e impedem execuções quando pausado.
12. `test_bridge_note_generation_validates_existing_sources`: Valida que `generate_bridge_note` requer a existência factual de ambas as notas de origem no cofre.

---

### 3. Evidência do Build de Produção do Frontend
Comando executado:
```
npm run build --prefix frontend
```
Saída verificada:
```
✓ 3506 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                                          4.03 kB │ gzip:   0.97 kB
dist/assets/index-DooPX-GI.js                        1,004.40 kB │ gzip: 293.99 kB
✓ built in 4.14s
```
Zero erros de compilação TypeScript, zero falhas de lint e zero advertências bloqueantes.

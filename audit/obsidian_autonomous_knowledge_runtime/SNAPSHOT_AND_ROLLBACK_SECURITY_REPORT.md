# 2. SNAPSHOT AND ROLLBACK SECURITY REPORT

**Status:** IMPLEMENTED | INTEGRATED | UNIT_TESTED | INTEGRATION_TESTED | INDEPENDENTLY_VALIDATED  
**Data:** 2026-11-05  
**Componente:** `services/obsidian_graph_engine.py` (`create_note_backup_snapshot`, `rollback_note`)

---

## 2.1 Protocolo de Escrita Atómica em 2 Fases (Two-Stage Atomic Snapshot)

A criação de snapshots históricos foi reforçada para garantir impossibilidade de snapshots órfãos ou corrompidos:
1. **Escrita Temporária do Markdown:** Ficheiro temporário `.tmp_{snapshot_filename}.tmp` escrito em `.history/`.
2. **Validação de Hash e Comprimento de Bytes:** Leitura imediata do ficheiro temporário para aferir integridade SHA-256 e tamanho exato de bytes.
3. **Escrita Temporária do Sidecar Metadata:** Geração do sidecar `.tmp_{snapshot_filename}.json.tmp` com esquema estruturado v2.
4. **Validação de Metadados:** Verificação da validade do JSON e integridade dos campos `schema_version == 2`, `content_sha256`, `note_rel_path`.
5. **Publicação Atómica Simultânea:** Renomeação atómica `os.replace` do Markdown e do JSON para os nomes finais canónicos.

---

## 2.2 Validação Restritiva de Rollback e Rejeição Adversarial

A função `rollback_note` impõe 9 verificações de segurança obrigatórias:
- **Contenção no Cofre:** O alvo tem de resolver estritamente dentro de `vault_root`.
- **Contenção no Diretório Histórico:** O snapshot tem de resolver estritamente dentro de `vault_root/.history`.
- **Existência Obrigatória de Sidecar:** Snapshots sem `.json` sidecar associado são rejeitados com `ObsidianSecurityError`.
- **Validação de Esquema:** Snapshots com `schema_version != 2` são rejeitados.
- **Correspondência Exata de Identidade:** O campo `note_rel_path` nos metadados tem de ser idêntico ao caminho relativo da nota alvo (rejeição de rollback cruzado entre notas).
- **Verificação de Hash do Conteúdo:** O hash SHA-256 dos bytes do snapshot tem de coincidir exatamente com `content_sha256`.
- **Verificação de Tamanho:** O comprimento em bytes tem de coincidir com `content_bytes_len`.
- **Snapshot Pré-Rollback:** Antes da restauração, é criado um snapshot de segurança da nota atual.
- **Substituição Atómica e Verificação:** Substituição atómica via ficheiro temporário e verificação do hash resultante.

Testado com êxito contra 5 cenários adversariais em `tests/test_obsidian_knowledge_hardening.py`.

# RELATÓRIO DE AUDITORIA DE SEGURANÇA E CONTENÇÃO DE CAMINHOS
## JARVIS OS — Obsidian Knowledge Engine Hardening

### 1. Resumo Executivo
Esta auditoria avalia e valida o endurecimento de segurança aplicado aos métodos de manipulação de ficheiros do `ObsidianGraphEngine` e aos respetivos canais WebSocket. O objetivo prioritário consistiu em eliminar vulnerabilidades de *Path Traversal*, garantir que nenhum ficheiro fora dos limites estritos do `obsidian_vault` ou do histórico `.history` possa ser lido, escrito, sobrescrito ou restaurado, e estabelecer garantias transacionais de escrita atómica CAS (*Compare-And-Swap*).

---

### 2. Contenção Estrita de Caminhos (Path Containment)

#### 2.1 Resolução e Validação de Notas (`_resolve_contained_note_path`)
O método `_resolve_contained_note_path(rel_path)` substitui qualquer resolução permissiva anterior pelas seguintes regras determinísticas:
1. **Rejeição de Nulos e Bytes Nulos:** Caminhos vazios, nulos ou contendo `\x00` disparam imediatamente `ObsidianSecurityError`.
2. **Rejeição Explícita de Traversal:** A presença de segmentos `..` nos componentes do caminho resulta em rejeição sumária (`ObsidianSecurityError`).
3. **Resolução de Títulos Canónicos e Relativos:** Consulta os índices canónicos `canonical_notes` e `canonical_rel_paths` gerados pelo cofre.
4. **Verificação de Fronteira Canónica:** Todo o caminho resolvido (`Path.resolve()`) é submetido a `_is_path_contained(resolved, self.vault_root)`. Se `resolved` não partilhar a raiz de `vault_root` ou se escapar ao diretório raiz, é rejeitado.
5. **Rejeição de Ficheiros Fora do Vault:** Tentativas de passar caminhos absolutos como `C:\Windows\System32\...` ou caminhos relativos maliciosos são travadas antes de qualquer I/O de disco.

#### 2.2 Resolução e Validação de Snapshots (`_resolve_contained_snapshot_path`)
Para operações de restauro e rollback, o método `_resolve_contained_snapshot_path(backup_target)` impõe:
1. O snapshot tem de estar estritamente contido no diretório autorizado `obsidian_vault/.history` (ou `history_dir` injetado).
2. Não são aceites ficheiros arbitrários do sistema como fontes de snapshot.
3. Se um caminho tentar aceder a `obsidian_vault/01 - AI/Nota.md` como se fosse um snapshot para sobrescrever outra nota, o motor rejeita a operação com `ObsidianSecurityError`.

---

### 3. Escrita Atómica CAS e Proteção contra Concorrência

#### 3.1 Mecanismo de Escrita Atómica (`atomic_write_note`)
A escrita em notas Markdown adota um fluxo transacional à prova de falhas:
1. **Cálculo de Hash Inicial:** Obtém o SHA-256 do ficheiro de destino em disco através de leitura crua de bytes (`read_bytes()`).
2. **Verificação Otimista CAS:** Se `expected_sha256` for fornecido pelo cliente e divergir do hash atual em disco, dispara imediatamente `ObsidianConcurrencyError`, abortando a escrita sem modificar o estado.
3. **Criação de Snapshot Verificado:** Gera previamente um snapshot completo e os seus metadados `.json`.
4. **Escrita em Ficheiro Temporário Oculto:** O novo conteúdo é escrito num ficheiro temporário (`.tmp_<uuid>.tmp`) localizado no mesmo diretório da nota de destino, garantindo que a operação de renomeação ocorra dentro do mesmo sistema de ficheiros.
5. **Re-verificação CAS:** Revalida o hash do ficheiro original antes da troca. Se tiver sido modificado em paralelo por outro processo, o ficheiro temporário é apagado e a transação é cancelada.
6. **Substituição Atómica:** Executa `os.replace(temp_file, target_path)`, uma operação atómica garantida pelo SO.

---

### 4. Snapshots Históricos com Identidade e Metadados Sidecar

#### 4.1 Nomenclatura Livre de Colisões
Os snapshots deixaram de usar carimbos temporais de baixa resolução (segundos), adotando a seguinte assinatura:
```
snap_{rel_path_hash}_{timestamp_ns}_{content_sha256[:8]}_{uuid[:8]}.md
```
Adicionalmente, cada snapshot é acompanhado por um ficheiro sidecar `.json` com `schema_version: 2`:
```json
{
  "snapshot_id": "snap_f1b2c3d4",
  "snapshot_filename": "snap_...",
  "snapshot_path": "C:/Users/.../obsidian_vault/.history/snap_...",
  "schema_version": 2,
  "note_rel_path": "01 - AI/Model Context Protocol.md",
  "note_stem": "Model Context Protocol",
  "rel_path_hash": "a1b2c3d4",
  "timestamp_ns": 1730768400000000000,
  "timestamp_iso": "2026-11-05T01:00:00.000000",
  "content_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "content_bytes_len": 4096
}
```

#### 4.2 Verificação de Identidade no Rollback
No método `rollback_note(target_note, backup_path_or_id)`:
- O motor lê o ficheiro de metadados correspondente ao snapshot.
- Compara `meta["note_rel_path"]` com a nota que está a ser restaurada.
- Se um operador tentar restaurar um snapshot de `Nota A` sobre `Nota B`, a operação é imediatamente rejeitada com `ObsidianSecurityError: Snapshot pertence a 'Nota A', não a 'Nota B'. Rollback rejeitado.`
- O hash SHA-256 do ficheiro de snapshot é validado antes da substituição.

---

### 5. Blindagem dos Handlers WebSocket

No ficheiro `backend/websocket/handlers/knowledge.py`:
- Os handlers `enrich_note` e `rollback_note` capturam explicitamente:
  - `ObsidianSecurityError` -> Retorna `{ "success": false, "code": "SECURITY_VIOLATION", "error": "..." }`
  - `ObsidianNotFoundError` -> Retorna `{ "success": false, "code": "NOT_FOUND", "error": "..." }`
  - `ObsidianConcurrencyError` -> Retorna `{ "success": false, "code": "CONCURRENCY_CONFLICT", "error": "..." }`
- Nenhuma exceção de segurança escapa como falha não tratada de servidor.
- O cliente nunca pode fazer com que o servidor copie um ficheiro arbitrário para o cofre.

---

### 6. Matriz de Testes Adversariais Realizados

| Cenário de Teste | Entrada Adversarial | Comportamento Esperado | Resultado |
|---|---|---|---|
| Traversal com `../` em nota | `../../Windows/System32/drivers/etc/hosts` | `ObsidianSecurityError` | **PASS (0.01s)** |
| Traversal absoluto fora do Vault | `C:/Windows/win.ini` | `ObsidianSecurityError` | **PASS (0.01s)** |
| Traversal com bytes nulos | `01 - AI/Note.md\x00.exe` | `ObsidianSecurityError` | **PASS (0.01s)** |
| Rollback com fonte fora do `.history` | `01 - AI/OtherNote.md` | `ObsidianSecurityError` | **PASS (0.01s)** |
| Rollback de snapshot cruzado | Snapshot de `Nota A` aplicado em `Nota B` | `ObsidianSecurityError` | **PASS (0.01s)** |
| Escrita com hash CAS desatualizado | `expected_sha256 = stale_hash` | `ObsidianConcurrencyError` | **PASS (0.01s)** |

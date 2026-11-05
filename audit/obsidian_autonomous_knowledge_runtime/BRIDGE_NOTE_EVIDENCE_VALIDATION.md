# 9. BRIDGE NOTE EVIDENCE VALIDATION

**Status:** IMPLEMENTED | INTEGRATED | UNIT_TESTED | INTEGRATION_TESTED | INDEPENDENTLY_VALIDATED  
**Data:** 2026-11-05  

---

## 9.1 Validação de Notas de Origem e Evidência

A função `generate_bridge_note` foi reformulada para eliminar referências fabricadas:
- **Verificação de Existência:** As notas de origem A e B têm de existir no cofre canónico, sob pena de exceção `ObsidianNotFoundError`.
- **Eliminação de RFCs Fictícios:** O fallback pré-fabricado `["RFC_MCP_2024", "JARVIS_SWARM_V2"]` foi eliminado. Se nenhuma referência de evidência for fornecida, a evidência é explicitamente ancorada nas próprias notas de origem (`SOURCE_NOTE:<origem>`).
- **Escrita Segura com Snapshot:** Se uma Bridge Note já existir, a atualização é efetuada através de `create_note_backup_snapshot` e `atomic_write_note`.

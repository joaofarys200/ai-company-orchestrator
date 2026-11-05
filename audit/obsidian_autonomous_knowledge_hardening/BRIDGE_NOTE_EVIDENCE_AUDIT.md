# AUDITORIA DE EVIDÊNCIA DE BRIDGE NOTES
## JARVIS OS — Síntese Transversal e Relações Teoria-Código

### 1. Conceito e Função das Bridge Notes
Uma **Bridge Note** é um artefacto de síntese transversal que une conceitos teóricos/académicos (provenientes de artigos científicos ou normas primárias) à sua respetiva materialização na arquitetura de código do JARVIS OS. 

As Bridge Notes previnem a desconexão entre o repositório de engenharia e a base de conhecimento Obsidian, garantindo que qualquer decisão de design no código disponha de fundamentação bibliográfica e conceptual imediata.

---

### 2. Validação Estrita de Existência Prévia
O método `generate_bridge_note` foi endurecido com a verificação de contenção e integridade:
1. `_resolve_contained_note_path(source_note_a)` deve validar que a primeira nota fonte existe no cofre.
2. `_resolve_contained_note_path(source_note_b)` deve validar que a segunda nota fonte existe no cofre.
3. Se qualquer uma das notas não existir no cofre canónico, a geração é abortada com `ObsidianNotFoundError`, impedindo a criação de pontes fictícias para nós inexistentes.
4. O caminho de saída é estritamente contido em `obsidian_vault/09 - JARVIS/Bridge Notes/`.

---

### 3. Evidência no Cofre Real

No cofre real, a nota de síntese transversal demonstrativa encontra-se persistida em:
`obsidian_vault/09 - JARVIS/Bridge Notes/Bridge - Model Context Protocol & Hierarchical Agent Governance.md`

#### 3.1 Estrutura e Frontmatter
```markdown
---
type: bridge_note
domain: jarvis-architecture
status: verified
provenance: JARVIS_INTERNAL
confidence: high
source_notes:
  - "Model Context Protocol (MCP) and Capability Discovery Architecture"
  - "JARVIS Autonomous Agent Hierarchy"
tags:
  - bridge-note
  - cross-synthesis
  - architecture
---

# 🌉 Model Context Protocol & Hierarchical Agent Governance (Bridge Note)

Esta nota de síntese transversal estabelece a ponte conceptual e arquitetural entre o fundamento teórico de [[Model Context Protocol (MCP) and Capability Discovery Architecture]] e a realização técnica em [[JARVIS Autonomous Agent Hierarchy]].

---

## 📌 Conceitos Partilhados
- **Capability Discovery & Invocação Remota**
- **Isolamento de Contexto & Menor Privilégio**
- **Arbitragem de Turnos & Backpressure**

---

## 🏛️ Fundamento Teórico & Académico
O protocolo aberto MCP padroniza a exposição de ferramentas e capacidades contextuais para LLMs, garantindo que modelos não necessitam de código ad-hoc para aceder a sistemas de ficheiros e bases de dados.

---

## ⚙️ Implementação Prática no JARVIS OS
No JARVIS OS, o `SwarmOrchestrator` implementa discovery dinâmico de ferramentas via MCP, permitindo ao Coder e Tester invocar competências sem quebrar a separação de responsabilidades.

---

## 🔗 Relações no Grafo
- **Fundamento Teórico:** [[Model Context Protocol (MCP) and Capability Discovery Architecture]]
- **Arquitetura & Código:** [[JARVIS Autonomous Agent Hierarchy]]
- **MOCs Relacionados:** [[00 - Knowledge Index]], [[JARVIS Index]]
```

---

### 4. Validação em Suite de Testes

O teste `test_bridge_note_generation_validates_existing_sources` em `tests/test_obsidian_knowledge_hardening.py`:
1. Tenta criar uma bridge note referenciando notas existentes ➔ Conclui com sucesso, cria o ficheiro Markdown, atualiza o índice e preserva os links.
2. Tenta criar uma bridge note referenciando uma nota fictícia ➔ Dispara `ObsidianNotFoundError`, comprovando a rejeição de fontes sem evidência real no cofre.

# RELATÓRIO DE PRECISÃO DE LIGAÇÕES SEMÂNTICAS
## JARVIS OS — Resolução Ontológica em Camadas e Relações Tipadas

### 1. Objetivo
Evitar a proliferação de ligações fracas ou acidentais ("link density por palavras comuns") e estabelecer um grafo de alta precisão semântica através de um motor de resolução em camadas e 7 tipos explícitos de relação ontológica.

---

### 2. Motor de Resolução Semântica em Camadas

O método `resolve_concept_link(candidate_text, source_note_stem, context_window)` processa as ligações por ordem estrita de confiança decrescente:

1. **Camada 1: Correspondência Exata de Título Canónico (Confiança: 0.98)**
   - Valida o título normalizado da nota em `canonical_notes`.
   - Método: `CANONICAL_TITLE_MATCH`.
2. **Camada 2: Correspondência de Alias YAML (Confiança: 0.95)**
   - Valida sinónimos oficiais declarados no frontmatter YAML das notas (`aliases`).
   - Método: `YAML_ALIAS_MATCH`.
3. **Camada 3: Registo de Sinónimos Técnicos / Ontologia Curada (Confiança: 0.92)**
   - Mapeia acrónimos técnicos para notas especializadas (ex.: `pqc` para *Post-Quantum Cryptography*, `mcp` para *Model Context Protocol*).
   - Método: `CURATED_SYNONYM_RESOLVER`.
4. **Camada 4: Alinhamento de Domínio por Tags Partilhadas (Confiança: 0.85)**
   - Mapeia conceitos que partilham domínios e taxonomias formais (`#domain`).
   - Método: `DOMAIN_TAG_ALIGNMENT`.
5. **Camada 5: Resolução Contextual LLM com `qwen3.5:9b` (Confiança: 0.80)**
   - Acionada apenas quando as camadas determinísticas não conseguem resolver a relação e existe ambiguidade técnica relevante.

---

### 3. Eliminação de Associações Ontológicas Inadequadas

Durante a auditoria forense do registo ontológico, foram identificados e corrigidos mapeamentos inadequados:
1. **Remoção de TOGAF -> API Contracts:** O acrónimo TOGAF (*The Open Group Architecture Framework*) estava mapeado para `API Contract Evolution...`. A relação foi removida; TOGAF é um framework de arquitetura empresarial com nota dedicada, enquanto contratos de API são especificações de software.
2. **Remoção de SIUM -> TOGAF:** SIUM (*Sistema de Informação e Urbanismo Municipal*) foi desassociado de TOGAF.
3. **Eliminação de Falsos Positivos de Código:** Expressões de código de linguagens formais (como tipos genéricos em blocos de código) foram completamente excluídas da extração de links.

---

### 4. Os 7 Tipos de Relações Ontológicas Suportadas

Cada relação inferida pelo `_infer_relationship_type` e justificada por `_get_relationship_justification` expressa formalmente a natureza semântica da conexão:

| Tipo de Relação | Semântica | Padrões de Gatilho no Contexto |
|---|---|---|
| **`PREREQUISITE_OF`** | A nota alvo constitui base fundamental indispensável para a fonte. | *pré-requisito, prerequisite, fundamento, base, depende de* |
| **`EXTENDS`** | A nota fonte expande, aprofunda ou generaliza a nota alvo. | *estende, extends, expande, aprofunda* |
| **`SUPPORTS`** | A nota fonte fornece provas, evidências ou validações empíricas da nota alvo. | *suporta, supports, comprova, demonstra* |
| **`CONTRASTS_WITH`** | A nota fonte estabelece diferenças, trade-offs ou opostos em relação ao alvo. | *contrasta, diferença, versus, vs, contrasts, diverge* |
| **`APPLIES_TO`** | A nota fonte implementa ou utiliza na prática o conceito da nota alvo. | *aplica, applies, implementa, utilizado em* |
| **`EXAMPLE_OF`** | A nota fonte é um caso de uso, instância ou padrão representativo da nota alvo. | *exemplo, caso de uso, instância, example* |
| **`RELATED_TO`** | Associação conceptual direta entre tópicos afins de um mesmo domínio. | *Fallback contextual semântico* |

---

### 5. Formato das Relações Injetadas no Markdown

Quando uma nota é enriquecida, as relações são formatadas numa secção clara e rastreável, sem duplicar backlinks já geridos pelo Obsidian:
```markdown
---

## 🔗 Grafo de Conhecimento & Relações Tipadas
- **PREREQUISITE_OF** ➔ [[Model Context Protocol (MCP) and Capability Discovery Architecture]] — *'Agent Systems' estabelece os fundamentos necessários para 'Model Context Protocol (MCP) and Capability Discovery Architecture'*
- **SUPPORTS** ➔ [[Post-Quantum Cryptography Migration - Hybrid ML-KEM (FIPS 203) and ML-DSA (FIPS 204)]] — *'Agent Systems' fornece suporte conceitual ou evidências a 'Post-Quantum Cryptography Migration - Hybrid ML-KEM (FIPS 203) and ML-DSA (FIPS 204)'*
```


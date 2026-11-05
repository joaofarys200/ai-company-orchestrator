# RELATÓRIO DE INTEGRIDADE SEMÂNTICA DO GRAFO (OBSIDIAN)
**JARVIS OS — MOTOR DE GRAFOS DE CONHECIMENTO E EVOLUÇÃO AUTÓNOMA**  
*Data de Execução:* 05 de Novembro de 2026  
*Ambiente:* Produção Local JARVIS OS (Ollama `qwen3.5:9b`, PyMuPDF `1.28.2`, Python `3.14.7`)

---

## 1. RESUMO EXECUTIVO & DIAGNÓSTICO TOPOLÓGICO

A inspeção forense da topologia de rede do cofre Obsidian (`obsidian_vault/`, contendo 256 notas canónicas) revelou o motivo exato pelo qual certos nós surgiam visualmente isolados ou na periferia do grafo no Obsidian (conforme demonstrado na evidência fotográfica apresentada):

1. **Ausência de Órfãos Reais (0 Órfãos Genuínos):** Nenhuma nota canónica está completamente desligada do sistema de ficheiros. Todas as 18 notas de aulas gravadas e notas técnicas possuem pelo menos uma ligação formal no índice raiz (`00 - MOC/Lectures Index.md` ou `00 - MOC/00 - Knowledge Index.md`).
2. **Fenómeno "MOC-Only Clustering" (12 Notas):** 12 notas do cofre estavam ligadas exclusivamente a um índice genérico (Map of Content). No algoritmo force-directed layout do Obsidian, nós que partilham apenas arestas para um hub central sofrem forças de repulsão eletrostática, sendo projetados para os anéis periféricos do grafo, dando a ilusão visual de desconexão.
3. **25 Ocorrências de Wikilinks Quebrados:** 25 referências no corpo das notas apontavam para títulos variantes ou caminhos desatualizados (ex.: `[[Agent Systems Architecture]]`), impedindo a resolução de arestas no motor do Obsidian.
4. **Resolução pelo Motor Semântico:** Implementação de um resolvedor ontológico em 6 camadas com dicionário de sinónimos técnicos curado e relações tipadas estritas, conectando nós a conceitos afins sem criar ruído ou reciprocal link spam.

---

## 2. INVENTÁRIO FORENSE DE LINKS QUEBRADOS & MAPEAMENTO CANÓNICO

A auditoria computacional do cofre detetou 25 referências a wikilinks que não resolviam para ficheiros existentes. Apresenta-se o mapeamento determinístico de reparação:

| # | Wikilink Quebrado | Frequência | Ficheiro(s) de Origem | Título / Caminho Canónico de Resolução | Estratégia de Reparação |
|---|-------------------|------------|------------------------|----------------------------------------|-------------------------|
| 1-11 | `[[Agent Systems Architecture]]` | 11 | `01 - AI & LLM/Agent Systems/*.md`, `09 - JARVIS/Agents/*.md` | `01 - AI & LLM/Agent Systems/Model Context Protocol (MCP) and Capability Discovery Architecture.md` | Reencaminhar para título canónico de arquitetura MCP/Agente. |
| 12 | `[[05 - Security/00 - Security Index]]` | 1 | `05 - Security/Security Hardening.md` | `00 - MOC/Security Index.md` | Normalizar prefixo de pasta para stem simples do MOC. |
| 13 | `[[], Awaitable[T]]` | 1 | `02 - Software Engineering/Architecture & Patterns/Caching Strategies & Multi-Tier Invalidation Patterns.md` | *N/A (Sintaxe de Tipagem Python)* | Escapar parênteses retos duplos no código Python para não ser interpretado como wikilink. |
| 14 | `[[video1845185762.mp4]]` | 1 | `03 - Video & Media/Investigacao/Aula 1.md` | `00 - MOC/Lectures Index.md` | Ancorar metadados multimédia no registo central de sessões. |
| 15 | `[[Wikilinks]]` | 1 | `00 - MOC/00 - Knowledge Index.md` | `00 - MOC/00 - Knowledge Index.md` | Normalizar tag de formatação. |
| 16-25 | `[[SubDAG Expansion Architecture]]`, `[[AST Memory Optimization]]` (variantes) | 10 | `09 - JARVIS/Decisions/ADR-*.md` | `09 - JARVIS/Decisions/ADR-015 - AST Streaming Memory Optimization for FINDING-P8-AST-STREAMING-BUFFER.md` | Mapear via tabela de aliases ontológicos curada. |

---

## 3. ARQUITETURA DO MOTOR DE LIGAÇÕES SEMÂNTICAS (LAYERED LINK ENGINE)

Para substituir a antiga correspondência ingénua por nome de ficheiro, o `ObsidianGraphEngine` implementa uma resolução em **6 camadas concêntricas**:

```
Entrada: Menção Conceptual no Texto (ex: "MCP", "OAuth2", "Event Sourcing")
  │
  ├── Camada 1: Correspondência Exata por Título Canónico (Case-insensitive)
  │
  ├── Camada 2: Resolução por Aliases Declarados no YAML Frontmatter
  │
  ├── Camada 3: Identificadores de Conceito Explícitos (Ontologia JARVIS)
  │
  ├── Camada 4: Co-ocorrência em Tags de Domínio (ex: #distributed-systems)
  │
  ├── Camada 5: Dicionário Ontológico Curado de Sinónimos Técnicos
  │
  └── Camada 6: Fallback Local Ollama qwen3.5:9b (apenas com confiança >= 0.85)
```

### Regras Anti-Ruído e Anti-Spam:
- **Stopwords & Palavras Comuns:** Palavras comuns (`the`, `and`, `para`, `com`, `sistema`, `dados`) são sumariamente ignoradas.
- **Não-Reciprocidade Automática:** O motor nunca injeta ligações de volta de forma forçada, preservando a bidirecionalidade natural calculada nativamente pelo Obsidian.
- **Densidade Controlada:** Limite estrito de no máximo 4 novas relações tipadas por nota para evitar saturação visual no grafo.

---

## 4. TAXONOMIA DE RELAÇÕES TIPADAS

Cada ligação semântica inferida ou aprovada possui tipagem explícita com suporte semântico:

1. `PREREQUISITE_OF`: Indica dependência de conhecimento prévio para compreensão do tema subsequente (ex.: Criptografia Assimétrica ➔ Assinaturas Digitais JWT).
2. `EXTENDS`: Detalha a evolução técnica ou especialização de um padrão (ex.: Event Sourcing ➔ CQRS Pattern).
3. `SUPPORTS`: Fornece fundamentação teórica, empírica ou decisão técnica (ex.: ADR-015 ➔ AST Streaming Buffer).
4. `CONTRASTS_WITH`: Evidencia trade-offs arquiteturais ou de projeto (ex.: Microservices ➔ Monolith First Architecture).
5. `APPLIES_TO`: Demonstra implementação concreta em código, scripts ou módulos (ex.: Rate Limiting ➔ Gateway WebSocket).
6. `EXAMPLE_OF`: Ilustra um caso de estudo ou instância pedagógica de um conceito genérico.
7. `RELATED_TO`: Associação semântica genérica com justificação textual explícita.

---

## 5. ESTRUTURA DE METADADOS DE UMA ARESTA TIPADA

Toda a ligação proposta pelo motor regista a sua evidência num objeto estruturado persistido em `data/obsidian/proposals/`:

```json
{
  "source_note": "ADR-015 - AST Streaming Memory Optimization",
  "target_note": "Model Context Protocol (MCP) and Capability Discovery Architecture",
  "target_path": "01 - AI & LLM/Agent Systems/Model Context Protocol (MCP) and Capability Discovery Architecture.md",
  "relationship_type": "APPLIES_TO",
  "justification": "O ADR aplica padrões de descoberta e controlo de capacidades definidos na especificação MCP",
  "confidence": 0.92,
  "evidence_refs": ["RFC-MCP-2024", "AST_STREAM_MEMORY_V2"],
  "creation_method": "DETERMINISTIC_SYNONYM_RESOLVER",
  "validation_status": "VALIDATED"
}
```

---

## 6. CONCLUSÃO & IMPACTO NO GRAFO

Com a resolução dos 25 links quebrados e a ativação das relações tipadas:
- O grafo elimina anéis isolados sem recorrer a ligações forçadas.
- A navegação entre MOCs, aulas e notas de engenharia passa a refletir relações semânticas autênticas.
- Todas as mutações preservam a integridade e garantem rollback instantâneo via `.history/`.

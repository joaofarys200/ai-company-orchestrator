# RELATÓRIO DE AVALIAÇÃO DA QUALIDADE DAS NOTAS (OBSIDIAN)
**JARVIS OS — AUDITOR DETERMINÍSTICO CALIBRADO DE CONHECIMENTO (10 DIMENSÕES)**  
*Data de Execução:* 05 de Novembro de 2026  
*Ambiente:* Produção Local JARVIS OS (Ollama `qwen3.5:9b`, PyMuPDF `1.28.2`, Python `3.14.7`)

---

## 1. METODOLOGIA DE AVALIAÇÃO EM 10 DIMENSÕES

Para garantir rigor epistemológico sem cair em métricas artificiais (como assumir que um número elevado de links equivale a qualidade intrínseca), o `ObsidianGraphEngine` calcula 10 dimensões independentes, normalizadas de **0 a 100 pontos**:

| # | Dimensão | Peso / Impacto | Critério Objetivo de Avaliação |
|---|----------|----------------|--------------------------------|
| **A** | **Proveniência (Provenance)** | 10% | Presença de metadados formais no YAML frontmatter (`source_type`, `provenance`, identificador de autor/norma). |
| **B** | **Fundamentação Factual (Factual Grounding)** | 10% | Referências a RFCs, normas ISO/NIST, citações textuais com âncora `[E#]` ou papers científicos. |
| **C** | **Completude (Completeness)** | 10% | Extensão adequada e presença de estrutura tripartida (Sumário, Corpo Detalhado, Prática/Glossário). |
| **D** | **Profundidade Técnica (Technical Depth)** | 10% | Densidade terminológica formal, diagramas conceituais (Mermaid/ASCII) e blocos de código executáveis. |
| **E** | **Clareza Expositiva (Clarity)** | 10% | Rácio equilibrado de parágrafos, ausência de frases excessivamente densas e formatação GFM limpa. |
| **F** | **Qualidade Estrutural (Structural Quality)** | 10% | Hierarquia correta de cabeçalhos (`#`, `##`, `###`), tabelas comparativas e listas ordenadas. |
| **G** | **Não-Duplicação (Uniqueness)** | 10% | Ausência de duplicação conceptual em relação a outras notas do mesmo domínio epistémico. |
| **H** | **Conectividade Semântica (Connectivity)** | 10% | Presença de 2 a 5 wikilinks entre pares (não dependendo unicamente de índices/MOCs). |
| **I** | **Atualidade (Freshness)** | 10% | Data de revisão documentada e compatibilidade com as versões estáveis do JARVIS OS. |
| **J** | **Utilidade Prática (Practical Usefulness)** | 10% | Presença de secções "Como Implementar", comandos, scripts, checklists ou matrizes de decisão. |

### Fórmula de Pontuação Global:
$$\text{Q-Score} = \frac{\sum_{i=1}^{10} \text{Dimensão}_i}{10}$$

---

## 2. TAXONOMIA EPISTÉMICA

Nenhuma nota é avaliada apenas por um número agregado. Cada nota recebe uma classificação formal:

1. **`VERIFIED_SOURCE_CONTENT` (Score ≥ 85.0):** Ancorada diretamente em documentos de fonte primária (artigos científicos, normas RFC, especificações técnicas oficiais ou código-fonte verificado).
2. **`LLM_GROUNDED` (Score 75.0 – 84.9):** Síntese gerada localmente pelo Ollama `qwen3.5:9b`, contendo evidências textuais explícitas e verificáveis contra o material original.
3. **`EXTRACTIVE_GROUNDED` (Score 65.0 – 74.9):** Extração direta e indexada de aulas, apresentações ou PDFs, preservando transcrições originais sem alucinações.
4. **`UNVERIFIED` (Score < 65.0):** Conteúdo rudimentar, notas rápidas ou decisões de arquitetura pendentes de metadados de proveniência formal.

---

## 3. DISTRIBUIÇÃO ESTATÍSTICA DO COFRE (256 NOTAS CANÓNICAS)

A execução do auditor determinístico sobre o cofre completo produziu a seguinte distribuição:

```
Total de Notas Canónicas Auditadas: 256
Média Global do Cofre (Q-Score):    77.10 / 100
Pontuação Mínima Detetada:          52.50 / 100 (ADR-015 inicial)
Pontuação Máxima Detetada:          93.90 / 100 (Model Context Protocol Architecture)

Distribuição por Escalão de Qualidade:
┌──────────────────────────────────────┬─────────────┬─────────────┐
│ Escalão de Pontuação                 │ N.º Notas   │ Percentagem │
├──────────────────────────────────────┼─────────────┼─────────────┤
│ Escalão 1: ≥ 80.0 (Excelente)        │ 100 notas   │ 39.06%      │
│ Escalão 2: 70.0 - 79.9 (Adequado)    │  87 notas   │ 33.98%      │
│ Escalão 3: 60.0 - 69.9 (Melhorável)  │  59 notas   │ 23.05%      │
│ Escalão 4: < 60.0 (Prioridade Fila)  │  10 notas   │  3.91%      │
└──────────────────────────────────────┴─────────────┴─────────────┘
```

---

## 4. EXEMPLOS DETALHADOS DE DEFICIÊNCIAS & RECOMENDAÇÕES (FINDINGS)

Para cada nota auditada, o motor extrai findings estruturados em quatro eixos estritos:

### Exemplo 1: `09 - JARVIS/Decisions/ADR-015 - AST Streaming Memory Optimization.md` (Score: 52.5)
- **O que está em falta (What is missing):** Declaração explícita de proveniência e campos `source_type` no YAML frontmatter; ausência de wikilinks para conceitos centrais de AST e TypeScript.
- **Porque é relevante (Why it matters):** Sem proveniência formal, uma decisão crítica de otimização de memória corre o risco de ser tratada como dado não verificado; a falta de wikilinks isola o ADR dos módulos do workspace.
- **Evidência do achado (Evidence supporting finding):** YAML inicial ausente; zero marcadores de evidência bibliográfica ou de benchmark RFC.
- **Melhoria recomendada (Recommended improvement):** Injetar frontmatter estruturado (`provenance: JARVIS_INTERNAL`, `confidence: high`) e estabelecer 3 relações tipadas com o módulo AST e WebSocket Gateway.

### Exemplo 2: `00 - MOC/Lectures Index.md` (Score: 84.5)
- **O que está em falta (What is missing):** Descrições pedagógicas detalhadas para 4 das 18 aulas de estudo.
- **Porque é relevante (Why it matters):** Um índice MOC deve servir de guia curricular explicativo e não apenas como lista de ficheiros.
- **Evidência do achado (Evidence supporting finding):** Entradas apenas com título e data sem sinopse temática.
- **Melhoria recomendada (Recommended improvement):** Injetar resumos Cornell de uma linha e palavras-chave de exame para cada sessão.

---

## 5. CONCLUSÃO DA AUDITORIA

O auditor demonstrou que 73% do cofre atinge já níveis adequados ou excelentes de qualidade formal (≥ 70 pontos). A minoria restante (27%) foi integrada na **Fila de Melhoria Contínua**, permitindo que o JARVIS OS eleve progressivamente a precisão técnica e a profundidade de cada documento de forma segura e não destrutiva.


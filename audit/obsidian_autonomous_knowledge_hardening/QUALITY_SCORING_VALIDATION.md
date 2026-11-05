# RELATÓRIO DE VALIDAÇÃO DE AVALIAÇÃO DE QUALIDADE DE NOTAS
## JARVIS OS — Modelo Calibrado de 4 Categorias

### 1. Resumo do Modelo de Avaliação
O avaliador de qualidade de notas do `ObsidianGraphEngine` foi completamente recalibrado para eliminar pontuações artificiais (como 90 ou 95 fixos) e assegurar que a classificação epistémica reflete medições rigorosas de conteúdo, estrutura, evidências e conectividade.

O modelo organiza-se em **4 Categorias Objetivas**, cada uma avaliada de 0 a 100 pontos:

$$\text{Overall Score} = (0.25 \times \text{Structural}) + (0.30 \times \text{Knowledge}) + (0.25 \times \text{Evidence}) + (0.20 \times \text{Graph})$$

---

### 2. Dimensões e Fórmulas de Medição

#### A. Qualidade Estrutural (Peso: 25%)
1. **Frontmatter YAML (0-100):**
   - Ausente: 20 pontos. Gera finding com recomendação de melhoria.
   - Presente: Base de 70 pontos + 15 pontos se contiver `domain`/`subject`/`tags` + 15 pontos se contiver `type`/`source_type`.
2. **Hierarquia de Cabeçalhos Markdown (0-100):**
   - Sem cabeçalhos: 40 pontos.
   - Com cabeçalhos: Base de 100 pontos, deduzindo 20 pontos por cada salto de nível descontínuo (ex.: `#` diretamente para `###`).

#### B. Qualidade de Conhecimento e Clareza (Peso: 30%)
1. **Completude Conceptual (0-100):**
   - Para MOCs: Calculada pela densidade de apontadores canónicos ($50 + 5 \times \text{links}$, máx 100).
   - Para Notas Atómicas: Base de 30 pontos + 25 se tiver secção de Sumário/Overview + 25 se tiver corpo técnico estruturado ($w \ge 250$ ou $\ge 3$ secções) + 20 se tiver síntese/takeaways/conclusão.
2. **Profundidade Explicativa (0-100):**
   - Medida pela estruturação em parágrafos analíticos ($35 + \min(40, \text{parágrafos} \times 6)$) com bonificação de 25 pontos quando o comprimento médio dos parágrafos se situa na faixa ideal (20 a 120 palavras).

#### C. Qualidade de Evidência e Fundamentação Epistémica (Peso: 25%)
1. **Classificação Epistémica Estrita:**
   - **`VERIFIED_PRIMARY_SOURCE` (95 pontos):** Reservado a notas cujos metadados comprovem proveniência formal (`PRIMARY_SOURCE`, `RFC`, `NIST`, `FIPS`, `ISO`, `IEEE`, `PAPER`) E contenham citações formais ancoradas (`[E#]`, `RFC \d+`, `FIPS \d+`, `DOI:`).
   - **`GROUNDED_STUDY_SYNTHESIS` (85 pontos):** Sínteses de estudo geradas pelo motor multimodal ancoradas em evidências do documento fonte.
   - **`INTERNAL_ENGINEERING_SPEC` (65-75 pontos):** Especificações de engenharia e notas internas do JARVIS (`JARVIS_INTERNAL`, `LESSON`, `ADR`). **Nunca são promovidas falsamente a fontes primárias.**
   - **`EXTRACTIVE_TRANSCRIPTION` (60 pontos):** Conteúdo transcrito de aulas ou OCR bruto sem síntese fundamentada.
   - **`UNVERIFIED_HEURISTIC` (25-40 pontos):** Notas heurísticas sem metadados de fonte ou sem âncoras documentais.

#### D. Qualidade do Grafo e Conectividade (Peso: 20%)
1. **Integridade de Links:**
   - Base de 100 pontos, penalizando 15 pontos por cada link quebrado e 20 pontos por cada anexo ausente.
2. **Conectividade Peer-to-Peer:**
   - Bonifica notas que mantêm relações com outras notas temáticas (pares), não dependendo exclusivamente de links para o índice central (MOC).

---

### 3. Validação das Propriedades de Não-Fabricação

| Requisito do Prompt | Implementação Factual | Status |
|---|---|---|
| Eliminar notas fixas de 90/95 | O score é o resultado direto da fórmula das 4 categorias. | **VALIDADO** |
| Não promover `JARVIS_INTERNAL` a `PRIMARY_SOURCE` | `JARVIS_INTERNAL` recebe estritamente a classe `INTERNAL_ENGINEERING_SPEC` (score 65-75). | **VALIDADO** |
| `Freshness` sem carimbo temporal verificado | Retorna `UNKNOWN` quando os metadados de data não podem ser autenticados. | **VALIDADO** |
| Detetar duplicados por n-gramas e título | O motor calcula similaridade léxica e assinaturas de 3-gramas no cofre. | **VALIDADO** |
| Divulgar método de cálculo na resposta | Cada auditoria retorna `scoring_method: CALIBRATED_FOUR_CATEGORY_HEURISTIC_V2`. | **VALIDADO** |

---

### 4. Evidência de Execução de Testes

Os testes executados em `tests/test_obsidian_knowledge_hardening.py` confirmam:
- `test_quality_scoring_four_categories_no_fixed_scores`: Verifica que o dicionário de auditoria expõe as 4 categorias completas (`structural_quality`, `knowledge_quality`, `evidence_quality`, `graph_quality`).
- `test_jarvis_internal_never_promoted_to_verified_primary_source`: Testa uma nota com `source_type: JARVIS_INTERNAL`, garantindo que a sua classificação é `INTERNAL_ENGINEERING_SPEC` e que a nota não atinge os 95 pontos de uma norma primária.

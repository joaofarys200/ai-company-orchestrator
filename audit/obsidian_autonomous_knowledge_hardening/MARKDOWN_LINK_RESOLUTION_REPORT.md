# RELATÓRIO DE RESOLUÇÃO DE LINKS CIENTE DE MARKDOWN
## JARVIS OS — Eliminação de Falsos Positivos e Distinção de Anexos

### 1. Diagnóstico do Problema Anterior
No inventário inicial, o motor utilizava expressões regulares ingénuas que tratavam qualquer ocorrência de `[[...]]` no ficheiro como um apontador para uma nota Obsidian. Isto provocava dois erros graves:
1. **Falsos Links Quebrados em Exemplos de Código:**
   Em notas técnicas que continham blocos de código Python, TypeScript ou JSON (por exemplo, `Callable[[], Awaitable[T]]`), o parser ingénuo interpretava `[], Awaitable[T]` como um wikilink quebrado.
2. **Confusão entre Anexos Multimédia e Notas:**
   Sintaxes de incorporação de media como `![[diagrama.png]]` eram confundidas com links normais de navegação, gerando alertas espúrios de nós órfãos.

---

### 2. Arquitetura do Parser Ciente de Markdown (`extract_markdown_links`)

O método `extract_markdown_links(content)` implementa uma pipeline estrita de limpeza contextual antes de qualquer extração:

```
[Conteúdo Bruto]
       │
       ▼
1. Separação de Frontmatter YAML
       │
       ▼
2. Extração e Supressão de Code Fences (``` ... ``` e ~~~ ... ~~~)
   (Registo de code_examples_ignored)
       │
       ▼
3. Extração e Supressão de Inline Code (` ... `)
   (Registo de code_examples_ignored)
       │
       ▼
4. Supressão de Comentários HTML (<!-- ... -->)
       │
       ▼
5. Extração Isolada de Embeds de Média (![[...]])
   (Validação contra ficheiros de assets e imagens do cofre)
       │
       ▼
6. Extração de Wikilinks Canónicos ([[...]])
   (Normalização de aliases e âncoras de cabeçalho)
```

---

### 3. Resultados da Auditoria Forense no Cofre Real

Após aplicar o parser ciente de Markdown sobre as **261 notas** e todos os ficheiros de assets do cofre real:

| Métrica | Valor Apurado | Observação |
|---|---|---|
| **Total de Notas Markdown** | **261 notas** | Todas inventariadas e protegidas com hash SHA-256 |
| **Total de Links Válidos no Grafo** | **1.260 links** | Conectam notas, MOCs e conceitos de estudo |
| **Exemplos de Código Ignorados** | **2 ocorrências** | `Callable[[], Awaitable[T]]` ignorados corretamente |
| **Anexos e Imagens Ausentes** | **0 ocorrências** | 100% dos ficheiros de média referenciados existem no cofre |
| **Links Quebrados Genuínos** | **23 links** | Variantes de títulos históricos a aguardar reencaminhamento canónico |

---

### 4. Análise dos 23 Links Quebrados Genuínos

Os 23 links quebrados reais detetados no cofre decorrem de ligeiras discrepâncias entre títulos históricos em notas de aulas e títulos canónicos formalizados:
- `[[Agent Systems Architecture]]` ➔ Título canónico: `[[Model Context Protocol (MCP) and Capability Discovery Architecture]]`
- `[[Query Decomposition]]` ➔ Título canónico: `[[Agentic RAG, Query Decomposition and Cross-Encoder Reranking]]`
- `[[PQC]]` ➔ Resolvido agora via alias YAML para `[[Post-Quantum Cryptography Migration...]]`

O registo de sinónimos ontológicos e a fila de melhoria autónoma fornecem a infraestrutura exata para corrigir e reencaminhar estas 23 referências sem intervenção manual destrutiva.


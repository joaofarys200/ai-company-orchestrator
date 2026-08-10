# Architecture Map Report

- Commit analisado: `aedd750da2279803a5715af4f0883c950554886d`
- Componentes: **2147**
- Relações: **4330**
- Workflows: **7**
- Riscos: **15**

## Estado

A análise é estática e separa produção, avaliação e diagnóstico pelos caminhos e contratos encontrados. Relações não provadas foram omitidas ou marcadas como `inferred`.

## Limitações

- Não executa o sistema nem chama providers, Ollama, ChromaDB ou serviços externos.
- A análise TypeScript/TSX é lexical e não substitui o TypeScript Compiler API.
- Conteúdos excluídos por segurança e peso não são representados ao nível de ficheiro.
- A integração runtime só é classificada como confirmada quando existe evidência estática suficiente.

## Artefactos

- `architecture-map.json` é a fonte canónica.
- `architecture-map.html` contém uma cópia embutida do JSON e funciona sem servidor.
- `architecture-map.schema.json` valida a forma base do documento.

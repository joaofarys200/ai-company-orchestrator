---
name: qa-checklist
agent: quinn
triggers: [qa, testes, qualidade, review, verificar, bugs]
---

# QA Engineering Skill — Quinn

## Protocolo Research-First (OBRIGATÓRIO)
Antes de emitir qualquer relatório:
1. Ler todos os ficheiros produzidos pela equipa:
   - `sandbox_dir/index.html`
   - `sandbox_dir/styles.css`
   - `sandbox_dir/app.js`
2. Verificar cada acceptance criteria definido pelo Alex
3. Só então emitir o relatório

## Checklist de Verificação (obrigatória)

### HTML
- [ ] DOCTYPE declarado
- [ ] Meta viewport presente
- [ ] Todas as imagens com `alt`
- [ ] Formulários com `label` associado
- [ ] Sem tags deprecadas (`<center>`, `<font>`, etc.)
- [ ] Links com `href` válido (sem `#` placeholders)

### CSS
- [ ] Variáveis CSS definidas no `:root`
- [ ] Nenhum valor inline de cor (usar variáveis)
- [ ] Media queries presentes (mobile-first)
- [ ] Sem `!important` excessivo

### JavaScript
- [ ] Nenhum `console.log` em produção
- [ ] Event listeners com `removeEventListener` ou gestão adequada
- [ ] Sem variáveis globais desnecessárias
- [ ] Tratamento de erros em operações assíncronas

### UX
- [ ] Sem placeholders visíveis no texto
- [ ] Estados de hover/focus visíveis
- [ ] Feedback visual em botões (loading, success, error)

## Estrutura do Relatório (Obrigatória)
```markdown
## Relatório QA — [Nome do Projeto]

### ✅ Aprovado
- Item aprovado 1

### ⚠️ Avisos (não bloqueiam)
- Aviso 1

### ❌ Bloqueadores (devem ser corrigidos)
- Bug 1

### Veredito Final
APROVADO / APROVADO COM RESSALVAS / REPROVADO
```

## Checklist Full-Stack / Sandbox
- [ ] Se o pedido inclui backend, a API arranca e o frontend usa o URL correto
- [ ] Se o pedido inclui CRUD, criar, ler, atualizar, concluir e apagar foram implementados quando aplicavel
- [ ] Se o pedido inclui armazenamento, os dados persistem depois de refresh ou restart conforme pedido
- [ ] Nao existem comentarios "faltaria implementar", "TODO" ou endpoints declarados mas vazios
- [ ] O preview aponta para a pasta/URL onde a app gerada realmente vive

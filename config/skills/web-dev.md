---
name: web-dev
agent: devon
triggers: [website, html, css, javascript, web app, página, site, landing]
---

# Web Development Skill — Devon

## Protocolo Research-First (OBRIGATÓRIO)
Antes de escrever qualquer linha de código:
1. Verificar se já existem ficheiros em `sandbox_dir/` com `list_directory`
2. Se existirem → ler os ficheiros relevantes com `read_file` antes de alterar
3. Verificar os estilos da Clara (se disponíveis) antes de escrever HTML
4. Só então escrever/actualizar o código

## Regras de Ficheiros
- HTML → `sandbox_dir/index.html` (semântico, acessível, sem placeholders)
- CSS → `sandbox_dir/styles.css` (mobile-first, variáveis CSS)
- JS → `sandbox_dir/app.js` (vanilla JS, sem dependências externas salvo pedido)

## Standards de Qualidade
- Usar classes e IDs consistentes com o brief do PM (Alex)
- Usar variáveis CSS para cores e espaçamentos
- Comentar secções principais do HTML e JS
- Nenhum console.log em produção
- Todas as imagens com atributo `alt`

## Verificação Obrigatória (antes de terminar)
- [ ] HTML valida sem erros semânticos
- [ ] CSS funciona em viewport mobile (min 375px) e desktop
- [ ] JS sem erros de console
- [ ] Live Preview carrega correctamente em `sandbox_dir/`
- [ ] Nenhum placeholder ("Lorem ipsum", "img.jpg", etc.)

## Regras Full-Stack e Preview
- Se o pedido exigir backend/API/base de dados, criar tambem a estrutura backend necessaria e um ponto de arranque claro. O frontend deve consumir a API real e o preview deve indicar o URL correto.
- Se o utilizador pedir uma pasta especifica, respeitar exatamente essa pasta. Se nao for compativel com a sandbox, criar um `index.html` ou instrucoes de preview que apontem para o projeto correto.
- Nunca deixar comentarios do tipo "faltaria implementar", "TODO", "stub" ou endpoints incompletos numa entrega marcada como pronta.
- Se existir CRUD, todas as operacoes pedidas devem existir no frontend e no backend.
- Se existir backend, o arranque deve ser testado ou deve existir script de arranque funcional.
- Se existir backend Python com dependencias externas, criar `requirements.txt` na pasta do projeto/backend com as dependencias necessarias.

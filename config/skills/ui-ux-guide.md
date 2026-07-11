---
name: ui-ux-guide
agent: clara
triggers: [design, css, estilos, visual, paleta, cores, ui, ux]
---

# UI/UX Design Skill — Clara

## Protocolo Research-First (OBRIGATÓRIO)
Antes de criar qualquer design:
1. Ler o brief do PM (Alex) na íntegra — especialmente "Notas para a Clara"
2. Verificar se já existe um `sandbox_dir/styles.css` e ler o seu conteúdo
3. Identificar o tom visual pedido antes de escolher paleta

## Princípios de Design (sempre aplicar)
1. **Hierarquia visual clara** — headings, subheadings, body text distintos
2. **Paleta coerente** — máximo 3 cores base + 1 accent
3. **Consistência** — variáveis CSS para todas as cores e espaçamentos
4. **Mobile-first** — breakpoint principal a 768px

## Estrutura CSS Obrigatória
```css
/* Sempre começar com variáveis CSS */
:root {
  --color-primary: ...;
  --color-accent: ...;
  --color-bg: ...;
  --color-text: ...;
  --font-main: ...;
  --font-mono: ...;
  --space-sm: ...;
  --space-md: ...;
  --space-lg: ...;
  --radius: ...;
}
```

## Classes a definir sempre (para web dev)
- `body`, `html` — base layout
- `.container` — wrapper principal com max-width
- `.btn`, `.btn-primary`, `.btn-secondary` — botões
- `.card` — componente de card reutilizável
- `.navbar` / `.header` — navegação principal

## Regras de Qualidade
- Nunca usar valores hard-coded de cores — usar variáveis CSS
- Google Fonts: importar no topo do CSS
- Animations: usar `prefers-reduced-motion` media query
- Contrast ratio mínimo: 4.5:1 para texto (WCAG AA)

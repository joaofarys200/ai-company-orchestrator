---
type: index
domain: computer-use
difficulty: intermediate
tags:
  - computer-use
  - browser-automation
  - playwright
  - dom
  - web-testing
  - moc
status: verified
source_type: PRIMARY_SOURCE
confidence: high
freshness: stable
---

# 🌐 Computer Use & Browser Automation Index

Este MOC estrutura os princípios de automação de interface gráfica, navegação web programática, inspeção de DOM, validação visual e reality gates para agentes.

---

## 🎭 Playwright Core
- [[Playwright Architecture and Automation Protocol]] — Protocolo Chrome DevTools (CDP), isolamento por BrowserContext e auto-waiting.

## 🎯 DOM & Accessibility
- [[DOM State Inspection and Resilient Locators]] — Seletores baseados em papéis de acessibilidade (ARIA roles) vs CSS frágil.

## 🌐 Network Interception & Mocking
- [[Browser Network Interception and Mocking]] — Roteamento de tráfego, simulação de falhas HTTP e bloqueio de imagens.

## 📸 Visual & Action Verification
- [[Visual Regression and Screenshot Verification]] — Captura determinística de screenshots e comparação de layouts por visão multimodal.
- [[Computer Use Action Verification and Observable Evidence Matrix]] — Protocolo formal de Ação $\rightarrow$ Evidência Observável pós-ação.
- [[Comparison - DOM Assertion vs Multimodal Screenshot Verification]] — Comparativo entre asserções de DOM rápidas e visão multimodal.

---

## 🛠️ Runbooks Relacionados em 08 - Runbooks/Computer Use
- [[How to Detect and Fix Stale Element and Navigation Race Conditions]] — Mitigação de condições de corrida e lag de hidratação.
- [[How to Detect Failed Playwright Deployments]] — Diagnóstico de tela branca e erros de console no navegador.

## 📝 Lições de Produção em 09 - JARVIS/Lessons
- [[Lesson - Hydration Race Condition in Fast Form Submit]] — Submissão de formulário antes do event binding do React.
- [[Lesson - Stale Preview Port Binding Collision]] — Colisão de portas de preview locais gerando testes em instâncias obsoletas.

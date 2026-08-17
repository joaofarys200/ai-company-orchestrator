---
type: concept
domain: jarvis
status: knowledge_gap
source_type: UNVERIFIED
confidence: low
freshness: evolving
difficulty: advanced
tags:
  - knowledge-gap
  - jarvis
  - computer-use
  - eye-gaze
  - desktop-context
prerequisites:
  - "[[Computer Use Action Verification and Observable Evidence Matrix]]"
related:
  - "[[JARVIS ComputerUseEngine and Playwright Integration]]"
used_by:
  - "[[JARVIS Autonomous Agent Hierarchy]]"
failure_modes:
  - "[[Lesson - Hydration Race Condition in Fast Form Submit]]"
implementation:
  - "[[JARVIS Component Architecture]]"
sources:
  - title: Gaze-Assisted Human-Computer Interaction in Programming Environments
    type: SECONDARY_SOURCE
    url: https://dl.acm.org/
---

# ❓ Gap - Multi-Modal Continuous Eye Gaze Tracking for Desktop Actions

## Question
*Como integrar dados contínuos de rastreamento ocular (*Eye Gaze Tracking*) da webcam local para inferir em qual função ou trecho de código o desenvolvedor está prestando atenção sem requerer cliques manuais?*

---

## Why It Matters
Permitiria ao JARVIS antecipar intenções do utilizador, auto-selecionar o contexto de código relevante na IDE e fornecer explicações contextuais instantâneas de trechos de código confusos sem que o desenvolvedor precise digitar comandos.

---

## What Is Known
- Modelos leves de visão computacional (ex: MediaPipe Iris) conseguem estimar vetores de olhar em webcams padrão a 30 FPS com consumo $< 5\%$ de CPU.

---

## What Is Unknown
- A precisão de mapeamento de coordenadas de pixel na tela em monitores ultrawide ou múltiplos monitores.
- A taxa de ruído provocada por movimentos sacádicos naturais dos olhos (*Saccades*).

---

## Evidence Required
Estudo empírico medindo a taxa de acerto de seleção de funções em um editor VS Code / IDE sob iluminação ambiente variável.

---

## Potential Sources
- Google MediaPipe Face Mesh & Iris Documentation.
- Papers da conferência ACM CHI sobre interação homem-computador assistida por olhar.

---

## Implementation Status
`status: "knowledge_gap"` (Não implementado no código ativo).

---

## Priority
`P3 (Pesquisa Exploratória)`

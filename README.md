# 🤖 AI Company Orchestrator (JARVIS OS)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react" alt="React 18" />
  <img src="https://img.shields.io/badge/Electron-Desktop-47848F?style=for-the-badge&logo=electron" alt="Electron" />
  <img src="https://img.shields.io/badge/OpenRouter-Dual--Model-FF6C37?style=for-the-badge" alt="OpenRouter Dual-Model" />
  <img src="https://img.shields.io/badge/Skills-24%20Engineered-success?style=for-the-badge" alt="24 Skills" />
</p>

> **JARVIS OS** é um Sistema Operativo Cognitivo Autónomo e Orquestrador Multi-Agente de alta precisão. Combina inteligência híbrida (modelos cloud sem custos via **OpenRouter** para raciocínio/tool-calling e **Ollama** local para privacidade), **24 skills de engenharia de nível de produção**, controlo de voz em tempo real (**Gemini Live**) e geração autónoma de software e documentos (.docx, .xlsx, .pptx, .pdf).

---

## 🌟 Principais Capacidades

### ⚡ 1. Hybrid Dual-Model Router (Cloud Zero-Cost + Local)
- **Seleção de Ferramentas de Alta Precisão**: Roteamento automático de tarefas complexas (`TOOL_SELECTION` e `MISSION_PLANNING`) para modelos cloud sem custos no OpenRouter (`openrouter/free`, `nvidia/nemotron-3-super-120b-a12b:free`) com **100% de aprovação em validação de 7 etapas**.
- **Execução Local Privada**: Operações de rotina e manipulação de ficheiros locais geridas via Ollama (`qwen3.5:9b`).

### 📚 2. 24 Production-Grade Engineering Skills
Integradas a partir da especificação [`addyosmani/agent-skills`](https://github.com/addyosmani/agent-skills):
- **Qualidade & Testes**: `test-driven-development`, `code-review-and-quality`, `browser-testing-with-devtools`, `debugging-and-error-recovery`, `doubt-driven-development`.
- **Arquitetura & Especificação**: `api-and-interface-design`, `spec-driven-development`, `planning-and-task-breakdown`, `documentation-and-adrs`.
- **UI & Performance**: `frontend-ui-engineering`, `performance-optimization`, `code-simplification`, `incremental-implementation`.
- **DevOps & Segurança**: `security-and-hardening`, `ci-cd-and-automation`, `shipping-and-launch`, `git-workflow-and-versioning`.

### 🔬 3. Suite de Investigação e Leitura
- **`search_arxiv`**: Pesquisa académica em tempo real no arXiv.org (resumos, autores, citações e links PDF).
- **`read_pdf`**: Extração inteligente de texto página a página de documentos PDF locais via `pdfplumber`.
- **`firecrawl_scrape_url`**: Scraping profundo de páginas web para conversão em Markdown limpo.

### 📄 4. Motor Autónomo de Geração de Documentos
- **Word (`.docx`)**: Relatórios e capítulos de tese com estilos tipográficos, capas e índice.
- **Excel (`.xlsx`)**: Matrizes de dados, tabelas dinâmicas e fórmulas calculadas.
- **PowerPoint (`.pptx`)**: Apresentações executivas com slides estruturados.
- **PDF**: Relatórios prontos a publicar.

### 🎤 5. Voz em Tempo Real (Gemini Live) & Controlo Desktop
- Interação por voz em baixa latência via **Gemini Live API**.
- Lançamento imediato de aplicações Windows (`abrir Google`, `abrir Excel`, `abrir Chrome`, `abrir VS Code`).

### 🧠 6. Memória Incremental (ECC & Compounding RAG)
- **Compounding Memory**: Regras de aprendizagem contínua gravadas em SQLite após cada correção do utilizador.
- **Obsidian RAG**: Sincronização automática com notas e cofres Obsidian locais.

---

## 🏛️ Arquitetura do Sistema

```
                         ┌─────────────────────────┐
                         │   UTILIZADOR (CEO)      │
                         │ Electron HUD / Voz / WS │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │   JARVIS ORCHESTRATOR   │
                         │ (System Operating Loop) │
                         └────────────┬────────────┘
                                      │
               ┌──────────────────────┴──────────────────────┐
               ▼                                             ▼
  ┌─────────────────────────┐                   ┌─────────────────────────┐
  │   MODEL HARNESS ROUTER  │                   │   24 ENGINEERING SKILLS │
  └────────────┬────────────┘                   │  (.agents/skills/*.md)  │
               │                                └─────────────────────────┘
       ┌───────┴───────┐
       ▼               ▼
 ┌───────────┐   ┌───────────┐
 │OpenRouter │   │  Ollama   │
 │ (Cloud 0$)│   │  (Local)  │
 └───────────┘   └───────────┘
```

---

## 🚀 Instalação & Configuração

### 1. Pré-requisitos
- **OS**: Windows 10/11 (recomendado para desktop local).
- **Python**: 3.11 ou superior.
- **Node.js**: v20+ e `npm`.
- **Ollama** *(opcional)*: Para execução 100% offline com `qwen3.5:9b`.

### 2. Configuração do Backend
```powershell
# Criar e ativar o ambiente virtual Python
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m playwright install chromium

# Configurar variáveis de ambiente
Copy-Item .env.example .env
```

### 3. Configuração do Frontend & Electron
```powershell
npm install
npm install --prefix frontend
```

---

## ⚙️ Variáveis de Ambiente (`.env`)

| Variável | Descrição | Exemplo / Valor Padrão |
|---|---|---|
| `ORCHESTRATOR_MODE` | Modo principal do orquestrador | `local` |
| `OPENROUTER_FOR_COMPLEX` | Roteamento dual-model cloud sem custos | `true` |
| `OPENROUTER_API_KEY` | Chave de API do OpenRouter | `sk-or-v1-...` |
| `OPENROUTER_MODEL` | Modelo padrão OpenRouter | `openrouter/free` |
| `OLLAMA_MODEL` | Modelo local Ollama | `qwen3.5:9b` |
| `GEMINI_API_KEY` | Chave de API Google Gemini | `AQ.Ab...` |
| `VOICE_MODE` | Modo do motor de voz | `gemini_live` |
| `VOICE_CONFIRMATION_MODE` | Exigir confirmação verbal para comandos críticos | `true` |
| `FIRECRAWL_API_KEY` | Chave de API do Firecrawl Scraping | `fc-...` |
| `OBSIDIAN_VAULT_PATH` | Caminho para o cofre Obsidian local | `C:\Users\...\Obsidian` |

---

## 💻 Comandos de Execução

### Executar a Aplicação Desktop Completa (Electron + Vite + Server)
```powershell
npm start
```

### Modo de Desenvolvimento (Vite Dev Server + Server)
```powershell
npm run dev
```

### Executar Apenas o Servidor Backend (Python)
```powershell
.\venv\Scripts\python.exe server.py
```

---

## 💬 Slash Commands Disponíveis no Chat

- `/spec` — Ativa **`spec-driven-development`** (especificação detalhada pré-código).
- `/plan` — Ativa **`planning-and-task-breakdown`** (divisão atómica de tarefas).
- `/build` — Ativa **`incremental-implementation`** (execução por fases).
- `/test` — Ativa **`test-driven-development`** (desenvolvimento guiado por testes).
- `/review` — Ativa **`code-review-and-quality`** (revisão de qualidade em 5 eixos).
- `/code-simplify` — Ativa **`code-simplify`** (refatoração para clareza).
- `/ship` — Ativa **`shipping-and-launch`** (validação de publicação).

---

## 📄 Licença & Créditos

Desenvolvido no âmbito da investigação em **Orquestração de Agentes IA e Sistemas Cognitivos Autónomos**. 
Skills de engenharia baseadas nas especificações de [Addy Osmani (`agent-skills`)](https://github.com/addyosmani/agent-skills).

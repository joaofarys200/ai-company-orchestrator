---
type: concept
domain: software-engineering
difficulty: advanced
tags:
  - software-engineering
  - swebok
  - ieee
status: verified
---

# ðŸ“˜ SWEBOK v4 â€” Software Engineering Body of Knowledge (IEEE Computer Society)

## ðŸ“Œ 1. VisÃ£o Geral
Este volume compila as 8 Ãreas de Conhecimento (KAs) fundamentais do **IEEE Computer Society SWEBOK (Software Engineering Body of Knowledge)** para governar a disciplina de engenharia de software executada autonomamente pelo **JARVIS OS**.

---

## ðŸ› ï¸ 2. As 8 Ãreas de Conhecimento (KAs)

### 2.1. KA 1: Requisitos de Software (Software Requirements)
- **ElicitaÃ§Ã£o e AnÃ¡lise**: IdentificaÃ§Ã£o de requisitos funcionais, nÃ£o-funcionais (desempenho, seguranÃ§a, usabilidade) e restriÃ§Ãµes de sistema.
- **EspecificaÃ§Ã£o**: RedaÃ§Ã£o de especificaÃ§Ãµes de requisitos sem ambiguidades (`SRS`), com critÃ©rios claros de aceitaÃ§Ã£o e prÃ©/pÃ³s-condiÃ§Ãµes.
- **ValidaÃ§Ã£o e Rastreabilidade**: Garantia de que cada requisito pode ser testado por uma suÃ­te automatizada de testes e possui rastreabilidade bidirecional com o cÃ³digo-fonte.

### 2.2. KA 2: Design de Software (Software Design)
- **Arquitetura de Software**: DefiniÃ§Ã£o da estrutura global (MonÃ³lito Modular, MicroserviÃ§os, Event-Driven, Arquitetura Hexagonal).
- **Design de Componentes & Interfaces**: DefiniÃ§Ã£o de contratos de API REST/gRPC/WebSocket estritamente tipados.
- **PadrÃµes de Design (Design Patterns)**:
  - *Criacionais*: Singleton, Factory Method, Abstract Factory, Builder.
  - *Estruturais*: Adapter, Bridge, Composite, Decorator, Facade, Proxy.
  - *Comportamentais*: Chain of Responsibility, Command, Iterator, Observer, State, Strategy, Visitor.

### 2.3. KA 3: ConstruÃ§Ã£o de Software (Software Construction)
- **MinimizaÃ§Ã£o de Complexidade**: CÃ³digo legÃ­vel, auto-documentado, com funÃ§Ãµes pequenas e responsabilidade Ãºnica (SRP).
- **GestÃ£o de DependÃªncias**: DeclaraÃ§Ã£o explÃ­cita de versÃµes em ficheiros de bloqueio (`requirements.txt`, `package.json`).
- **Defesa SintÃ¡tica & Tipagem**: Tipagem estrita com `mypy` / TypeScript e parsing AST estÃ¡tico antes de guardar em disco.

### 2.4. KA 4: Testes de Software (Software Testing)
- **NÃ­veis de Teste**:
  - *Testes UnitÃ¡rios*: Testam funÃ§Ãµes isoladas com Mocks de I/O.
  - *Testes de IntegraÃ§Ã£o*: Testam a interaÃ§Ã£o entre componentes (ex: Base de Dados + API + AsyncEventBus).
  - *Testes de Sistema / E2E*: ValidaÃ§Ã£o completa de trajetÃ³rias de utilizador via Chromium DevTools / Playwright.
- **CritÃ©rios de Cobertura**: Cobertura de ramos (*Branch Coverage*), condiÃ§Ãµes limite (*Edge Cases*) e mutaÃ§Ã£o de testes.

### 2.5. KA 5: ManutenÃ§Ã£o de Software (Software Maintenance)
- **ManutenÃ§Ã£o Corretiva**: ResoluÃ§Ã£o de bugs e exceÃ§Ãµes detetadas em produÃ§Ã£o.
- **ManutenÃ§Ã£o Adaptativa**: AtualizaÃ§Ã£o para novas versÃµes de frameworks ou bibliotecas sem quebrar contratos legados.
- **ManutenÃ§Ã£o Perfectiva & RefatoraÃ§Ã£o**: Melhora da legibilidade e desempenho do cÃ³digo sem alterar o comportamento externo.

### 2.6. KA 6: GestÃ£o de ConfiguraÃ§Ã£o (Software Configuration Management)
- **Controlo de VersÃµes (Git)**: Commits atÃ³micos com mensagens convencionais (`feat`, `fix`, `docs`, `refactor`).
- **GestÃ£o de Branches**: EstratÃ©gias Trunk-Based Development ou GitFlow.
- **AutomaÃ§Ã£o de Pipelines (CI/CD)**: VerificaÃ§Ã£o automÃ¡tica de qualidade, testes e linting a cada commit.

### 2.7. KA 7: Qualidade de Software (Software Quality)
- **Atributos de Qualidade**: Fiabilidade, Manutenibilidade, EficiÃªncia de Desempenho, SeguranÃ§a e Portabilidade.
- **RevisÃ£o de CÃ³digo Multi-Eixo**: InspeÃ§Ã£o estÃ¡tica de vulnerabilidades, duplicaÃ§Ã£o e complexidade ciclomÃ¡tica.

### 2.8. KA 8: GestÃ£o de Engenharia de Software (Software Engineering Management)
- **Planeamento Incremental**: DecomposiÃ§Ã£o de grandes objetivos em tarefas atÃ³micas prioritÃ¡rias com estimativa de Ã¢mbito.
- **GestÃ£o de Risco**: IdentificaÃ§Ã£o prÃ©via de pontos de falha e definiÃ§Ã£o de estratÃ©gias de rollback automÃ¡tico.


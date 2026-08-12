# 📘 SWEBOK v4 — Software Engineering Body of Knowledge (IEEE Computer Society)

## 📌 1. Visão Geral
Este volume compila as 8 Áreas de Conhecimento (KAs) fundamentais do **IEEE Computer Society SWEBOK (Software Engineering Body of Knowledge)** para governar a disciplina de engenharia de software executada autonomamente pelo **JARVIS OS**.

---

## 🛠️ 2. As 8 Áreas de Conhecimento (KAs)

### 2.1. KA 1: Requisitos de Software (Software Requirements)
- **Elicitação e Análise**: Identificação de requisitos funcionais, não-funcionais (desempenho, segurança, usabilidade) e restrições de sistema.
- **Especificação**: Redação de especificações de requisitos sem ambiguidades (`SRS`), com critérios claros de aceitação e pré/pós-condições.
- **Validação e Rastreabilidade**: Garantia de que cada requisito pode ser testado por uma suíte automatizada de testes e possui rastreabilidade bidirecional com o código-fonte.

### 2.2. KA 2: Design de Software (Software Design)
- **Arquitetura de Software**: Definição da estrutura global (Monólito Modular, Microserviços, Event-Driven, Arquitetura Hexagonal).
- **Design de Componentes & Interfaces**: Definição de contratos de API REST/gRPC/WebSocket estritamente tipados.
- **Padrões de Design (Design Patterns)**:
  - *Criacionais*: Singleton, Factory Method, Abstract Factory, Builder.
  - *Estruturais*: Adapter, Bridge, Composite, Decorator, Facade, Proxy.
  - *Comportamentais*: Chain of Responsibility, Command, Iterator, Observer, State, Strategy, Visitor.

### 2.3. KA 3: Construção de Software (Software Construction)
- **Minimização de Complexidade**: Código legível, auto-documentado, com funções pequenas e responsabilidade única (SRP).
- **Gestão de Dependências**: Declaração explícita de versões em ficheiros de bloqueio (`requirements.txt`, `package.json`).
- **Defesa Sintática & Tipagem**: Tipagem estrita com `mypy` / TypeScript e parsing AST estático antes de guardar em disco.

### 2.4. KA 4: Testes de Software (Software Testing)
- **Níveis de Teste**:
  - *Testes Unitários*: Testam funções isoladas com Mocks de I/O.
  - *Testes de Integração*: Testam a interação entre componentes (ex: Base de Dados + API + AsyncEventBus).
  - *Testes de Sistema / E2E*: Validação completa de trajetórias de utilizador via Chromium DevTools / Playwright.
- **Critérios de Cobertura**: Cobertura de ramos (*Branch Coverage*), condições limite (*Edge Cases*) e mutação de testes.

### 2.5. KA 5: Manutenção de Software (Software Maintenance)
- **Manutenção Corretiva**: Resolução de bugs e exceções detetadas em produção.
- **Manutenção Adaptativa**: Atualização para novas versões de frameworks ou bibliotecas sem quebrar contratos legados.
- **Manutenção Perfectiva & Refatoração**: Melhora da legibilidade e desempenho do código sem alterar o comportamento externo.

### 2.6. KA 6: Gestão de Configuração (Software Configuration Management)
- **Controlo de Versões (Git)**: Commits atómicos com mensagens convencionais (`feat`, `fix`, `docs`, `refactor`).
- **Gestão de Branches**: Estratégias Trunk-Based Development ou GitFlow.
- **Automação de Pipelines (CI/CD)**: Verificação automática de qualidade, testes e linting a cada commit.

### 2.7. KA 7: Qualidade de Software (Software Quality)
- **Atributos de Qualidade**: Fiabilidade, Manutenibilidade, Eficiência de Desempenho, Segurança e Portabilidade.
- **Revisão de Código Multi-Eixo**: Inspeção estática de vulnerabilidades, duplicação e complexidade ciclomática.

### 2.8. KA 8: Gestão de Engenharia de Software (Software Engineering Management)
- **Planeamento Incremental**: Decomposição de grandes objetivos em tarefas atómicas prioritárias com estimativa de âmbito.
- **Gestão de Risco**: Identificação prévia de pontos de falha e definição de estratégias de rollback automático.

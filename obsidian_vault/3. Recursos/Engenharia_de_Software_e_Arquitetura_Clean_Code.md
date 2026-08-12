# 📐 Manual de Engenharia de Software, Arquitetura Hexagonal & AST Refactoring

## 📌 1. Visão Geral
Este manual estabelece as diretivas de arquitetura de software, padrões de refatoração autónoma e análise de código estático por **Árvore de Sintaxe Abstrata (AST)** para governar a produção de código do **JARVIS OS**.

---

## 🏛️ 2. Arquitetura Hexagonal (Ports & Adapters)

### 2.1. Princípios de Separação de Camadas
A arquitetura de software deve ser organizada em 3 círculos concêntricos estritos:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CAMADA EXTERNA (Adapters & Infrastructure)              │
│  - FastAPI / WebSockets / CLI / SQLite / HTTP Clients                       │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                 CAMADA DE APLICAÇÃO (Use Cases & Services)            │  │
│  │  - ModelHarness / SwarmOrchestrator / PatchEngine                     │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │              CAMADA DE DOMÍNIO (Core Entities & Rules)          │  │  │
│  │  │  - Contracts / TaskProfile / ValidationResult / FinancialMetrics   │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

- **Core de Domínio (`Domain`)**: Contém entidades puras e estruturas imutáveis (`@dataclass(frozen=True)`). NUNCA depende de bibliotecas externas de I/O, bases de dados ou frameworks.
- **Portas (`Ports`)**: Interfaces abstratas de Python (`typing.Protocol` ou `abc.ABC`) que definem o contrato de serviço sem revelar o mecanismo de implementação.
- **Adaptadores (`Adapters`)**: Implementações concretas de portas (ex: `OllamaProvider`, `SQLiteRepository`, `FastAPIWebSocketHandler`).

---

## 🔬 3. Manipulação Estática de Código por Árvore de Sintaxe Abstrata (AST)

### 3.1. Parsing e Inspeção de Ficheiros Python
Antes de aplicar qualquer modificação cirúrgica a um ficheiro de código, o sistema analisa o AST nativo (`ast.parse`):
```python
import ast

def inspect_python_symbols(source_code: str) -> dict[str, list[str]]:
    tree = ast.parse(source_code)
    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    return {"classes": classes, "functions": functions}
```

### 3.2. Validação Sintática Pré-Gravação (AST Safety Gate)
Para impedir a persistência de ficheiros corrompidos ou com erros de sintaxe no disco:
1. O código modificado é submetido a `ast.parse(modified_code)`.
2. Se for lançada uma exceção `SyntaxError`, o patch é rejeitado na memória e a alteração é abortada sem tocar no sistema de ficheiros.

---

## 🧼 4. Padrões de Clean Code & Refatoração Contínua

### 4.1. Princípio da Responsabilidade Única (SRP)
Cada classe ou módulo deve ter apenas uma razão para mudar. Se uma classe lida com a comunicação de rede E a validação de esquemas E a persistência no disco, deve ser decomposta em 3 classes distintas.

### 4.2. Imutabilidade e Value Objects
- Preferir estruturas imutáveis para transferência de dados entre serviços.
- Objetos de valor devem ser comparados por valor e não por referência de memória.

### 4.3. Test-Driven Development (TDD Red-Green-Refactor)
1. **Red**: Escrever um teste unitário focado na nova funcionalidade que inicialmente falha.
2. **Green**: Escrever o código mínimo necessário para fazer o teste passar.
3. **Refactor**: Otimizar a clareza, desempenho e tipagem do código mantendo a totalidade dos testes verdes.

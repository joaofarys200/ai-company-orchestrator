---
type: concept
domain: software-engineering
difficulty: advanced
tags:
  - software-engineering
  - clean-code
  - solid
status: verified
---

# ðŸ“ Manual de Engenharia de Software, Arquitetura Hexagonal & AST Refactoring

## ðŸ“Œ 1. VisÃ£o Geral
Este manual estabelece as diretivas de arquitetura de software, padrÃµes de refatoraÃ§Ã£o autÃ³noma e anÃ¡lise de cÃ³digo estÃ¡tico por **Ãrvore de Sintaxe Abstrata (AST)** para governar a produÃ§Ã£o de cÃ³digo do **JARVIS OS**.

---

## ðŸ›ï¸ 2. Arquitetura Hexagonal (Ports & Adapters)

### 2.1. PrincÃ­pios de SeparaÃ§Ã£o de Camadas
A arquitetura de software deve ser organizada em 3 cÃ­rculos concÃªntricos estritos:

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    CAMADA EXTERNA (Adapters & Infrastructure)              â”‚
â”‚  - FastAPI / WebSockets / CLI / SQLite / HTTP Clients                       â”‚
â”‚                                                                             â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚
â”‚  â”‚                 CAMADA DE APLICAÃ‡ÃƒO (Use Cases & Services)            â”‚  â”‚
â”‚  â”‚  - ModelHarness / SwarmOrchestrator / PatchEngine                     â”‚  â”‚
â”‚  â”‚                                                                       â”‚  â”‚
â”‚  â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚  â”‚
â”‚  â”‚  â”‚              CAMADA DE DOMÃNIO (Core Entities & Rules)          â”‚  â”‚  â”‚
â”‚  â”‚  â”‚  - Contracts / TaskProfile / ValidationResult / FinancialMetrics   â”‚  â”‚  â”‚
â”‚  â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚  â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

- **Core de DomÃ­nio (`Domain`)**: ContÃ©m entidades puras e estruturas imutÃ¡veis (`@dataclass(frozen=True)`). NUNCA depende de bibliotecas externas de I/O, bases de dados ou frameworks.
- **Portas (`Ports`)**: Interfaces abstratas de Python (`typing.Protocol` ou `abc.ABC`) que definem o contrato de serviÃ§o sem revelar o mecanismo de implementaÃ§Ã£o.
- **Adaptadores (`Adapters`)**: ImplementaÃ§Ãµes concretas de portas (ex: `OllamaProvider`, `SQLiteRepository`, `FastAPIWebSocketHandler`).

---

## ðŸ”¬ 3. ManipulaÃ§Ã£o EstÃ¡tica de CÃ³digo por Ãrvore de Sintaxe Abstrata (AST)

### 3.1. Parsing e InspeÃ§Ã£o de Ficheiros Python
Antes de aplicar qualquer modificaÃ§Ã£o cirÃºrgica a um ficheiro de cÃ³digo, o sistema analisa o AST nativo (`ast.parse`):
```python
import ast

def inspect_python_symbols(source_code: str) -> dict[str, list[str]]:
    tree = ast.parse(source_code)
    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    return {"classes": classes, "functions": functions}
```

### 3.2. ValidaÃ§Ã£o SintÃ¡tica PrÃ©-GravaÃ§Ã£o (AST Safety Gate)
Para impedir a persistÃªncia de ficheiros corrompidos ou com erros de sintaxe no disco:
1. O cÃ³digo modificado Ã© submetido a `ast.parse(modified_code)`.
2. Se for lanÃ§ada uma exceÃ§Ã£o `SyntaxError`, o patch Ã© rejeitado na memÃ³ria e a alteraÃ§Ã£o Ã© abortada sem tocar no sistema de ficheiros.

---

## ðŸ§¼ 4. PadrÃµes de Clean Code & RefatoraÃ§Ã£o ContÃ­nua

### 4.1. PrincÃ­pio da Responsabilidade Ãšnica (SRP)
Cada classe ou mÃ³dulo deve ter apenas uma razÃ£o para mudar. Se uma classe lida com a comunicaÃ§Ã£o de rede E a validaÃ§Ã£o de esquemas E a persistÃªncia no disco, deve ser decomposta em 3 classes distintas.

### 4.2. Imutabilidade e Value Objects
- Preferir estruturas imutÃ¡veis para transferÃªncia de dados entre serviÃ§os.
- Objetos de valor devem ser comparados por valor e nÃ£o por referÃªncia de memÃ³ria.

### 4.3. Test-Driven Development (TDD Red-Green-Refactor)
1. **Red**: Escrever um teste unitÃ¡rio focado na nova funcionalidade que inicialmente falha.
2. **Green**: Escrever o cÃ³digo mÃ­nimo necessÃ¡rio para fazer o teste passar.
3. **Refactor**: Otimizar a clareza, desempenho e tipagem do cÃ³digo mantendo a totalidade dos testes verdes.


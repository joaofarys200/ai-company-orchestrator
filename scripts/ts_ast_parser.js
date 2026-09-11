/**
 * JARVIS OS — Phase 39.1: Node.js TypeScript Compiler AST Bridge
 * High-performance AST extractor using the official TypeScript Compiler API.
 */

const fs = require('fs');
const path = require('path');

let ts;
try {
  ts = require(path.resolve(__dirname, '../frontend/node_modules/typescript'));
} catch (e) {
  try {
    ts = require('typescript');
  } catch (err) {
    console.error('TypeScript package not found.');
    process.exit(1);
  }
}

function parseSource(filePath, sourceCode) {
  const sf = ts.createSourceFile(
    filePath,
    sourceCode,
    ts.ScriptTarget.Latest,
    true,
    filePath.endsWith('.tsx') || filePath.endsWith('.jsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
  );

  const imports = [];
  const exports = [];
  const symbols = [];

  function visit(node) {
    // 1. Import Declarations
    if (ts.isImportDeclaration(node)) {
      const moduleSpecifier = node.moduleSpecifier ? node.moduleSpecifier.text : '';
      const lineNo = sf.getLineAndCharacterOfPosition(node.getStart()).line + 1;
      const isTypeOnly = !!node.importClause?.isTypeOnly;

      let defaultImport = null;
      let namespaceImport = null;
      const namedSymbols = [];

      if (node.importClause) {
        if (node.importClause.name) {
          defaultImport = node.importClause.name.text;
        }
        if (node.importClause.namedBindings) {
          if (ts.isNamespaceImport(node.importClause.namedBindings)) {
            namespaceImport = node.importClause.namedBindings.name.text;
          } else if (ts.isNamedImports(node.importClause.namedBindings)) {
            for (const el of node.importClause.namedBindings.elements) {
              namedSymbols.push(el.propertyName ? el.propertyName.text : el.name.text);
            }
          }
        }
      }

      imports.push({
        source_file: filePath,
        module_specifier: moduleSpecifier,
        imported_symbols: namedSymbols,
        default_import: defaultImport,
        namespace_import: namespaceImport,
        is_type_only: isTypeOnly,
        is_relative: moduleSpecifier.startsWith('.'),
        is_dynamic: false,
        line_number: lineNo,
        confidence: 'DETERMINISTIC',
        boundary: moduleSpecifier.startsWith('.') ? 'INTRA_PACKAGE' : 'EXTERNAL_PACKAGE',
      });
    }

    // 2. Dynamic Import or require()
    if (ts.isCallExpression(node)) {
      if (node.expression.kind === ts.SyntaxKind.ImportKeyword && node.arguments.length > 0) {
        const arg = node.arguments[0];
        if (ts.isStringLiteral(arg)) {
          const lineNo = sf.getLineAndCharacterOfPosition(node.getStart()).line + 1;
          imports.push({
            source_file: filePath,
            module_specifier: arg.text,
            imported_symbols: [],
            is_dynamic: true,
            is_relative: arg.text.startsWith('.'),
            line_number: lineNo,
            confidence: 'UNCERTAIN',
            boundary: arg.text.startsWith('.') ? 'INTRA_PACKAGE' : 'EXTERNAL_PACKAGE',
          });
        }
      }
    }

    // 3. Export Declarations (Named, Re-export, Star Export)
    if (ts.isExportDeclaration(node)) {
      const lineNo = sf.getLineAndCharacterOfPosition(node.getStart()).line + 1;
      const isTypeOnly = !!node.isTypeOnly;
      const moduleSpecifier = node.moduleSpecifier ? node.moduleSpecifier.text : null;
      const isReExport = !!moduleSpecifier;

      if (!node.exportClause && moduleSpecifier) {
        // export * from '...'
        exports.push({
          source_file: filePath,
          exported_symbols: [],
          is_default: false,
          is_re_export: true,
          re_export_source: moduleSpecifier,
          is_star_export: true,
          is_type_only: isTypeOnly,
          line_number: lineNo,
        });
      } else if (node.exportClause && ts.isNamedExports(node.exportClause)) {
        const syms = [];
        let hasDefault = false;
        for (const el of node.exportClause.elements) {
          const exportedName = el.name.text;
          if (exportedName === 'default') hasDefault = true;
          syms.push(exportedName);
        }
        exports.push({
          source_file: filePath,
          exported_symbols: syms,
          is_default: hasDefault,
          is_re_export: isReExport,
          re_export_source: moduleSpecifier,
          is_star_export: false,
          is_type_only: isTypeOnly,
          line_number: lineNo,
        });
      } else if (node.exportClause && ts.isNamespaceExport(node.exportClause)) {
        // export * as ns from '...'
        exports.push({
          source_file: filePath,
          exported_symbols: [],
          is_default: false,
          is_re_export: true,
          re_export_source: moduleSpecifier,
          is_star_export: true,
          star_namespace: node.exportClause.name.text,
          is_type_only: isTypeOnly,
          line_number: lineNo,
        });
      }
    }

    // 4. Default Export Assignment: export default ...
    if (ts.isExportAssignment(node)) {
      const lineNo = sf.getLineAndCharacterOfPosition(node.getStart()).line + 1;
      exports.push({
        source_file: filePath,
        exported_symbols: ['default'],
        is_default: true,
        is_re_export: false,
        line_number: lineNo,
      });
    }

    // 5. Function Declarations
    if (ts.isFunctionDeclaration(node) && node.name) {
      const lineNo = sf.getLineAndCharacterOfPosition(node.getStart()).line + 1;
      const isExported = hasExportModifier(node);
      const isDefault = hasDefaultModifier(node);
      symbols.push({
        name: node.name.text,
        symbol_type: 'FUNCTION',
        file_path: filePath,
        line_number: lineNo,
        is_exported: isExported,
        is_default: isDefault,
        signature: `function ${node.name.text}`,
      });
    }

    // 6. Class Declarations
    if (ts.isClassDeclaration(node) && node.name) {
      const lineNo = sf.getLineAndCharacterOfPosition(node.getStart()).line + 1;
      const isExported = hasExportModifier(node);
      symbols.push({
        name: node.name.text,
        symbol_type: 'CLASS',
        file_path: filePath,
        line_number: lineNo,
        is_exported: isExported,
        signature: `class ${node.name.text}`,
      });
    }

    // 7. Interface & Type Alias Declarations
    if (ts.isInterfaceDeclaration(node)) {
      const lineNo = sf.getLineAndCharacterOfPosition(node.getStart()).line + 1;
      const isExported = hasExportModifier(node);
      symbols.push({
        name: node.name.text,
        symbol_type: 'INTERFACE',
        file_path: filePath,
        line_number: lineNo,
        is_exported: isExported,
        signature: `interface ${node.name.text}`,
      });
    }
    if (ts.isTypeAliasDeclaration(node)) {
      const lineNo = sf.getLineAndCharacterOfPosition(node.getStart()).line + 1;
      const isExported = hasExportModifier(node);
      symbols.push({
        name: node.name.text,
        symbol_type: 'TYPE_ALIAS',
        file_path: filePath,
        line_number: lineNo,
        is_exported: isExported,
        signature: `type ${node.name.text}`,
      });
    }

    // 8. Enums
    if (ts.isEnumDeclaration(node)) {
      const lineNo = sf.getLineAndCharacterOfPosition(node.getStart()).line + 1;
      const isExported = hasExportModifier(node);
      symbols.push({
        name: node.name.text,
        symbol_type: 'ENUM',
        file_path: filePath,
        line_number: lineNo,
        is_exported: isExported,
        signature: `enum ${node.name.text}`,
      });
    }

    // 9. Variable Statements (Constants & React Components)
    if (ts.isVariableStatement(node)) {
      const lineNo = sf.getLineAndCharacterOfPosition(node.getStart()).line + 1;
      const isExported = hasExportModifier(node);
      for (const decl of node.declarationList.declarations) {
        if (ts.isIdentifier(decl.name)) {
          const symName = decl.name.text;
          const typeStr = decl.type ? decl.type.getText(sf) : '';
          const isComponent = typeStr.includes('React.FC') || typeStr.includes('FC<') || (symName[0] === symName[0].toUpperCase() && (filePath.endsWith('.tsx') || filePath.endsWith('.jsx')));
          symbols.push({
            name: symName,
            symbol_type: isComponent ? 'REACT_COMPONENT' : 'CONSTANT',
            file_path: filePath,
            line_number: lineNo,
            is_exported: isExported,
            signature: `const ${symName}`,
          });
        }
      }
    }

    ts.forEachChild(node, visit);
  }

  ts.forEachChild(sf, visit);
  return { imports, exports, symbols };
}

function hasExportModifier(node) {
  return node.modifiers && node.modifiers.some(m => m.kind === ts.SyntaxKind.ExportKeyword);
}

function hasDefaultModifier(node) {
  return node.modifiers && node.modifiers.some(m => m.kind === ts.SyntaxKind.DefaultKeyword);
}

// CLI handler
if (require.main === module) {
  const args = process.argv.slice(2);
  if (args[0] === '--single' && args[1]) {
    const filePath = args[1];
    let content = '';
    process.stdin.setEncoding('utf-8');
    process.stdin.on('data', chunk => { content += chunk; });
    process.stdin.on('end', () => {
      try {
        const result = parseSource(filePath, content);
        console.log(JSON.stringify(result));
      } catch (err) {
        console.error(err);
        process.exit(1);
      }
    });
  } else {
    console.error('Usage: node ts_ast_parser.js --single <filepath>');
    process.exit(1);
  }
}

module.exports = { parseSource };

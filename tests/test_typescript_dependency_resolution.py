"""
JARVIS OS — Phase 39.1: 24 Required Test Cases for TypeScript Dependency Resolution
Implements the exact 24 test cases mandated in Section 20 of Phase 39.1 specification.
"""

import os
import shutil
import tempfile
import pytest

from intelligence.typescript_dependency.cache import TypeScriptDependencyCache
from intelligence.typescript_dependency.graph import NormalizedTypeScriptGraph
from intelligence.typescript_dependency.index import TypeScriptDependencyService
from intelligence.typescript_dependency.models import (
    BoundaryType,
    ConfidenceClass,
    TypeScriptExport,
    TypeScriptImport,
)
from intelligence.typescript_dependency.parser import TypeScriptSyntaxParser
from intelligence.typescript_dependency.resolver import TypeScriptImportResolver


@pytest.fixture
def temp_ts_workspace():
    """Creates a temporary workspace with full tsconfig, package.json, and ts files."""
    tmp = tempfile.mkdtemp(prefix="jarvis_ts_test_")
    src = os.path.join(tmp, "src")
    components = os.path.join(src, "components")
    utils = os.path.join(src, "utils")
    os.makedirs(components, exist_ok=True)
    os.makedirs(utils, exist_ok=True)

    # tsconfig.json with aliases
    tsconfig = """{
      "compilerOptions": {
        "baseUrl": ".",
        "paths": {
          "@/*": ["src/*"],
          "@components/*": ["src/components/*"]
        }
      }
    }"""
    with open(os.path.join(tmp, "tsconfig.json"), "w", encoding="utf-8") as f:
        f.write(tsconfig)

    # package.json
    pkg = """{
      "name": "test-frontend",
      "version": "1.0.0",
      "exports": {
        "./utils": "./src/utils/index.ts"
      }
    }"""
    with open(os.path.join(tmp, "package.json"), "w", encoding="utf-8") as f:
        f.write(pkg)

    yield tmp, src, components, utils
    shutil.rmtree(tmp, ignore_errors=True)


def test_01_relative_import(temp_ts_workspace):
    """Case 1: Standard relative import ./foo."""
    tmp, src, _, _ = temp_ts_workspace
    with open(os.path.join(src, "foo.ts"), "w", encoding="utf-8") as f:
        f.write("export function foo() { return 1; }")
    with open(os.path.join(src, "bar.ts"), "w", encoding="utf-8") as f:
        f.write("import { foo } from './foo';")

    resolver = TypeScriptImportResolver(tmp)
    resolver.set_known_files({"src/foo.ts", "src/bar.ts"})
    target, conf, boundary = resolver.resolve_import("src/bar.ts", "./foo")
    assert target == "src/foo.ts"
    assert conf == ConfidenceClass.DETERMINISTIC
    assert boundary == BoundaryType.INTRA_PACKAGE


def test_02_nested_relative_import(temp_ts_workspace):
    """Case 2: Nested relative import ../../foo."""
    tmp, src, components, _ = temp_ts_workspace
    sub = os.path.join(components, "buttons", "primary")
    os.makedirs(sub, exist_ok=True)
    with open(os.path.join(src, "theme.ts"), "w", encoding="utf-8") as f:
        f.write("export const theme = 'dark';")
    with open(os.path.join(sub, "Button.tsx"), "w", encoding="utf-8") as f:
        f.write("import { theme } from '../../../theme';")

    resolver = TypeScriptImportResolver(tmp)
    resolver.set_known_files({"src/theme.ts", "src/components/buttons/primary/Button.tsx"})
    target, conf, _ = resolver.resolve_import("src/components/buttons/primary/Button.tsx", "../../../theme")
    assert target == "src/theme.ts"
    assert conf == ConfidenceClass.DETERMINISTIC


def test_03_index_barrel(temp_ts_workspace):
    """Case 3: Directory index barrel resolution ./components -> ./components/index.ts."""
    tmp, src, components, _ = temp_ts_workspace
    with open(os.path.join(components, "index.ts"), "w", encoding="utf-8") as f:
        f.write("export const Card = () => null;")
    with open(os.path.join(src, "App.tsx"), "w", encoding="utf-8") as f:
        f.write("import { Card } from './components';")

    resolver = TypeScriptImportResolver(tmp)
    resolver.set_known_files({"src/components/index.ts", "src/App.tsx"})
    target, conf, _ = resolver.resolve_import("src/App.tsx", "./components")
    assert target == "src/components/index.ts"


def test_04_named_export():
    """Case 4: Named export syntax."""
    code = "export { foo, bar as myBar };"
    imports, exports, _ = TypeScriptSyntaxParser.parse_content_python(code, "test.ts")
    assert len(exports) == 1
    assert "foo" in exports[0].exported_symbols
    assert "myBar" in exports[0].exported_symbols


def test_05_re_export():
    """Case 5: Re-export specific symbols export { X } from './foo'."""
    code = "export { Modal, Header } from './elements';"
    imports, exports, _ = TypeScriptSyntaxParser.parse_content_python(code, "test.ts")
    assert len(exports) == 1
    assert exports[0].is_re_export is True
    assert exports[0].re_export_source == "./elements"
    assert "Modal" in exports[0].exported_symbols
    assert "Header" in exports[0].exported_symbols


def test_06_export_star():
    """Case 6: Export star export * from './foo'."""
    code = "export * from './widgets';"
    imports, exports, _ = TypeScriptSyntaxParser.parse_content_python(code, "index.ts")
    assert len(exports) == 1
    assert exports[0].is_star_export is True
    assert exports[0].re_export_source == "./widgets"


def test_07_default_export():
    """Case 7: Default export export default X."""
    code = "export default function MainApp() { return null; }"
    imports, exports, symbols = TypeScriptSyntaxParser.parse_content_python(code, "App.tsx")
    assert any(e.is_default for e in exports)
    assert any(s.name == "MainApp" for s in symbols)


def test_08_namespace_import():
    """Case 8: Namespace import import * as X from './foo'."""
    code = "import * as Utils from './utils';"
    imports, _, _ = TypeScriptSyntaxParser.parse_content_python(code, "main.ts")
    assert len(imports) == 1
    assert imports[0].namespace_import == "Utils"
    assert imports[0].module_specifier == "./utils"


def test_09_side_effect_import():
    """Case 9: Side effect import import './style.css'."""
    code = "import './global.css';"
    imports, _, _ = TypeScriptSyntaxParser.parse_content_python(code, "index.tsx")
    assert len(imports) == 1
    assert imports[0].module_specifier == "./global.css"
    assert len(imports[0].imported_symbols) == 0


def test_10_tsconfig_alias(temp_ts_workspace):
    """Case 10: Path alias resolution @components/Button."""
    tmp, src, components, _ = temp_ts_workspace
    with open(os.path.join(components, "Button.tsx"), "w", encoding="utf-8") as f:
        f.write("export const Button = () => null;")
    with open(os.path.join(src, "App.tsx"), "w", encoding="utf-8") as f:
        f.write("import { Button } from '@components/Button';")

    resolver = TypeScriptImportResolver(tmp)
    resolver.set_known_files({"src/components/Button.tsx", "src/App.tsx"})
    target, conf, _ = resolver.resolve_import("src/App.tsx", "@components/Button")
    assert target == "src/components/Button.tsx"
    assert conf == ConfidenceClass.DETERMINISTIC


def test_11_base_url(temp_ts_workspace):
    """Case 11: BaseUrl resolution @/*."""
    tmp, src, _, utils = temp_ts_workspace
    with open(os.path.join(utils, "helpers.ts"), "w", encoding="utf-8") as f:
        f.write("export const noop = () => {};")

    resolver = TypeScriptImportResolver(tmp)
    resolver.set_known_files({"src/utils/helpers.ts", "src/App.tsx"})
    target, conf, _ = resolver.resolve_import("src/App.tsx", "@/utils/helpers")
    assert target == "src/utils/helpers.ts"


def test_12_workspace_package(temp_ts_workspace):
    """Case 12: Monorepo workspace package discovery."""
    tmp, src, _, _ = temp_ts_workspace
    pkg2_dir = os.path.join(tmp, "packages", "ui")
    os.makedirs(pkg2_dir, exist_ok=True)
    with open(os.path.join(pkg2_dir, "package.json"), "w", encoding="utf-8") as f:
        f.write('{"name": "@test/ui", "main": "./index.ts"}')
    with open(os.path.join(pkg2_dir, "index.ts"), "w", encoding="utf-8") as f:
        f.write("export const Widget = () => null;")

    resolver = TypeScriptImportResolver(tmp)
    resolver.set_known_files({"packages/ui/index.ts", "src/App.tsx"})
    target, conf, boundary = resolver.resolve_import("src/App.tsx", "@test/ui")
    assert target == "packages/ui/index.ts"
    assert boundary == BoundaryType.INTER_PACKAGE


def test_13_package_exports(temp_ts_workspace):
    """Case 13: Package.json subpath exports resolution."""
    tmp, src, _, utils = temp_ts_workspace
    with open(os.path.join(utils, "index.ts"), "w", encoding="utf-8") as f:
        f.write("export const u = 1;")

    resolver = TypeScriptImportResolver(tmp)
    resolver.set_known_files({"src/utils/index.ts", "src/App.tsx"})
    target, _, _ = resolver.resolve_import("src/App.tsx", "test-frontend/utils")
    assert target == "src/utils/index.ts"


def test_14_dynamic_import():
    """Case 14: Dynamic import() call expression."""
    code = "const module = await import('./lazyComponent');"
    imports, _, _ = TypeScriptSyntaxParser.parse_content_python(code, "Router.tsx")
    assert len(imports) == 1
    assert imports[0].is_dynamic is True
    assert imports[0].module_specifier == "./lazyComponent"
    assert imports[0].confidence == ConfidenceClass.UNCERTAIN


def test_15_unresolved_dynamic_dependency(temp_ts_workspace):
    """Case 15: Unresolved dynamic dependency flagged as UNCERTAIN."""
    tmp, src, _, _ = temp_ts_workspace
    resolver = TypeScriptImportResolver(tmp)
    target, conf, boundary = resolver.resolve_import("src/Dynamic.ts", "./missing_runtime_file")
    assert target is None
    assert conf == ConfidenceClass.UNCERTAIN


def test_16_file_rename(temp_ts_workspace):
    """Case 16: File rename removes stale path and indexes new path."""
    tmp, src, _, _ = temp_ts_workspace
    svc = TypeScriptDependencyService(tmp)
    old_file = os.path.join(src, "OldName.ts")
    new_file = os.path.join(src, "NewName.ts")

    with open(old_file, "w", encoding="utf-8") as f:
        f.write("export const val = 42;")
    svc.index_workspace()
    assert "src/OldName.ts" in svc.graph.nodes

    # Rename file
    os.rename(old_file, new_file)
    svc.cache.remove("src/OldName.ts")
    svc.index_workspace(force_reparse=True)
    assert "src/OldName.ts" not in svc.graph.nodes
    assert "src/NewName.ts" in svc.graph.nodes


def test_17_file_deletion(temp_ts_workspace):
    """Case 17: File deletion cleans references."""
    tmp, src, _, _ = temp_ts_workspace
    svc = TypeScriptDependencyService(tmp)
    file_to_del = os.path.join(src, "ToBeDeleted.ts")
    with open(file_to_del, "w", encoding="utf-8") as f:
        f.write("export const dead = true;")
    svc.index_workspace()
    assert "src/ToBeDeleted.ts" in svc.graph.nodes

    os.remove(file_to_del)
    svc.cache.remove("src/ToBeDeleted.ts")
    svc.index_workspace(force_reparse=True)
    assert "src/ToBeDeleted.ts" not in svc.graph.nodes


def test_18_tsconfig_modification(temp_ts_workspace):
    """Case 18: Tsconfig modification invalidates aliases."""
    tmp, src, _, utils = temp_ts_workspace
    with open(os.path.join(utils, "math.ts"), "w", encoding="utf-8") as f:
        f.write("export const add = (a: number, b: number) => a + b;")

    resolver = TypeScriptImportResolver(tmp)
    resolver.set_known_files({"src/utils/math.ts"})
    target, _, _ = resolver.resolve_import("src/index.ts", "@/utils/math")
    assert target == "src/utils/math.ts"

    # Modify tsconfig with a new alias @math/*
    new_cfg = """{
      "compilerOptions": {
        "baseUrl": ".",
        "paths": {
          "@math/*": ["src/utils/*"]
        }
      }
    }"""
    with open(os.path.join(tmp, "tsconfig.json"), "w", encoding="utf-8") as f:
        f.write(new_cfg)

    new_resolver = TypeScriptImportResolver(tmp)
    new_resolver.set_known_files({"src/utils/math.ts"})
    target_new, _, _ = new_resolver.resolve_import("src/index.ts", "@math/math")
    assert target_new == "src/utils/math.ts"


def test_19_package_json_modification(temp_ts_workspace):
    """Case 19: Package.json modification updates package exports."""
    tmp, _, _, _ = temp_ts_workspace
    new_pkg = '{"name": "modified-package", "version": "2.0.0"}'
    with open(os.path.join(tmp, "package.json"), "w", encoding="utf-8") as f:
        f.write(new_pkg)
    resolver = TypeScriptImportResolver(tmp)
    assert "modified-package" in resolver.packages


def test_20_circular_dependency(temp_ts_workspace):
    """Case 20: Circular dependency detected properly."""
    tmp, src, _, _ = temp_ts_workspace
    with open(os.path.join(src, "circleA.ts"), "w", encoding="utf-8") as f:
        f.write("import { b } from './circleB'; export const a = 1;")
    with open(os.path.join(src, "circleB.ts"), "w", encoding="utf-8") as f:
        f.write("import { a } from './circleA'; export const b = 2;")

    svc = TypeScriptDependencyService(tmp)
    graph = svc.index_workspace(force_reparse=True)
    cycles = graph.detect_circular_dependencies()
    assert len(cycles) > 0
    cycle_files = {node for cyc in cycles for node in cyc}
    assert "src/circleA.ts" in cycle_files
    assert "src/circleB.ts" in cycle_files


def test_21_type_only_import():
    """Case 21: Type-only import flag."""
    code = "import type { AppProps } from './types';"
    imports, _, _ = TypeScriptSyntaxParser.parse_content_python(code, "App.tsx")
    assert len(imports) == 1
    assert imports[0].is_type_only is True


def test_22_tsx_component_import(temp_ts_workspace):
    """Case 22: TSX component import."""
    tmp, src, components, _ = temp_ts_workspace
    with open(os.path.join(components, "Panel.tsx"), "w", encoding="utf-8") as f:
        f.write("export const Panel: React.FC = () => <div>Panel</div>;")
    with open(os.path.join(src, "App.tsx"), "w", encoding="utf-8") as f:
        f.write("import { Panel } from './components/Panel';")

    resolver = TypeScriptImportResolver(tmp)
    resolver.set_known_files({"src/components/Panel.tsx", "src/App.tsx"})
    target, conf, _ = resolver.resolve_import("src/App.tsx", "./components/Panel")
    assert target == "src/components/Panel.tsx"


def test_23_chained_barrel(temp_ts_workspace):
    """Case 23: Chained barrel resolution B -> index -> A."""
    tmp, src, components, _ = temp_ts_workspace
    with open(os.path.join(components, "RealButton.tsx"), "w", encoding="utf-8") as f:
        f.write("export function RealButton() { return '<button/>'; }")
    with open(os.path.join(components, "index.ts"), "w", encoding="utf-8") as f:
        f.write("export { RealButton } from './RealButton';")
    with open(os.path.join(src, "Consumer.tsx"), "w", encoding="utf-8") as f:
        f.write("import { RealButton } from './components';")

    svc = TypeScriptDependencyService(tmp)
    graph = svc.index_workspace(force_reparse=True)
    # Origin of RealButton should resolve to src/components/RealButton.tsx
    origin = graph.resolve_symbol_origin("src/components/index.ts", "RealButton")
    assert origin is not None
    assert origin[0] == "src/components/RealButton.tsx"
    assert origin[1].name == "RealButton"


def test_24_cross_package_dependency(temp_ts_workspace):
    """Case 24: Cross-package dependency boundary classification."""
    tmp, src, _, _ = temp_ts_workspace
    resolver = TypeScriptImportResolver(tmp)
    # External node_modules
    _, _, boundary_ext = resolver.resolve_import("src/App.tsx", "react")
    assert boundary_ext == BoundaryType.EXTERNAL_PACKAGE
    # Relative local
    with open(os.path.join(src, "local.ts"), "w", encoding="utf-8") as f:
        f.write("export const l = 1;")
    resolver.set_known_files({"src/local.ts", "src/App.tsx"})
    _, _, boundary_local = resolver.resolve_import("src/App.tsx", "./local")
    assert boundary_local == BoundaryType.INTRA_PACKAGE

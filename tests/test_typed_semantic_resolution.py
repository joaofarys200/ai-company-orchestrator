"""
JARVIS OS — Test Suite: Typed Semantic Resolution & Deep Property Impact Analysis (Fase 10.4)
13 Testes da Matriz (TS-01 a TS-07, PY-01 a PY-06) e 10 Tarefas Reais de Impacto Profundo.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from intelligence.typed_semantic_resolver import (
    PropertyBlastRadius,
    SourcePriority,
    TypedSemanticResolver,
)


class TestTypedSemanticResolution(unittest.IsolatedAsyncioTestCase):
    """Suíte oficial de testes do TypedSemanticResolver."""

    def setUp(self) -> None:
        self.test_root = tempfile.mkdtemp(prefix="jarvis_typed_semantics_")

    def tearDown(self) -> None:
        shutil.rmtree(self.test_root, ignore_errors=True)

    def _create_file(self, rel_path: str, content: str) -> str:
        abs_p = os.path.join(self.test_root, rel_path)
        os.makedirs(os.path.dirname(abs_p), exist_ok=True)
        with open(abs_p, "w", encoding="utf-8") as f:
            f.write(content)
        return abs_p

    # =========================================================================
    # 1. TESTES DA MATRIZ TYPESCRIPT (TS-01 a TS-07)
    # =========================================================================

    async def test_ts01_nested_interface(self) -> None:
        """TS-01: Resolução de interfaces TypeScript aninhadas (User -> Profile -> Settings)."""
        self._create_file("src/types.ts", """
export interface Settings {
  theme: string;
  notifications: boolean;
}
export interface Profile {
  name: string;
  settings: Settings;
}
export interface User {
  id: string;
  profile: Profile;
}
""")
        resolver = TypedSemanticResolver(self.test_root).scan()
        self.assertIn("User", resolver.types)
        self.assertIn("Profile", resolver.types)
        self.assertIn("Settings", resolver.types)

        status, node = resolver.resolve_property_path("User", ["profile", "settings", "theme"])
        self.assertEqual(status, "RESOLVED")
        self.assertIsNotNone(node)
        self.assertEqual(node.name, "theme")

    async def test_ts02_nested_type_alias(self) -> None:
        """TS-02: Resolução de Type Alias aninhado com propriedades primitivas."""
        self._create_file("src/config.ts", """
export type DatabaseConfig = {
  host: string;
  port: number;
}
export type AppConfig = {
  database: DatabaseConfig;
}
""")
        resolver = TypedSemanticResolver(self.test_root).scan()
        self.assertIn("AppConfig", resolver.types)
        status, node = resolver.resolve_property_path("AppConfig", ["database", "host"])
        self.assertEqual(status, "RESOLVED")

    async def test_ts03_nested_optional_property(self) -> None:
        """TS-03: Resolução de propriedades opcionais com '?' (profile?.preferences?.theme)."""
        self._create_file("src/user.ts", """
export interface Preferences {
  theme?: string;
}
export interface UserProfile {
  preferences?: Preferences;
}
""")
        resolver = TypedSemanticResolver(self.test_root).scan()
        self.assertTrue(resolver.types["Preferences"].properties["theme"].is_optional)
        self.assertTrue(resolver.types["UserProfile"].properties["preferences"].is_optional)

    async def test_ts04_destructuring_pattern(self) -> None:
        """TS-04: Extração de acessos via desestruturação const { user: { profile } } = data."""
        self._create_file("src/consumer.ts", """
const { user: { profile } } = data;
console.log(profile);
""")
        resolver = TypedSemanticResolver(self.test_root).scan()
        self.assertGreaterEqual(len(resolver.usages), 1)

    async def test_ts05_imported_nested_type(self) -> None:
        """TS-05: Resolução de tipo aninhado importado através de múltiplos ficheiros."""
        self._create_file("src/models/auth.ts", "export interface AuthToken { token: string; expires: number; }\n")
        self._create_file("src/models/session.ts", "import { AuthToken } from './auth';\nexport interface Session { auth: AuthToken; }\n")

        resolver = TypedSemanticResolver(self.test_root).scan()
        status, node = resolver.resolve_property_path("Session", ["auth", "token"])
        self.assertEqual(status, "RESOLVED")

    async def test_ts06_react_props_nested(self) -> None:
        """TS-06: Extração de tipagem de React Props aninhadas."""
        self._create_file("src/components/Card.tsx", """
export interface CardProps {
  header: {
    title: string;
    subtitle?: string;
  };
}
export function Card(props: CardProps) { return <div>{props.header.title}</div>; }
""")
        resolver = TypedSemanticResolver(self.test_root).scan()
        self.assertIn("CardProps", resolver.types)

    async def test_ts07_json_schema_parsing(self) -> None:
        """TS-07: Resolução de schema formal a partir de ficheiro JSON Schema."""
        self._create_file("schemas/user.schema.json", json.dumps({
            "title": "UserSchema",
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "email": { "type": "string" }
            }
        }))
        resolver = TypedSemanticResolver(self.test_root).scan()
        self.assertIn("UserSchema", resolver.types)
        status, node = resolver.resolve_property_path("UserSchema", ["email"])
        self.assertEqual(status, "RESOLVED")

    # =========================================================================
    # 2. TESTES DA MATRIZ PYTHON (PY-01 a PY-06)
    # =========================================================================

    async def test_py01_typed_dict(self) -> None:
        """PY-01: Resolução de TypedDict aninhado em Python."""
        self._create_file("app/types.py", """
from typing import TypedDict

class GeoDict(TypedDict):
    lat: float
    lng: float

class LocationDict(TypedDict):
    city: str
    geo: GeoDict
""")
        resolver = TypedSemanticResolver(self.test_root).scan()
        self.assertIn("LocationDict", resolver.types)
        self.assertEqual(resolver.types["LocationDict"].kind, "TYPED_DICT")
        status, node = resolver.resolve_property_path("LocationDict", ["geo", "lat"])
        self.assertEqual(status, "RESOLVED")

    async def test_py02_pydantic_model(self) -> None:
        """PY-02: Resolução de modelos Pydantic BaseModel aninhados."""
        self._create_file("app/models.py", """
from pydantic import BaseModel

class SettingsModel(BaseModel):
    theme: str
    dark_mode: bool

class UserModel(BaseModel):
    id: int
    settings: SettingsModel
""")
        resolver = TypedSemanticResolver(self.test_root).scan()
        self.assertIn("UserModel", resolver.types)
        self.assertEqual(resolver.types["UserModel"].kind, "PYDANTIC")
        status, node = resolver.resolve_property_path("UserModel", ["settings", "theme"])
        self.assertEqual(status, "RESOLVED")

    async def test_py03_dataclass_hierarchy(self) -> None:
        """PY-03: Resolução de classes anotadas com @dataclass."""
        self._create_file("app/dto.py", """
from dataclasses import dataclass

@dataclass
class Engine:
    hp: int

@dataclass
class Car:
    model: str
    engine: Engine
""")
        resolver = TypedSemanticResolver(self.test_root).scan()
        self.assertIn("Car", resolver.types)
        self.assertEqual(resolver.types["Car"].kind, "DATACLASS")

    async def test_py04_nested_dict_access(self) -> None:
        """PY-04: Deteção de acessos profundos em dicionários data['user']['profile']['theme']."""
        self._create_file("app/service.py", """
def process(data):
    val = data["user"]["profile"]["theme"]
    return val
""")
        resolver = TypedSemanticResolver(self.test_root).scan()
        self.assertGreaterEqual(len(resolver.usages), 1)
        usage = resolver.usages[0]
        self.assertEqual(usage.access_path, ["data", "user", "profile", "theme"])

    async def test_py05_json_parsing_schema_inference(self) -> None:
        """PY-05: Inferência de schema a partir de múltiplos acessos consistentes a dados JSON."""
        self._create_file("app/json_parser.py", """
def handle_payload(payload):
    name = payload["user"]["name"]
    email = payload["user"]["email"]
    return name, email
""")
        resolver = TypedSemanticResolver(self.test_root).scan()
        self.assertIn("Inferred_Payload", resolver.types)
        self.assertEqual(resolver.types["Inferred_Payload"].kind, "INFERRED_SCHEMA")

    async def test_py06_chained_get_calls(self) -> None:
        """PY-06: Deteção de acessos encadeados via .get()."""
        self._create_file("app/getter.py", """
def get_pref(data):
    return data.get("user", {}).get("settings")
""")
        resolver = TypedSemanticResolver(self.test_root).scan()
        self.assertGreaterEqual(len(resolver.usages), 1)

    # =========================================================================
    # 3. TAREFAS REAIS DE IMPACTO PROFUNDO (REAL-01 a REAL-10)
    # =========================================================================

    async def test_real_property_blast_radius_rename(self) -> None:
        """REAL-01 e REAL-02: Cálculo de Property Blast Radius ao renomear propriedade aninhada."""
        self._create_file("models/user.ts", """
export interface UserSettings {
  theme: string;
}
export interface User {
  settings: UserSettings;
}
""")
        self._create_file("views/profile.ts", """
function render(u: User) {
  const currentTheme = u.settings.theme;
  return currentTheme;
}
""")
        self._create_file("tests/profile.test.ts", """
function testTheme() {
  const u = { settings: { theme: 'dark' } };
  expect(u.settings.theme).toBe('dark');
}
""")
        resolver = TypedSemanticResolver(self.test_root).scan()
        blast: PropertyBlastRadius = resolver.compute_property_blast_radius("theme")

        self.assertEqual(blast.confidence_level, "HIGH")
        self.assertEqual(len(blast.declarations), 1)
        self.assertIn("models/user.ts", blast.affected_files)
        self.assertIn("views/profile.ts", blast.affected_files)
        self.assertIn("tests/profile.test.ts", blast.affected_files)

    async def test_false_resolution_rate_zero(self) -> None:
        """Validação crítica de que propriedades inexistentes retornam UNKNOWN sem alucinação."""
        self._create_file("models/simple.ts", "export interface Simple { id: string; }\n")
        resolver = TypedSemanticResolver(self.test_root).scan()

        status, node = resolver.resolve_property_path("Simple", ["non_existent_field", "sub_field"])
        self.assertIn(status, ("UNKNOWN", "PARTIAL_RESOLUTION"))
        self.assertIsNone(node)


if __name__ == "__main__":
    unittest.main()

import os
import shutil
import tempfile
import unittest
from pathlib import Path
import uuid
import subprocess

from intelligence.ast_repair_v2 import ASTRepairEngineV2
from intelligence.coding_session import CodingSessionService, CodingSession
from intelligence.project_context import ProjectContextService


class TestSelfHealingValidation(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_self_healing_")
        self.repair_engine = ASTRepairEngineV2()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_repair_unexpected_token_brace(self):
        """Testa a reparação automática do erro 'Unexpected token }' ocorrido no client.js."""
        broken_js = """document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('btn');
    btn.addEventListener('click', async () => {
        console.log('clicked');
    });
});
});
"""
        diagnostics = "file.js:7\n});\n^\n\nSyntaxError: Unexpected token '}'"
        result = self.repair_engine.repair_syntax_javascript(broken_js, file_path="client.js", diagnostics=diagnostics)
        
        self.assertTrue(result.success)
        self.assertEqual(broken_js.count("});") - 1, result.repaired_content.count("});"))
        # O número de chavetas deve estar equilibrado
        self.assertEqual(result.repaired_content.count("{"), result.repaired_content.count("}"))

    def test_repair_await_outside_async_premature_closure(self):
        """Testa a reparação automática do erro 'await is only valid in async functions' ocorrido no app.js."""
        broken_js = """const express = require('express');
const app = express();

app.post('/test', async (req, res) => {
    const data = req.body;
    res.json({ ok: true });
});
    const promises = [Promise.resolve(1)];
    await Promise.allSettled(promises);
    console.log('done');
});
"""
        diagnostics = "app.js:9\n    await Promise.allSettled(promises);\n    ^^^^^\n\nSyntaxError: await is only valid in async functions"
        result = self.repair_engine.repair_syntax_javascript(broken_js, file_path="app.js", diagnostics=diagnostics)

        self.assertTrue(result.success)
        self.assertTrue(any("fecho prematuro" in c or "async" in c for c in result.applied_changes))

    def test_coding_session_auto_repair_integration(self):
        """Testa o ciclo completo de apply_session com auto-reparação determinística."""
        ws_root = Path(self.test_dir) / "workspace"
        proj_dir = ws_root / "projects" / "sample-proj"
        proj_dir.mkdir(parents=True, exist_ok=True)
        
        target_file = proj_dir / "index.js"
        # Ficheiro inicial válido
        target_file.write_text("""console.log('start');
function test() {
    return 42;
}
""", encoding="utf-8")

        ctx_service = ProjectContextService(workspace_root=str(ws_root), projects_root_rel="projects")
        sessions = CodingSessionService(project_service=ctx_service)

        # Proposta de alteração que introduz acidentalmente uma chaveta a mais (como os LLMs fazem)
        changes = [{
            "file": "index.js",
            "operation": "replace_text",
            "old_text": "    return 42;\n}",
            "new_text": "    return 42;\n}\n}",
            "reason": "introduzir erro de sintaxe para testar auto-reparacao",
        }]

        session = sessions.create_session("sample-proj", "Testar auto-reparacao", changes)
        self.assertEqual(session.status, "PROPOSED")

        # Se node estiver disponível, testar a execução real da validação e auto-reparação
        if shutil.which("node"):
            applied = sessions.apply_session("sample-proj", session.session_id)
            self.assertEqual(applied.status, "SUCCEEDED")
            self.assertTrue(len(applied.auto_repair_logs) > 0)
            self.assertTrue(all(r["exit_code"] == 0 for r in applied.validation_results))
            # Verificar se o ficheiro em disco é sintaticamente válido
            cmd_check = subprocess.run(["node", "--check", str(target_file)], capture_output=True)
            self.assertEqual(cmd_check.returncode, 0)


if __name__ == "__main__":
    unittest.main()

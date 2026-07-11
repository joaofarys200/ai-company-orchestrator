import os
import tempfile
import unittest
from datetime import datetime


class WebSocketRequest:
    def __init__(self, path: str = "/", headers: dict[str, str] | None = None):
        self.path = path
        self.headers = headers or {}


class WebSocketStub:
    def __init__(self, path: str = "/", headers: dict[str, str] | None = None):
        self.request = WebSocketRequest(path, headers)


class BackendImportSmokeTest(unittest.TestCase):
    def test_backend_imports_and_uses_local_websocket_host(self):
        import server

        self.assertEqual(server.WS_HOST, "127.0.0.1")
        self.assertTrue(server.WS_AUTH_TOKEN)
        component_names = {component["name"] for component in server.build_runtime_health()["components"]}
        self.assertEqual(component_names, {"backend", "websocket", "sandbox", "frontend_static"})


class WebSocketProtocolSmokeTest(unittest.TestCase):
    def test_normalizes_core_server_messages(self):
        from websocket_schema import normalize_ws_message

        cases = [
            ({"type": "chat", "sender": None, "role": None, "content": 123}, "chat"),
            ({"type": "state", "value": None}, "state"),
            ({"type": "file", "filename": "app.py", "content": None}, "file"),
            ({"type": "kanban", "card_id": 7, "status": None}, "kanban"),
            ({"type": "project_output", "content": 42}, "project_output"),
            ({"type": "rules_list", "rules": "not-a-list"}, "rules_list"),
            ({"type": "planner_state", "data": []}, "planner_state"),
            ({"type": "ui", "action": 99}, "ui"),
            ({"type": "ui_action", "action": "open_workspace"}, "ui_action"),
            ({"type": "ui_theme", "theme": None}, "ui_theme"),
        ]

        for raw_message, expected_type in cases:
            with self.subTest(expected_type=expected_type):
                normalized = normalize_ws_message(raw_message)
                self.assertEqual(normalized["type"], expected_type)

        self.assertEqual(
            normalize_ws_message({"type": "chat", "content": "ola"}),
            {"type": "chat", "sender": "SISTEMA", "role": "System", "content": "ola"},
        )
        self.assertEqual(
            normalize_ws_message({"type": "planner_state", "data": []}),
            {"type": "planner_state", "data": None},
        )

    def test_unknown_message_types_are_preserved_for_controlled_logging(self):
        from websocket_schema import normalize_ws_message

        raw_message = {"type": "future_message", "payload": {"ok": True}}
        self.assertEqual(normalize_ws_message(raw_message), raw_message)

    def test_websocket_auth_accepts_query_and_header_tokens(self):
        import server

        token = server.WS_AUTH_TOKEN
        self.assertTrue(server._is_ws_authorized(WebSocketStub(f"/?token={token}"), ()))
        self.assertTrue(
            server._is_ws_authorized(
                WebSocketStub("/", {"Authorization": f"Bearer {token}"}),
                (),
            )
        )
        self.assertFalse(server._is_ws_authorized(WebSocketStub("/"), ()))
        self.assertFalse(server._is_ws_authorized(WebSocketStub("/?token=wrong-token"), ()))


class RuntimePolicySmokeTest(unittest.TestCase):
    def test_command_policy_allows_safe_commands_and_blocks_dangerous_ones(self):
        from agents.tools import validate_local_command

        self.assertEqual(validate_local_command("python --version"), (True, ""))
        self.assertFalse(validate_local_command("Remove-Item important.txt")[0])
        self.assertFalse(validate_local_command("taskkill /F /PID 1234")[0])
        self.assertFalse(validate_local_command("Get-Content ..\\secret.txt")[0])
        self.assertFalse(validate_local_command("Get-Content C:\\Windows\\win.ini")[0])

    def test_path_policy_keeps_file_access_inside_workspace(self):
        from agents.tools import WORKSPACE_ROOT, resolve_workspace_path

        resolved_root = resolve_workspace_path(".")
        self.assertEqual(os.path.realpath(resolved_root), os.path.realpath(WORKSPACE_ROOT))

        nested_path = resolve_workspace_path("sandbox_dir\\smoke.txt")
        self.assertTrue(os.path.realpath(nested_path).startswith(os.path.realpath(WORKSPACE_ROOT)))

        with self.assertRaises(ValueError):
            resolve_workspace_path("..\\outside.txt")

        with self.assertRaises(ValueError):
            resolve_workspace_path("C:\\Windows\\win.ini")


class LocalAppRoutingSmokeTest(unittest.TestCase):
    def test_excel_voice_prompt_maps_to_whitelisted_local_app(self):
        import server

        app = server.find_local_app_request("Tenta novamente abrir o Excel.")
        self.assertIsNotNone(app)
        self.assertEqual(app["id"], "excel")
        self.assertEqual(app["command"], "Start-Process -FilePath excel.exe")

        self.assertIsNone(server.find_local_app_request("Explica para que serve o Excel."))

    def test_local_app_query_strips_voice_filler_words(self):
        import server

        self.assertEqual(server.extract_local_app_query("Abre novamente o Spotify, por favor."), "spotify")

    def test_start_menu_shortcut_can_resolve_unknown_local_app(self):
        import server

        previous_program_data = os.environ.get("PROGRAMDATA")
        previous_app_data = os.environ.get("APPDATA")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                os.environ["PROGRAMDATA"] = os.path.join(temp_dir, "ProgramData")
                os.environ["APPDATA"] = os.path.join(temp_dir, "AppData", "Roaming")
                start_menu = os.path.join(
                    os.environ["PROGRAMDATA"],
                    "Microsoft",
                    "Windows",
                    "Start Menu",
                    "Programs",
                )
                os.makedirs(start_menu)
                shortcut_path = os.path.join(start_menu, "Spotify.lnk")
                with open(shortcut_path, "w", encoding="utf-8") as shortcut_file:
                    shortcut_file.write("")

                app = server.find_local_app_request("abre o Spotify")
                self.assertIsNotNone(app)
                self.assertEqual(app["source"], "start_menu")
                self.assertEqual(app["label"], "Spotify")
                self.assertEqual(app["path"], shortcut_path)
        finally:
            if previous_program_data is None:
                os.environ.pop("PROGRAMDATA", None)
            else:
                os.environ["PROGRAMDATA"] = previous_program_data
            if previous_app_data is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = previous_app_data

    def test_excel_open_request_is_classified_as_task_without_model_call(self):
        import asyncio
        import server

        self.assertEqual(asyncio.run(server.classify_intent("abre o Excel")), "TASK")


class ObsidianToolPolicySmokeTest(unittest.TestCase):
    def test_validator_rejects_obsidian_writes_for_sandbox_code_artifacts(self):
        from agents.orchestrator import INVALID_WITH_CORRECTION, TaskState, validate_next_tool

        state = TaskState(objective_declared=True)
        status = validate_next_tool(
            "Cria uma app frontend na sandbox.",
            state,
            "obsidian_write_note",
            {"filename": "sandbox_dir/frontend/style.css", "content": "body { color: red; }"},
        )
        self.assertEqual(status, INVALID_WITH_CORRECTION)

    def test_obsidian_write_tool_blocks_code_artifact_paths(self):
        import asyncio
        from pathlib import Path

        from agents import obsidian_tools

        previous_vault_path = os.environ.get("OBSIDIAN_VAULT_PATH")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                os.environ["OBSIDIAN_VAULT_PATH"] = temp_dir

                result = asyncio.run(
                    obsidian_tools.run_obsidian_write_note(
                        "sandbox_dir/backend/server.js",
                        "const express = require('express');",
                    )
                )
                self.assertIn("Erro ao escrever nota", result)
                self.assertFalse(Path(temp_dir, "sandbox_dir", "backend", "server.js.md").exists())

                ok_result = asyncio.run(obsidian_tools.run_obsidian_write_note("Projetos/Plano", "conteudo"))
                self.assertIn("guardada com sucesso", ok_result)
                self.assertTrue(Path(temp_dir, "Projetos", "Plano.md").exists())
        finally:
            if previous_vault_path is None:
                os.environ.pop("OBSIDIAN_VAULT_PATH", None)
            else:
                os.environ["OBSIDIAN_VAULT_PATH"] = previous_vault_path


class ToolRegistrySmokeTest(unittest.TestCase):
    def test_tool_registry_wraps_existing_tool_definitions(self):
        from agents.tools import JARVIS_TOOLS, get_tool_registry

        registry = get_tool_registry()
        self.assertEqual(len(registry.to_llm_tools()), len(JARVIS_TOOLS))
        self.assertIn("execute_command", registry.names())
        self.assertEqual(registry.get("execute_command").permissions, ("command", "workspace"))
        self.assertEqual(registry.validate(), [])


class ProviderFactorySmokeTest(unittest.TestCase):
    def test_provider_factory_falls_back_to_ollama_without_cloud_credentials(self):
        from agents.providers.factory import get_llm_provider

        self.assertEqual(get_llm_provider("local").name, "ollama")
        self.assertEqual(get_llm_provider("unknown").name, "ollama")


class OrchestratorRecoverySmokeTest(unittest.TestCase):
    def test_forces_single_write_file_recovery_after_list_directory_for_app_generation(self):
        from agents.orchestrator import keep_tools, should_force_write_file_recovery

        prompt = "Cria uma aplicação web completa de gestão de tarefas com frontend, backend simples e preview na sandbox."
        messages = [
            {"role": "tool_result", "tool_name": "declarar_objetivo", "content": "Objetivo registado."},
            {"role": "tool_result", "tool_name": "list_directory", "content": "[FILE] index.html"},
            {"role": "assistant", "content": "Vou começar por criar os ficheiros necessários."},
        ]

        self.assertTrue(should_force_write_file_recovery(prompt, messages, already_attempted=False))
        self.assertFalse(should_force_write_file_recovery(prompt, messages, already_attempted=True))

        tools = [{"name": "list_directory"}, {"name": "write_file"}, {"name": "execute_command"}]
        self.assertEqual(keep_tools(tools, {"write_file"}), [{"name": "write_file"}])

    def test_write_file_recovery_does_not_trigger_after_write_file_or_non_generation_prompt(self):
        from agents.orchestrator import should_force_write_file_recovery

        app_prompt = "Cria uma aplicação web completa de gestão de tarefas."
        messages_with_write = [
            {"role": "tool_result", "tool_name": "list_directory", "content": "[FILE] index.html"},
            {"role": "tool_result", "tool_name": "write_file", "content": "Ficheiro guardado."},
        ]
        self.assertFalse(should_force_write_file_recovery(app_prompt, messages_with_write, already_attempted=False))

        chatty_prompt = "Explica como organizar melhor as minhas tarefas."
        messages_after_list = [
            {"role": "tool_result", "tool_name": "list_directory", "content": "[FILE] index.html"},
        ]
        self.assertFalse(should_force_write_file_recovery(chatty_prompt, messages_after_list, already_attempted=False))

    def test_text_after_list_directory_is_invalid_when_work_is_missing(self):
        from agents.orchestrator import INVALID_WITH_CORRECTION, TaskState, update_task_state_after_tool, validate_next_tool

        state = TaskState()
        update_task_state_after_tool(state, "declarar_objetivo", {
            "criterios_de_sucesso": ["ficheiro criado"],
        }, "Objetivo registado.")
        update_task_state_after_tool(state, "list_directory", {"path": "sandbox_dir"}, "[FILE] index.html")

        status = validate_next_tool("Cria um ficheiro de notas.", state, "", {"response_text": "Vou criar agora."})
        self.assertEqual(status, INVALID_WITH_CORRECTION)

    def test_write_file_with_irrelevant_placeholder_is_rejected(self):
        from agents.orchestrator import INVALID_WITH_CORRECTION, TaskState, validate_next_tool

        state = TaskState(success_criteria=["gestao de tarefas"])
        state.objective_declared = True
        status = validate_next_tool(
            "Cria um sistema de gestao de tarefas.",
            state,
            "write_file",
            {"filename": "src/main.py", "content": "print('Hello, world!')"},
        )
        self.assertEqual(status, INVALID_WITH_CORRECTION)

    def test_operational_contract_requires_declared_objective_and_valid_tool_args(self):
        from agents.orchestrator import INVALID_WITH_CORRECTION, TaskState, validate_next_tool

        state = TaskState()
        self.assertEqual(
            validate_next_tool("Cria um ficheiro.", state, "write_file", {"filename": "a.txt", "content": "ok"}),
            INVALID_WITH_CORRECTION,
        )

    def test_declared_objective_must_match_user_prompt(self):
        from agents.orchestrator import INVALID_WITH_CORRECTION, VALID, TaskState, validate_next_tool

        state = TaskState()
        self.assertEqual(
            validate_next_tool(
                "Cria o ficheiro sandbox_dir/codex_smoke.txt.",
                state,
                "declarar_objetivo",
                {
                    "objetivo": "Configurar ambiente FastAPI",
                    "criterios_de_sucesso": ["FastAPI instalado"],
                },
            ),
            INVALID_WITH_CORRECTION,
        )
        self.assertEqual(
            validate_next_tool(
                "Cria o ficheiro sandbox_dir/codex_smoke.txt.",
                state,
                "declarar_objetivo",
                {
                    "objetivo": "Criar o ficheiro codex_smoke.txt",
                    "criterios_de_sucesso": ["codex_smoke.txt criado"],
                },
            ),
            VALID,
        )

        state.objective_declared = True
        self.assertEqual(
            validate_next_tool("Cria um ficheiro.", state, "write_file", {"filename": "", "content": ""}),
            INVALID_WITH_CORRECTION,
        )

    def test_quality_gate_blocks_early_success_without_evidence(self):
        from agents.orchestrator import INVALID_WITH_CORRECTION, TaskState, validate_next_tool

        state = TaskState(success_criteria=["ficheiro criado", "validacao executada"])
        status = validate_next_tool(
            "Cria um ficheiro e valida a execucao.",
            state,
            "verificar_qualidade",
            {"pronto_para_entrega": True, "criterios_cumpridos": ["feito"]},
        )
        self.assertEqual(status, INVALID_WITH_CORRECTION)

    def test_start_autonomous_plan_is_controlled_inside_async_loop(self):
        import asyncio
        from agents.orchestrator import run_start_autonomous_plan_safely

        result = asyncio.run(run_start_autonomous_plan_safely({"goal": "teste"}))
        self.assertIn("Erro controlado", result)
        self.assertIn("loop async", result)

    def test_timeout_error_contains_operational_context(self):
        from agents.orchestrator import CONTROLLED_STOP, TaskState, ToolDecision, format_operational_error

        state = TaskState(last_tool="write_file", files_created=[])
        decision = ToolDecision(
            CONTROLLED_STOP,
            "Limite de passos atingido sem evidencia suficiente.",
            "LLM",
            ["ficheiros criados"],
            "Criar um artefacto verificavel.",
        )
        message = format_operational_error("geracao_ficheiros", state, decision)
        self.assertIn("Erro controlado", message)
        self.assertIn("Ultima tool: write_file", message)
        self.assertIn("Categoria da falha: LLM", message)

    def test_small_file_creation_can_pass_operational_validation(self):
        from agents.orchestrator import VALID, TaskState, update_task_state_after_tool, validate_next_tool

        state = TaskState(success_criteria=["notas"])
        state.objective_declared = True
        status = validate_next_tool(
            "Cria um ficheiro notas.txt com notas.",
            state,
            "write_file",
            {"filename": "sandbox_dir/notas.txt", "content": "notas\n- item inicial\n"},
        )
        self.assertEqual(status, VALID)
        update_task_state_after_tool(state, "write_file", {"filename": "sandbox_dir/notas.txt"}, "Ficheiro guardado com sucesso.")
        self.assertEqual(state.files_created, ["sandbox_dir/notas.txt"])

    def test_task_plan_filters_tools_by_current_step(self):
        from agents.orchestrator import TaskState, allowed_tools_for_current_step, create_task_plan

        plan = create_task_plan("Cria um ficheiro e valida.")
        tools = [{"name": "declarar_objetivo"}, {"name": "write_file"}, {"name": "execute_command"}]
        self.assertEqual(allowed_tools_for_current_step(plan, tools), [{"name": "declarar_objetivo"}])

        state = TaskState(objective_declared=True)
        plan.advance_if_ready(state, "Cria um ficheiro e valida.")
        self.assertEqual(plan.current_step.id, "analisar_workspace")

    def test_structured_action_parser_recovers_json_action(self):
        from agents.orchestrator import parse_structured_action

        tools = [{"name": "write_file"}]
        text = '{"next_action":"write_file","args":{"filename":"sandbox_dir/a.txt","content":"ok"},"reason":"teste"}'
        calls = parse_structured_action(text, tools, 0)
        self.assertEqual(calls[0]["name"], "write_file")
        self.assertEqual(calls[0]["input"]["filename"], "sandbox_dir/a.txt")

    def test_structured_action_parser_maps_safe_file_creation_alias(self):
        from agents.orchestrator import parse_structured_action

        tools = [{"name": "write_file"}]
        text = '{"next_action":"create_file","args":{"path":"/sandbox/a.txt","content":"ok"},"reason":"teste"}'
        calls = parse_structured_action(text, tools, 0)
        self.assertEqual(calls[0]["name"], "write_file")
        self.assertEqual(calls[0]["input"]["path"], "/sandbox/a.txt")

    def test_workspace_path_aliases_are_normalized_safely(self):
        from agents.orchestrator import normalize_tool_input_paths

        self.assertEqual(
            normalize_tool_input_paths("list_directory", {"path": "/workspace/sandbox"})["path"],
            "sandbox_dir",
        )
        self.assertEqual(
            normalize_tool_input_paths("list_directory", {"path": "/sandbox_dir"})["path"],
            "sandbox_dir",
        )
        self.assertEqual(
            normalize_tool_input_paths("write_file", {"filename": "/sandbox/app.js"})["filename"],
            "sandbox_dir/app.js",
        )

    def test_repair_converts_path_to_filename_and_preserves_content(self):
        from agents.orchestrator import TaskState, create_task_plan, repair_proposed_action

        state = TaskState(objective_declared=True, workspace_listed=True)
        plan = create_task_plan("Cria um ficheiro.")
        plan.current_index = 2
        repair = repair_proposed_action(
            state,
            plan,
            "write_file",
            {"path": "/sandbox/x.txt", "content": "ok"},
        )
        self.assertEqual(repair.tool_input["filename"], "sandbox_dir/x.txt")
        self.assertEqual(repair.tool_input["content"], "ok")

    def test_repair_converts_file_text_to_content(self):
        from agents.orchestrator import TaskState, create_task_plan, repair_proposed_action

        state = TaskState(objective="Cria sandbox_dir/a.html.", objective_declared=True, workspace_listed=True)
        plan = create_task_plan(state.objective)
        plan.current_index = 2
        repair = repair_proposed_action(
            state,
            plan,
            "write_file",
            {"path": "/sandbox/a.html", "file_text": "<!doctype html>"},
        )
        self.assertEqual(repair.tool_input["filename"], "sandbox_dir/a.html")
        self.assertEqual(repair.tool_input["content"], "<!doctype html>")

    def test_repair_adds_workspace_analysis_before_early_write_file(self):
        from agents.orchestrator import TaskState, create_task_plan, repair_proposed_action

        state = TaskState(objective_declared=True, workspace_listed=False)
        plan = create_task_plan("Cria um ficheiro.")
        plan.current_index = 1
        repair = repair_proposed_action(
            state,
            plan,
            "write_file",
            {"path": "/sandbox/hello.txt", "content": "hello"},
        )
        self.assertEqual(repair.pre_actions[0]["tool_name"], "list_directory")
        self.assertEqual(repair.tool_input["filename"], "sandbox_dir/hello.txt")

    def test_repair_rejects_path_outside_workspace(self):
        from agents.orchestrator import CONTROLLED_STOP, TaskState, create_task_plan, repair_proposed_action

        state = TaskState(objective_declared=True, workspace_listed=True)
        plan = create_task_plan("Cria um ficheiro.")
        repair = repair_proposed_action(
            state,
            plan,
            "write_file",
            {"filename": "C:/Windows/win.ini", "content": "x"},
        )
        self.assertEqual(repair.status, CONTROLLED_STOP)

    def test_t001_repair_path_can_progress_to_file_creation_step(self):
        from agents.orchestrator import TaskState, create_task_plan, repair_proposed_action, update_task_state_after_tool

        prompt = "Cria o ficheiro sandbox_dir/bench_T001_hello.txt com o conteudo hello."
        state = TaskState(objective=prompt, objective_declared=True, success_criteria=["artefactos criados no workspace/sandbox"])
        plan = create_task_plan(prompt)
        plan.advance_if_ready(state, prompt)
        repair = repair_proposed_action(
            state,
            plan,
            "write_file",
            {"path": "/sandbox/bench_T001_hello.txt", "content": "hello"},
        )
        self.assertEqual(plan.current_step.id, "analisar_workspace")
        self.assertEqual(repair.pre_actions[0]["tool_name"], "list_directory")
        update_task_state_after_tool(state, "list_directory", {"path": "sandbox_dir"}, "[FILE] index.html")
        plan.advance_if_ready(state, prompt)
        self.assertEqual(plan.current_step.id, "criar_ficheiros")
        update_task_state_after_tool(state, repair.tool_name, repair.tool_input, "Ficheiro guardado com sucesso.")
        plan.advance_if_ready(state, prompt)
        self.assertEqual(plan.current_step.id, "finalizar")

    def test_repair_turns_creation_stage_listing_into_requested_file_write(self):
        from agents.orchestrator import TaskState, create_task_plan, repair_proposed_action

        prompt = "Cria uma app simples em sandbox_dir/bench_T007 com index.html, style.css e app.js."
        state = TaskState(objective=prompt, objective_declared=True, workspace_listed=True)
        plan = create_task_plan(prompt)
        plan.current_index = 2
        repair = repair_proposed_action(state, plan, "list_directory", {"path": "sandbox_dir"})
        self.assertEqual(repair.tool_name, "write_file")
        self.assertEqual(repair.tool_input["filename"], "sandbox_dir/bench_T007/index.html")
        self.assertIn("<!doctype html>", repair.tool_input["content"])

    def test_repair_turns_validation_listing_into_safe_execute_command(self):
        from agents.orchestrator import TaskState, create_task_plan, repair_proposed_action

        prompt = "Executa um comando seguro para listar sandbox_dir e valida que o comando correu."
        state = TaskState(objective=prompt, objective_declared=True, workspace_listed=True)
        plan = create_task_plan(prompt)
        plan.current_index = 2
        repair = repair_proposed_action(state, plan, "list_directory", {"path": "sandbox_dir"})
        self.assertEqual(repair.tool_name, "execute_command")
        self.assertEqual(repair.tool_input["command"], "Get-ChildItem -LiteralPath sandbox_dir")

    def test_explicit_requested_paths_define_creation_minimum(self):
        from agents.orchestrator import TaskState, artifacts_satisfy_minimum

        prompt = "Cria sandbox_dir/demo/index.html e sandbox_dir/demo/app.js."
        state = TaskState(files_created=["sandbox_dir/demo/index.html"])
        self.assertFalse(artifacts_satisfy_minimum(prompt, state))
        state.files_created.append("sandbox_dir/demo/app.js")
        self.assertTrue(artifacts_satisfy_minimum(prompt, state))

    def test_task_requirements_are_inferred_abstractly(self):
        from agents.orchestrator import infer_task_requirements

        req = infer_task_requirements(
            "Cria uma app web com frontend, backend simples, armazenamento local, autenticacao, CRUD, pesquisa, dashboard e preview."
        )
        self.assertTrue(req.requires_frontend)
        self.assertTrue(req.requires_backend)
        self.assertTrue(req.requires_storage)
        self.assertTrue(req.requires_auth)
        self.assertTrue(req.requires_crud)
        self.assertTrue(req.requires_search)
        self.assertTrue(req.requires_dashboard)
        self.assertTrue(req.requires_preview)

    def test_existing_app_preview_does_not_require_new_frontend_artifact(self):
        from agents.orchestrator import infer_task_requirements

        req = infer_task_requirements("Executa sandbox/preview para uma app existente em sandbox_dir.")
        self.assertFalse(req.requires_artifacts)
        self.assertFalse(req.requires_frontend)
        self.assertTrue(req.requires_preview)
        self.assertTrue(req.requires_validation)

    def test_preview_command_is_normalized_to_safe_powershell_probe(self):
        from agents.orchestrator import normalize_tool_input_paths

        normalized = normalize_tool_input_paths(
            "execute_command",
            {"command": "cd /sandbox && python -m http.server 8000"},
        )
        self.assertEqual(normalized["command"], "Get-ChildItem -Force -LiteralPath sandbox_dir")

    def test_implementation_plan_validation_accepts_obligation_mapping(self):
        from agents.orchestrator import parse_implementation_plan, infer_task_requirements, validate_implementation_plan

        req = infer_task_requirements("Cria uma app com frontend, backend simples e armazenamento local.")
        plan = parse_implementation_plan({
            "stack": "Vanilla UI + servidor Python",
            "files": [
                {"path": "sandbox_dir/ui.html", "purpose": "interface frontend", "obligations": ["frontend", "storage"]},
                {"path": "sandbox_dir/server.py", "purpose": "API backend", "obligations": ["backend"]},
            ],
            "storage_strategy": "localStorage no frontend",
            "validation_commands": ["python sandbox_dir/server.py --check"],
            "completion_criteria": ["UI e API existem"],
        })
        validated = validate_implementation_plan(req, plan)
        self.assertTrue(validated.valid)

    def test_implementation_plan_validation_rejects_missing_backend(self):
        from agents.orchestrator import parse_implementation_plan, infer_task_requirements, validate_implementation_plan

        req = infer_task_requirements("Cria uma app com frontend e backend simples.")
        plan = parse_implementation_plan({
            "stack": "HTML",
            "files": [
                {"path": "sandbox_dir/app.html", "purpose": "interface frontend", "obligations": ["frontend"]},
            ],
        })
        validated = validate_implementation_plan(req, plan)
        self.assertFalse(validated.valid)
        self.assertTrue(any("backend" in issue for issue in validated.issues))

    def test_completion_uses_obligations_not_all_planned_files(self):
        from agents.orchestrator import ImplementationPlan, PlannedArtifact, TaskRequirements, TaskState, artifacts_satisfy_minimum

        state = TaskState(
            objective="Cria uma app com frontend e backend simples.",
            requirements=TaskRequirements(requires_artifacts=True, requires_frontend=True, requires_backend=True),
            implementation_plan=ImplementationPlan(
                valid=True,
                files=[
                    PlannedArtifact("sandbox_dir/server.py", "API backend", ["backend"]),
                    PlannedArtifact("sandbox_dir/index.html", "UI frontend", ["frontend"]),
                    PlannedArtifact("sandbox_dir/extra.md", "documentacao opcional", ["validation"]),
                ],
            ),
            files_created=["sandbox_dir/server.py", "sandbox_dir/index.html"],
            artifact_contents={
                "sandbox_dir/server.py": "from flask import Flask\n@app.route('/api/tasks')\ndef tasks(): pass\n",
                "sandbox_dir/index.html": "<html><body><main>UI</main></body></html>",
            },
        )
        self.assertTrue(artifacts_satisfy_minimum(state.objective, state))

    def test_plan_alone_is_not_completion_evidence(self):
        from agents.orchestrator import ImplementationPlan, PlannedArtifact, TaskRequirements, TaskState, artifacts_satisfy_minimum

        state = TaskState(
            objective="Cria uma app com frontend e backend simples.",
            requirements=TaskRequirements(requires_artifacts=True, requires_frontend=True, requires_backend=True),
            implementation_plan=ImplementationPlan(
                valid=True,
                files=[
                    PlannedArtifact("sandbox_dir/server.py", "API backend", ["backend"]),
                    PlannedArtifact("sandbox_dir/index.html", "UI frontend", ["frontend"]),
                ],
            ),
        )
        self.assertFalse(artifacts_satisfy_minimum(state.objective, state))

    def test_frontend_evidence_does_not_match_ui_inside_require(self):
        from agents.orchestrator import TaskRequirements, TaskState, missing_requirement_evidence

        state = TaskState(
            objective="Cria uma app com frontend e backend simples.",
            requirements=TaskRequirements(requires_artifacts=True, requires_frontend=True, requires_backend=True),
            files_created=["sandbox_dir/server.js"],
            artifact_contents={
                "sandbox_dir/server.js": "const express = require('express'); if (url.endsWith('.css')) serveStatic(); // API interface only\napp.get('/api/tasks', handler);",
            },
        )
        self.assertIn("frontend/UI", missing_requirement_evidence(state.objective, state, include_quality=False))

    def test_crud_evidence_accepts_rest_http_verbs(self):
        from agents.orchestrator import TaskRequirements, TaskState, missing_requirement_evidence

        state = TaskState(
            objective="Cria API com CRUD de tarefas.",
            requirements=TaskRequirements(requires_artifacts=True, requires_backend=True, requires_crud=True),
            files_created=["sandbox_dir/routes/tasks.js"],
            artifact_contents={
                "sandbox_dir/routes/tasks.js": "router.get('/tasks'); router.post('/tasks'); router.put('/tasks/:id'); router.delete('/tasks/:id');",
            },
        )
        self.assertNotIn("CRUD", missing_requirement_evidence(state.objective, state, include_quality=False))

    def test_creation_step_can_finish_before_preview_validation(self):
        from agents.orchestrator import TaskRequirements, TaskState, artifacts_satisfy_minimum

        state = TaskState(
            objective="Cria uma app com frontend, backend e preview funcional na sandbox.",
            requirements=TaskRequirements(
                requires_artifacts=True,
                requires_frontend=True,
                requires_backend=True,
                requires_preview=True,
                requires_validation=True,
            ),
            files_created=["sandbox_dir/server.js", "sandbox_dir/public/index.html"],
            artifact_contents={
                "sandbox_dir/server.js": "const express = require('express'); app.get('/api/tasks', handler);",
                "sandbox_dir/public/index.html": "<html><body><main>UI</main></body></html>",
            },
        )
        self.assertTrue(artifacts_satisfy_minimum(state.objective, state, include_execution=False))
        self.assertFalse(artifacts_satisfy_minimum(state.objective, state))

    def test_step_limit_recovery_can_validate_completed_artifacts(self):
        from agents.orchestrator import (
            TaskRequirements,
            TaskState,
            deterministic_validation_command_for_state,
            step_limit_completion_recovery_available,
        )

        state = TaskState(
            objective="Cria uma app com frontend, backend e preview funcional na sandbox.",
            requirements=TaskRequirements(
                requires_artifacts=True,
                requires_frontend=True,
                requires_backend=True,
                requires_preview=True,
                requires_validation=True,
            ),
            files_created=["sandbox_dir/server.js", "sandbox_dir/public/index.html"],
            artifact_contents={
                "sandbox_dir/server.js": "const express = require('express'); app.get('/api/tasks', handler);",
                "sandbox_dir/public/index.html": "<html><body><main>UI</main></body></html>",
            },
        )

        self.assertTrue(step_limit_completion_recovery_available(state.objective, state))
        self.assertEqual(
            deterministic_validation_command_for_state(state.objective, state),
            "Get-ChildItem -Force -LiteralPath sandbox_dir",
        )

    def test_step_limit_recovery_does_not_mask_missing_artifacts(self):
        from agents.orchestrator import TaskRequirements, TaskState, step_limit_completion_recovery_available

        state = TaskState(
            objective="Cria uma app com frontend, backend e preview funcional na sandbox.",
            requirements=TaskRequirements(
                requires_artifacts=True,
                requires_frontend=True,
                requires_backend=True,
                requires_preview=True,
                requires_validation=True,
            ),
        )

        self.assertFalse(step_limit_completion_recovery_available(state.objective, state))

    def test_failed_command_result_does_not_mark_validation_executed(self):
        from agents.orchestrator import TaskState, update_task_state_after_tool

        state = TaskState()
        update_task_state_after_tool(
            state,
            "execute_command",
            {"command": "python missing.py"},
            "Comando terminado com codigo 1.\n\n[STDERR]\nerror: missing file",
        )
        self.assertEqual(state.commands_executed, [])
        self.assertFalse(state.sandbox_validated)

    def test_debug_trace_writes_json_when_enabled(self):
        import json
        from pathlib import Path
        from agents.orchestrator import OrchestrationTrace, TaskState

        trace = OrchestrationTrace(prompt="teste", model="local", enabled=True)
        trace.record("unit.test", ok=True)
        path = trace.save(TaskState())
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual(data["prompt"], "teste")
        self.assertEqual(data["events"][0]["event"], "unit.test")


class OrchestrationResultStatusSmokeTest(unittest.TestCase):
    def test_orchestration_result_error_markers_prevent_false_success_message(self):
        import server

        self.assertTrue(server.is_orchestration_result_error("Fallback local interrompido: sem tool call valida."))
        self.assertTrue(server.is_orchestration_result_error("Limite de passos atingido."))
        self.assertTrue(server.is_orchestration_result_error("Recovery write_file falhou: sem tool_call."))
        self.assertFalse(server.is_orchestration_result_error("Projeto concluido e validado."))

    def test_empty_or_completed_persistent_plan_is_not_reported_as_active(self):
        import json
        import server

        with tempfile.TemporaryDirectory() as temp_dir:
            plan_path = os.path.join(temp_dir, ".jarvis_plan.json")
            with open(plan_path, "w", encoding="utf-8") as f:
                json.dump({"goal": "", "steps": [], "status": "NONE"}, f)
            self.assertIsNone(server.read_persistent_plan_state(plan_path))

            with open(plan_path, "w", encoding="utf-8") as f:
                json.dump({"goal": "antigo", "steps": [{"id": 1, "action": "x", "status": "DONE"}], "status": "DONE"}, f)
            self.assertIsNone(server.read_persistent_plan_state(plan_path))

            with open(plan_path, "w", encoding="utf-8") as f:
                json.dump({"goal": "ativo", "steps": [{"id": 1, "action": "x", "status": "PENDING"}], "status": "PENDING"}, f)
            self.assertEqual(server.read_persistent_plan_state(plan_path)["goal"], "ativo")


class LocalHardeningSmokeTest(unittest.TestCase):
    def test_error_and_log_sanitizers_redact_sensitive_values(self):
        from backend.errors import safe_user_error
        from backend.logging_config import sanitize_log_value

        message = safe_user_error(
            "Erro",
            "token=secret-value Bearer abc.def C:\\Users\\joaor\\secret.txt",
        )
        self.assertNotIn("secret-value", message)
        self.assertNotIn("abc.def", message)
        self.assertNotIn("joaor", message)

        payload = sanitize_log_value({
            "auth": "api_key=real-key",
            "nested": ["Bearer token-value"],
            "path": "C:\\Users\\joaor\\.config\\settings.json",
        })
        self.assertEqual(payload["auth"], "api_key=[REDACTED]")
        self.assertEqual(payload["nested"], ["Bearer [REDACTED]"])
        self.assertNotIn("joaor", payload["path"])

    def test_health_report_contains_explicit_local_components(self):
        from backend.health import build_local_health_report

        with tempfile.TemporaryDirectory() as temp_dir:
            frontend_dist = os.path.join(temp_dir, "frontend", "dist")
            sandbox_dir = os.path.join(temp_dir, "sandbox_dir")
            os.makedirs(frontend_dist)
            os.makedirs(sandbox_dir)
            open(os.path.join(frontend_dist, "index.html"), "w", encoding="utf-8").close()
            open(os.path.join(sandbox_dir, "index.html"), "w", encoding="utf-8").close()

            report = build_local_health_report(
                project_root=temp_dir,
                websocket_host="127.0.0.1",
                websocket_port=8001,
                active_connections_count=0,
                sandbox_dir=sandbox_dir,
                sandbox_port=8080,
                frontend_port=8000,
            )

        self.assertEqual(report["status"], "ok")
        self.assertEqual(
            {component["name"] for component in report["components"]},
            {"backend", "websocket", "sandbox", "frontend_static"},
        )


class DatabaseSmokeTest(unittest.TestCase):
    def setUp(self):
        import database

        self.database = database
        self.original_db_file = database.DB_FILE
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_file.close()
        self.temp_db_file = temp_file.name
        database.DB_FILE = self.temp_db_file
        database.init_db()

    def tearDown(self):
        self.database.DB_FILE = self.original_db_file
        if os.path.exists(self.temp_db_file):
            os.unlink(self.temp_db_file)

    def test_core_database_functions_work_against_isolated_sqlite_file(self):
        db = self.database

        session = db.create_session("smoke session")
        self.assertIsInstance(session.id, int)
        conn = db.get_connection()
        try:
            created_at = conn.execute(
                "SELECT created_at FROM sessions WHERE id = ?",
                (session.id,),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertIsNotNone(datetime.fromisoformat(created_at).tzinfo)

        db.add_message(session.id, "tester", "User", "hello")
        db.save_project(session.id, "Smoke Project", "desc", "<main />", "body {}", "console.log(1)")

        db.add_compounding_rule("smoke_rule", "desc", "correction")
        rules = db.get_compounding_rules()
        self.assertTrue(any(rule["rule_key"] == "smoke_rule" for rule in rules))
        self.assertTrue(db.delete_compounding_rule("smoke_rule"))

        db.add_architecture_memory("smoke.module", "purpose", "dep_a", "constraint")
        architecture = db.get_architecture_memory()
        self.assertTrue(any(item["module"] == "smoke.module" for item in architecture))
        self.assertTrue(db.delete_architecture_memory("smoke.module"))

        db.add_engineering_decision("Use smoke test", "runtime validation", "lower regression risk")
        decisions = db.get_engineering_decisions()
        self.assertTrue(any(item["decision"] == "Use smoke test" for item in decisions))
        self.assertTrue(db.delete_engineering_decision("Use smoke test"))


class PersistenceRepositorySmokeTest(unittest.TestCase):
    def setUp(self):
        import database

        self.database = database
        self.original_db_file = database.DB_FILE
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_file.close()
        self.temp_db_file = temp_file.name
        database.DB_FILE = self.temp_db_file
        database.init_db()

    def tearDown(self):
        self.database.DB_FILE = self.original_db_file
        if os.path.exists(self.temp_db_file):
            os.unlink(self.temp_db_file)

    def test_repository_facades_use_existing_sqlite_schema(self):
        from persistence.repositories import decisions, messages, projects, rules, sessions

        session = sessions.create_session("repository smoke")
        messages.add_message(session.id, "tester", "User", "hello")
        projects.save_project(session.id, "Repo Project", "desc", "<main />", "body {}", "console.log(1)")

        rules.add_compounding_rule("repo_rule", "desc", "correction")
        self.assertTrue(any(rule["rule_key"] == "repo_rule" for rule in rules.get_compounding_rules()))
        self.assertTrue(rules.delete_compounding_rule("repo_rule"))

        decisions.add_engineering_decision("Repository facade", "modularization", "same schema")
        self.assertTrue(
            any(item["decision"] == "Repository facade" for item in decisions.get_engineering_decisions())
        )
        self.assertTrue(decisions.delete_engineering_decision("Repository facade"))


if __name__ == "__main__":
    unittest.main()

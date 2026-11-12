from __future__ import annotations

import ast
import json
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.transport_gateway import (
    StdioTransportGateway,
    VirtualIPCClient,
    bind_response_request_id,
)
from backend.websocket.contracts import (
    CRITICAL_SERVER_EVENT_TYPES,
    MISSION_UNIMPLEMENTED_STUB_OPERATIONS,
    MISSION_UNREGISTERED_LEGACY_BRANCHES,
)
from backend.websocket.dispatcher import WebSocketDispatcher
from backend.websocket.handlers.missions import MISSION_HANDLERS, MissionWebSocketHandler
from websocket_schema import (
    CLIENT_MESSAGE_TYPES,
    SERVER_MESSAGE_TYPES,
    normalize_ws_message,
)


TS_PROTOCOL_PATH = PROJECT_ROOT / "frontend" / "src" / "protocol" / "websocket.ts"


def _extract_ts_union_types(ts_source: str, type_name: str) -> set[str]:
    marker = f"export type {type_name} ="
    start = ts_source.find(marker)
    if start == -1:
        raise AssertionError(f"Could not locate `{marker}` in {TS_PROTOCOL_PATH}")
    end = ts_source.find("\n\n", start)
    if end == -1:
        end = ts_source.find(";", start)
    block = ts_source[start:end]
    types: set[str] = set()
    for match in re.finditer(r"\btype\s*:\s*([^;\n}]+)", block):
        for literal in re.findall(r"'([A-Za-z0-9_]+)'", match.group(1)):
            types.add(literal)
    return types


def _extract_ts_normalized_server_types(ts_source: str) -> set[str]:
    marker = "export type NormalizedServerMessage ="
    start = ts_source.find(marker)
    if start == -1:
        raise AssertionError(f"Could not locate `{marker}` in {TS_PROTOCOL_PATH}")
    end = ts_source.find("export type ServerMessage =", start)
    union_block = ts_source[start:end]
    result: set[str] = set()

    for literal in re.findall(r"'([A-Za-z0-9_]+)'", union_block):
        result.add(literal)

    iface_names = re.findall(r"\b([A-Z][A-Za-z0-9_]+Message)\b", union_block)
    for iface in iface_names:
        iface_match = re.search(rf"export interface {re.escape(iface)}\s*\{{(.*?)\n\}}", ts_source, re.DOTALL)
        if not iface_match:
            continue
        type_line = re.search(r"\btype\s*:\s*([^;\n]+)", iface_match.group(1))
        if type_line:
            for literal in re.findall(r"'([A-Za-z0-9_]+)'", type_line.group(1)):
                result.add(literal)
    result.discard("unknown")
    return result


def _extract_ts_normalize_switch_cases(ts_source: str) -> set[str]:
    start = ts_source.find("const normalizeServerPayload")
    if start == -1:
        raise AssertionError("Could not find normalizeServerPayload in websocket.ts")
    end = ts_source.find("export const normalizeServerMessage", start)
    block = ts_source[start:end]
    return set(re.findall(r"case\s+'([A-Za-z0-9_]+)'\s*:", block))


def _extract_frontend_dispatched_types() -> set[str]:
    frontend_src = PROJECT_ROOT / "frontend" / "src"
    dispatched: set[str] = set()
    pattern = re.compile(
        r"(?:sendClientMessage|sendMissionOperation|transport\.(?:send|invoke)\w*|sendJson|send)\s*\(\s*\{\s*type\s*:\s*'([A-Za-z0-9_]+)'",
        re.MULTILINE,
    )
    for path in sorted(frontend_src.rglob("*.ts*")):
        if "__tests__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        dispatched.update(pattern.findall(text))
    return dispatched


class ProtocolContractTests(unittest.TestCase):
    def test_frontend_client_messages_match_python_schema(self) -> None:
        ts_source = TS_PROTOCOL_PATH.read_text(encoding="utf-8")
        ts_mission_ops = _extract_ts_union_types(ts_source, "MissionClientOperation")
        ts_client_msgs = _extract_ts_union_types(ts_source, "ClientMessage") | ts_mission_ops

        missing_from_python = sorted(ts_client_msgs - CLIENT_MESSAGE_TYPES)
        self.assertEqual(
            missing_from_python,
            [],
            f"TypeScript ClientMessage types missing from Python CLIENT_MESSAGE_TYPES: {missing_from_python}",
        )

        phantom_study_types = {
            "study_get_notes_and_highlights",
            "study_prepare_exam",
            "study_save_highlight",
            "study_save_note",
            "study_update_reading_progress",
        }
        self.assertEqual(sorted(ts_client_msgs & phantom_study_types), [])

        dispatched = _extract_frontend_dispatched_types()
        self.assertEqual(
            sorted(dispatched - ts_client_msgs),
            [],
            "Frontend dispatches client types absent from TypeScript ClientMessage union",
        )
        self.assertEqual(
            sorted(dispatched - CLIENT_MESSAGE_TYPES),
            [],
            "Frontend dispatches client types absent from Python CLIENT_MESSAGE_TYPES",
        )

    def test_critical_and_emitted_server_events_in_schema_and_normalizer(self) -> None:
        ts_source = TS_PROTOCOL_PATH.read_text(encoding="utf-8")
        ts_server_types = _extract_ts_normalized_server_types(ts_source)
        ts_switch_cases = _extract_ts_normalize_switch_cases(ts_source)

        for event_type in sorted(CRITICAL_SERVER_EVENT_TYPES):
            self.assertIn(event_type, SERVER_MESSAGE_TYPES, f"{event_type} missing from SERVER_MESSAGE_TYPES")
            self.assertIn(event_type, ts_server_types, f"{event_type} missing from TS ServerMessage union")
            self.assertIn(event_type, ts_switch_cases, f"{event_type} missing from normalizeServerPayload switch")

        # Also check all active study video + impact + gateway error events
        expected_additional = {
            "error",
            "study_video_context_result",
            "study_explain_video_moment_result",
            "study_explain_video_visual_result",
            "study_search_video_transcript_result",
            "study_ask_video_result",
            "study_video_note_saved",
            "study_video_progress_updated",
            "study_progress_updated",
            "study_document_retried",
            "project_deleted",
            "project_delete_error",
            "project_file_deleted",
            "project_file_delete_error",
            "mission_control_events",
            "mission_understanding_review_ack",
            "mission_timeline",
            "IMPACT_APPLIED",
            "IMPACT_PREDICTION_COMPLETED",
        }
        for event_type in sorted(expected_additional):
            self.assertIn(event_type, SERVER_MESSAGE_TYPES)
            self.assertIn(event_type, ts_server_types)
            self.assertIn(event_type, ts_switch_cases)

    def test_mission_handler_audit_counts_and_non_silent_stub_handling(self) -> None:
        missions_path = PROJECT_ROOT / "backend" / "websocket" / "handlers" / "missions.py"
        tree = ast.parse(missions_path.read_text(encoding="utf-8"))

        handle_branches: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "handle":
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Compare) and isinstance(sub.left, ast.Name) and sub.left.id == "operation":
                        if (
                            len(sub.ops) == 1
                            and isinstance(sub.ops[0], ast.Eq)
                            and len(sub.comparators) == 1
                            and isinstance(sub.comparators[0], ast.Constant)
                            and isinstance(sub.comparators[0].value, str)
                        ):
                            handle_branches.add(sub.comparators[0].value)
                        elif (
                            len(sub.ops) == 1
                            and isinstance(sub.ops[0], ast.In)
                            and len(sub.comparators) == 1
                            and isinstance(sub.comparators[0], (ast.Tuple, ast.List, ast.Set))
                        ):
                            for elt in sub.comparators[0].elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    handle_branches.add(elt.value)

        actual_stubs = set(MISSION_HANDLERS.keys()) - handle_branches
        actual_legacy = handle_branches - set(MISSION_HANDLERS.keys())

        self.assertEqual(len(MISSION_HANDLERS), 129)
        self.assertEqual(actual_stubs, set(MISSION_UNIMPLEMENTED_STUB_OPERATIONS))
        self.assertEqual(len(MISSION_UNIMPLEMENTED_STUB_OPERATIONS), 33)
        self.assertEqual(actual_legacy, set(MISSION_UNREGISTERED_LEGACY_BRANCHES))
        self.assertEqual(len(MISSION_UNREGISTERED_LEGACY_BRANCHES), 14)

    def test_mission_stub_operation_emits_diagnostic_instead_of_silent_drop(self) -> None:
        import asyncio

        sent_events: list[dict] = []

        async def _send_ws(_ws, payload: dict) -> None:
            sent_events.append(payload)

        handler = MissionWebSocketHandler(
            mission_planner=SimpleNamespace(),
            mission_executor=SimpleNamespace(),
            mission_autonomy=SimpleNamespace(),
            responder=SimpleNamespace(
                connections=SimpleNamespace(send=_send_ws),
                send_json=_send_ws,
            ),
        )
        stub_op = sorted(MISSION_UNIMPLEMENTED_STUB_OPERATIONS)[0]
        dummy_session = SimpleNamespace(selected_project_id="proj-1")
        asyncio.run(
            handler.handle(
                object(),
                {
                    "type": stub_op,
                    "project_id": "proj-1",
                    "mission_id": "m-1",
                    "request_id": "req-stub-1",
                },
                dummy_session,
            )
        )
        self.assertEqual(len(sent_events), 1)
        self.assertEqual(sent_events[0]["type"], "system")
        self.assertIn(stub_op, sent_events[0]["content"])
        normalized = normalize_ws_message(sent_events[0])
        self.assertIsNotNone(normalized)

    def test_normalize_ws_message_preserves_request_id(self) -> None:
        msg_with_id = normalize_ws_message(
            {
                "type": "note_content",
                "filename": "notes.md",
                "content": "hello",
                "request_id": "corr-abc-123",
            }
        )
        self.assertEqual(msg_with_id["request_id"], "corr-abc-123")

        msg_without_id = normalize_ws_message(
            {
                "type": "note_content",
                "filename": "notes.md",
                "content": "hello",
            }
        )
        self.assertNotIn("request_id", msg_without_id)

    def test_virtual_ipc_and_stdio_gateway_preserve_correlation_and_validate(self) -> None:
        import asyncio

        async def _noop(*_args, **_kwargs) -> None:
            return None

        async def _run() -> list[dict]:
            captured: list[dict] = []

            class CaptureGateway(StdioTransportGateway):
                async def send_message(self, message: dict) -> None:
                    captured.append(message)

            dispatcher = WebSocketDispatcher(
                services=SimpleNamespace(),
                result_sender=_noop,
                result_broadcaster=_noop,
            )
            gateway = CaptureGateway(dispatcher=dispatcher)

            # 1) Invalid mission payload missing required `project_id`
            await gateway._handle_raw_line(
                json.dumps(
                    {
                        "type": "mission_list",
                        "request_id": "stdio-corr-1",
                    }
                )
            )
            # 2) Invalid payload missing `type`
            await gateway._handle_raw_line(
                json.dumps(
                    {
                        "request_id": "stdio-corr-2",
                    }
                )
            )
            # 3) Invalid study payload missing required `document_id`
            await gateway._handle_raw_line(
                json.dumps(
                    {
                        "type": "study_get_document_file",
                        "request_id": "stdio-corr-3",
                    }
                )
            )
            return captured

        captured = asyncio.run(_run())
        self.assertEqual(len(captured), 3)
        self.assertEqual(captured[0]["type"], "system")
        self.assertEqual(captured[0]["request_id"], "stdio-corr-1")
        self.assertEqual(captured[1]["type"], "error")
        self.assertEqual(captured[1]["request_id"], "stdio-corr-2")
        self.assertEqual(captured[2]["type"], "study_error")
        self.assertEqual(captured[2]["request_id"], "stdio-corr-3")

        # VirtualIPCClient preserves active bound request_id
        emitted_virtual: list[dict] = []

        async def _send_with_virtual_client() -> None:
            class VirtualCaptureGateway(StdioTransportGateway):
                async def send_message(self, message: dict) -> None:
                    emitted_virtual.append(message)

            gateway = VirtualCaptureGateway(dispatcher=SimpleNamespace())
            client = VirtualIPCClient(gateway)
            with bind_response_request_id("virt-req-9"):
                await client.send({"type": "coding_session_error", "error": "boom"})

        asyncio.run(_send_with_virtual_client())
        self.assertEqual(len(emitted_virtual), 1)
        self.assertEqual(emitted_virtual[0]["type"], "coding_session_error")
        self.assertEqual(emitted_virtual[0]["error"], "boom")
        self.assertEqual(emitted_virtual[0]["request_id"], "virt-req-9")


if __name__ == "__main__":
    unittest.main()

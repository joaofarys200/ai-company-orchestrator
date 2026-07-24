import json
import shutil
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx

from agents.orchestrator import project_builder
from agents.orchestrator.flight_recorder import ProjectBuilderFlightRecorder


class ProjectBuilderFlightRecorderTest(unittest.TestCase):
    def make_recorder(self, root: str, **kwargs):
        return ProjectBuilderFlightRecorder(Path(root) / "diagnostics", heartbeat_interval=1.0, **kwargs)

    @staticmethod
    def events(recorder):
        return [json.loads(line) for line in recorder.events_path.read_text(encoding="utf-8").splitlines()]

    def test_completed_spans_have_unique_ids_and_monotonic_offsets(self):
        with TemporaryDirectory() as root:
            recorder = self.make_recorder(root)
            with recorder.span("planning", phase="PLANNING") as parent:
                with recorder.span("request", phase="REQUESTER") as child:
                    child.progress(operation="chunk")
            recorder.close(status="SUCCEEDED", final_state={"status": "SUCCEEDED"})

            events = self.events(recorder)
            spans = [item for item in events if item["event"] == "span_started"]
            completed = [item for item in events if item["event"] == "span_completed"]
            self.assertEqual(len(spans), 2)
            self.assertEqual(len({item["span_id"] for item in spans}), 2)
            self.assertEqual({item["span_id"] for item in spans}, {item["span_id"] for item in completed})
            child_start = next(item for item in spans if item["metadata"]["operation"] == "request")
            parent_start = next(item for item in spans if item["metadata"]["operation"] == "planning")
            self.assertEqual(child_start["parent_span_id"], parent_start["span_id"])
            offsets = [item["monotonic_offset_ms"] for item in events]
            self.assertEqual(offsets, sorted(offsets))
            self.assertTrue(recorder.summary_path.is_file())
            self.assertIn("## Gaps", recorder.timeline_path.read_text(encoding="utf-8"))

    def test_failed_span_preserves_exception_without_swallowing(self):
        with TemporaryDirectory() as root:
            recorder = self.make_recorder(root)
            with self.assertRaisesRegex(ValueError, "bad plan"):
                with recorder.span("semantic", phase="SEMANTIC_VALIDATION"):
                    raise ValueError("bad plan")
            recorder.close(status="FAILED", final_state={"status": "FAILED"})

            failed = [item for item in self.events(recorder) if item["event"] == "span_failed"]
            self.assertEqual(len(failed), 1)
            self.assertEqual(failed[0]["error_type"], "ValueError")
            self.assertIn("bad plan", failed[0]["error_message"])
            errors = json.loads(recorder.errors_path.read_text(encoding="utf-8"))
            self.assertEqual(errors[0]["error_type"], "ValueError")

    def test_interrupted_span_and_last_event_survive_close(self):
        with TemporaryDirectory() as root:
            recorder = self.make_recorder(root)
            recorder.event("http_request_started", phase="REQUESTER")
            with self.assertRaises(KeyboardInterrupt):
                with recorder.span("model", phase="REQUESTER"):
                    raise KeyboardInterrupt()
            recorder.close(status="INTERRUPTED", final_state={"status": "INTERRUPTED"})

            events = self.events(recorder)
            self.assertEqual(events[-1]["event"], "span_interrupted")
            self.assertTrue(recorder.final_state_path.is_file())
            self.assertEqual(
                json.loads(recorder.final_state_path.read_text(encoding="utf-8"))["status"],
                "INTERRUPTED",
            )

    def test_sanitizes_secrets_and_bounds_output_samples(self):
        with TemporaryDirectory() as root:
            recorder = self.make_recorder(root, diagnostics_enabled=True)
            recorder.event(
                "command_stdout_progress",
                phase="TECHNICAL_VALIDATION",
                metadata={
                    "authorization": "Bearer super-secret",
                    "stdout": "x" * 10000,
                    "path": "workspace/projects/demo/app.js",
                },
            )
            recorder.write_raw_artifact("response.txt", "token=super-secret\n" + ("x" * 10000))
            recorder.close(status="SUCCEEDED", final_state={"status": "SUCCEEDED"})

            raw = recorder.events_path.read_text(encoding="utf-8")
            self.assertNotIn("super-secret", raw)
            self.assertLess(len(raw), 8000)
            response = (recorder.directory / "response.txt").read_text(encoding="utf-8")
            self.assertNotIn("super-secret", response)
            self.assertLessEqual(len(response), 1_000_000)

    def test_heartbeat_records_active_phase_and_resource_sample(self):
        with TemporaryDirectory() as root:
            recorder = self.make_recorder(root)
            with recorder.span("long_operation", phase="REQUESTER"):
                time.sleep(1.1)
            recorder.close(status="SUCCEEDED", final_state={"status": "SUCCEEDED"})

            events = self.events(recorder)
            heartbeats = [item for item in events if item["event"] == "heartbeat"]
            self.assertTrue(heartbeats)
            self.assertEqual(heartbeats[0]["phase"], "REQUESTER")
            samples = recorder.resources_path.read_text(encoding="utf-8").splitlines()
            self.assertTrue(samples)

    def test_summary_reports_slowest_phase_and_progress_gap(self):
        with TemporaryDirectory() as root:
            recorder = self.make_recorder(root)
            with recorder.span("fast", phase="PLAN"):
                pass
            with recorder.span("slow", phase="MODEL"):
                time.sleep(0.05)
            recorder.close(status="FAILED", final_state={"status": "FAILED"})

            summary = json.loads(recorder.summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["slowest_phase"]["operation"], "slow")
            self.assertIn("last_phase_started", summary)
            self.assertIn("max_period_without_progress_ms", summary)
            self.assertIn("gaps", summary)


class ProjectBuilderFlightRecorderIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_build_project_records_materialization_and_final_state(self):
        project_root = Path("workspace/projects/flight-recorder-integration")
        absolute_root = project_root.resolve()
        shutil.rmtree(absolute_root, ignore_errors=True)
        with TemporaryDirectory() as root:
            recorder = ProjectBuilderFlightRecorder(Path(root) / "diagnostics")

            async def requester(_prompt, _correction):
                return {
                    "project_name": "Flight Recorder Integration",
                    "stack": "Node.js",
                    "files": [{"path": "app.js", "content": "console.log('ok');\n"}],
                    "validation_commands": ["node --check app.js"],
                    "entrypoints": ["app.js"],
                    "preview_command": "",
                }

            try:
                result = await project_builder.build_project(
                    "cria uma app node",
                    plan_requester=requester,
                    start_preview=False,
                    flight_recorder=recorder,
                )
                events = [
                    json.loads(line)
                    for line in recorder.events_path.read_text(encoding="utf-8").splitlines()
                ]
                names = {item["event"] for item in events}
                self.assertIn("build_project_entered", names)
                self.assertIn("file_write_started", names)
                self.assertIn("file_write_completed", names)
                self.assertIn("command_execution_started", names)
                self.assertIn("command_execution_completed", names)
                self.assertIn("build_completed", names)
                self.assertEqual(result.flight_recorder_path, str(recorder.directory))
                summary = json.loads(recorder.summary_path.read_text(encoding="utf-8"))
                self.assertIn("slowest_phase", summary)
            finally:
                shutil.rmtree(absolute_root, ignore_errors=True)

    async def test_requester_records_stream_metrics_without_full_response_by_default(self):
        with TemporaryDirectory() as root:
            recorder = ProjectBuilderFlightRecorder(Path(root) / "diagnostics")

            def handler(request):
                if request.url.path == "/api/tags":
                    return httpx.Response(200, json={"models": [{"name": "test-model"}]})
                if request.url.path == "/api/ps":
                    return httpx.Response(200, json={"models": [{"name": "test-model"}]})
                payload = {
                    "message": {"role": "assistant", "content": '{"project_name":"demo"}'},
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 10,
                    "eval_count": 8,
                    "eval_duration": 100,
                }
                return httpx.Response(200, content=(json.dumps(payload) + "\n").encode("utf-8"))

            async def no_sleep(_seconds):
                return None

            with patch.dict("os.environ", {"OLLAMA_MODEL": "test-model"}):
                requester = project_builder.OllamaPlanRequester(
                    transport=httpx.MockTransport(handler),
                    sleep=no_sleep,
                    flight_recorder=recorder,
                )
                result = await requester("cria um projeto demo")
            recorder.close(status="SUCCEEDED", final_state={"status": "SUCCEEDED"})

            self.assertIn("project_name", result)
            events = [
                json.loads(line)
                for line in recorder.events_path.read_text(encoding="utf-8").splitlines()
            ]
            names = {item["event"] for item in events}
            self.assertTrue({
                "requester_started",
                "readiness_check_started",
                "response_headers_received",
                "first_response_byte",
                "first_http_chunk",
                "first_nonempty_content",
                "first_valid_json_object",
                "stream_completed",
                "requester_completed",
            }.issubset(names))
            metrics = json.loads(recorder.payload_metrics_path.read_text(encoding="utf-8"))
            self.assertEqual(metrics["attempts"][0]["chunk_count"], 1)
            self.assertEqual(metrics["attempts"][0]["eval_count"], 8)
            self.assertFalse((recorder.directory / "response_attempt_1.jsonl").exists())


if __name__ == "__main__":
    unittest.main()

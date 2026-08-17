"""
Test runner using standard library unittest for lecture recording, synthesis and WebSocket handlers.
"""

import sys
import os
import asyncio
import tempfile
import unittest
from pathlib import Path

# Ensure root directory is in sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tests.test_lecture_recorder import (
    test_lecture_session_dataclass,
    test_recorder_start_and_stop,
    test_recorder_prevents_double_start,
)
from tests.test_lecture_synthesizer import (
    test_vault_linker_auto_linking,
    test_cornell_note_generation,
    test_process_lecture_end_to_end,
)
from tests.test_lecture_websocket_handler import (
    test_lecture_websocket_workflow,
)
from tests.test_transport_gateway import (
    test_stdio_gateway_handle_valid_json,
    test_stdio_gateway_ignores_non_json_logs,
    test_stdio_gateway_broadcast,
)


class TestLectureModules(unittest.TestCase):
    def test_session_dataclass(self):
        test_lecture_session_dataclass()

    def test_recorder_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_recorder_start_and_stop(Path(tmpdir))

    def test_recorder_double_start(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_recorder_prevents_double_start(Path(tmpdir))

    def test_linker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_vault_linker_auto_linking(Path(tmpdir))

    def test_cornell_gen(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_cornell_note_generation(Path(tmpdir))

    def test_process_e2e(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_process_lecture_end_to_end(Path(tmpdir))

    def test_websocket_handler(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            asyncio.run(test_lecture_websocket_workflow(Path(tmpdir)))

    def test_transport_gateway_json(self):
        test_stdio_gateway_handle_valid_json()

    def test_transport_gateway_filter_logs(self):
        test_stdio_gateway_ignores_non_json_logs()

    def test_transport_gateway_broadcast(self):
        test_stdio_gateway_broadcast()


if __name__ == "__main__":
    unittest.main()

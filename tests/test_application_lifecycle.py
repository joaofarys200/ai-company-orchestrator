import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from backend.application_lifecycle import ApplicationLifecycle


class ApplicationLifecycleTest(unittest.TestCase):
    def test_startup_and_shutdown_have_explicit_symmetric_order(self):
        events = []
        database = SimpleNamespace(
            init_db=lambda: events.append("database.start")
        )
        sandbox = SimpleNamespace(
            start_docker_sandbox=lambda: events.append(
                "sandbox.start"
            ),
            stop_custom_project=lambda: events.append(
                "preview.stop"
            ),
            stop_docker_sandbox=lambda: events.append(
                "sandbox.stop"
            ),
        )
        voice = SimpleNamespace(
            stop=lambda: events.append("voice.stop")
        )
        frontend = SimpleNamespace(
            stop=lambda: events.append("frontend.stop")
        )
        services = SimpleNamespace(
            database=database,
            sandbox=sandbox,
        )
        lifecycle = ApplicationLifecycle(
            services=services,
            initialize_voice=lambda: events.append("voice.start"),
            get_voice_service=lambda: voice,
            start_frontend=lambda: (
                events.append("frontend.start") or frontend
            ),
        )

        lifecycle.startup()
        lifecycle.startup()
        lifecycle.shutdown()
        lifecycle.shutdown()

        self.assertEqual(
            events,
            [
                "database.start",
                "voice.start",
                "frontend.start",
                "sandbox.start",
                "voice.stop",
                "preview.stop",
                "sandbox.stop",
                "frontend.stop",
            ],
        )
        self.assertFalse(lifecycle.started)

    def test_shutdown_tolerates_disabled_voice_and_frontend(self):
        sandbox = SimpleNamespace(
            start_docker_sandbox=Mock(),
            stop_custom_project=Mock(),
            stop_docker_sandbox=Mock(),
        )
        lifecycle = ApplicationLifecycle(
            services=SimpleNamespace(
                database=SimpleNamespace(init_db=Mock()),
                sandbox=sandbox,
            ),
            initialize_voice=Mock(),
            get_voice_service=lambda: None,
            start_frontend=lambda: None,
        )

        lifecycle.startup()
        lifecycle.shutdown()

        sandbox.stop_custom_project.assert_called_once_with()
        sandbox.stop_docker_sandbox.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

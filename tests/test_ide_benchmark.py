from types import SimpleNamespace

from scripts.ide_benchmark import rollback_session_if_needed, session_primary_error_message


class RollbackSpy:
    def __init__(self):
        self.calls = 0

    def rollback_session(self, project_id, session_id, confirmed=False):
        self.calls += 1
        raise AssertionError("rollback nao devia ser chamado")


def test_benchmark_does_not_rollback_without_checkpoint():
    sessions = RollbackSpy()
    session = SimpleNamespace(
        session_id="session-id",
        checkpoint={},
        checkpoint_created=False,
        status="ERROR",
        applied_changes=[],
        writes_started=False,
        rollback_succeeded=False,
        primary_error={
            "type": "RuntimeError",
            "message": "checkpoint original failure",
            "traceback": "trace",
        },
        errors=["secondary error must not replace primary"],
    )

    restored, rollback_executed = rollback_session_if_needed(sessions, "project", session)

    assert restored is session
    assert rollback_executed is False
    assert sessions.calls == 0
    assert session_primary_error_message(session) == "checkpoint original failure"

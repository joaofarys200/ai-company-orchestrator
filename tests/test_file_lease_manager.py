"""
Phase 24: Unit tests for FileLeaseManager
Validates:
1. Exclusive lock acquisition.
2. Conflict detection when two holders attempt concurrent modification.
3. Renewal by the same holder.
4. Expiration behavior.
5. Release and cleanup.
6. Context manager behavior.
"""

import time
import pytest
from agents.file_lease_manager import (
    FileLeaseConflictError,
    FileLeaseManager,
    get_file_lease_manager,
    reset_file_lease_manager,
)


@pytest.fixture
def lease_mgr():
    reset_file_lease_manager()
    mgr = FileLeaseManager(default_ttl_seconds=10.0)
    yield mgr
    reset_file_lease_manager()


def test_acquire_and_release_file_lease(tmp_path, lease_mgr):
    """1. Deve adquirir lease exclusiva e libertá-la com sucesso."""
    test_file = str(tmp_path / "app.js")
    lease = lease_mgr.acquire_file_lease(test_file, holder_id="mission_1")

    assert lease.holder_id == "mission_1"
    assert lease_mgr.is_file_locked(test_file) is True
    assert lease_mgr.get_lease_holder(test_file) == "mission_1"

    # Liberta lease
    released = lease_mgr.release_file_lease(lease.lease_id, holder_id="mission_1")
    assert released is True
    assert lease_mgr.is_file_locked(test_file) is False


def test_concurrent_conflict_detected(tmp_path, lease_mgr):
    """2. Segundo titular deve ser rejeitado com FileLeaseConflictError."""
    test_file = str(tmp_path / "app.js")
    lease_mgr.acquire_file_lease(test_file, holder_id="mission_1")

    with pytest.raises(FileLeaseConflictError) as exc_info:
        lease_mgr.acquire_file_lease(test_file, holder_id="mission_2")

    assert "Conflito de modificação" in str(exc_info.value)
    assert "mission_1" in str(exc_info.value)


def test_same_holder_renewal(tmp_path, lease_mgr):
    """3. Mesmo titular pode renovar a sua lease sem conflito."""
    test_file = str(tmp_path / "app.js")
    now = 1000.0
    lease1 = lease_mgr.acquire_file_lease(test_file, holder_id="mission_1", ttl_seconds=10.0, now=now)
    assert lease1.expires_at == 1010.0

    lease2 = lease_mgr.acquire_file_lease(test_file, holder_id="mission_1", ttl_seconds=20.0, now=now + 5.0)
    assert lease2.lease_id == lease1.lease_id
    assert lease2.expires_at == 1025.0


def test_expired_lease_allows_new_holder(tmp_path, lease_mgr):
    """4. Lease expirada permite que novo titular adquira sem erro."""
    test_file = str(tmp_path / "app.js")
    now = 1000.0
    lease_mgr.acquire_file_lease(test_file, holder_id="mission_1", ttl_seconds=5.0, now=now)

    # 10 segundos depois: expirou
    lease2 = lease_mgr.acquire_file_lease(test_file, holder_id="mission_2", ttl_seconds=10.0, now=now + 10.0)
    assert lease2.holder_id == "mission_2"
    assert lease_mgr.get_lease_holder(test_file, now=now + 10.0) == "mission_2"


def test_release_all_for_holder(tmp_path, lease_mgr):
    """5. release_all_for_holder deve libertar todos os ficheiros detidos por uma missão."""
    f1 = str(tmp_path / "app.js")
    f2 = str(tmp_path / "logger.js")
    f3 = str(tmp_path / "config.json")

    lease_mgr.acquire_file_lease(f1, holder_id="mission_1")
    lease_mgr.acquire_file_lease(f2, holder_id="mission_1")
    lease_mgr.acquire_file_lease(f3, holder_id="mission_2")

    count = lease_mgr.release_all_for_holder("mission_1")
    assert count == 2

    assert lease_mgr.is_file_locked(f1) is False
    assert lease_mgr.is_file_locked(f2) is False
    assert lease_mgr.is_file_locked(f3) is True


def test_file_lock_context_manager(tmp_path, lease_mgr):
    """6. Context manager deve garantir libertação automática."""
    test_file = str(tmp_path / "app.js")
    with lease_mgr.file_lock(test_file, holder_id="mission_ctx"):
        assert lease_mgr.is_file_locked(test_file) is True
        assert lease_mgr.get_lease_holder(test_file) == "mission_ctx"

    assert lease_mgr.is_file_locked(test_file) is False

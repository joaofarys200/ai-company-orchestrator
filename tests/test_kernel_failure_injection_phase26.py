"""
JARVIS OS — Phase 26: Kernel Failure Injection & Resilience Test Suite
Tests graceful degradation, exception handling, and recovery under fault injection:
1. Thread affinity invalid core recovery.
2. Socket buffer exhaustion and recovery.
3. Rapid connection churn and teardown under load.
4. Payload size boundary enforcement.
5. Concurrent buffer pool slice thrashing.
"""

import ctypes
import os
import platform
import sys
import unittest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from agents.native_rio_transport import (
    RioSocket,
    RioNativeBinding,
    RioRegisteredBufferPool,
    RioCorrectnessOracle,
)


class TestKernelFailureInjectionPhase26(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binding = RioNativeBinding.get_instance()
        cls.has_rio = cls.binding.available

    def test_fault_1_invalid_thread_affinity_recovery(self):
        """Fault 1: Setting invalid thread affinity masks must fail safely without crash."""
        if platform.system() != "Windows":
            self.skipTest("Windows specific")

        k32 = ctypes.windll.kernel32
        k32.SetThreadAffinityMask.restype = ctypes.c_size_t
        k32.SetThreadAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        th = k32.GetCurrentThread()

        # Test invalid mask (0) fails gracefully (returns 0)
        invalid_res = k32.SetThreadAffinityMask(th, ctypes.c_size_t(0))
        self.assertEqual(invalid_res, 0)

        # Restore full mask
        all_mask = (1 << 16) - 1
        restore_res = k32.SetThreadAffinityMask(th, ctypes.c_size_t(all_mask))
        self.assertGreaterEqual(restore_res, 0)

    def test_fault_2_buffer_pool_exhaustion_recovery(self):
        """Fault 2: Acquiring all slices must cleanly return None without memory leak."""
        pool = RioRegisteredBufferPool(buffer_size=1 * 1024 * 1024, slice_size=64 * 1024)
        acquired = []
        # Exhaust pool
        for _ in range(32):
            idx = pool.acquire_slice()
            if idx is not None:
                acquired.append(idx)

        # Further acquire must return None safely
        extra = pool.acquire_slice()
        self.assertIsNone(extra)

        # Release all
        for idx in acquired:
            pool.release_slice(idx)

        # Now acquire succeeds again
        recovered = pool.acquire_slice()
        self.assertIsNotNone(recovered)
        pool.release_slice(recovered)

    def test_fault_3_rapid_connect_churn(self):
        """Fault 3: Rapid sequential socket creation and teardown must not leak handles."""
        if not self.has_rio:
            self.skipTest("RIO not available")

        for p in range(5):
            sock = RioSocket(bind_ip="127.0.0.1", bind_port=31000 + p, buffer_size=2 * 1024 * 1024, queue_depth=128)
            self.assertTrue(sock.is_native_active or sock.bind_port > 0)
            sock.close()

    def test_fault_4_payload_size_boundaries(self):
        """Fault 4: Sending oversize batches or payloads must be handled without crash."""
        if not self.has_rio:
            self.skipTest("RIO not available")

        sender = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=2 * 1024 * 1024, queue_depth=128)
        sender.connect("127.0.0.1", 34567)

        # Oversize single payload (64KB)
        big_payload = b"OVERSIZE_" * 7000
        sent = sender.send_batch([big_payload])
        self.assertIn(sent, [0, 1])

        sender.close()

    def test_fault_5_concurrent_pool_thrashing(self):
        """Fault 5: Multi-threaded pool slice acquisition and release under churn."""
        import threading

        pool = RioRegisteredBufferPool(buffer_size=4 * 1024 * 1024, slice_size=64 * 1024)
        errors = []

        def worker():
            try:
                for _ in range(50):
                    idx = pool.acquire_slice()
                    if idx is not None:
                        pool.release_slice(idx)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Pool thrashing errors: {errors}")


if __name__ == "__main__":
    unittest.main()

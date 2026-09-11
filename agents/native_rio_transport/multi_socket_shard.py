"""
JARVIS OS — Phase 27: Multi-Socket Sharding Architecture (Experimental)
Provides deterministic UDP socket sharding across N independent RIO sockets,
independent port tuples, and dedicated completion queues.
"""

from __future__ import annotations

import hashlib
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from agents.native_rio_transport import (
    RioSocket,
    RioNativeBinding,
    RioRegisteredBufferPool,
    RioCorrectnessOracle,
)


class MultiSocketTransportShard:
    """
    Experimental Multi-Socket Sharded Datapath.
    Distributes high-throughput UDP streams across N independent RIO sockets.
    Each shard possesses:
    - Distinct UDP port
    - Dedicated RIO request queue & completion queue
    - Dedicated registered buffer pool
    """

    def __init__(
        self,
        num_shards: int = 1,
        base_bind_port: int = 33000,
        strategy: str = "hash_stream",
        buffer_size_per_shard: int = 4 * 1024 * 1024,
        queue_depth_per_shard: int = 512,
        bind_ip: str = "127.0.0.1",
    ):
        self.num_shards = max(1, num_shards)
        self.base_bind_port = base_bind_port
        self.strategy = strategy
        self.bind_ip = bind_ip
        self.buffer_size_per_shard = buffer_size_per_shard
        self.queue_depth_per_shard = queue_depth_per_shard

        self.shards: List[RioSocket] = []
        self.active_status: List[bool] = []
        self.shard_stats: List[Dict[str, int]] = []
        self._rr_index = 0
        self._lock = threading.Lock()
        self.oracle = RioCorrectnessOracle()

        self._init_shards()

    def _init_shards(self):
        for i in range(self.num_shards):
            port = self.base_bind_port + i
            sock = RioSocket(
                bind_ip=self.bind_ip,
                bind_port=port,
                buffer_size=self.buffer_size_per_shard,
                queue_depth=self.queue_depth_per_shard,
            )
            self.shards.append(sock)
            self.active_status.append(True)
            self.shard_stats.append({
                "shard_id": i,
                "port": port,
                "packets_sent": 0,
                "bytes_sent": 0,
                "control_packets_sent": 0,
                "drops": 0,
                "errors": 0,
            })

    def connect(self, dest_ip: str, base_dest_port: int):
        """Connects each shard to its corresponding destination peer port."""
        for i, sock in enumerate(self.shards):
            sock.connect(dest_ip, base_dest_port + i)

    def route_stream(self, stream_id: int, flow_id: Optional[int] = None, is_control: bool = False) -> int:
        """
        Deterministically maps a stream to an active shard.
        Stream 0 and Stream 2 (control plane) are always prioritized on Shard 0.
        """
        # Get list of currently active shard indices
        active_indices = [idx for idx, active in enumerate(self.active_status) if active]
        if not active_indices:
            return 0  # Fallback to 0 if all failed

        # Priority control plane traffic
        if is_control or stream_id in (0, 2):
            return active_indices[0]

        if self.strategy == "round_robin":
            with self._lock:
                idx = active_indices[self._rr_index % len(active_indices)]
                self._rr_index += 1
                return idx
        elif self.strategy == "hash_flow":
            key = flow_id if flow_id is not None else stream_id
            h = int(hashlib.md5(str(key).encode()).hexdigest(), 16)
            return active_indices[h % len(active_indices)]
        else:  # default: hash_stream
            h = int(hashlib.sha256(f"stream_{stream_id}".encode()).hexdigest(), 16)
            return active_indices[h % len(active_indices)]

    def send_stream_packet(self, stream_id: int, payload: bytes, is_control: bool = False) -> bool:
        """Sends a single packet on the deterministically mapped shard."""
        shard_idx = self.route_stream(stream_id, is_control=is_control)
        sock = self.shards[shard_idx]

        try:
            if is_control:
                sock.send_priority_control(payload)
                self.shard_stats[shard_idx]["control_packets_sent"] += 1
            else:
                sent = sock.send_batch([payload])
                if sent < 1:
                    self.shard_stats[shard_idx]["drops"] += 1
                    return False
            self.shard_stats[shard_idx]["packets_sent"] += 1
            self.shard_stats[shard_idx]["bytes_sent"] += len(payload)
            return True
        except Exception:
            self.shard_stats[shard_idx]["errors"] += 1
            return False

    def send_batch_to_shard(self, shard_idx: int, batch: List[bytes]) -> int:
        """Sends a pre-formed batch directly to a specific shard."""
        if not (0 <= shard_idx < self.num_shards) or not self.active_status[shard_idx]:
            return 0
        sock = self.shards[shard_idx]
        try:
            sent = sock.send_batch(batch)
            self.shard_stats[shard_idx]["packets_sent"] += sent
            self.shard_stats[shard_idx]["bytes_sent"] += sum(len(p) for p in batch[:sent])
            if sent < len(batch):
                self.shard_stats[shard_idx]["drops"] += (len(batch) - sent)
            return sent
        except Exception:
            self.shard_stats[shard_idx]["errors"] += len(batch)
            return 0

    def fail_shard(self, shard_idx: int) -> bool:
        """Simulates abrupt failure of a shard for chaos/failover testing."""
        if 0 <= shard_idx < self.num_shards:
            self.active_status[shard_idx] = False
            return True
        return False

    def recover_shard(self, shard_idx: int) -> bool:
        """Recovers and re-activates a previously failed shard."""
        if 0 <= shard_idx < self.num_shards:
            self.active_status[shard_idx] = True
            return True
        return False

    def get_aggregate_stats(self) -> Dict[str, Any]:
        """Calculates global and per-shard telemetry and Jain fairness index."""
        pkts = [s["packets_sent"] for s in self.shard_stats]
        bytes_list = [s["bytes_sent"] for s in self.shard_stats]
        total_pkts = sum(pkts)
        total_bytes = sum(bytes_list)
        total_drops = sum(s["drops"] for s in self.shard_stats)
        total_errors = sum(s["errors"] for s in self.shard_stats)

        # Jain's fairness index: (sum(x_i))^2 / (n * sum(x_i^2))
        n = len(pkts)
        sum_x = sum(pkts)
        sum_x_sq = sum(x * x for x in pkts)
        jain_fairness = 1.0
        if n > 0 and sum_x_sq > 0:
            jain_fairness = round((sum_x * sum_x) / (n * sum_x_sq), 4)

        return {
            "num_shards": self.num_shards,
            "active_shards": sum(1 for a in self.active_status if a),
            "strategy": self.strategy,
            "total_packets": total_pkts,
            "total_bytes": total_bytes,
            "total_drops": total_drops,
            "total_errors": total_errors,
            "jain_fairness_index": jain_fairness,
            "per_shard": self.shard_stats,
        }

    def close(self):
        """Closes all underlying RIO sockets."""
        for sock in self.shards:
            try:
                sock.close()
            except Exception:
                pass
        self.shards.clear()
        self.active_status.clear()

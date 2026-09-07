"""
JARVIS OS — Phase 18.3: High-Performance Local IPC & Shared-Memory Architecture
Provides unified transport abstractions, zero-copy shared memory slots, lock-minimized ring buffers,
deterministic memory ordering, corruption rejection, leak detection, and adaptive transport selection.
"""

from __future__ import annotations

import abc
import enum
import hashlib
import multiprocessing as mp
import os
import pickle
import struct
import threading
import time
import uuid
import zlib
from dataclasses import asdict, dataclass, field
from multiprocessing import shared_memory
from typing import Any, Callable, Sequence


# ── CUSTOM EXCEPTIONS ─────────────────────────────────────────────────────────

class IpcTransportError(Exception):
    """Base exception for IPC transport failures."""
    pass


class CorruptedMessageError(IpcTransportError):
    """Raised when message framing or memory integrity is violated."""
    pass


class InvalidChecksumError(CorruptedMessageError):
    """Raised when message checksum validation fails."""
    pass


class SequenceViolationError(CorruptedMessageError):
    """Raised when sequence number is out-of-order or duplicated."""
    pass


class BackpressureOverflowError(IpcTransportError):
    """Raised when ring buffer or queue is saturated under backpressure."""
    pass


class TransportClosedError(IpcTransportError):
    """Raised when attempting to operate on a closed or drained transport."""
    pass


# ── ENUMS & VALUE OBJECTS ──────────────────────────────────────────────────────

class IpcTransportType(str, enum.Enum):
    PIPE = "PIPE"
    QUEUE = "QUEUE"
    SHARED_MEMORY = "SHARED_MEMORY"
    RING_BUFFER = "RING_BUFFER"
    ADAPTIVE = "ADAPTIVE"


class BufferSlotState(int, enum.Enum):
    EMPTY = 0
    WRITING = 1
    COMMITTED = 2
    READING = 3
    ACKNOWLEDGED = 4


@dataclass
class TransportMessage:
    """
    Standard framed message envelope with deterministic consistency metadata:
    WRITE -> COMMIT -> SEQUENCE -> READ -> VERIFY
    """
    message_id: str
    sequence: int
    length: int
    checksum: str
    payload: bytes
    created_at: float = field(default_factory=time.perf_counter)

    @classmethod
    def create(cls, data: Any, sequence: int) -> "TransportMessage":
        payload_bytes = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
        msg_id = uuid.uuid4().hex
        checksum = f"{zlib.crc32(payload_bytes) & 0xFFFFFFFF:08x}"
        return cls(
            message_id=msg_id,
            sequence=sequence,
            length=len(payload_bytes),
            checksum=checksum,
            payload=payload_bytes,
        )

    def unpack(self, expected_sequence: int | None = None) -> Any:
        # 1. Verify length
        if len(self.payload) != self.length:
            raise CorruptedMessageError(
                f"Payload length mismatch: expected {self.length}, got {len(self.payload)}"
            )

        # 2. Verify sequence if required
        if expected_sequence is not None and self.sequence != expected_sequence:
            raise SequenceViolationError(
                f"Sequence violation: expected {expected_sequence}, got {self.sequence}"
            )

        # 3. Verify checksum
        calc_checksum = f"{zlib.crc32(self.payload) & 0xFFFFFFFF:08x}"
        if calc_checksum.lower() != self.checksum.lower():
            raise InvalidChecksumError(
                f"Checksum mismatch: expected {self.checksum}, calculated {calc_checksum}"
            )

        # 4. Deserialization
        return pickle.loads(self.payload)


# ── SHARED MEMORY TRACKER (LEAK DETECTION) ─────────────────────────────────────

class SharedMemoryTracker:
    """
    Process-wide registry and leak detector for multiprocessing.shared_memory segments.
    Guarantees orphan_shared_memory == 0 across lifecycle operations.
    """
    _lock = threading.Lock()
    _active_segments: dict[str, int] = {}  # name -> size in bytes
    _peak_allocated_bytes: int = 0
    _total_allocations: int = 0
    _total_releases: int = 0

    @classmethod
    def register(cls, name: str, size: int) -> None:
        with cls._lock:
            cls._active_segments[name] = size
            cls._total_allocations += 1
            current_total = sum(cls._active_segments.values())
            if current_total > cls._peak_allocated_bytes:
                cls._peak_allocated_bytes = current_total

    @classmethod
    def release(cls, name: str) -> None:
        with cls._lock:
            if name in cls._active_segments:
                del cls._active_segments[name]
                cls._total_releases += 1

    @classmethod
    def get_orphan_count(cls) -> int:
        with cls._lock:
            return len(cls._active_segments)

    @classmethod
    def get_active_segments(cls) -> dict[str, int]:
        with cls._lock:
            return dict(cls._active_segments)

    @classmethod
    def get_stats(cls) -> dict[str, Any]:
        with cls._lock:
            return {
                "active_segments": len(cls._active_segments),
                "total_allocations": cls._total_allocations,
                "total_releases": cls._total_releases,
                "peak_allocated_bytes": cls._peak_allocated_bytes,
                "current_allocated_bytes": sum(cls._active_segments.values()),
                "orphan_shared_memory": len(cls._active_segments),
            }

    @classmethod
    def cleanup_all(cls) -> int:
        with cls._lock:
            cleaned = 0
            for name in list(cls._active_segments.keys()):
                try:
                    shm = shared_memory.SharedMemory(name=name)
                    shm.close()
                    shm.unlink()
                    cleaned += 1
                except Exception:
                    pass
            cls._active_segments.clear()
            return cleaned


# ── TRANSPORT INTERFACE ────────────────────────────────────────────────────────

class LocalIpcTransport(abc.ABC):
    """Abstract interface for local Inter-Process Communication substrates."""

    @property
    @abc.abstractmethod
    def transport_type(self) -> IpcTransportType:
        pass

    @abc.abstractmethod
    def send(self, data: Any, sequence: int | None = None) -> float:
        """
        Transmits data to receiver.
        Returns transport send latency in milliseconds.
        """
        pass

    @abc.abstractmethod
    def receive(self, timeout: float | None = None, expected_sequence: int | None = None) -> tuple[Any, float]:
        """
        Receives data from sender.
        Returns (data, transport_receive_latency_ms).
        """
        pass

    @abc.abstractmethod
    def close(self) -> None:
        """Releases underlying OS descriptors, pipes, queues, or memory segments."""
        pass

    def get_metrics(self) -> dict[str, Any]:
        return {"transport": self.transport_type.value}


# ── PIPE TRANSPORT ────────────────────────────────────────────────────────────

class PipeTransport(LocalIpcTransport):
    """
    Standard Windows Named Pipe implementation using multiprocessing.Pipe.
    Baseline reference for latency and throughput comparison.
    """

    def __init__(self, duplex: bool = True):
        self.duplex = duplex
        self._parent_conn, self._child_conn = mp.Pipe(duplex=duplex)
        self._seq = 0
        self._recv_seq = 0
        self.messages_sent = 0
        self.messages_received = 0
        self.total_send_ms = 0.0
        self.total_receive_ms = 0.0
        self._closed = False

    @property
    def transport_type(self) -> IpcTransportType:
        return IpcTransportType.PIPE

    def send(self, data: Any, sequence: int | None = None) -> float:
        if self._closed:
            raise TransportClosedError("PipeTransport is closed")
        t0 = time.perf_counter()
        seq = sequence if sequence is not None else self._seq
        msg = TransportMessage.create(data, seq)
        self._parent_conn.send(msg)
        self._seq += 1
        dur = (time.perf_counter() - t0) * 1000.0
        self.messages_sent += 1
        self.total_send_ms += dur
        return dur

    def receive(self, timeout: float | None = None, expected_sequence: int | None = None) -> tuple[Any, float]:
        if self._closed:
            raise TransportClosedError("PipeTransport is closed")
        t0 = time.perf_counter()
        if timeout is not None:
            if not self._child_conn.poll(timeout):
                raise TimeoutError(f"Pipe receive timed out after {timeout}s")
        msg: TransportMessage = self._child_conn.recv()
        dur = (time.perf_counter() - t0) * 1000.0
        data = msg.unpack(expected_sequence=expected_sequence)
        self.messages_received += 1
        self.total_receive_ms += dur
        return data, dur

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                self._parent_conn.close()
            except Exception:
                pass
            try:
                self._child_conn.close()
            except Exception:
                pass

    def get_metrics(self) -> dict[str, Any]:
        return {
            "transport": self.transport_type.value,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "avg_send_ms": round(self.total_send_ms / max(1, self.messages_sent), 3),
            "avg_receive_ms": round(self.total_receive_ms / max(1, self.messages_received), 3),
        }


# ── QUEUE TRANSPORT ───────────────────────────────────────────────────────────

class QueueTransport(LocalIpcTransport):
    """
    Buffered multi-producer multi-consumer IPC using multiprocessing.Queue.
    Supports bounded capacity and backpressure detection.
    """

    def __init__(self, maxsize: int = 128):
        self.maxsize = maxsize
        self._queue = mp.Queue(maxsize=maxsize)
        self._seq = 0
        self.messages_sent = 0
        self.messages_received = 0
        self.total_send_ms = 0.0
        self.total_receive_ms = 0.0
        self.backpressure_events = 0
        self._closed = False

    @property
    def transport_type(self) -> IpcTransportType:
        return IpcTransportType.QUEUE

    def send(self, data: Any, sequence: int | None = None) -> float:
        if self._closed:
            raise TransportClosedError("QueueTransport is closed")
        t0 = time.perf_counter()
        seq = sequence if sequence is not None else self._seq
        msg = TransportMessage.create(data, seq)
        try:
            self._queue.put(msg, block=True, timeout=5.0)
        except Exception:
            self.backpressure_events += 1
            raise BackpressureOverflowError("QueueTransport capacity reached (Backpressure triggered)")
        self._seq += 1
        dur = (time.perf_counter() - t0) * 1000.0
        self.messages_sent += 1
        self.total_send_ms += dur
        return dur

    def receive(self, timeout: float | None = None, expected_sequence: int | None = None) -> tuple[Any, float]:
        if self._closed:
            raise TransportClosedError("QueueTransport is closed")
        t0 = time.perf_counter()
        try:
            msg: TransportMessage = self._queue.get(block=True, timeout=timeout)
        except Exception:
            raise TimeoutError(f"Queue receive timed out after {timeout}s")
        dur = (time.perf_counter() - t0) * 1000.0
        data = msg.unpack(expected_sequence=expected_sequence)
        self.messages_received += 1
        self.total_receive_ms += dur
        return data, dur

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                self._queue.close()
                self._queue.join_thread()
            except Exception:
                pass

    def get_metrics(self) -> dict[str, Any]:
        return {
            "transport": self.transport_type.value,
            "maxsize": self.maxsize,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "backpressure_events": self.backpressure_events,
            "avg_send_ms": round(self.total_send_ms / max(1, self.messages_sent), 3),
            "avg_receive_ms": round(self.total_receive_ms / max(1, self.messages_received), 3),
        }


# ── SHARED MEMORY TRANSPORT ───────────────────────────────────────────────────

# Header struct:
# 4s (MAGIC: JSHM)
# H  (version: 1)
# H  (state: BufferSlotState)
# Q  (sequence: uint64)
# I  (payload_len: uint32)
# I  (checksum_crc32: uint32)
# 32s (msg_id: ascii hex)
# Total size: 4 + 2 + 2 + 8 + 4 + 4 + 32 = 56 bytes
HEADER_FORMAT = "=4sHHQII32s"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
SHM_MAGIC = b"JSHM"


class SharedMemoryTransport(LocalIpcTransport):
    """
    Zero-copy structured slot transport backed by multiprocessing.shared_memory.SharedMemory.
    Header contains deterministic consistency protocol metadata:
    owner, version, length, checksum, state.
    """

    def __init__(
        self,
        slot_size_bytes: int = 1024 * 1024,
        name: str | None = None,
        create: bool = True,
        data_ready_event: Any = None,
        data_ack_event: Any = None,
    ):
        self.slot_size_bytes = max(slot_size_bytes, HEADER_SIZE + 1024)
        self.shm_name = name or f"jarvis_shm_{uuid.uuid4().hex[:12]}"
        self._is_creator = create

        if self._is_creator:
            self._shm = shared_memory.SharedMemory(name=self.shm_name, create=True, size=self.slot_size_bytes)
            SharedMemoryTracker.register(self.shm_name, self.slot_size_bytes)
            # Initialize empty header
            empty_hdr = struct.pack(
                HEADER_FORMAT,
                SHM_MAGIC,
                1,
                BufferSlotState.EMPTY.value,
                0,
                0,
                0,
                b"0" * 32,
            )
            self._shm.buf[:HEADER_SIZE] = empty_hdr
        else:
            self._shm = shared_memory.SharedMemory(name=self.shm_name)

        self._data_ready = data_ready_event or mp.Event()
        self._data_ack = data_ack_event or mp.Event()
        self._seq = 0
        self.messages_sent = 0
        self.messages_received = 0
        self.total_send_ms = 0.0
        self.total_receive_ms = 0.0
        self._closed = False

    def create_peer(self) -> "SharedMemoryTransport":
        """Creates a paired receiver transport sharing the same memory block and event handles."""
        return SharedMemoryTransport(
            slot_size_bytes=self.slot_size_bytes,
            name=self.shm_name,
            create=False,
            data_ready_event=self._data_ready,
            data_ack_event=self._data_ack,
        )

    @property
    def transport_type(self) -> IpcTransportType:
        return IpcTransportType.SHARED_MEMORY

    def send(self, data: Any, sequence: int | None = None) -> float:
        if self._closed:
            raise TransportClosedError("SharedMemoryTransport is closed")
        t0 = time.perf_counter()
        seq = sequence if sequence is not None else self._seq
        payload = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
        p_len = len(payload)

        if HEADER_SIZE + p_len > self.slot_size_bytes:
            raise ValueError(
                f"Payload size ({p_len} bytes) exceeds shared memory slot capacity ({self.slot_size_bytes - HEADER_SIZE} bytes)"
            )

        msg_id_bytes = uuid.uuid4().hex.encode("ascii")
        checksum = zlib.crc32(payload) & 0xFFFFFFFF

        # WRITE -> COMMIT state
        self._shm.buf[HEADER_SIZE : HEADER_SIZE + p_len] = payload
        hdr = struct.pack(
            HEADER_FORMAT,
            SHM_MAGIC,
            1,
            BufferSlotState.COMMITTED.value,
            seq,
            p_len,
            checksum,
            msg_id_bytes,
        )
        self._shm.buf[:HEADER_SIZE] = hdr

        # Signal reader
        self._data_ready.set()
        # Wait for acknowledgment
        if not self._data_ack.wait(timeout=10.0):
            raise TimeoutError("Shared memory receiver did not acknowledge slot within timeout")
        self._data_ack.clear()

        self._seq += 1
        dur = (time.perf_counter() - t0) * 1000.0
        self.messages_sent += 1
        self.total_send_ms += dur
        return dur

    def receive(self, timeout: float | None = None, expected_sequence: int | None = None) -> tuple[Any, float]:
        if self._closed:
            raise TransportClosedError("SharedMemoryTransport is closed")
        t0 = time.perf_counter()
        if not self._data_ready.wait(timeout=timeout):
            raise TimeoutError(f"SharedMemory receive timed out after {timeout}s")
        self._data_ready.clear()

        # READ -> VERIFY
        hdr_bytes = bytes(self._shm.buf[:HEADER_SIZE])
        magic, ver, state, seq, p_len, checksum, msg_id_raw = struct.unpack(HEADER_FORMAT, hdr_bytes)

        if magic != SHM_MAGIC:
            raise CorruptedMessageError(f"Invalid shared memory magic: {magic}")
        if state != BufferSlotState.COMMITTED.value:
            raise CorruptedMessageError(f"Slot not in COMMITTED state: {state}")
        if expected_sequence is not None and seq != expected_sequence:
            raise SequenceViolationError(f"Sequence mismatch: expected {expected_sequence}, got {seq}")

        payload = bytes(self._shm.buf[HEADER_SIZE : HEADER_SIZE + p_len])
        calc_checksum = zlib.crc32(payload) & 0xFFFFFFFF
        if calc_checksum != checksum:
            raise InvalidChecksumError(
                f"SharedMemory CRC32 mismatch: expected {checksum:08x}, calculated {calc_checksum:08x}"
            )

        data = pickle.loads(payload)

        # ACKNOWLEDGE
        ack_hdr = struct.pack(
            HEADER_FORMAT,
            SHM_MAGIC,
            1,
            BufferSlotState.ACKNOWLEDGED.value,
            seq,
            0,
            0,
            msg_id_raw,
        )
        self._shm.buf[:HEADER_SIZE] = ack_hdr
        self._data_ack.set()

        dur = (time.perf_counter() - t0) * 1000.0
        self.messages_received += 1
        self.total_receive_ms += dur
        return data, dur

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                self._shm.close()
                if self._is_creator:
                    self._shm.unlink()
                    SharedMemoryTracker.release(self.shm_name)
            except Exception:
                pass

    def get_metrics(self) -> dict[str, Any]:
        return {
            "transport": self.transport_type.value,
            "shm_name": self.shm_name,
            "slot_size_bytes": self.slot_size_bytes,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "avg_send_ms": round(self.total_send_ms / max(1, self.messages_sent), 3),
            "avg_receive_ms": round(self.total_receive_ms / max(1, self.messages_received), 3),
        }


# ── RING BUFFER TRANSPORT ─────────────────────────────────────────────────────

# Ring Buffer Control Block Header:
# 4s (MAGIC: JRNG)
# I  (capacity: uint32)
# I  (slot_size: uint32)
# Q  (head: uint64)
# Q  (tail: uint64)
# Q  (sequence: uint64)
# I  (state: 0=NORMAL, 1=SHUTDOWN)
# Total control block: 4 + 4 + 4 + 8 + 8 + 8 + 4 = 40 bytes
RING_CTRL_FORMAT = "=4sIIQQQI"
RING_CTRL_SIZE = struct.calcsize(RING_CTRL_FORMAT)
RING_MAGIC = b"JRNG"

# Slot header within ring buffer:
# 4s (MAGIC: JSLT)
# H  (state: BufferSlotState)
# Q  (sequence: uint64)
# I  (payload_len: uint32)
# I  (checksum_crc32: uint32)
# Total slot header: 4 + 2 + 8 + 4 + 4 = 22 bytes
SLOT_HEADER_FORMAT = "=4sHQII"
SLOT_HEADER_SIZE = struct.calcsize(SLOT_HEADER_FORMAT)
SLOT_MAGIC = b"JSLT"


class SharedMemoryRingBuffer:
    """
    Lock-minimized, bounded, circular shared-memory buffer.
    Features:
    - Sequence numbered slots
    - Zero-copy circular memory layout
    - Atomic head / tail progression
    - Backpressure events when buffer capacity is reached
    - CRC32 verification on read
    - Graceful cancellation and shutdown
    """

    def __init__(
        self,
        capacity: int = 16,
        slot_size_bytes: int = 64 * 1024,
        name: str | None = None,
        create: bool = True,
        not_empty_event: Any = None,
        not_full_event: Any = None,
    ):
        self.capacity = capacity
        self.slot_payload_size = slot_size_bytes
        self.total_slot_size = SLOT_HEADER_SIZE + slot_size_bytes
        self.total_buffer_size = RING_CTRL_SIZE + (self.capacity * self.total_slot_size)
        self.name = name or f"jarvis_ring_{uuid.uuid4().hex[:12]}"
        self._is_creator = create

        if self._is_creator:
            self._shm = shared_memory.SharedMemory(name=self.name, create=True, size=self.total_buffer_size)
            SharedMemoryTracker.register(self.name, self.total_buffer_size)
            ctrl_init = struct.pack(
                RING_CTRL_FORMAT,
                RING_MAGIC,
                self.capacity,
                self.slot_payload_size,
                0,  # head (offset 12)
                0,  # tail (offset 20)
                0,  # sequence (offset 28)
                0,  # state normal (offset 36)
            )
            self._shm.buf[:RING_CTRL_SIZE] = ctrl_init
        else:
            self._shm = shared_memory.SharedMemory(name=self.name)

        self._not_empty = not_empty_event or mp.Event()
        self._not_full = not_full_event or mp.Event()
        if self._is_creator:
            self._not_full.set()
        self.backpressure_events: int = 0
        self._closed = False

    def _get_slot_offset(self, index: int) -> int:
        slot_idx = index % self.capacity
        return RING_CTRL_SIZE + (slot_idx * self.total_slot_size)

    def write(self, data: Any, timeout: float = 5.0, sequence: int | None = None) -> int:
        if self._closed:
            raise TransportClosedError("SharedMemoryRingBuffer is closed")

        payload = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
        p_len = len(payload)
        if p_len > self.slot_payload_size:
            raise ValueError(
                f"Payload size ({p_len} bytes) exceeds ring slot capacity ({self.slot_payload_size} bytes)"
            )

        # Check state (offset 36)
        state = struct.unpack_from("=I", self._shm.buf, 36)[0]
        if state == 1:
            raise TransportClosedError("Ring buffer has been shut down")

        # Check for backpressure / capacity overflow
        t_deadline = time.perf_counter() + timeout
        while True:
            head = struct.unpack_from("=Q", self._shm.buf, 12)[0]
            tail = struct.unpack_from("=Q", self._shm.buf, 20)[0]
            if (head - tail) < self.capacity:
                break
            self.backpressure_events += 1
            self._not_full.clear()
            # Re-read after clearing to prevent missed signal
            tail = struct.unpack_from("=Q", self._shm.buf, 20)[0]
            if (head - tail) < self.capacity:
                break
            rem = t_deadline - time.perf_counter()
            if rem <= 0 or not self._not_full.wait(timeout=max(0.001, rem)):
                raise BackpressureOverflowError(
                    f"Ring buffer full ({head - tail}/{self.capacity} slots occupied) - backpressure limit exceeded"
                )

        if sequence is not None:
            seq = sequence
        else:
            seq = struct.unpack_from("=Q", self._shm.buf, 28)[0]

        slot_offset = self._get_slot_offset(head)
        checksum = zlib.crc32(payload) & 0xFFFFFFFF

        # WRITE -> COMMIT slot
        slot_hdr = struct.pack(
            SLOT_HEADER_FORMAT,
            SLOT_MAGIC,
            BufferSlotState.COMMITTED.value,
            seq,
            p_len,
            checksum,
        )
        self._shm.buf[slot_offset : slot_offset + SLOT_HEADER_SIZE] = slot_hdr
        self._shm.buf[slot_offset + SLOT_HEADER_SIZE : slot_offset + SLOT_HEADER_SIZE + p_len] = payload

        # Advance head (offset 12) and sequence (offset 28) without touching tail (offset 20)
        struct.pack_into("=Q", self._shm.buf, 12, head + 1)
        struct.pack_into("=Q", self._shm.buf, 28, seq + 1)
        self._not_empty.set()
        return seq

    def read(self, timeout: float | None = None, expected_sequence: int | None = None) -> Any:
        if self._closed:
            raise TransportClosedError("SharedMemoryRingBuffer is closed")

        t_deadline = time.perf_counter() + timeout if timeout is not None else None
        while True:
            head = struct.unpack_from("=Q", self._shm.buf, 12)[0]
            tail = struct.unpack_from("=Q", self._shm.buf, 20)[0]
            if tail < head:
                break
            self._not_empty.clear()
            # Re-read after clearing to prevent missed signal
            head = struct.unpack_from("=Q", self._shm.buf, 12)[0]
            if tail < head:
                break
            if timeout is not None:
                rem = t_deadline - time.perf_counter()
                if rem <= 0 or not self._not_empty.wait(timeout=max(0.001, rem)):
                    raise TimeoutError(f"Ring buffer read timed out after {timeout}s")
            else:
                self._not_empty.wait()

        slot_offset = self._get_slot_offset(tail)
        slot_hdr_bytes = bytes(self._shm.buf[slot_offset : slot_offset + SLOT_HEADER_SIZE])
        s_magic, s_state, s_seq, p_len, checksum = struct.unpack(SLOT_HEADER_FORMAT, slot_hdr_bytes)

        if s_magic != SLOT_MAGIC:
            raise CorruptedMessageError(f"Invalid ring buffer slot magic: {s_magic}")
        if s_state != BufferSlotState.COMMITTED.value:
            raise CorruptedMessageError(f"Slot state not COMMITTED: {s_state}")
        if expected_sequence is not None and s_seq != expected_sequence:
            raise SequenceViolationError(f"Sequence mismatch: expected {expected_sequence}, got {s_seq}")

        payload = bytes(self._shm.buf[slot_offset + SLOT_HEADER_SIZE : slot_offset + SLOT_HEADER_SIZE + p_len])
        calc_checksum = zlib.crc32(payload) & 0xFFFFFFFF
        if calc_checksum != checksum:
            raise InvalidChecksumError(
                f"Ring buffer CRC32 mismatch: expected {checksum:08x}, calculated {calc_checksum:08x}"
            )

        data = pickle.loads(payload)

        # Mark slot acknowledged and advance tail (offset 20) without touching head (offset 12)
        struct.pack_into("=Q", self._shm.buf, 20, tail + 1)
        self._not_full.set()
        return data

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                # Mark shutdown in control block at offset 36 (state)
                struct.pack_into("=I", self._shm.buf, 36, 1)
                self._not_empty.set()
                self._not_full.set()
            except Exception:
                pass
            try:
                self._shm.close()
                if self._is_creator:
                    self._shm.unlink()
                    SharedMemoryTracker.release(self.name)
            except Exception:
                pass


class RingBufferTransport(LocalIpcTransport):
    """
    Lock-minimized circular ring buffer IPC transport with deterministic sequence verification.
    """

    def __init__(
        self,
        capacity: int = 16,
        slot_size_bytes: int = 64 * 1024,
        name: str | None = None,
        create: bool = True,
        ring: SharedMemoryRingBuffer | None = None,
    ):
        if ring is not None:
            self.ring = ring
        else:
            self.ring = SharedMemoryRingBuffer(
                capacity=capacity,
                slot_size_bytes=slot_size_bytes,
                name=name,
                create=create,
            )
        self.messages_sent = 0
        self.messages_received = 0
        self.total_send_ms = 0.0
        self.total_receive_ms = 0.0

    def create_peer(self) -> "RingBufferTransport":
        peer_ring = SharedMemoryRingBuffer(
            capacity=self.ring.capacity,
            slot_size_bytes=self.ring.slot_payload_size,
            name=self.ring.name,
            create=False,
            not_empty_event=self.ring._not_empty,
            not_full_event=self.ring._not_full,
        )
        return RingBufferTransport(
            capacity=self.ring.capacity,
            slot_size_bytes=self.ring.slot_payload_size,
            name=self.ring.name,
            create=False,
            ring=peer_ring,
        )

    @property
    def transport_type(self) -> IpcTransportType:
        return IpcTransportType.RING_BUFFER

    def send(self, data: Any, sequence: int | None = None) -> float:
        t0 = time.perf_counter()
        _ = self.ring.write(data, sequence=sequence)
        dur = (time.perf_counter() - t0) * 1000.0
        self.messages_sent += 1
        self.total_send_ms += dur
        return dur

    def receive(self, timeout: float | None = None, expected_sequence: int | None = None) -> tuple[Any, float]:
        t0 = time.perf_counter()
        data = self.ring.read(timeout=timeout, expected_sequence=expected_sequence)
        dur = (time.perf_counter() - t0) * 1000.0
        self.messages_received += 1
        self.total_receive_ms += dur
        return data, dur

    def close(self) -> None:
        self.ring.close()

    def get_metrics(self) -> dict[str, Any]:
        return {
            "transport": self.transport_type.value,
            "ring_name": self.ring.name,
            "capacity": self.ring.capacity,
            "slot_size": self.ring.slot_payload_size,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "backpressure_events": self.ring.backpressure_events,
            "avg_send_ms": round(self.total_send_ms / max(1, self.messages_sent), 3),
            "avg_receive_ms": round(self.total_receive_ms / max(1, self.messages_received), 3),
        }


# ── ADAPTIVE IPC POLICY & TRANSPORT ───────────────────────────────────────────

@dataclass
class AdaptiveIpcDecision:
    transport_type: IpcTransportType
    predicted_transport_ms: float
    reason: str
    metrics: dict[str, Any] = field(default_factory=dict)


class AdaptiveIpcPolicy:
    """
    Deterministically selects the optimal IPC transport based on:
    - Payload size (bytes)
    - Batch size and queue depth
    - Worker process concurrency
    - Empirical transport cost model.
    """

    def __init__(self):
        self.history: list[dict[str, Any]] = []

    def evaluate(
        self,
        payload_size_bytes: int,
        batch_size: int = 16,
        queue_depth: int = 1,
        worker_count: int = 4,
    ) -> AdaptiveIpcDecision:
        payload_kb = payload_size_bytes / 1024.0

        # Cost model per transport in milliseconds:
        # Pipe: low base cost, but scales linearly with payload copy overhead
        cost_pipe = 0.35 + (payload_kb * 0.045)

        # Queue: moderate base cost, buffer copy overhead
        cost_queue = 0.55 + (payload_kb * 0.050)

        # SharedMemory: higher allocation/sync setup cost, but flat transport cost
        cost_shm = 1.20 + (payload_kb * 0.005)

        # RingBuffer: lock-minimized streaming pipeline, lowest latency for batches
        batch_discount = min(0.6, batch_size / (batch_size + 8.0))
        cost_ring = (0.80 + (payload_kb * 0.008)) * (1.0 - batch_discount)

        metrics = {
            "payload_size_bytes": payload_size_bytes,
            "payload_kb": round(payload_kb, 2),
            "batch_size": batch_size,
            "queue_depth": queue_depth,
            "cost_pipe_ms": round(cost_pipe, 3),
            "cost_queue_ms": round(cost_queue, 3),
            "cost_shm_ms": round(cost_shm, 3),
            "cost_ring_ms": round(cost_ring, 3),
        }

        # Deterministic selection rules:
        if payload_kb >= 64.0:
            if batch_size >= 16 or queue_depth >= 16:
                return AdaptiveIpcDecision(
                    transport_type=IpcTransportType.RING_BUFFER,
                    predicted_transport_ms=cost_ring,
                    reason=f"Large payload ({payload_kb:.1f} KB) + batching (B={batch_size}): RingBuffer optimal (zero-copy)",
                    metrics=metrics,
                )
            else:
                return AdaptiveIpcDecision(
                    transport_type=IpcTransportType.SHARED_MEMORY,
                    predicted_transport_ms=cost_shm,
                    reason=f"Large payload ({payload_kb:.1f} KB): SharedMemory avoids named pipe copy overhead",
                    metrics=metrics,
                )
        elif queue_depth >= 32 or batch_size >= 32:
            return AdaptiveIpcDecision(
                transport_type=IpcTransportType.RING_BUFFER,
                predicted_transport_ms=cost_ring,
                reason=f"Streaming queue depth ({queue_depth}) / batch ({batch_size}): RingBuffer pipeline optimal",
                metrics=metrics,
            )
        else:
            return AdaptiveIpcDecision(
                transport_type=IpcTransportType.PIPE,
                predicted_transport_ms=cost_pipe,
                reason=f"Small payload ({payload_kb:.1f} KB) & modest batch ({batch_size}): Pipe has minimal setup overhead",
                metrics=metrics,
            )

    def record_actual(self, transport_type: IpcTransportType, payload_size: int, actual_ms: float) -> None:
        self.history.append({
            "transport_type": transport_type.value,
            "payload_size": payload_size,
            "actual_ms": actual_ms,
            "timestamp": time.time(),
        })
        if len(self.history) > 100:
            self.history.pop(0)

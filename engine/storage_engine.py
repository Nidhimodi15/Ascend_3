"""
12-Hook transactional write pipeline.

The engine has ZERO knowledge of which hooks are "dangerous".
It simply executes steps and raises CrashInjected at the requested hook.
Recovery and invariant checking happen AFTER the crash — that is where
bugs are discovered.
"""
from engine.simulated_disk import SimulatedDisk
from engine.types import WriteOperation


class CrashInjected(Exception):
    """Raised to simulate a crash at a specific hook point."""
    def __init__(self, hook: int):
        self.hook = hook
        super().__init__(f"CrashInjected at hook {hook}")


# Metadata describing each hook — used by the verifier and the UI
HOOK_METADATA = [
    {"hook": 1,  "phase": "LOG",    "step": "Write WAL header to volatile buffer"},
    {"hook": 2,  "phase": "LOG",    "step": "Write WAL payload to volatile buffer"},
    {"hook": 3,  "phase": "LOG",    "step": "Flush WAL buffer to disk (fsync)"},
    {"hook": 4,  "phase": "DATA",   "step": "Allocate data block in memory"},
    {"hook": 5,  "phase": "DATA",   "step": "Write data payload to volatile buffer"},
    {"hook": 6,  "phase": "DATA",   "step": "Flush data buffer to disk (fsync)"},
    {"hook": 7,  "phase": "META",   "step": "Create metadata index entry in buffer"},
    {"hook": 8,  "phase": "META",   "step": "Set active metadata pointer in buffer"},
    {"hook": 9,  "phase": "META",   "step": "Flush metadata buffer to disk (fsync)"},
    {"hook": 10, "phase": "COMMIT", "step": "Prepare checksum (compute in memory)"},
    {"hook": 11, "phase": "COMMIT", "step": "Persist checksum (write + flush to disk)"},
    {"hook": 12, "phase": "COMMIT", "step": "Persist commit marker (write + flush to disk)"},
]


def _compute_checksum(op: WriteOperation) -> str:
    """Deterministic checksum over key + value + version."""
    raw = f"{op.key}:{op.value}:{op.version}"
    # Pure-Python CRC32-style hash (no external libs)
    h = 5381
    for ch in raw:
        h = ((h << 5) + h) ^ ord(ch)
    return f"crc32_{h & 0xFFFFFFFF:08x}"


def _allocate_block(op: WriteOperation) -> str:
    """Generate a deterministic block ID for this operation."""
    return f"blk_{op.txn_id}_{op.key}"


def execute_write(
    disk: SimulatedDisk,
    op: WriteOperation,
    crash_at: int | None = None,
) -> dict:
    """
    Execute the full 12-step write path with optional crash injection.

    crash_at=N  → crash BEFORE step N executes.
                  Steps 1..(N-1) have completed; step N and beyond have NOT.
    crash_at=None → complete the write successfully (acknowledged).

    Raises CrashInjected(N) if crash is requested, which caller should
    catch to then call disk.crash() to discard volatile buffers.
    """

    # ── Phase 1: LOG (Write-Ahead Log) ────────────────────────────────────────

    if crash_at == 1:
        raise CrashInjected(1)
    disk.buf_wal_append({"type": "header", "txn_id": op.txn_id, "key": op.key})

    if crash_at == 2:
        raise CrashInjected(2)
    disk.buf_wal_append({
        "type": "payload", "txn_id": op.txn_id,
        "value": op.value, "version": op.version,
        "old_value": op.old_value,
    })

    if crash_at == 3:
        raise CrashInjected(3)
    disk.flush("wal")

    # ── Phase 2: DATA ─────────────────────────────────────────────────────────

    if crash_at == 4:
        raise CrashInjected(4)
    block_id = _allocate_block(op)

    if crash_at == 5:
        raise CrashInjected(5)
    disk.buf_data_write(block_id, {
        "key": op.key,
        "value": op.value,
        "version": op.version,
        "txn_id": op.txn_id,
    })

    if crash_at == 6:
        raise CrashInjected(6)
    disk.flush("data")

    # ── Phase 3: METADATA ─────────────────────────────────────────────────────

    if crash_at == 7:
        raise CrashInjected(7)
    disk.buf_meta_write(op.key, {
        "block_id": block_id,
        "txn_id": op.txn_id,
        "active": False,
    })

    if crash_at == 8:
        raise CrashInjected(8)
    disk.buf_meta_write(op.key, {
        "block_id": block_id,
        "txn_id": op.txn_id,
        "active": True,
    })

    if crash_at == 9:
        raise CrashInjected(9)
    disk.flush("metadata")

    # ── Phase 4: COMMIT ───────────────────────────────────────────────────────

    if crash_at == 10:
        raise CrashInjected(10)
    checksum = _compute_checksum(op)          # Exists in RAM only

    if crash_at == 11:
        raise CrashInjected(11)
    disk.buf_checksum_write(op.txn_id, checksum)
    disk.flush("checksums")                   # Now persisted to disk

    if crash_at == 12:
        raise CrashInjected(12)
    disk.buf_commit_write(op.txn_id, {"committed": True, "txn_id": op.txn_id})
    disk.flush("commit_markers")              # Now persisted to disk

    # ── OPERATION COMPLETE — write is officially acknowledged ─────────────────
    return {"acknowledged": True, "txn_id": op.txn_id}

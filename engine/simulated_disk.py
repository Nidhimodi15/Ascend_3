"""
Simulated dual-layer disk model.

Two layers of state:
  - persisted: survives a crash  (simulates fsync'd / committed disk data)
  - buffer:    lost on crash     (simulates OS page cache / write buffers)

A flush() copies buffer region → persisted.
A crash() discards ALL buffer contents — like a power cut.
"""
import copy
from engine.types import DiskSnapshot


class SimulatedDisk:

    def __init__(self):
        self.persisted: dict = {
            "wal": [],
            "data_pages": {},
            "metadata_index": {},
            "checksums": {},
            "commit_markers": {},
        }
        self.buffer: dict = {
            "wal": [],
            "data_pages": {},
            "metadata_index": {},
            "checksums": {},
            "commit_markers": {},
        }

    # ─── Write to volatile buffer ─────────────────────────────────────────────

    def buf_wal_append(self, entry: dict):
        self.buffer["wal"].append(copy.deepcopy(entry))

    def buf_data_write(self, block_id: str, data: dict):
        self.buffer["data_pages"][block_id] = copy.deepcopy(data)

    def buf_meta_write(self, key: str, meta: dict):
        self.buffer["metadata_index"][key] = copy.deepcopy(meta)

    def buf_checksum_write(self, txn_id: str, checksum: str):
        self.buffer["checksums"][txn_id] = checksum

    def buf_commit_write(self, txn_id: str, marker: dict):
        self.buffer["commit_markers"][txn_id] = copy.deepcopy(marker)

    # ─── Flush (buffer → persisted) ───────────────────────────────────────────

    def flush(self, region: str):
        """Move a region from volatile buffer to persisted disk."""
        if region == "wal":
            self.persisted["wal"].extend(copy.deepcopy(self.buffer["wal"]))
            self.buffer["wal"] = []
        elif region == "data":
            self.persisted["data_pages"].update(copy.deepcopy(self.buffer["data_pages"]))
            self.buffer["data_pages"] = {}
        elif region == "metadata":
            self.persisted["metadata_index"].update(copy.deepcopy(self.buffer["metadata_index"]))
            self.buffer["metadata_index"] = {}
        elif region == "checksums":
            self.persisted["checksums"].update(copy.deepcopy(self.buffer["checksums"]))
            self.buffer["checksums"] = {}
        elif region == "commit_markers":
            self.persisted["commit_markers"].update(copy.deepcopy(self.buffer["commit_markers"]))
            self.buffer["commit_markers"] = {}

    # ─── Crash (discard all volatile buffers) ─────────────────────────────────

    def crash(self):
        """Simulate power loss: everything in the volatile buffer is lost forever."""
        self.buffer = {
            "wal": [],
            "data_pages": {},
            "metadata_index": {},
            "checksums": {},
            "commit_markers": {},
        }

    # ─── Snapshot persisted state ─────────────────────────────────────────────

    def snapshot(self) -> DiskSnapshot:
        """Return a deep copy of persisted disk state for inspection."""
        return DiskSnapshot(
            wal=copy.deepcopy(self.persisted["wal"]),
            data_pages=copy.deepcopy(self.persisted["data_pages"]),
            metadata_index=copy.deepcopy(self.persisted["metadata_index"]),
            checksums=copy.deepcopy(self.persisted["checksums"]),
            commit_markers=copy.deepcopy(self.persisted["commit_markers"]),
        )

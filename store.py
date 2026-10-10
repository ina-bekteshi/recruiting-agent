"""Audit log (JSONL, one event per line) and final decisions (JSON)."""

import json
from datetime import datetime, timezone
from pathlib import Path


class AuditLog:
    def __init__(self, out_dir: Path):
        out_dir.mkdir(parents=True, exist_ok=True)
        self.path = out_dir / "audit_log.jsonl"
        self.path.write_text("")  # fresh log per run

    def event(self, candidate_id: str, kind: str, **data) -> None:
        record = {"ts": datetime.now(timezone.utc).isoformat(), "candidate_id": candidate_id, "event": kind, **data}
        with self.path.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def for_candidate(self, candidate_id: str):
        return lambda kind, **data: self.event(candidate_id, kind, **data)


def write_decisions(out_dir: Path, decisions: list[dict]) -> Path:
    path = out_dir / "decisions.json"
    path.write_text(json.dumps(decisions, indent=2))
    return path

"""Append-only JSONL, capped. The durable record of what the bot did and decided.

Same reasoning as scanner/ledger.py: an Actions log is deleted after 90 days, and the runs
worth reading later are exactly the ones that failed.
"""
import json
from pathlib import Path

KEEP = 500


def append_jsonl(path, record: dict, keep: int = KEEP) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = p.read_text().splitlines() if p.exists() else []
    lines.append(json.dumps(record, sort_keys=True))
    lines = lines[-keep:]
    p.write_text("\n".join(lines) + "\n")
    return len(lines)

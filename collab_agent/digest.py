"""Append-only digest store. Records are never edited or deleted here —
corrections arrive as newer records. The digest is derived state (like
results/*.json): it lives outside version control.
"""
import json
import pathlib


def load(digest_path: pathlib.Path) -> list:
    if not digest_path.exists():
        return []
    return json.loads(digest_path.read_text())


def last(records: list) -> dict | None:
    return records[-1] if records else None


def append(digest_path: pathlib.Path, record: dict) -> list:
    try:
        records = load(digest_path)
    except (ValueError, UnicodeDecodeError, OSError):
        records = []
    record = dict(record)
    record["seq"] = len(records) + 1
    if records:
        record["prev_seq"] = records[-1]["seq"]
    records.append(record)
    digest_path.parent.mkdir(parents=True, exist_ok=True)
    digest_path.write_text(json.dumps(records, indent=1) + "\n")
    return records

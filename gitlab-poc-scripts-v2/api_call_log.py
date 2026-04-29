"""
Structured per-API-call recorder.

Used by gitlab_client.py and phase scripts to capture every HTTP call made
during a PoC run, plus high-level "phase" boundaries. The result is a JSON
file (api-calls.jsonl) and an in-memory list that the HTML report consumes.

One record per API call, plus phase markers. JSONL keeps the file streamable —
if a run crashes, the partial log is still readable.

Sensitive values (PRIVATE-TOKEN headers, raw token strings, password fields)
are redacted before recording.
"""
from __future__ import annotations

import json
import os
import re
import time
import threading
from datetime import datetime, timezone
from typing import Any

# --- public state -----------------------------------------------------------

_records: list[dict[str, Any]] = []
_current_phase: str | None = None
_log_path: str | None = None
_lock = threading.Lock()
_max_body_chars = 2000  # truncate request/response excerpts beyond this

# patterns to redact from request bodies and any string we render
_REDACT_KEYS = re.compile(r'("(?:token|password|private_token|access_token|value)"\s*:\s*")([^"]*)(")')
_REDACT_TOKEN_LITERAL = re.compile(r'(glpat-|glrt-|gloas-|glsoat-)[A-Za-z0-9_.\-]+')


def _redact(text: str) -> str:
    if not text:
        return text
    text = _REDACT_KEYS.sub(r'\1***REDACTED***\3', text)
    text = _REDACT_TOKEN_LITERAL.sub(r'\1***REDACTED***', text)
    return text


def _truncate(text: str) -> str:
    if text is None:
        return ""
    if len(text) <= _max_body_chars:
        return text
    return text[:_max_body_chars] + f"\n... [truncated, total {len(text)} chars]"


# --- session lifecycle -----------------------------------------------------

def init(log_path: str) -> None:
    """Open a fresh log file. Subsequent records are appended as JSONL."""
    global _log_path, _records, _current_phase
    _log_path = log_path
    _records = []
    _current_phase = None
    os.makedirs(os.path.dirname(os.path.abspath(log_path)) or ".", exist_ok=True)
    # Clear any prior file
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("")


def begin_phase(phase_id: str, title: str) -> None:
    global _current_phase
    _current_phase = phase_id
    _append({
        "kind": "phase_begin",
        "phase_id": phase_id,
        "title": title,
        "ts": _now(),
    })


def end_phase(phase_id: str, status: str = "ok", note: str = "") -> None:
    _append({
        "kind": "phase_end",
        "phase_id": phase_id,
        "status": status,
        "note": note,
        "ts": _now(),
    })


def step(message: str, level: str = "info") -> None:
    """Record a non-API operational note (e.g., 'skipping X', 'computed Y')."""
    _append({
        "kind": "step",
        "phase_id": _current_phase,
        "level": level,
        "message": message,
        "ts": _now(),
    })


def record_call(
    method: str,
    url: str,
    request_body: Any,
    status: int | None,
    response_body: Any,
    duration_ms: float,
    error: str | None = None,
) -> None:
    req_text = ""
    if request_body is not None:
        if isinstance(request_body, (dict, list)):
            req_text = json.dumps(request_body, indent=2, default=str)
        else:
            req_text = str(request_body)
    req_text = _truncate(_redact(req_text))

    if isinstance(response_body, (dict, list)):
        resp_text = json.dumps(response_body, indent=2, default=str)
    else:
        resp_text = "" if response_body is None else str(response_body)
    resp_text = _truncate(_redact(resp_text))

    _append({
        "kind": "call",
        "phase_id": _current_phase,
        "method": method,
        "url": _redact(url),
        "request_body": req_text,
        "status": status,
        "response_body": resp_text,
        "duration_ms": round(duration_ms, 1),
        "error": error,
        "ts": _now(),
    })


def record_evidence(scenario: dict[str, Any]) -> None:
    """Record one UI evidence scenario (set of screenshots) for the current
    phase. Consumed by phase_14_report.py to render screenshots inline."""
    _append({
        "kind": "ui_evidence",
        "phase_id": _current_phase,
        "scenario_id": scenario.get("id"),
        "section": scenario.get("section"),
        "title": scenario.get("title"),
        "persona": scenario.get("persona"),
        "ok": scenario.get("ok"),
        "shots": scenario.get("shots", []),
        "ts": _now(),
    })


def all_records() -> list[dict[str, Any]]:
    """Return a snapshot of records (in-memory)."""
    return list(_records)


def load(log_path: str) -> list[dict[str, Any]]:
    """Read records from a JSONL file written by an earlier run."""
    out: list[dict[str, Any]] = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


# --- internals --------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"


def _append(rec: dict[str, Any]) -> None:
    with _lock:
        _records.append(rec)
        if _log_path:
            try:
                with open(_log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, default=str) + "\n")
            except OSError:
                pass  # logging must never break the run

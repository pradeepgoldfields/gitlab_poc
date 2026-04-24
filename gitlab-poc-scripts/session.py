"""
Session persistence for the PoC suite.

Stores the admin URL + PAT in a local `.pocenv` file (chmod 600) so the user
is prompted only once. Loaded automatically by config.py if the corresponding
environment variables are not already set.

File format is plain `KEY=value` lines (no quoting, no expansion). It's NOT a
shell script — do not `source` it. The path is `.pocenv` in the script
directory by default; override with $POC_SESSION_FILE.

Security stance: the file holds a long-lived admin PAT. It's chmod 600 on
POSIX. On Windows, NTFS ACLs aren't touched (the user must rely on their
profile's default ACL). Both ways: do NOT commit this file. A .gitignore
entry is shipped alongside.
"""
from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_PATH = Path(__file__).parent / ".pocenv"


def _path() -> Path:
    return Path(os.environ.get("POC_SESSION_FILE", str(_DEFAULT_PATH)))


def load_into_env() -> None:
    """If the session file exists, load any keys not already in os.environ."""
    p = _path()
    if not p.exists():
        return
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


def save(values: dict[str, str]) -> Path:
    """Write key=value lines to the session file, chmod 600 on POSIX."""
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"{k}={v}" for k, v in values.items()) + "\n"
    p.write_text(body, encoding="utf-8")
    if os.name == "posix":
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass
    return p


def clear() -> None:
    p = _path()
    if p.exists():
        p.unlink()

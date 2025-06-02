# chuk_artifacts/grid.py
"""Utility helpers for grid-style paths.

Pattern: grid/{sandbox_id}/{session_id}/{artifact_id}[/{subpath}]"""

from typing import Optional, Dict

_ROOT = "grid"


def canonical_prefix(sandbox_id: str, session_id: str) -> str:
    return f"{_ROOT}/{sandbox_id}/{session_id}/"


def artifact_key(sandbox_id: str, session_id: str, artifact_id: str) -> str:
    return f"{_ROOT}/{sandbox_id}/{session_id}/{artifact_id}"


def parse(key: str) -> Optional[Dict[str, str]]:
    parts = key.split("/")
    if len(parts) < 4 or parts[0] != _ROOT:
        return None
    return {
        "sandbox_id": parts[1],
        "session_id": parts[2],
        "artifact_id": parts[3] if len(parts) > 3 else None,
        "subpath": "/".join(parts[4:]) if len(parts) > 4 else None,
    }

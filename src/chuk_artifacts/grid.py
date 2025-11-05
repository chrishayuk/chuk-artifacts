# -*- coding: utf-8 -*-
# chuk_artifacts/grid.py
"""Utility helpers for grid-style paths.

Pattern: grid/{sandbox_id}/{session_id}/{artifact_id}[/{subpath}]

All components (sandbox_id, session_id, artifact_id) must be non-empty strings
to ensure proper grid organization and prevent path collisions.
"""

from typing import Optional
from .models import GridKeyComponents

_ROOT = "grid"


class GridError(ValueError):
    """Raised when grid path operations encounter invalid input."""

    pass


def _validate_component(component: str, name: str) -> None:
    """Validate a grid path component."""
    if not isinstance(component, str):
        raise GridError(f"{name} must be a string, got {type(component).__name__}")
    if not component:
        raise GridError(f"{name} cannot be empty")
    if "/" in component:
        raise GridError(f"{name} cannot contain '/' characters: {component!r}")


def canonical_prefix(sandbox_id: str, session_id: str) -> str:
    """
    Generate canonical prefix for a sandbox/session combination.

    Args:
        sandbox_id: Non-empty sandbox identifier
        session_id: Non-empty session identifier

    Returns:
        Canonical prefix ending with '/'

    Raises:
        GridError: If any component is invalid
    """
    _validate_component(sandbox_id, "sandbox_id")
    _validate_component(session_id, "session_id")

    return f"{_ROOT}/{sandbox_id}/{session_id}/"


def artifact_key(sandbox_id: str, session_id: str, artifact_id: str) -> str:
    """
    Generate artifact key for grid storage.

    Args:
        sandbox_id: Non-empty sandbox identifier
        session_id: Non-empty session identifier
        artifact_id: Non-empty artifact identifier

    Returns:
        Grid artifact key

    Raises:
        GridError: If any component is invalid
    """
    _validate_component(sandbox_id, "sandbox_id")
    _validate_component(session_id, "session_id")
    _validate_component(artifact_id, "artifact_id")

    return f"{_ROOT}/{sandbox_id}/{session_id}/{artifact_id}"


def parse(key: str) -> Optional[GridKeyComponents]:
    """
    Parse a grid key into components.

    Args:
        key: Grid key to parse

    Returns:
        GridKeyComponents model with parsed components, or None if invalid

    Examples:
        >>> parse("grid/sandbox/session/artifact")
        GridKeyComponents(sandbox_id='sandbox', session_id='session', artifact_id='artifact', subpath=None)

        >>> parse("grid/sandbox/session/artifact/sub/path")
        GridKeyComponents(sandbox_id='sandbox', session_id='session', artifact_id='artifact', subpath='sub/path')

        >>> parse("invalid/key")
        None
    """
    if not isinstance(key, str):
        return None

    parts = key.split("/")

    # Must have at least 4 parts: root, sandbox, session, artifact
    if len(parts) < 4:
        return None

    # Must start with correct root
    if parts[0] != _ROOT:
        return None

    # Extract components
    sandbox_id = parts[1]
    session_id = parts[2]
    artifact_id = parts[3]

    # Validate that core components are non-empty
    if not sandbox_id or not session_id or not artifact_id:
        return None

    # Check for slashes in components
    if "/" in sandbox_id or "/" in session_id or "/" in artifact_id:
        return None

    # Handle subpath
    subpath = None
    if len(parts) > 4:
        subpath_parts = parts[4:]
        subpath = "/".join(subpath_parts)
        # Convert empty subpath to None for consistency
        if subpath == "":
            subpath = None

    try:
        return GridKeyComponents(
            sandbox_id=sandbox_id,
            session_id=session_id,
            artifact_id=artifact_id,
            subpath=subpath,
        )
    except Exception:
        return None


def is_valid_grid_key(key: str) -> bool:
    """
    Check if a string is a valid grid key.

    Args:
        key: String to validate

    Returns:
        True if valid grid key, False otherwise
    """
    return parse(key) is not None


def validate_grid_key(key: str) -> GridKeyComponents:
    """
    Validate and parse a grid key, raising an exception if invalid.

    Args:
        key: Grid key to validate

    Returns:
        Parsed grid components as GridKeyComponents model

    Raises:
        GridError: If key is invalid
    """
    result = parse(key)
    if result is None:
        raise GridError(f"Invalid grid key: {key!r}")
    return result

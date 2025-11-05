# -*- coding: utf-8 -*-
# chuk_artifacts/access_control.py
"""
Access control utilities for scope-based artifact storage.

Implements security policies for session, user, and sandbox scopes.
"""

from typing import Optional
from .models import ArtifactMetadata, AccessContext
from .exceptions import AccessDeniedError


def check_access(artifact: ArtifactMetadata, context: AccessContext) -> None:
    """
    Check if the given context has access to the artifact.

    Args:
        artifact: Artifact metadata to check access for
        context: Access context with user/session information

    Raises:
        AccessDeniedError: If access is denied

    Security Rules:
    - Session scope: Only the owning session can access
    - User scope: Only the owning user can access
    - Sandbox scope: Any user in the sandbox can access (read-only)
    """
    # Sandbox must match
    if artifact.sandbox_id != context.sandbox_id:
        raise AccessDeniedError(
            f"Sandbox mismatch: artifact belongs to '{artifact.sandbox_id}', "
            f"context is for '{context.sandbox_id}'"
        )

    # Scope-specific access control
    if artifact.scope == "session":
        # Session-scoped: Only the owning session can access
        if artifact.session_id != context.session_id:
            raise AccessDeniedError(
                f"Access denied: artifact belongs to session '{artifact.session_id}', "
                f"current session is '{context.session_id}'. "
                f"Session-scoped artifacts can only be accessed within their session."
            )

    elif artifact.scope == "user":
        # User-scoped: Only the owning user can access
        if not context.user_id:
            raise AccessDeniedError(
                "Access denied: user_id required to access user-scoped artifacts"
            )
        if artifact.owner_id != context.user_id:
            raise AccessDeniedError(
                f"Access denied: artifact belongs to user '{artifact.owner_id}', "
                f"current user is '{context.user_id}'. "
                f"User-scoped artifacts can only be accessed by their owner."
            )

    elif artifact.scope == "sandbox":
        # Sandbox-scoped: Anyone in the sandbox can access
        # Already checked sandbox_id match above
        pass

    else:
        raise AccessDeniedError(f"Unknown artifact scope: {artifact.scope}")


def can_modify(artifact: ArtifactMetadata, context: AccessContext) -> bool:
    """
    Check if the context can modify (update/delete) the artifact.

    Args:
        artifact: Artifact metadata to check
        context: Access context with user/session information

    Returns:
        True if modification is allowed

    Modification Rules (stricter than read access):
    - Session scope: Only the owning session can modify
    - User scope: Only the owning user can modify
    - Sandbox scope: No one can modify (admin operations only via separate endpoints)
    """
    # Sandbox must match
    if artifact.sandbox_id != context.sandbox_id:
        return False

    # Scope-specific modification rules
    if artifact.scope == "session":
        return artifact.session_id == context.session_id

    elif artifact.scope == "user":
        return context.user_id is not None and artifact.owner_id == context.user_id

    elif artifact.scope == "sandbox":
        # Sandbox-scoped artifacts cannot be modified via regular operations
        # Use admin endpoints for sandbox artifact management
        return False

    return False


def build_context(
    *, user_id: Optional[str] = None, session_id: Optional[str] = None, sandbox_id: str
) -> AccessContext:
    """
    Convenience function to build an AccessContext.

    Args:
        user_id: User identifier (optional)
        session_id: Session identifier (optional)
        sandbox_id: Sandbox identifier (required)

    Returns:
        AccessContext instance
    """
    return AccessContext(user_id=user_id, session_id=session_id, sandbox_id=sandbox_id)

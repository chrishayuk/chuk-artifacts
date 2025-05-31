# -*- coding: utf-8 -*-
# chuk_artifacts/exceptions.py
"""
Exception classes for artifact store operations.
"""

from __future__ import annotations


class ArtifactStoreError(Exception):
    """Base exception for artifact store operations."""
    pass


class ArtifactNotFoundError(ArtifactStoreError):
    """Raised when an artifact cannot be found."""
    pass


class ArtifactExpiredError(ArtifactStoreError):
    """Raised when an artifact has expired."""
    pass


class ArtifactCorruptedError(ArtifactStoreError):
    """Raised when artifact metadata is corrupted."""
    pass


class ProviderError(ArtifactStoreError):
    """Raised when the storage provider encounters an error."""
    pass


class SessionError(ArtifactStoreError):
    """Raised when the session provider encounters an error."""
    pass
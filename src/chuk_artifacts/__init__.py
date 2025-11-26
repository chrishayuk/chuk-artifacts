# -*- coding: utf-8 -*-
# chuk_artifacts/__init__.py
"""
Asynchronous, object-store-backed artifact manager.

This package provides a high-level interface for storing and retrieving
artifacts across multiple storage backends (S3, IBM COS, filesystem, memory)
with metadata caching and presigned URL support.
"""

from __future__ import annotations
from dotenv import load_dotenv

# Core classes
from .store import ArtifactStore
from .models import (
    ArtifactEnvelope,
    ArtifactMetadata,
    AccessContext,
    GridKeyComponents,
    StreamUploadRequest,
    StreamDownloadRequest,
    MultipartUploadInitRequest,
    MultipartUploadCompleteRequest,
    MultipartUploadPart,
)

# Type definitions and enums
from .types import (
    # Enums
    StorageScope,
    StorageProvider,
    SessionProvider,
    OperationStatus,
    NamespaceType,  # NEW - unified VFS
    # Constants
    DEFAULT_TTL,
    DEFAULT_PRESIGN_EXPIRES,
    DEFAULT_SESSION_TTL_HOURS,
    DEFAULT_BUCKET,
    DEFAULT_SANDBOX_PREFIX,
    # Response Models
    ProviderStatus,
    ValidationResponse,
    SessionStats,
    StorageStats,
    StatsResponse,
    SessionInfo,
    SandboxInfo,
    PresignedUploadResponse,
    MultipartUploadInitResponse,
    UpdateMetadataResponse,
    BatchStoreResponse,
    # Type Aliases
    ArtifactID,
    SessionID,
    SandboxID,
    UserID,
    WorkspaceID,
    NamespaceID,  # NEW - unified VFS
    # Unified Namespace Models (Clean API)
    NamespaceInfo,  # NEW - unified VFS
    # Workspace Models (Legacy - kept for backward compat if needed)
    WorkspaceInfo,
    CheckpointInfo,
)

# Exception classes
from .exceptions import (
    ArtifactStoreError,
    ArtifactNotFoundError,
    ArtifactExpiredError,
    ArtifactCorruptedError,
    ProviderError,
    SessionError,
    AccessDeniedError,
)

# Operation modules (for advanced usage)
from .core import CoreStorageOperations
from .presigned import PresignedURLOperations
from .metadata import MetadataOperations
from .batch import BatchOperations
from .admin import AdminOperations
from .namespace import NamespaceOperations  # NEW - unified VFS
from .store import _DEFAULT_TTL, _DEFAULT_PRESIGN_EXPIRES


# load dot env
load_dotenv()

# version
__version__ = "1.0.0"

__all__ = [
    # Main class
    "ArtifactStore",
    # Models
    "ArtifactEnvelope",
    "ArtifactMetadata",
    "AccessContext",
    "GridKeyComponents",
    "StreamUploadRequest",
    "StreamDownloadRequest",
    "MultipartUploadInitRequest",
    "MultipartUploadCompleteRequest",
    "MultipartUploadPart",
    # Type definitions and enums
    "StorageScope",
    "StorageProvider",
    "SessionProvider",
    "OperationStatus",
    "NamespaceType",  # NEW - unified VFS
    # Constants
    "DEFAULT_TTL",
    "DEFAULT_PRESIGN_EXPIRES",
    "DEFAULT_SESSION_TTL_HOURS",
    "DEFAULT_BUCKET",
    "DEFAULT_SANDBOX_PREFIX",
    "_DEFAULT_TTL",  # Legacy support
    "_DEFAULT_PRESIGN_EXPIRES",  # Legacy support
    # Response Models
    "ProviderStatus",
    "ValidationResponse",
    "SessionStats",
    "StorageStats",
    "StatsResponse",
    "SessionInfo",
    "SandboxInfo",
    "PresignedUploadResponse",
    "MultipartUploadInitResponse",
    "UpdateMetadataResponse",
    "BatchStoreResponse",
    # Type Aliases
    "ArtifactID",
    "SessionID",
    "SandboxID",
    "UserID",
    "WorkspaceID",
    "NamespaceID",  # NEW - unified VFS
    # Unified Namespace Models (Clean API)
    "NamespaceInfo",  # NEW - unified VFS
    # Workspace Models (Legacy - kept for backward compat if needed)
    "WorkspaceInfo",
    "CheckpointInfo",
    # Exceptions
    "ArtifactStoreError",
    "ArtifactNotFoundError",
    "ArtifactExpiredError",
    "ArtifactCorruptedError",
    "ProviderError",
    "SessionError",
    "AccessDeniedError",
    # Operation modules (advanced usage)
    "CoreStorageOperations",
    "PresignedURLOperations",
    "MetadataOperations",
    "BatchOperations",
    "AdminOperations",
    "NamespaceOperations",  # NEW - unified VFS
]


# Convenience aliases for common operations
def create_store(**kwargs) -> ArtifactStore:
    """
    Convenience function to create an ArtifactStore with sensible defaults.

    Parameters
    ----------
    **kwargs
        Passed to ArtifactStore constructor

    Returns
    -------
    ArtifactStore
        Configured artifact store

    Examples
    --------
    >>> store = create_store()  # Memory-based
    >>> store = create_store(storage_provider="ibm_cos", bucket="my-bucket")
    """
    return ArtifactStore(**kwargs)


async def quick_store(
    data: bytes,
    *,
    mime: str = "application/octet-stream",
    summary: str = "Quick upload",
    **store_kwargs,
) -> tuple[ArtifactStore, str]:
    """
    Convenience function for quick one-off artifact storage.

    Parameters
    ----------
    data : bytes
        Data to store
    mime : str, optional
        MIME type
    summary : str, optional
        Description
    **store_kwargs
        Passed to ArtifactStore constructor

    Returns
    -------
    tuple
        (store_instance, artifact_id)

    Examples
    --------
    >>> store, artifact_id = await quick_store(
    ...     b"Hello world",
    ...     mime="text/plain",
    ...     storage_provider="filesystem"
    ... )
    >>> url = await store.presign(artifact_id)
    """
    store = ArtifactStore(**store_kwargs)
    artifact_id = await store.store(data, mime=mime, summary=summary)
    return store, artifact_id


# Module-level configuration helper
def configure_logging(level: str = "INFO"):
    """
    Configure logging for the artifacts package.

    Parameters
    ----------
    level : str
        Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    import logging

    logger = logging.getLogger("chuk_artifacts")
    logger.setLevel(getattr(logging, level.upper()))

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

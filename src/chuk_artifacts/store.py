# -*- coding: utf-8 -*-
# chuk_artifacts/store.py (ENHANCED)
"""
Asynchronous, object-store-backed artefact manager with MCP server support.
"""

from __future__ import annotations

import os, logging
from typing import Any, Dict, List, Callable, AsyncContextManager, Optional, Union

try:
    import aioboto3
except ImportError as e:
    raise ImportError(f"Required dependency missing: {e}. Install with: pip install aioboto3") from e

# Auto-load .env files if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger = logging.getLogger(__name__)
    logger.debug("Loaded environment variables from .env file")
except ImportError:
    logger = logging.getLogger(__name__)
    logger.debug("python-dotenv not available, skipping .env file loading")

# Import exceptions
from .exceptions import ArtifactStoreError

# Configure structured logging
logger = logging.getLogger(__name__)

_DEFAULT_TTL = 900  # seconds (15 minutes for metadata)
_DEFAULT_PRESIGN_EXPIRES = 3600  # seconds (1 hour for presigned URLs)

# ─────────────────────────────────────────────────────────────────────
# Default factories
# ─────────────────────────────────────────────────────────────────────
def _default_storage_factory() -> Callable[[], AsyncContextManager]:
    """Return a zero-arg callable that yields an async ctx-mgr S3 client."""
    from .provider_factory import factory_for_env
    return factory_for_env()  # Defaults to memory provider


def _default_session_factory() -> Callable[[], AsyncContextManager]:
    """Return a zero-arg callable that yields an async ctx-mgr session store."""
    from chuk_sessions.provider_factory import factory_for_env
    return factory_for_env()  # Defaults to memory provider


# ─────────────────────────────────────────────────────────────────────
class ArtifactStore:
    """
    Asynchronous artifact storage with MCP server support.
    
    Enhanced with MCP-specific operations for file management within sessions.
    """

    def __init__(
        self,
        *,
        bucket: Optional[str] = None,
        s3_factory: Optional[Callable[[], AsyncContextManager]] = None,
        storage_provider: Optional[str] = None,
        session_factory: Optional[Callable[[], AsyncContextManager]] = None,
        session_provider: Optional[str] = None,
        max_retries: int = 3,
        # Backward compatibility - deprecated but still supported
        redis_url: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        # Read from environment variables with memory as defaults
        bucket = bucket or os.getenv("ARTIFACT_BUCKET", "mcp-bucket")
        storage_provider = storage_provider or os.getenv("ARTIFACT_PROVIDER", "memory")
        session_provider = session_provider or os.getenv("SESSION_PROVIDER", "memory")
        
        # Handle backward compatibility
        if redis_url is not None:
            import warnings
            warnings.warn(
                "redis_url parameter is deprecated. Use session_provider='redis' "
                "and set SESSION_REDIS_URL environment variable instead.",
                DeprecationWarning,
                stacklevel=2
            )
            os.environ["SESSION_REDIS_URL"] = redis_url
            session_provider = "redis"
            
        if provider is not None:
            import warnings
            warnings.warn(
                "provider parameter is deprecated. Use storage_provider instead.",
                DeprecationWarning,
                stacklevel=2
            )
            storage_provider = provider

        # Validate factory/provider combinations
        if s3_factory and storage_provider:
            raise ValueError("Specify either s3_factory or storage_provider—not both")
        if session_factory and session_provider:
            raise ValueError("Specify either session_factory or session_provider—not both")

        # Initialize storage factory
        if s3_factory:
            self._s3_factory = s3_factory
        elif storage_provider:
            self._s3_factory = self._load_storage_provider(storage_provider)
        else:
            self._s3_factory = _default_storage_factory()

        # Initialize session factory
        if session_factory:
            self._session_factory = session_factory
        elif session_provider:
            self._session_factory = self._load_session_provider(session_provider)
        else:
            self._session_factory = _default_session_factory()

        self.bucket = bucket
        self.max_retries = max_retries
        self._storage_provider_name = storage_provider or "memory"
        self._session_provider_name = session_provider or "memory"
        self._closed = False

        # Initialize operation modules
        from .core import CoreStorageOperations
        from .presigned import PresignedURLOperations
        from .metadata import MetadataOperations
        from .batch import BatchOperations
        from .admin import AdminOperations
        from .session_operations import SessionOperations 
        
        self._core = CoreStorageOperations(self)
        self._presigned = PresignedURLOperations(self)
        self._metadata = MetadataOperations(self)
        self._batch = BatchOperations(self)
        self._admin = AdminOperations(self)
        self._session = SessionOperations(self)

        logger.info(
            "ArtifactStore initialized with session operations support",
            extra={
                "bucket": bucket,
                "storage_provider": self._storage_provider_name,
                "session_provider": self._session_provider_name,
            }
        )

    # ─────────────────────────────────────────────────────────────────
    # Core storage operations (delegated to CoreStorageOperations)
    # ─────────────────────────────────────────────────────────────────

    async def store(
        self,
        data: bytes,
        *,
        mime: str,
        summary: str,
        meta: Dict[str, Any] | None = None,
        filename: str | None = None,
        session_id: str | None = None,
        ttl: int = _DEFAULT_TTL,
    ) -> str:
        """Store artifact data with metadata."""
        return await self._core.store(
            data,
            mime=mime,
            summary=summary,
            meta=meta,
            filename=filename,
            session_id=session_id,
            ttl=ttl,
        )

    async def retrieve(self, artifact_id: str) -> bytes:
        """Retrieve artifact data directly."""
        return await self._core.retrieve(artifact_id)

    # ─────────────────────────────────────────────────────────────────
    # Presigned URL operations (delegated to PresignedURLOperations)
    # ─────────────────────────────────────────────────────────────────

    async def presign(self, artifact_id: str, expires: int = _DEFAULT_PRESIGN_EXPIRES) -> str:
        """Generate a presigned URL for artifact download."""
        return await self._presigned.presign(artifact_id, expires)

    async def presign_short(self, artifact_id: str) -> str:
        """Generate a short-lived presigned URL (15 minutes)."""
        return await self._presigned.presign_short(artifact_id)
    
    async def presign_medium(self, artifact_id: str) -> str:
        """Generate a medium-lived presigned URL (1 hour)."""
        return await self._presigned.presign_medium(artifact_id)
    
    async def presign_long(self, artifact_id: str) -> str:
        """Generate a long-lived presigned URL (24 hours)."""
        return await self._presigned.presign_long(artifact_id)

    async def presign_upload(
        self, 
        session_id: str | None = None,
        filename: str | None = None,
        mime_type: str = "application/octet-stream",
        expires: int = _DEFAULT_PRESIGN_EXPIRES
    ) -> tuple[str, str]:
        """Generate a presigned URL for uploading a new artifact."""
        return await self._presigned.presign_upload(
            session_id=session_id,
            filename=filename,
            mime_type=mime_type,
            expires=expires
        )

    async def register_uploaded_artifact(
        self,
        artifact_id: str,
        *,
        mime: str,
        summary: str,
        meta: Dict[str, Any] | None = None,
        filename: str | None = None,
        session_id: str | None = None,
        ttl: int = _DEFAULT_TTL,
    ) -> bool:
        """Register metadata for an artifact uploaded via presigned URL."""
        return await self._presigned.register_uploaded_artifact(
            artifact_id,
            mime=mime,
            summary=summary,
            meta=meta,
            filename=filename,
            session_id=session_id,
            ttl=ttl,
        )

    async def presign_upload_and_register(
        self,
        *,
        mime: str,
        summary: str,
        meta: Dict[str, Any] | None = None,
        filename: str | None = None,
        session_id: str | None = None,
        ttl: int = _DEFAULT_TTL,
        expires: int = _DEFAULT_PRESIGN_EXPIRES
    ) -> tuple[str, str]:
        """Convenience method combining presign_upload and pre-register metadata."""
        return await self._presigned.presign_upload_and_register(
            mime=mime,
            summary=summary,
            meta=meta,
            filename=filename,
            session_id=session_id,
            ttl=ttl,
            expires=expires
        )

    # ─────────────────────────────────────────────────────────────────
    # Metadata operations (delegated to MetadataOperations)
    # ─────────────────────────────────────────────────────────────────

    async def metadata(self, artifact_id: str) -> Dict[str, Any]:
        """Get artifact metadata."""
        return await self._metadata.metadata(artifact_id)

    async def exists(self, artifact_id: str) -> bool:
        """Check if artifact exists and hasn't expired."""
        return await self._metadata.exists(artifact_id)

    async def delete(self, artifact_id: str) -> bool:
        """Delete artifact and its metadata."""
        return await self._metadata.delete(artifact_id)

    async def update_metadata(
        self, 
        artifact_id: str, 
        *,
        summary: str = None,
        meta: Dict[str, Any] = None,
        filename: str = None,
        ttl: int = None,
        # NEW: MCP-specific parameters
        new_meta: Dict[str, Any] = None,
        merge: bool = True
    ) -> Dict[str, Any]:
        """Update artifact metadata with MCP server compatibility."""
        return await self._metadata.update_metadata(
            artifact_id,
            summary=summary,
            meta=meta,
            filename=filename,
            ttl=ttl,
            new_meta=new_meta,
            merge=merge
        )

    async def extend_ttl(self, artifact_id: str, additional_seconds: int) -> Dict[str, Any]:
        """Extend the TTL of an artifact's metadata."""
        return await self._metadata.extend_ttl(artifact_id, additional_seconds)

    async def list_by_session(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """List artifacts for a specific session."""
        return await self._metadata.list_by_session(session_id, limit)

    async def list_by_prefix(
        self, 
        session_id: str, 
        prefix: str = "", 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List artifacts in a session with filename prefix filtering."""
        return await self._metadata.list_by_prefix(session_id, prefix, limit)

    # ─────────────────────────────────────────────────────────────────
    # Batch operations (delegated to BatchOperations)
    # ─────────────────────────────────────────────────────────────────

    async def store_batch(
        self,
        items: List[Dict[str, Any]],
        session_id: str | None = None,
        ttl: int = _DEFAULT_TTL,
    ) -> List[str]:
        """Store multiple artifacts in a batch operation."""
        return await self._batch.store_batch(items, session_id, ttl)

    # ─────────────────────────────────────────────────────────────────
    # Administrative operations (delegated to AdminOperations)
    # ─────────────────────────────────────────────────────────────────

    async def validate_configuration(self) -> Dict[str, Any]:
        """Validate store configuration and connectivity."""
        return await self._admin.validate_configuration()

    async def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        return await self._admin.get_stats()

    # ─────────────────────────────────────────────────────────────────
    # Session-based file operations (delegated to SessionOperations)
    # ─────────────────────────────────────────────────────────────────

    async def move_file(
        self,
        artifact_id: str,
        *,
        new_filename: str = None,
        new_session_id: str = None,
        new_meta: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Move a file within sessions or rename it."""
        return await self._session.move_file(
            artifact_id,
            new_filename=new_filename,
            new_session_id=new_session_id,
            new_meta=new_meta
        )

    async def copy_file(
        self,
        artifact_id: str,
        *,
        new_filename: str = None,
        target_session_id: str = None,
        new_meta: Dict[str, Any] = None,
        summary: str = None
    ) -> str:
        """Copy a file within or across sessions."""
        return await self._session.copy_file(
            artifact_id,
            new_filename=new_filename,
            target_session_id=target_session_id,
            new_meta=new_meta,
            summary=summary
        )

    async def read_file(
        self,
        artifact_id: str,
        *,
        encoding: str = "utf-8",
        as_text: bool = True
    ) -> Union[str, bytes]:
        """Read file content directly."""
        return await self._session.read_file(
            artifact_id,
            encoding=encoding,
            as_text=as_text
        )

    async def write_file(
        self,
        content: Union[str, bytes],
        *,
        filename: str,
        mime: str = "text/plain",
        summary: str = "",
        session_id: str = None,
        meta: Dict[str, Any] = None,
        encoding: str = "utf-8",
        overwrite_artifact_id: str = None
    ) -> str:
        """Write content to a new file or overwrite existing."""
        return await self._session.write_file(
            content,
            filename=filename,
            mime=mime,
            summary=summary,
            session_id=session_id,
            meta=meta,
            encoding=encoding,
            overwrite_artifact_id=overwrite_artifact_id
        )

    async def get_directory_contents(
        self,
        session_id: str,
        directory_prefix: str = "",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List files in a directory-like structure within a session."""
        return await self._session.get_directory_contents(
            session_id,
            directory_prefix,
            limit
        )

    # ─────────────────────────────────────────────────────────────────
    # Resource management
    # ─────────────────────────────────────────────────────────────────

    async def close(self):
        """Mark store as closed."""
        if not self._closed:
            self._closed = True
            logger.info("ArtifactStore closed")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # ─────────────────────────────────────────────────────────────────
    # Helper functions (still needed for provider loading)
    # ─────────────────────────────────────────────────────────────────

    def _load_storage_provider(self, name: str) -> Callable[[], AsyncContextManager]:
        """Load storage provider by name."""
        from importlib import import_module

        try:
            mod = import_module(f"chuk_artifacts.providers.{name}")
        except ModuleNotFoundError as exc:
            available = ["memory", "filesystem", "s3", "ibm_cos", "ibm_cos_iam"]
            raise ValueError(
                f"Unknown storage provider '{name}'. "
                f"Available providers: {', '.join(available)}"
            ) from exc

        if not hasattr(mod, "factory"):
            raise AttributeError(f"Storage provider '{name}' lacks factory()")
        
        logger.info(f"Loaded storage provider: {name}")
        return mod.factory()

    def _load_session_provider(self, name: str) -> Callable[[], AsyncContextManager]:
        """Load session provider by name."""
        from importlib import import_module

        try:
            mod = import_module(f"chuk_sessions.providers.{name}")
        except ModuleNotFoundError as exc:
            raise ValueError(f"Unknown session provider '{name}'") from exc

        if not hasattr(mod, "factory"):
            raise AttributeError(f"Session provider '{name}' lacks factory()")
        
        logger.info(f"Loaded session provider: {name}")
        return mod.factory()
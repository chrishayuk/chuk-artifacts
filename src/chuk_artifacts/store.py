# -*- coding: utf-8 -*-
# chuk_artifacts/store.py
"""
Clean ArtifactStore with mandatory sessions and grid architecture.

Grid Architecture:
- Mandatory session allocation (no anonymous artifacts)
- Grid paths: grid/{sandbox_id}/{session_id}/{artifact_id}
- Clean, focused implementation
"""

from __future__ import annotations

import os, logging, uuid
from datetime import datetime
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
from .exceptions import ArtifactStoreError, ProviderError
from .session.session_manager import SessionManager

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
    Clean ArtifactStore with grid architecture and mandatory sessions.
    
    Simple rules:
    - Always allocate a session (no anonymous artifacts)
    - Grid paths only: grid/{sandbox_id}/{session_id}/{artifact_id}
    - Clean, focused implementation
    """

    def __init__(
        self,
        *,
        bucket: Optional[str] = None,
        storage_provider: Optional[str] = None,
        session_provider: Optional[str] = None,
        sandbox_id: Optional[str] = None,
        session_ttl_hours: int = 24,
        max_retries: int = 3,
    ):
        # Configuration
        self.bucket = bucket or os.getenv("ARTIFACT_BUCKET", "artifacts")
        self.sandbox_id = sandbox_id or self._detect_sandbox_id()
        self.session_ttl_hours = session_ttl_hours
        self.max_retries = max_retries
        self._closed = False
        
        # Storage provider
        storage_provider = storage_provider or os.getenv("ARTIFACT_PROVIDER", "memory")
        self._s3_factory = self._load_storage_provider(storage_provider)
        self._storage_provider_name = storage_provider
        
        # Session provider
        session_provider = session_provider or os.getenv("SESSION_PROVIDER", "memory")
        self._session_factory = self._load_session_provider(session_provider)
        self._session_provider_name = session_provider
        
        # Session manager (always enabled)
        self._session_manager = SessionManager(
            sandbox_id=self.sandbox_id,
            session_factory=self._session_factory,
            default_ttl_hours=session_ttl_hours,
        )
        
        # Operation modules
        from .core import CoreStorageOperations as CoreOps
        from .metadata import MetadataOperations as MetaOps
        from .presigned import PresignedURLOperations as PresignedOps
        from .batch import BatchOperations as BatchOps
        from .admin import AdminOperations as AdminOps
        
        self._core = CoreOps(self)
        self._metadata = MetaOps(self)
        self._presigned = PresignedOps(self)
        self._batch = BatchOps(self)
        self._admin = AdminOps(self)
        
        logger.info(
            "ArtifactStore initialized",
            extra={
                "bucket": self.bucket,
                "sandbox_id": self.sandbox_id,
                "storage_provider": storage_provider,
                "session_provider": session_provider,
            }
        )

    # ─────────────────────────────────────────────────────────────────
    # Core operations
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
        user_id: str | None = None,
        ttl: int = _DEFAULT_TTL,
    ) -> str:
        """Store artifact with mandatory session allocation."""
        # Always allocate/validate session
        session_id = await self._session_manager.allocate_session(
            session_id=session_id,
            user_id=user_id,
        )
        
        # Work around the naming conflict in CoreStorageOperations
        # where self.store is the artifact store instance, not the method
        core_store_method = getattr(self._core.__class__, 'store')
        return await core_store_method(
            self._core,
            data=data,
            mime=mime,
            summary=summary,
            meta=meta,
            filename=filename,
            session_id=session_id,
            ttl=ttl,
        )

    async def retrieve(self, artifact_id: str) -> bytes:
        """Retrieve artifact data."""
        return await self._core.retrieve(artifact_id)

    async def metadata(self, artifact_id: str) -> Dict[str, Any]:
        """Get artifact metadata."""
        return await self._metadata.get_metadata(artifact_id)

    async def exists(self, artifact_id: str) -> bool:
        """Check if artifact exists."""
        return await self._metadata.exists(artifact_id)

    async def delete(self, artifact_id: str) -> bool:
        """Delete artifact."""
        return await self._metadata.delete(artifact_id)

    async def list_by_session(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """List artifacts in session."""
        return await self._metadata.list_by_session(session_id, limit)

    # ─────────────────────────────────────────────────────────────────
    # Session operations
    # ─────────────────────────────────────────────────────────────────

    async def create_session(
        self,
        user_id: Optional[str] = None,
        ttl_hours: Optional[int] = None,
    ) -> str:
        """Create a new session."""
        return await self._session_manager.allocate_session(
            user_id=user_id,
            ttl_hours=ttl_hours,
        )

    async def validate_session(self, session_id: str) -> bool:
        """Validate session."""
        return await self._session_manager.validate_session(session_id)

    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information."""
        return await self._session_manager.get_session_info(session_id)

    # ─────────────────────────────────────────────────────────────────
    # Grid operations
    # ─────────────────────────────────────────────────────────────────

    def get_canonical_prefix(self, session_id: str) -> str:
        """Get grid path prefix for session."""
        return self._session_manager.get_canonical_prefix(session_id)

    def generate_artifact_key(self, session_id: str, artifact_id: str) -> str:
        """Generate grid artifact key."""
        return self._session_manager.generate_artifact_key(session_id, artifact_id)

    # ─────────────────────────────────────────────────────────────────
    # File operations
    # ─────────────────────────────────────────────────────────────────

    async def write_file(
        self,
        content: Union[str, bytes],
        *,
        filename: str,
        mime: str = "text/plain",
        summary: str = "",
        session_id: str = None,
        user_id: str = None,
        meta: Dict[str, Any] = None,
        encoding: str = "utf-8",
    ) -> str:
        """Write content to file."""
        if isinstance(content, str):
            data = content.encode(encoding)
        else:
            data = content
        
        return await self.store(
            data=data,
            mime=mime,
            summary=summary or f"File: {filename}",
            filename=filename,
            session_id=session_id,
            user_id=user_id,
            meta=meta,
        )

    async def read_file(
        self,
        artifact_id: str,
        *,
        encoding: str = "utf-8",
        as_text: bool = True
    ) -> Union[str, bytes]:
        """Read file content."""
        data = await self.retrieve(artifact_id)
        
        if as_text:
            return data.decode(encoding)
        return data

    async def list_files(
        self,
        session_id: str,
        prefix: str = "",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List files in session with optional prefix filter."""
        return await self._metadata.list_by_prefix(session_id, prefix, limit)

    async def get_directory_contents(
        self,
        session_id: str,
        directory_prefix: str = "",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List files in a directory-like structure within a session.
        """
        try:
            return await self._metadata.list_by_prefix(session_id, directory_prefix, limit)
        except Exception as e:
            logger.error(
                "Directory listing failed for session %s: %s",
                session_id,
                str(e),
                extra={
                    "session_id": session_id,
                    "directory_prefix": directory_prefix,
                    "operation": "get_directory_contents"
                }
            )
            raise ProviderError(f"Directory listing failed: {e}") from e

    async def copy_file(
        self,
        artifact_id: str,
        *,
        new_filename: str = None,
        target_session_id: str = None,
        new_meta: Dict[str, Any] = None,
        summary: str = None
    ) -> str:
        """Copy a file WITHIN THE SAME SESSION only (security enforced)."""
        # Get original metadata to check session
        original_meta = await self.metadata(artifact_id)
        original_session = original_meta.get("session_id")
        
        # STRICT SECURITY: Block ALL cross-session copies
        if target_session_id and target_session_id != original_session:
            raise ArtifactStoreError(
                f"Cross-session copies are not permitted for security reasons. "
                f"Artifact {artifact_id} belongs to session '{original_session}', "
                f"cannot copy to session '{target_session_id}'. Files can only be "
                f"copied within the same session."
            )
        
        # Get original data
        original_data = await self.retrieve(artifact_id)
        
        # Prepare copy metadata
        copy_filename = new_filename or (
            (original_meta.get("filename", "file") or "file") + "_copy"
        )
        copy_summary = summary or f"Copy of {original_meta.get('summary', 'artifact')}"
        
        # Merge metadata
        copy_meta = {**original_meta.get("meta", {})}
        if new_meta:
            copy_meta.update(new_meta)
        
        # Add copy tracking
        copy_meta["copied_from"] = artifact_id
        copy_meta["copy_timestamp"] = datetime.utcnow().isoformat() + "Z"
        
        # Store the copy in the same session
        return await self.store(
            data=original_data,
            mime=original_meta["mime"],
            summary=copy_summary,
            filename=copy_filename,
            session_id=original_session,  # Always same session
            meta=copy_meta
        )

    async def move_file(
        self,
        artifact_id: str,
        *,
        new_filename: str = None,
        new_session_id: str = None,
        new_meta: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Move/rename a file WITHIN THE SAME SESSION only (security enforced)."""
        # Get current metadata
        record = await self.metadata(artifact_id)
        current_session = record.get("session_id")
        
        # STRICT SECURITY: Block ALL cross-session moves
        if new_session_id and new_session_id != current_session:
            raise ArtifactStoreError(
                f"Cross-session moves are not permitted for security reasons. "
                f"Artifact {artifact_id} belongs to session '{current_session}', "
                f"cannot move to session '{new_session_id}'. Use copy operations within "
                f"the same session only."
            )
        
        # For now, just simulate a move by updating metadata
        # A full implementation would update the metadata record
        if new_filename:
            # This is a simplified move - just return updated record
            record["filename"] = new_filename
        if new_meta:
            existing_meta = record.get("meta", {})
            existing_meta.update(new_meta)
            record["meta"] = existing_meta
        
        return record

    # ─────────────────────────────────────────────────────────────────
    # Presigned URL operations
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
        return await self._presigned.presign_upload(session_id, filename, mime_type, expires)

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
    # Batch operations
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
    # Metadata operations
    # ─────────────────────────────────────────────────────────────────

    async def update_metadata(
        self,
        artifact_id: str,
        *,
        summary: str = None,
        meta: Dict[str, Any] = None,
        merge: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """Update artifact metadata."""
        return await self._metadata.update_metadata(
            artifact_id,
            summary=summary,
            meta=meta,
            merge=merge,
            **kwargs
        )

    async def extend_ttl(
        self,
        artifact_id: str,
        additional_seconds: int
    ) -> Dict[str, Any]:
        """Extend artifact TTL."""
        return await self._metadata.extend_ttl(artifact_id, additional_seconds)

    # ─────────────────────────────────────────────────────────────────
    # Administrative operations
    # ─────────────────────────────────────────────────────────────────

    async def validate_configuration(self) -> Dict[str, Any]:
        """Validate store configuration and connectivity."""
        return await self._admin.validate_configuration()

    async def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        return await self._admin.get_stats()

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────

    def _detect_sandbox_id(self) -> str:
        """Auto-detect sandbox ID."""
        candidates = [
            os.getenv("ARTIFACT_SANDBOX_ID"),
            os.getenv("SANDBOX_ID"),
            os.getenv("HOSTNAME"),
        ]
        
        for candidate in candidates:
            if candidate:
                clean_id = "".join(c for c in candidate if c.isalnum() or c in "-_")[:32]
                if clean_id:
                    return clean_id
        
        # Generate fallback
        return f"sandbox-{uuid.uuid4().hex[:8]}"

    def _load_storage_provider(self, name: str) -> Callable[[], AsyncContextManager]:
        """Load storage provider."""
        from importlib import import_module
        
        try:
            mod = import_module(f"chuk_artifacts.providers.{name}")
            return mod.factory()
        except ModuleNotFoundError as exc:
            available = ["memory", "filesystem", "s3", "ibm_cos"]
            raise ValueError(f"Unknown storage provider '{name}'. Available: {', '.join(available)}") from exc

    def _load_session_provider(self, name: str) -> Callable[[], AsyncContextManager]:
        """Load session provider."""
        from importlib import import_module
        
        try:
            mod = import_module(f"chuk_sessions.providers.{name}")
            return mod.factory()
        except ModuleNotFoundError as exc:
            raise ValueError(f"Unknown session provider '{name}'") from exc

    # ─────────────────────────────────────────────────────────────────
    # Resource management
    # ─────────────────────────────────────────────────────────────────

    async def close(self):
        """Close the store."""
        if not self._closed:
            self._closed = True
            logger.info("ArtifactStore closed")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
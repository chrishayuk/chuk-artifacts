# -*- coding: utf-8 -*-
# chuk_artifacts/store.py
"""
Clean ArtifactStore with mandatory sessions and grid architecture.

Grid Architecture:
- Mandatory session allocation (no anonymous artifacts)
- Grid paths: grid/{sandbox_id}/{session_id}/{artifact_id}
- Clean, focused implementation
- Now uses chuk_sessions for session management
"""

from __future__ import annotations

import os
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Callable, AsyncContextManager, Optional, Union
from importlib.util import find_spec
from chuk_sessions.session_manager import SessionManager
from .grid import canonical_prefix, artifact_key, parse
from .models import ArtifactMetadata, GridKeyComponents

# Check for required dependencies
if not find_spec("aioboto3"):
    raise ImportError(
        "Required dependency missing: aioboto3. Install with: pip install aioboto3"
    )

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

# Import chuk_sessions instead of local session manager

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
    - Uses chuk_sessions for session management
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

        # Session manager (now using chuk_sessions)
        self._session_manager = SessionManager(
            sandbox_id=self.sandbox_id,
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
            },
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
        scope: str = "session",  # "session", "user", or "sandbox"
    ) -> str:
        """
        Store artifact with scope-based storage support.

        Args:
            data: Artifact data bytes
            mime: MIME type
            summary: Human-readable description
            meta: Optional custom metadata
            filename: Optional filename
            session_id: Session ID (auto-allocated if not provided)
            user_id: User ID (used for session allocation and user scope)
            ttl: Time-to-live in seconds (default 900 = 15 min)
            scope: Storage scope - "session" (ephemeral), "user" (persistent), or "sandbox" (shared)

        Returns:
            Artifact ID

        Examples:
            >>> # Session-scoped (default, ephemeral)
            >>> artifact_id = await store.store(data, mime="...", summary="...")

            >>> # User-scoped (persistent across sessions)
            >>> artifact_id = await store.store(
            ...     data, mime="...", summary="...",
            ...     user_id="alice", scope="user", ttl=None
            ... )

            >>> # Sandbox-scoped (shared by all users)
            >>> artifact_id = await store.store(
            ...     data, mime="...", summary="...",
            ...     scope="sandbox"
            ... )
        """
        # For user-scoped artifacts, user_id is required
        if scope == "user" and not user_id:
            raise ValueError("user_id is required for user-scoped artifacts")

        # Always allocate/validate session using chuk_sessions
        # (even for user/sandbox scope, we track which session created it)
        session_id = await self._session_manager.allocate_session(
            session_id=session_id,
            user_id=user_id,
        )

        # Store using core operations with scope
        return await self._core.store(
            data=data,
            mime=mime,
            summary=summary,
            meta=meta,
            filename=filename,
            session_id=session_id,
            ttl=ttl,
            scope=scope,
            owner_id=user_id if scope == "user" else None,
        )

    async def update_file(
        self,
        artifact_id: str,
        *,
        data: Optional[bytes] = None,
        meta: Optional[Dict[str, Any]] = None,
        filename: Optional[str] = None,
        summary: Optional[str] = None,
        mime: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Update an artifact's content, metadata, filename, summary, or mime type.
        All parameters are optional. At least one must be provided.
        """
        if not any(
            [
                data is not None,
                meta is not None,
                filename is not None,
                summary is not None,
                mime is not None,
                ttl is not None,
            ]
        ):
            raise ValueError("At least one update parameter must be provided.")

        return await self._core.update_file(
            artifact_id=artifact_id,
            new_data=data,
            mime=mime,
            summary=summary,
            meta=meta,
            filename=filename,
            ttl=ttl,
        )

    async def retrieve(
        self,
        artifact_id: str,
        *,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> bytes:
        """
        Retrieve artifact data with optional access control.

        Args:
            artifact_id: ID of artifact to retrieve
            user_id: User ID for access control (required for user-scoped artifacts)
            session_id: Session ID for access control (optional for session-scoped artifacts)

        Returns:
            Artifact data bytes

        Raises:
            AccessDeniedError: If access is denied (only for user/sandbox scoped artifacts)
            ArtifactNotFoundError: If artifact not found

        Examples:
            >>> # Legacy usage (backward compatible, no access check)
            >>> data = await store.retrieve(artifact_id)

            >>> # Session-scoped artifact with access control
            >>> data = await store.retrieve(artifact_id, session_id="sess123")

            >>> # User-scoped artifact
            >>> data = await store.retrieve(artifact_id, user_id="alice")

            >>> # Sandbox-scoped artifact (anyone in sandbox can read)
            >>> data = await store.retrieve(artifact_id)

        Note:
            Access control is enforced for user-scoped and sandbox-scoped artifacts.
            For session-scoped artifacts (default), access control is only enforced
            if session_id is explicitly provided (opt-in for new security model).
        """
        # Get metadata to check if access control is needed
        metadata = await self.metadata(artifact_id)

        # Only enforce access control for:
        # 1. User-scoped artifacts (always)
        # 2. Sandbox-scoped artifacts (always)
        # 3. Session-scoped artifacts when session_id is explicitly provided (opt-in)
        # Handle both ArtifactMetadata objects and dict-style metadata (backward compat)
        metadata_scope = (
            getattr(metadata, "scope", None) or metadata.get("scope", "session")
            if isinstance(metadata, dict)
            else metadata.scope
        )

        should_check_access = metadata_scope in ("user", "sandbox") or (
            metadata_scope == "session" and session_id is not None
        )

        if should_check_access:
            from .access_control import check_access, build_context

            context = build_context(
                user_id=user_id, session_id=session_id, sandbox_id=self.sandbox_id
            )
            check_access(metadata, context)

        # Access granted (or no check needed), retrieve data
        return await self._core.retrieve(artifact_id)

    async def metadata(self, artifact_id: str) -> ArtifactMetadata:
        """Get artifact metadata."""
        return await self._metadata.get_metadata(artifact_id)

    async def exists(self, artifact_id: str) -> bool:
        """Check if artifact exists."""
        return await self._metadata.exists(artifact_id)

    async def delete(
        self,
        artifact_id: str,
        *,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> bool:
        """
        Delete artifact with optional access control.

        Args:
            artifact_id: ID of artifact to delete
            user_id: User ID for access control (required for user-scoped artifacts)
            session_id: Session ID for access control (optional for session-scoped artifacts)

        Returns:
            True if deleted successfully

        Raises:
            AccessDeniedError: If modification is denied
            ArtifactNotFoundError: If artifact not found

        Note:
            Access control is enforced for user-scoped and sandbox-scoped artifacts.
            For session-scoped artifacts (default), access control is only enforced
            if session_id is explicitly provided (opt-in for new security model).
            Sandbox-scoped artifacts cannot be deleted via this method - use admin
            endpoints for sandbox artifact management.
        """
        # Get metadata to check if access control is needed
        metadata = await self.metadata(artifact_id)

        # Only enforce access control for:
        # 1. User-scoped artifacts (always)
        # 2. Sandbox-scoped artifacts (always)
        # 3. Session-scoped artifacts when session_id is explicitly provided (opt-in)
        # Handle both ArtifactMetadata objects and dict-style metadata (backward compat)
        metadata_scope = (
            getattr(metadata, "scope", None) or metadata.get("scope", "session")
            if isinstance(metadata, dict)
            else metadata.scope
        )

        should_check_access = metadata_scope in ("user", "sandbox") or (
            metadata_scope == "session" and session_id is not None
        )

        if should_check_access:
            from .access_control import can_modify, build_context

            context = build_context(
                user_id=user_id, session_id=session_id, sandbox_id=self.sandbox_id
            )

            # Check modification permission
            if not can_modify(metadata, context):
                from .exceptions import AccessDeniedError

                owner_id = (
                    getattr(metadata, "owner_id", None) or metadata.get("owner_id")
                    if isinstance(metadata, dict)
                    else None
                )
                session_id_from_meta = (
                    getattr(metadata, "session_id", None) or metadata.get("session_id")
                    if isinstance(metadata, dict)
                    else None
                )
                raise AccessDeniedError(
                    f"Cannot delete artifact {artifact_id}: insufficient permissions. "
                    f"Scope: {metadata_scope}, Owner: {owner_id or session_id_from_meta}"
                )

        # Permission granted (or no check needed), delete
        return await self._metadata.delete(artifact_id)

    async def list_by_session(
        self, session_id: str, limit: int = 100
    ) -> List[ArtifactMetadata]:
        """List artifacts in session."""
        return await self._metadata.list_by_session(session_id, limit)

    async def search(
        self,
        *,
        user_id: Optional[str] = None,
        scope: Optional[str] = None,
        mime_prefix: Optional[str] = None,
        meta_filter: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[ArtifactMetadata]:
        """
        Search artifacts by scope, user, MIME type, and metadata.

        This is useful for finding user artifacts across all sessions, or searching
        within specific scopes.

        Args:
            user_id: Filter by owner (user-scoped artifacts only)
            scope: Filter by scope ("session", "user", or "sandbox")
            mime_prefix: Filter by MIME type prefix (e.g., "image/" for all images)
            meta_filter: Filter by custom metadata (exact match)
            limit: Maximum number of results

        Returns:
            List of matching artifacts

        Examples:
            >>> # Find all user's artifacts across sessions
            >>> artifacts = await store.search(user_id="alice", scope="user")

            >>> # Find all images for a user
            >>> images = await store.search(
            ...     user_id="alice",
            ...     scope="user",
            ...     mime_prefix="image/"
            ... )

            >>> # Find by custom metadata
            >>> artifacts = await store.search(
            ...     user_id="alice",
            ...     meta_filter={"project": "Q4-deck"}
            ... )

        Note:
            This method requires iterating through storage keys. For large datasets,
            consider using a proper search index (Elasticsearch, Typesense, etc.).
        """
        results = []

        try:
            # Build prefix based on scope and user
            if scope == "user" and user_id:
                prefix = f"grid/{self.sandbox_id}/users/{user_id}/"
            elif scope == "session":
                # Can't search all sessions efficiently without index
                logger.warning(
                    "Searching session scope requires session_id, use list_by_session() instead"
                )
                return []
            elif scope == "sandbox":
                prefix = f"grid/{self.sandbox_id}/shared/"
            elif user_id:
                # Search user artifacts specifically
                prefix = f"grid/{self.sandbox_id}/users/{user_id}/"
            else:
                # Search entire sandbox (expensive!)
                prefix = f"grid/{self.sandbox_id}/"

            storage_ctx_mgr = self._s3_factory()
            async with storage_ctx_mgr as s3:
                if not hasattr(s3, "list_objects_v2"):
                    logger.warning("Storage provider doesn't support listing")
                    return []

                response = await s3.list_objects_v2(
                    Bucket=self.bucket,
                    Prefix=prefix,
                    MaxKeys=limit * 2,  # Get more to account for filtering
                )

                for obj in response.get("Contents", []):
                    key = obj["Key"]
                    parsed = self.parse_grid_key(key)

                    if not parsed:
                        continue

                    artifact_id = parsed.artifact_id

                    try:
                        metadata = await self.metadata(artifact_id)

                        # Apply filters
                        if scope and metadata.scope != scope:
                            continue

                        if user_id and metadata.owner_id != user_id:
                            continue

                        if mime_prefix and not metadata.mime.startswith(mime_prefix):
                            continue

                        if meta_filter:
                            # Check if all filter items match
                            matches = all(
                                metadata.meta.get(k) == v
                                for k, v in meta_filter.items()
                            )
                            if not matches:
                                continue

                        results.append(metadata)

                        if len(results) >= limit:
                            break

                    except Exception as e:
                        logger.debug(f"Skipping artifact {artifact_id}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise ProviderError(f"Search operation failed: {e}") from e

        return results

    # ─────────────────────────────────────────────────────────────────
    # Session operations - now delegated to chuk_sessions
    # ─────────────────────────────────────────────────────────────────

    async def create_session(
        self,
        user_id: Optional[str] = None,
        ttl_hours: Optional[int] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new session."""
        return await self._session_manager.allocate_session(
            user_id=user_id,
            ttl_hours=ttl_hours,
            custom_metadata=custom_metadata,
        )

    async def validate_session(self, session_id: str) -> bool:
        """Validate session."""
        return await self._session_manager.validate_session(session_id)

    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information."""
        return await self._session_manager.get_session_info(session_id)

    async def update_session_metadata(
        self, session_id: str, metadata: Dict[str, Any]
    ) -> bool:
        """Update session metadata."""
        return await self._session_manager.update_session_metadata(session_id, metadata)

    async def extend_session_ttl(self, session_id: str, additional_hours: int) -> bool:
        """Extend session TTL."""
        return await self._session_manager.extend_session_ttl(
            session_id, additional_hours
        )

    async def delete_session(self, session_id: str) -> bool:
        """Delete session."""
        return await self._session_manager.delete_session(session_id)

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        return await self._session_manager.cleanup_expired_sessions()

    # ─────────────────────────────────────────────────────────────────
    # Grid operations - now delegated to chuk_sessions
    # ─────────────────────────────────────────────────────────────────

    def get_canonical_prefix(self, session_id: str) -> str:
        """Get grid path prefix for session."""
        return canonical_prefix(self.sandbox_id, session_id)

    def generate_artifact_key(self, session_id: str, artifact_id: str) -> str:
        """Generate grid artifact key."""
        return artifact_key(self.sandbox_id, session_id, artifact_id)

    def parse_grid_key(self, grid_key: str) -> Optional[GridKeyComponents]:
        """Parse grid key to extract components."""
        return parse(grid_key)

    def get_session_prefix_pattern(self) -> str:
        """Get session prefix pattern for this sandbox."""
        return f"grid/{self.sandbox_id}/"

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
        self, artifact_id: str, *, encoding: str = "utf-8", as_text: bool = True
    ) -> Union[str, bytes]:
        """Read file content."""
        data = await self.retrieve(artifact_id)

        if as_text:
            return data.decode(encoding)
        return data

    async def list_files(
        self, session_id: str, prefix: str = "", limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List files in session with optional prefix filter."""
        return await self._metadata.list_by_prefix(session_id, prefix, limit)

    async def get_directory_contents(
        self, session_id: str, directory_prefix: str = "", limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List files in a directory-like structure within a session.
        """
        try:
            return await self._metadata.list_by_prefix(
                session_id, directory_prefix, limit
            )
        except Exception as e:
            logger.error(
                "Directory listing failed for session %s: %s",
                session_id,
                str(e),
                extra={
                    "session_id": session_id,
                    "directory_prefix": directory_prefix,
                    "operation": "get_directory_contents",
                },
            )
            raise ProviderError(f"Directory listing failed: {e}") from e

    async def copy_file(
        self,
        artifact_id: str,
        *,
        new_filename: str = None,
        target_session_id: str = None,
        new_meta: Dict[str, Any] = None,
        summary: str = None,
    ) -> str:
        """Copy a file WITHIN THE SAME SESSION only (security enforced)."""
        # Get original metadata to check session
        original_meta = await self.metadata(artifact_id)
        original_session = original_meta.session_id

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
        copy_filename = new_filename or ((original_meta.filename or "file") + "_copy")
        copy_summary = summary or f"Copy of {original_meta.summary}"

        # Merge metadata
        copy_meta = {**original_meta.meta}
        if new_meta:
            copy_meta.update(new_meta)

        # Add copy tracking
        copy_meta["copied_from"] = artifact_id
        copy_meta["copy_timestamp"] = datetime.utcnow().isoformat() + "Z"

        # Store the copy in the same session
        return await self.store(
            data=original_data,
            mime=original_meta.mime,
            summary=copy_summary,
            filename=copy_filename,
            session_id=original_session,  # Always same session
            meta=copy_meta,
        )

    async def move_file(
        self,
        artifact_id: str,
        *,
        new_filename: str = None,
        new_session_id: str = None,
        new_meta: Dict[str, Any] = None,
    ) -> ArtifactMetadata:
        """Move/rename a file WITHIN THE SAME SESSION only (security enforced)."""
        # Get current metadata
        record = await self.metadata(artifact_id)
        current_session = record.session_id

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
            record.filename = new_filename
        if new_meta:
            record.meta.update(new_meta)

        return record

    # ─────────────────────────────────────────────────────────────────
    # Presigned URL operations
    # ─────────────────────────────────────────────────────────────────

    async def presign(
        self, artifact_id: str, expires: int = _DEFAULT_PRESIGN_EXPIRES
    ) -> str:
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
        expires: int = _DEFAULT_PRESIGN_EXPIRES,
    ) -> tuple[str, str]:
        """Generate a presigned URL for uploading a new artifact."""
        return await self._presigned.presign_upload(
            session_id, filename, mime_type, expires
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
        expires: int = _DEFAULT_PRESIGN_EXPIRES,
    ) -> tuple[str, str]:
        """Convenience method combining presign_upload and pre-register metadata."""
        return await self._presigned.presign_upload_and_register(
            mime=mime,
            summary=summary,
            meta=meta,
            filename=filename,
            session_id=session_id,
            ttl=ttl,
            expires=expires,
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
        **kwargs,
    ) -> Dict[str, Any]:
        """Update artifact metadata."""
        return await self._metadata.update_metadata(
            artifact_id, summary=summary, meta=meta, merge=merge, **kwargs
        )

    async def extend_ttl(
        self, artifact_id: str, additional_seconds: int
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
        stats = await self._admin.get_stats()

        # Add session manager stats
        session_stats = self._session_manager.get_cache_stats()
        stats["session_manager"] = session_stats

        return stats

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
                clean_id = "".join(c for c in candidate if c.isalnum() or c in "-_")[
                    :32
                ]
                if clean_id:
                    return clean_id

        # Generate fallback
        return f"sandbox-{uuid.uuid4().hex[:8]}"

    def _load_storage_provider(self, name: str) -> Callable[[], AsyncContextManager]:
        """Load storage provider."""
        from .provider_factory import factory_for_env
        from importlib import import_module
        import os

        # Temporarily set the provider name in environment
        # so factory_for_env can pick it up
        original_provider = os.environ.get("ARTIFACT_PROVIDER")
        try:
            os.environ["ARTIFACT_PROVIDER"] = name
            return factory_for_env()
        except ValueError:
            # If factory_for_env doesn't recognize it, try direct import
            try:
                mod = import_module(f"chuk_artifacts.providers.{name}")
                return mod.factory()
            except ModuleNotFoundError as exc:
                available = [
                    "memory",
                    "filesystem",
                    "s3",
                    "ibm_cos",
                    "vfs",
                    "vfs-memory",
                    "vfs-filesystem",
                    "vfs-s3",
                    "vfs-sqlite",
                ]
                raise ValueError(
                    f"Unknown storage provider '{name}'. Available: {', '.join(available)}"
                ) from exc
        finally:
            # Restore original environment
            if original_provider is not None:
                os.environ["ARTIFACT_PROVIDER"] = original_provider
            else:
                os.environ.pop("ARTIFACT_PROVIDER", None)

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

    async def get_sandbox_info(self) -> Dict[str, Any]:
        """
        Get sandbox information and metadata.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing sandbox information including:
            - sandbox_id: The current sandbox identifier
            - bucket: The storage bucket name
            - storage_provider: The storage provider type
            - session_provider: The session provider type
            - session_ttl_hours: Default session TTL
            - grid_prefix_pattern: The grid path pattern for this sandbox
            - created_at: Timestamp of when this info was retrieved
        """
        from datetime import datetime

        # Get session manager stats if available
        session_stats = {}
        try:
            session_stats = self._session_manager.get_cache_stats()
        except Exception:
            pass  # Session manager might not have stats

        # Get storage stats if available
        storage_stats = {}
        try:
            storage_stats = await self._admin.get_stats()
        except Exception:
            pass  # Storage might not have stats

        return {
            "sandbox_id": self.sandbox_id,
            "bucket": self.bucket,
            "storage_provider": self._storage_provider_name,
            "session_provider": self._session_provider_name,
            "session_ttl_hours": self.session_ttl_hours,
            "max_retries": self.max_retries,
            "grid_prefix_pattern": self.get_session_prefix_pattern(),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "session_stats": session_stats,
            "storage_stats": storage_stats,
            "closed": self._closed,
        }

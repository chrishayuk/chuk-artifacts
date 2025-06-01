# -*- coding: utf-8 -*-
# chuk_artifacts/presigned.py
"""
Presigned URL operations: download URLs, upload URLs, and upload registration.
Now uses chuk_sessions for session management.
"""

from __future__ import annotations

import uuid, time, logging, json
from datetime import datetime
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .store import ArtifactStore

from .exceptions import (
    ArtifactStoreError, ArtifactNotFoundError, ArtifactExpiredError, 
    ProviderError, SessionError
)

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 900
_DEFAULT_PRESIGN_EXPIRES = 3600


class PresignedURLOperations:
    """Handles all presigned URL operations."""

    def __init__(self, artifact_store: 'ArtifactStore'):
        self.artifact_store = artifact_store

    async def presign(self, artifact_id: str, expires: int = _DEFAULT_PRESIGN_EXPIRES) -> str:
        """Generate a presigned URL for artifact download."""
        if self.artifact_store._closed:
            raise ArtifactStoreError("Store is closed")
        
        start_time = time.time()
        
        try:
            record = await self._get_record(artifact_id)
            
            storage_ctx_mgr = self.artifact_store._s3_factory()
            async with storage_ctx_mgr as s3:
                url = await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.artifact_store.bucket, "Key": record["key"]},
                    ExpiresIn=expires,
                )
                
                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    "Presigned URL generated",
                    extra={
                        "artifact_id": artifact_id,
                        "expires_in": expires,
                        "duration_ms": duration_ms,
                    }
                )
                
                return url
                
        except (ArtifactNotFoundError, ArtifactExpiredError):
            raise
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Presigned URL generation failed",
                extra={
                    "artifact_id": artifact_id,
                    "error": str(e),
                    "duration_ms": duration_ms,
                }
            )
            
            if "oauth" in str(e).lower() or "credential" in str(e).lower():
                raise NotImplementedError(
                    "This provider cannot generate presigned URLs with the "
                    "current credential type (e.g. OAuth). Use HMAC creds instead."
                ) from e
            else:
                raise ProviderError(f"Presigned URL generation failed: {e}") from e

    async def presign_short(self, artifact_id: str) -> str:
        """Generate a short-lived presigned URL (15 minutes)."""
        return await self.presign(artifact_id, expires=900)
    
    async def presign_medium(self, artifact_id: str) -> str:
        """Generate a medium-lived presigned URL (1 hour)."""
        return await self.presign(artifact_id, expires=3600)
    
    async def presign_long(self, artifact_id: str) -> str:
        """Generate a long-lived presigned URL (24 hours)."""
        return await self.presign(artifact_id, expires=86400)

    async def presign_upload(
        self, 
        session_id: str | None = None,
        filename: str | None = None,
        mime_type: str = "application/octet-stream",
        expires: int = _DEFAULT_PRESIGN_EXPIRES
    ) -> tuple[str, str]:
        """Generate a presigned URL for uploading a new artifact."""
        if self.artifact_store._closed:
            raise ArtifactStoreError("Store is closed")
        
        start_time = time.time()
        
        # Ensure session is allocated using chuk_sessions
        if session_id is None:
            session_id = await self.artifact_store._session_manager.allocate_session()
        else:
            session_id = await self.artifact_store._session_manager.allocate_session(session_id=session_id)
        
        # Generate artifact ID and key path
        artifact_id = uuid.uuid4().hex
        key = self.artifact_store.generate_artifact_key(session_id, artifact_id)
        
        try:
            storage_ctx_mgr = self.artifact_store._s3_factory()
            async with storage_ctx_mgr as s3:
                url = await s3.generate_presigned_url(
                    "put_object",
                    Params={
                        "Bucket": self.artifact_store.bucket, 
                        "Key": key,
                        "ContentType": mime_type
                    },
                    ExpiresIn=expires,
                )
                
                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    "Upload presigned URL generated",
                    extra={
                        "artifact_id": artifact_id,
                        "key": key,
                        "mime_type": mime_type,
                        "expires_in": expires,
                        "duration_ms": duration_ms,
                    }
                )
                
                return url, artifact_id
                
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Upload presigned URL generation failed",
                extra={
                    "artifact_id": artifact_id,
                    "error": str(e),
                    "duration_ms": duration_ms,
                }
            )
            
            if "oauth" in str(e).lower() or "credential" in str(e).lower():
                raise NotImplementedError(
                    "This provider cannot generate presigned URLs with the "
                    "current credential type (e.g. OAuth). Use HMAC creds instead."
                ) from e
            else:
                raise ProviderError(f"Upload presigned URL generation failed: {e}") from e

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
        if self.artifact_store._closed:
            raise ArtifactStoreError("Store is closed")
        
        start_time = time.time()
        
        # Ensure session is allocated using chuk_sessions
        if session_id is None:
            session_id = await self.artifact_store._session_manager.allocate_session()
        else:
            session_id = await self.artifact_store._session_manager.allocate_session(session_id=session_id)
        
        # Reconstruct the key path
        key = self.artifact_store.generate_artifact_key(session_id, artifact_id)
        
        try:
            # Verify the object exists and get its size
            storage_ctx_mgr = self.artifact_store._s3_factory()
            async with storage_ctx_mgr as s3:
                try:
                    response = await s3.head_object(Bucket=self.artifact_store.bucket, Key=key)
                    file_size = response.get('ContentLength', 0)
                except Exception:
                    logger.warning(f"Artifact {artifact_id} not found in storage")
                    return False
            
            # Build metadata record
            record = {
                "artifact_id": artifact_id,
                "session_id": session_id,
                "sandbox_id": self.artifact_store.sandbox_id,
                "key": key,
                "mime": mime,
                "summary": summary,
                "meta": meta or {},
                "filename": filename,
                "bytes": file_size,
                "sha256": None,  # We don't have the hash since we didn't upload it directly
                "stored_at": datetime.utcnow().isoformat() + "Z",
                "ttl": ttl,
                "storage_provider": self.artifact_store._storage_provider_name,
                "session_provider": self.artifact_store._session_provider_name,
                "uploaded_via_presigned": True,  # Flag to indicate upload method
            }

            # Cache metadata using session provider
            session_ctx_mgr = self.artifact_store._session_factory()
            async with session_ctx_mgr as session:
                await session.setex(artifact_id, ttl, json.dumps(record))

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "Artifact metadata registered after presigned upload",
                extra={
                    "artifact_id": artifact_id,
                    "bytes": file_size,
                    "mime": mime,
                    "duration_ms": duration_ms,
                }
            )

            return True

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Artifact metadata registration failed",
                extra={
                    "artifact_id": artifact_id,
                    "error": str(e),
                    "duration_ms": duration_ms,
                }
            )
            
            if "session" in str(e).lower() or "redis" in str(e).lower():
                raise SessionError(f"Metadata registration failed: {e}") from e
            else:
                raise ProviderError(f"Metadata registration failed: {e}") from e

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
        # Generate presigned URL
        upload_url, artifact_id = await self.presign_upload(
            session_id=session_id,
            filename=filename,
            mime_type=mime,
            expires=expires
        )
        
        # Pre-register metadata (with unknown file size)
        await self.register_uploaded_artifact(
            artifact_id,
            mime=mime,
            summary=summary,
            meta=meta,
            filename=filename,
            session_id=session_id,
            ttl=ttl
        )
        
        return upload_url, artifact_id

    async def _get_record(self, artifact_id: str) -> Dict[str, Any]:
        """Get artifact metadata record."""
        try:
            session_ctx_mgr = self.artifact_store._session_factory()
            async with session_ctx_mgr as session:
                raw = await session.get(artifact_id)
        except Exception as e:
            raise SessionError(f"Session error for {artifact_id}: {e}") from e
        
        if raw is None:
            raise ArtifactNotFoundError(f"Artifact {artifact_id} not found")
        
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ProviderError(f"Corrupted metadata for {artifact_id}") from e
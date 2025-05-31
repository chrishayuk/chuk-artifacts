# -*- coding: utf-8 -*-
# chuk_artifacts/core.py
"""
Core storage operations: store, retrieve, and related helpers.
"""

from __future__ import annotations

import uuid, hashlib, time, asyncio, logging, json
from datetime import datetime
from typing import Any, Dict, Optional

from .base import BaseOperations
from .exceptions import (
    ArtifactStoreError, ArtifactNotFoundError, ArtifactExpiredError, 
    ArtifactCorruptedError, ProviderError, SessionError
)

logger = logging.getLogger(__name__)

_ANON_PREFIX = "anon"
_DEFAULT_TTL = 900


class CoreStorageOperations(BaseOperations):
    """Handles core storage operations: store and retrieve."""

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
        self._check_closed()
        
        start_time = time.time()
        artifact_id = uuid.uuid4().hex
        
        scope = session_id or f"{_ANON_PREFIX}_{artifact_id}"
        key = f"sess/{scope}/{artifact_id}"

        try:
            # Store in object storage with retries
            await self._store_with_retry(data, key, mime, filename, scope)

            # Build metadata record
            record = {
                "scope": scope,
                "key": key,
                "mime": mime,
                "summary": summary,
                "meta": meta or {},
                "filename": filename,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "stored_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "ttl": ttl,
                "storage_provider": self.storage_provider_name,
                "session_provider": self.session_provider_name,
            }

            # Cache metadata using session provider
            session_ctx_mgr = self.session_factory()
            async with session_ctx_mgr as session:
                await session.setex(artifact_id, ttl, json.dumps(record))

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "Artifact stored successfully",
                extra={
                    "artifact_id": artifact_id,
                    "bytes": len(data),
                    "mime": mime,
                    "duration_ms": duration_ms,
                    "storage_provider": self.storage_provider_name,
                }
            )

            return artifact_id

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Artifact storage failed",
                extra={
                    "artifact_id": artifact_id,
                    "error": str(e),
                    "duration_ms": duration_ms,
                    "storage_provider": self.storage_provider_name,
                },
                exc_info=True
            )
            
            if "session" in str(e).lower() or "redis" in str(e).lower():
                raise SessionError(f"Metadata caching failed: {e}") from e
            else:
                raise ProviderError(f"Storage operation failed: {e}") from e

    async def _store_with_retry(self, data: bytes, key: str, mime: str, filename: str, scope: str):
        """Store data with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                storage_ctx_mgr = self.s3_factory()
                async with storage_ctx_mgr as s3:
                    await s3.put_object(
                        Bucket=self.bucket,
                        Key=key,
                        Body=data,
                        ContentType=mime,
                        Metadata={"filename": filename or "", "scope": scope},
                    )
                return  # Success
                
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        f"Storage attempt {attempt + 1} failed, retrying in {wait_time}s",
                        extra={"error": str(e), "attempt": attempt + 1}
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All {self.max_retries} storage attempts failed")
        
        raise last_exception

    async def retrieve(self, artifact_id: str) -> bytes:
        """Retrieve artifact data directly."""
        self._check_closed()
        
        start_time = time.time()
        
        try:
            record = await self._get_record(artifact_id)
            
            storage_ctx_mgr = self.s3_factory()
            async with storage_ctx_mgr as s3:
                response = await s3.get_object(Bucket=self.bucket, Key=record["key"])
                
                # Handle different response formats from different providers
                if hasattr(response["Body"], "read"):
                    data = await response["Body"].read()
                elif isinstance(response["Body"], bytes):
                    data = response["Body"]
                else:
                    data = bytes(response["Body"])
                
                # Verify integrity if SHA256 is available
                if "sha256" in record and record["sha256"]:
                    computed_hash = hashlib.sha256(data).hexdigest()
                    if computed_hash != record["sha256"]:
                        raise ArtifactCorruptedError(
                            f"SHA256 mismatch: expected {record['sha256']}, got {computed_hash}"
                        )
                
                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    "Artifact retrieved successfully",
                    extra={
                        "artifact_id": artifact_id,
                        "bytes": len(data),
                        "duration_ms": duration_ms,
                    }
                )
                
                return data
                
        except (ArtifactNotFoundError, ArtifactExpiredError, ArtifactCorruptedError):
            raise
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Artifact retrieval failed",
                extra={
                    "artifact_id": artifact_id,
                    "error": str(e),
                    "duration_ms": duration_ms,
                }
            )
            raise ProviderError(f"Retrieval failed: {e}") from e
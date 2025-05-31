# ===========================================================================
# chuk_artifacts/batch.py - Batch operations
# ===========================================================================
"""
Batch operations for multiple artifacts.
"""

from __future__ import annotations

import uuid, hashlib, json, logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseOperations
from .exceptions import ArtifactStoreError

logger = logging.getLogger(__name__)

_ANON_PREFIX = "anon"
_DEFAULT_TTL = 900


class BatchOperations(BaseOperations):
    """Handles batch operations for multiple artifacts."""

    async def store_batch(
        self,
        items: List[Dict[str, Any]],
        session_id: str | None = None,
        ttl: int = _DEFAULT_TTL,
    ) -> List[str]:
        """Store multiple artifacts in a batch operation."""
        self._check_closed()
        
        artifact_ids = []
        failed_items = []
        
        for i, item in enumerate(items):
            try:
                artifact_id = uuid.uuid4().hex
                scope = session_id or f"{_ANON_PREFIX}_{artifact_id}"
                key = f"sess/{scope}/{artifact_id}"
                
                # Store in object storage
                await self._store_with_retry(
                    item["data"], key, item["mime"], 
                    item.get("filename"), scope
                )
                
                # Prepare metadata record
                record = {
                    "scope": scope,
                    "key": key,
                    "mime": item["mime"],
                    "summary": item["summary"],
                    "meta": item.get("meta", {}),
                    "filename": item.get("filename"),
                    "bytes": len(item["data"]),
                    "sha256": hashlib.sha256(item["data"]).hexdigest(),
                    "stored_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    "ttl": ttl,
                    "storage_provider": self.storage_provider_name,
                    "session_provider": self.session_provider_name,
                }
                
                # Store metadata via session provider
                session_ctx_mgr = self.session_factory()
                async with session_ctx_mgr as session:
                    await session.setex(artifact_id, ttl, json.dumps(record))
                
                artifact_ids.append(artifact_id)
                
            except Exception as e:
                logger.error(f"Batch item {i} failed: {e}")
                failed_items.append(i)
                artifact_ids.append(None)  # Placeholder
        
        if failed_items:
            logger.warning(f"Batch operation completed with {len(failed_items)} failures")
        
        return artifact_ids

    async def _store_with_retry(self, data: bytes, key: str, mime: str, filename: str, scope: str):
        """Store data with retry logic (copied from core for batch operations)."""
        import asyncio
        
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
                        f"Batch storage attempt {attempt + 1} failed, retrying in {wait_time}s",
                        extra={"error": str(e), "attempt": attempt + 1}
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All {self.max_retries} batch storage attempts failed")
        
        raise last_exception


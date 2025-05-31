# -*- coding: utf-8 -*-
# chuk_artifacts/metadata.py
"""
Metadata operations: exists, metadata retrieval, and deletion.
"""

from __future__ import annotations

import logging, json
from datetime import datetime
from typing import Any, Dict, List

from .base import BaseOperations
from .exceptions import (
    ArtifactStoreError, ArtifactNotFoundError, ArtifactExpiredError, 
    ProviderError
)

logger = logging.getLogger(__name__)


class MetadataOperations(BaseOperations):
    """Handles metadata-related operations."""

    async def metadata(self, artifact_id: str) -> Dict[str, Any]:
        """
        Get artifact metadata.
        
        Parameters
        ----------
        artifact_id : str
            The artifact identifier
            
        Returns
        -------
        dict
            Artifact metadata
            
        Raises
        ------
        ArtifactNotFoundError
            If artifact doesn't exist or has expired
        """
        return await self._get_record(artifact_id)

    async def exists(self, artifact_id: str) -> bool:
        """
        Check if artifact exists and hasn't expired.
        
        Parameters
        ----------
        artifact_id : str
            The artifact identifier
            
        Returns
        -------
        bool
            True if artifact exists, False otherwise
        """
        try:
            await self._get_record(artifact_id)
            return True
        except (ArtifactNotFoundError, ArtifactExpiredError):
            return False

    async def delete(self, artifact_id: str) -> bool:
        """
        Delete artifact and its metadata.
        
        Parameters
        ----------
        artifact_id : str
            The artifact identifier
            
        Returns
        -------
        bool
            True if deleted, False if not found
            
        Raises
        ------
        ProviderError
            If deletion fails
        """
        self._check_closed()
        
        try:
            record = await self._get_record(artifact_id)
            
            # Delete from object storage
            storage_ctx_mgr = self.s3_factory()
            async with storage_ctx_mgr as s3:
                await s3.delete_object(Bucket=self.bucket, Key=record["key"])
            
            # Delete metadata from session store
            session_ctx_mgr = self.session_factory()
            async with session_ctx_mgr as session:
                if hasattr(session, 'delete'):
                    await session.delete(artifact_id)
                else:
                    logger.warning(
                        "Session provider doesn't support delete operation",
                        extra={"artifact_id": artifact_id, "provider": self.session_provider_name}
                    )
            
            logger.info("Artifact deleted", extra={"artifact_id": artifact_id})
            return True
            
        except (ArtifactNotFoundError, ArtifactExpiredError):
            logger.warning("Attempted to delete non-existent artifact", extra={"artifact_id": artifact_id})
            return False
        except Exception as e:
            logger.error(
                "Artifact deletion failed",
                extra={"artifact_id": artifact_id, "error": str(e)}
            )
            raise ProviderError(f"Deletion failed: {e}") from e

    async def update_metadata(
        self, 
        artifact_id: str, 
        *,
        summary: str = None,
        meta: Dict[str, Any] = None,
        filename: str = None,
        ttl: int = None
    ) -> Dict[str, Any]:
        """
        Update artifact metadata without changing the stored data.
        
        Parameters
        ----------
        artifact_id : str
            The artifact identifier
        summary : str, optional
            New summary description
        meta : dict, optional
            New or additional metadata fields
        filename : str, optional
            New filename
        ttl : int, optional
            New TTL for metadata
            
        Returns
        -------
        dict
            Updated metadata record
            
        Raises
        ------
        ArtifactNotFoundError
            If artifact doesn't exist
        ProviderError
            If update fails
        """
        self._check_closed()
        
        try:
            # Get existing record
            record = await self._get_record(artifact_id)
            
            # Update fields if provided
            if summary is not None:
                record["summary"] = summary
            if meta is not None:
                # Merge with existing meta, allowing overwrites
                existing_meta = record.get("meta", {})
                existing_meta.update(meta)
                record["meta"] = existing_meta
            if filename is not None:
                record["filename"] = filename
            if ttl is not None:
                record["ttl"] = ttl
            
            # Update stored metadata
            record["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            
            session_ctx_mgr = self.session_factory()
            async with session_ctx_mgr as session:
                final_ttl = ttl or record.get("ttl", 900)  # Use provided TTL or existing/default
                await session.setex(artifact_id, final_ttl, json.dumps(record))
            
            logger.info(
                "Artifact metadata updated", 
                extra={"artifact_id": artifact_id, "updated_fields": list([
                    k for k, v in [
                        ("summary", summary), ("meta", meta), 
                        ("filename", filename), ("ttl", ttl)
                    ] if v is not None
                ])}
            )
            
            return record
            
        except (ArtifactNotFoundError, ArtifactExpiredError):
            raise
        except Exception as e:
            logger.error(
                "Metadata update failed",
                extra={"artifact_id": artifact_id, "error": str(e)}
            )
            raise ProviderError(f"Metadata update failed: {e}") from e

    async def extend_ttl(self, artifact_id: str, additional_seconds: int) -> Dict[str, Any]:
        """
        Extend the TTL of an artifact's metadata.
        
        Parameters
        ----------
        artifact_id : str
            The artifact identifier
        additional_seconds : int
            Additional seconds to add to the current TTL
            
        Returns
        -------
        dict
            Updated metadata record
            
        Raises
        ------
        ArtifactNotFoundError
            If artifact doesn't exist
        ProviderError
            If TTL extension fails
        """
        self._check_closed()
        
        try:
            # Get current record to find existing TTL
            record = await self._get_record(artifact_id)
            current_ttl = record.get("ttl", 900)
            new_ttl = current_ttl + additional_seconds
            
            # Update with extended TTL
            return await self.update_metadata(artifact_id, ttl=new_ttl)
            
        except (ArtifactNotFoundError, ArtifactExpiredError):
            raise
        except Exception as e:
            logger.error(
                "TTL extension failed",
                extra={
                    "artifact_id": artifact_id, 
                    "additional_seconds": additional_seconds,
                    "error": str(e)
                }
            )
            raise ProviderError(f"TTL extension failed: {e}") from e

    async def list_by_session(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        List artifacts for a specific session.
        
        Note: This is a basic implementation that would need to be enhanced
        with proper indexing for production use. Currently, this method
        cannot be efficiently implemented with the session provider abstraction
        since we don't have a way to query by session_id patterns.
        
        Parameters
        ----------
        session_id : str
            Session identifier to search for
        limit : int, optional
            Maximum number of artifacts to return
            
        Returns
        -------
        list
            List of metadata records for artifacts in the session
            
        Raises
        ------
        NotImplementedError
            This method requires additional indexing infrastructure
        """
        # This would require either:
        # 1. A separate index of session_id -> artifact_ids 
        # 2. Storage provider support for prefix queries
        # 3. Enhanced session provider with query capabilities
        
        raise NotImplementedError(
            "list_by_session requires additional indexing infrastructure. "
            "Consider implementing session-based indexing or using storage "
            "provider list operations if available."
        )
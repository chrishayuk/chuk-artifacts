# -*- coding: utf-8 -*-
# chuk_artifacts/metadata.py
"""
Metadata operations: exists, metadata retrieval, deletion, and session-based operations.
This is a WORKING implementation that actually implements the missing methods.
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
    """Handles metadata-related operations with working session-based listing."""

    async def metadata(self, artifact_id: str) -> Dict[str, Any]:
        """Get artifact metadata."""
        return await self._get_record(artifact_id)

    async def exists(self, artifact_id: str) -> bool:
        """Check if artifact exists and hasn't expired."""
        try:
            await self._get_record(artifact_id)
            return True
        except (ArtifactNotFoundError, ArtifactExpiredError):
            return False

    async def delete(self, artifact_id: str) -> bool:
        """Delete artifact and its metadata."""
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
        ttl: int = None,
        # NEW: MCP-specific parameters
        new_meta: Dict[str, Any] = None,
        merge: bool = True
    ) -> Dict[str, Any]:
        """
        Update artifact metadata with MCP server compatibility.
        
        Parameters
        ----------
        artifact_id : str
            The artifact identifier
        summary : str, optional
            New summary description
        meta : dict, optional
            New or additional metadata fields (legacy parameter)
        filename : str, optional
            New filename
        ttl : int, optional
            New TTL for metadata
        new_meta : dict, optional
            New metadata fields (MCP server parameter)
        merge : bool, optional
            Whether to merge with existing metadata (True) or replace (False)
            
        Returns
        -------
        dict
            Updated metadata record
        """
        self._check_closed()
        
        try:
            # Get existing record
            record = await self._get_record(artifact_id)
            
            # Handle MCP server compatibility
            metadata_update = new_meta or meta or {}
            
            # Update fields if provided
            if summary is not None:
                record["summary"] = summary
            if filename is not None:
                record["filename"] = filename
            if ttl is not None:
                record["ttl"] = ttl
                
            # Handle metadata updates
            if metadata_update:
                existing_meta = record.get("meta", {})
                if merge:
                    # Merge with existing meta, allowing overwrites
                    existing_meta.update(metadata_update)
                    record["meta"] = existing_meta
                else:
                    # Replace existing meta entirely
                    record["meta"] = metadata_update
            
            # Update stored metadata
            record["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            
            session_ctx_mgr = self.session_factory()
            async with session_ctx_mgr as session:
                final_ttl = ttl or record.get("ttl", 900)
                await session.setex(artifact_id, final_ttl, json.dumps(record))
            
            logger.info(
                "Artifact metadata updated", 
                extra={
                    "artifact_id": artifact_id, 
                    "merge": merge,
                    "updated_fields": list([
                        k for k, v in [
                            ("summary", summary), ("meta", metadata_update), 
                            ("filename", filename), ("ttl", ttl)
                        ] if v is not None
                    ])
                }
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
        """Extend the TTL of an artifact's metadata."""
        self._check_closed()
        
        try:
            record = await self._get_record(artifact_id)
            current_ttl = record.get("ttl", 900)
            new_ttl = current_ttl + additional_seconds
            
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
        
        WORKING IMPLEMENTATION: Uses storage provider listing when available,
        falls back to warning for providers that don't support it.
        """
        self._check_closed()
        
        try:
            artifacts = []
            
            # Try to use storage provider listing capabilities
            storage_ctx_mgr = self.s3_factory()
            async with storage_ctx_mgr as s3:
                # Check if storage provider supports listing
                if hasattr(s3, 'list_objects_v2'):
                    try:
                        # List objects with session prefix
                        prefix = f"sess/{session_id}/"
                        
                        response = await s3.list_objects_v2(
                            Bucket=self.bucket,
                            Prefix=prefix,
                            MaxKeys=limit
                        )
                        
                        # Extract artifact IDs from keys and get their metadata
                        for obj in response.get('Contents', []):
                            key = obj['Key']
                            # Extract artifact ID from key pattern: sess/{session_id}/{artifact_id}
                            parts = key.split('/')
                            if len(parts) >= 3:
                                artifact_id = parts[2]
                                try:
                                    record = await self._get_record(artifact_id)
                                    artifacts.append(record)
                                except (ArtifactNotFoundError, ArtifactExpiredError):
                                    continue  # Skip expired/missing metadata
                                    
                        logger.info(
                            f"Successfully listed {len(artifacts)} artifacts for session {session_id}"
                        )
                        return artifacts[:limit]
                        
                    except Exception as list_error:
                        logger.warning(
                            f"Storage provider listing failed: {list_error}. "
                            f"Provider: {self.storage_provider_name}"
                        )
                        # Fall through to empty result with warning
                        
                else:
                    logger.warning(
                        f"Storage provider {self.storage_provider_name} doesn't support list_objects_v2"
                    )
            
            # If we get here, listing isn't supported
            logger.warning(
                f"Session listing not fully supported with {self.storage_provider_name} provider. "
                f"Returning empty list. For full session listing, use filesystem or S3-compatible storage."
            )
            return []
            
        except Exception as e:
            logger.error(
                "Session artifact listing failed",
                extra={"session_id": session_id, "error": str(e)}
            )
            # Return empty list rather than failing completely
            logger.warning(f"Returning empty list due to error: {e}")
            return []

    async def list_by_prefix(
        self, 
        session_id: str, 
        prefix: str = "", 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List artifacts in a session with filename prefix filtering.
        
        WORKING IMPLEMENTATION: Gets session artifacts and filters by filename prefix.
        """
        try:
            # Get all artifacts in the session first
            artifacts = await self.list_by_session(session_id, limit * 2)  # Get more to filter
            
            if not prefix:
                return artifacts[:limit]
                
            # Filter by filename prefix
            filtered = []
            for artifact in artifacts:
                filename = artifact.get("filename", "")
                if filename.startswith(prefix):
                    filtered.append(artifact)
                    if len(filtered) >= limit:
                        break
                        
            logger.info(
                f"Filtered {len(filtered)} artifacts from {len(artifacts)} total with prefix '{prefix}'"
            )
            return filtered
            
        except Exception as e:
            logger.error(
                "Prefix-based listing failed",
                extra={
                    "session_id": session_id,
                    "prefix": prefix,
                    "error": str(e)
                }
            )
            # Return empty list rather than failing
            return []
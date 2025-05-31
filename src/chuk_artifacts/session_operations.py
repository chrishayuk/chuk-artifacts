# -*- coding: utf-8 -*-
# chuk_artifacts/session_operations.py (LOGGING FIX)
"""
Session-based file operations with strict session isolation.
FIXED: Resolved logging conflict with 'filename' parameter.
"""

from __future__ import annotations

import uuid, hashlib, json, logging
from datetime import datetime
from typing import Any, Dict, Optional, Union, List

from .base import BaseOperations
from .exceptions import (
    ArtifactStoreError, ArtifactNotFoundError, ArtifactExpiredError, 
    ProviderError, SessionError
)

logger = logging.getLogger(__name__)

_ANON_PREFIX = "anon"
_DEFAULT_TTL = 900


class SessionOperations(BaseOperations):
    """Session-based file operations with strict session isolation."""

    async def move_file(
        self,
        artifact_id: str,
        *,
        new_filename: str = None,
        new_session_id: str = None,
        new_meta: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Move a file within the SAME session or rename it.
        """
        self._check_closed()
        
        try:
            # Get current metadata
            record = await self._get_record(artifact_id)
            current_session = record.get("session_id")
            
            # STRICT SECURITY: Block ALL cross-session moves
            if new_session_id and new_session_id != current_session:
                raise ArtifactStoreError(
                    f"Cross-session moves are not permitted for security reasons. "
                    f"Artifact {artifact_id} belongs to session '{current_session}', "
                    f"cannot move to session '{new_session_id}'. Use copy operations within "
                    f"the same session only."
                )
            
            # Update metadata fields (only filename and meta allowed)
            updates = {}
            if new_filename:
                updates["filename"] = new_filename
            if new_meta:
                existing_meta = record.get("meta", {})
                existing_meta.update(new_meta)
                updates["new_meta"] = existing_meta
                updates["merge"] = True
            
            if updates:
                # Use the metadata operations to update
                from .metadata import MetadataOperations
                metadata_ops = MetadataOperations(self._artifact_store)
                return await metadata_ops.update_metadata(artifact_id, **updates)
            
            return record
            
        except (ArtifactNotFoundError, ArtifactExpiredError):
            raise
        except Exception as e:
            logger.error(
                "File move failed for artifact %s: %s",
                artifact_id,
                str(e),
                extra={
                    "artifact_id": artifact_id,
                    "new_file_name": new_filename,  # FIXED: Renamed from 'new_filename'
                    "new_session_id": new_session_id,
                    "operation": "move_file"
                }
            )
            raise ProviderError(f"Move operation failed: {e}") from e

    async def copy_file(
        self,
        artifact_id: str,
        *,
        new_filename: str = None,
        target_session_id: str = None,
        new_meta: Dict[str, Any] = None,
        summary: str = None
    ) -> str:
        """
        Copy a file WITHIN THE SAME SESSION only.
        """
        self._check_closed()
        
        try:
            # Get original metadata first to check session
            original_meta = await self._get_record(artifact_id)
            original_session = original_meta.get("session_id")
            
            # STRICT SECURITY: Block ALL cross-session copies
            if target_session_id and target_session_id != original_session:
                raise ArtifactStoreError(
                    f"Cross-session copies are not permitted for security reasons. "
                    f"Artifact {artifact_id} belongs to session '{original_session}', "
                    f"cannot copy to session '{target_session_id}'. Files can only be "
                    f"copied within the same session."
                )
            
            # Ensure target session is the same as source
            copy_session = original_session  # Always use source session
            
            # Get original data
            original_data = await self._retrieve_data(artifact_id)
            
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
            copy_meta["copy_timestamp"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            copy_meta["copy_within_session"] = original_session
            
            # Store the copy using core operations
            from .core import CoreStorageOperations
            core_ops = CoreStorageOperations(self._artifact_store)
            
            new_artifact_id = await core_ops.store(
                data=original_data,
                mime=original_meta["mime"],
                summary=copy_summary,
                filename=copy_filename,
                session_id=copy_session,  # Always same session
                meta=copy_meta
            )
            
            logger.info(
                "File copied within session: %s -> %s",
                artifact_id,
                new_artifact_id,
                extra={
                    "source_artifact_id": artifact_id,
                    "new_artifact_id": new_artifact_id,
                    "session": copy_session,
                    "security_level": "same_session_only",
                    "operation": "copy_file"
                }
            )
            
            return new_artifact_id
            
        except (ArtifactNotFoundError, ArtifactExpiredError):
            raise
        except Exception as e:
            logger.error(
                "File copy failed for artifact %s: %s",
                artifact_id,
                str(e),
                extra={
                    "artifact_id": artifact_id,
                    "new_file_name": new_filename,  # FIXED: Renamed from 'new_filename'
                    "target_session_id": target_session_id,
                    "operation": "copy_file"
                }
            )
            raise ProviderError(f"Copy operation failed: {e}") from e

    async def read_file(
        self,
        artifact_id: str,
        *,
        encoding: str = "utf-8",
        as_text: bool = True
    ) -> Union[str, bytes]:
        """
        Read file content directly.
        """
        self._check_closed()
        
        try:
            data = await self._retrieve_data(artifact_id)
            
            if as_text:
                try:
                    return data.decode(encoding)
                except UnicodeDecodeError as e:
                    logger.warning(f"Failed to decode with {encoding}: {e}")
                    raise ProviderError(f"Cannot decode file as text with {encoding} encoding") from e
            else:
                return data
                
        except (ArtifactNotFoundError, ArtifactExpiredError):
            raise
        except Exception as e:
            logger.error(
                "File read failed for artifact %s: %s",
                artifact_id,
                str(e),
                extra={"artifact_id": artifact_id, "operation": "read_file"}
            )
            raise ProviderError(f"Read operation failed: {e}") from e

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
        """
        Write content to a new file or overwrite existing WITHIN THE SAME SESSION.
        """
        self._check_closed()
        
        try:
            # Convert content to bytes if needed
            if isinstance(content, str):
                data = content.encode(encoding)
            else:
                data = content
            
            # Handle overwrite case with session security check
            if overwrite_artifact_id:
                try:
                    existing_meta = await self._get_record(overwrite_artifact_id)
                    existing_session = existing_meta.get("session_id")
                    
                    # STRICT SECURITY: Can only overwrite files in the same session
                    if session_id and session_id != existing_session:
                        raise ArtifactStoreError(
                            f"Cross-session overwrite not permitted. Artifact {overwrite_artifact_id} "
                            f"belongs to session '{existing_session}', cannot overwrite from "
                            f"session '{session_id}'. Overwrite operations must be within the same session."
                        )
                    
                    # Use the existing session if no session_id provided
                    session_id = session_id or existing_session
                    
                    # Delete old version (within same session)
                    from .metadata import MetadataOperations
                    metadata_ops = MetadataOperations(self._artifact_store)
                    await metadata_ops.delete(overwrite_artifact_id)
                    
                except (ArtifactNotFoundError, ArtifactExpiredError):
                    pass  # Original doesn't exist, proceed with new creation
            
            # Store new content using core operations
            from .core import CoreStorageOperations
            core_ops = CoreStorageOperations(self._artifact_store)
            
            write_meta = {**(meta or {})}
            if overwrite_artifact_id:
                write_meta["overwrote"] = overwrite_artifact_id
                write_meta["overwrite_timestamp"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
                write_meta["overwrite_within_session"] = session_id
            
            artifact_id = await core_ops.store(
                data=data,
                mime=mime,
                summary=summary or f"Written file: {filename}",
                filename=filename,
                session_id=session_id,
                meta=write_meta
            )
            
            # FIXED: Use separate variables for logging to avoid 'filename' conflict
            logger.info(
                "File written successfully: %s (artifact_id: %s)",
                filename,
                artifact_id,
                extra={
                    "artifact_id": artifact_id,
                    "file_name": filename,  # FIXED: Renamed from 'filename'
                    "bytes": len(data),
                    "overwrite": bool(overwrite_artifact_id),
                    "session_id": session_id,
                    "security_level": "session_isolated",
                    "operation": "write_file"
                }
            )
            
            return artifact_id
            
        except Exception as e:
            # FIXED: Use separate variables for logging to avoid 'filename' conflict
            logger.error(
                "File write failed for %s: %s",
                filename,
                str(e),
                extra={
                    "file_name": filename,  # FIXED: Renamed from 'filename'
                    "overwrite_artifact_id": overwrite_artifact_id,
                    "session_id": session_id,
                    "operation": "write_file"
                }
            )
            raise ProviderError(f"Write operation failed: {e}") from e

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
            from .metadata import MetadataOperations
            metadata_ops = MetadataOperations(self._artifact_store)
            return await metadata_ops.list_by_prefix(session_id, directory_prefix, limit)
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

    async def _retrieve_data(self, artifact_id: str) -> bytes:
        """Helper to retrieve artifact data using core operations."""
        from .core import CoreStorageOperations
        core_ops = CoreStorageOperations(self._artifact_store)
        return await core_ops.retrieve(artifact_id)

    # Session security validation helper
    async def _validate_session_access(self, artifact_id: str, expected_session_id: str = None) -> Dict[str, Any]:
        """
        Validate that an artifact belongs to the expected session.
        """
        record = await self._get_record(artifact_id)
        actual_session = record.get("session_id")
        
        if expected_session_id and actual_session != expected_session_id:
            raise ArtifactStoreError(
                f"Session access violation: Artifact {artifact_id} belongs to "
                f"session '{actual_session}', but access was attempted from "
                f"session '{expected_session_id}'. Cross-session access is not permitted."
            )
        
        return record
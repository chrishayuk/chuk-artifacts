# -*- coding: utf-8 -*-
# chuk_artifacts/base.py
"""
base class for operation modules
"""

from __future__ import annotations
import json, logging
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .store import ArtifactStore

from .exceptions import ArtifactNotFoundError, ArtifactCorruptedError, SessionError, ArtifactStoreError

logger = logging.getLogger(__name__)


class BaseOperations:
    """Fixed base class for all operation modules."""
    
    def __init__(self, store: 'ArtifactStore'):
        # FIXED: Renamed from self.store to self._artifact_store to avoid method name conflicts
        self._artifact_store = store
    
    @property
    def bucket(self) -> str:
        return self._artifact_store.bucket
    
    @property
    def s3_factory(self):
        return self._artifact_store._s3_factory
    
    @property
    def session_factory(self):
        return self._artifact_store._session_factory
    
    @property
    def storage_provider_name(self) -> str:
        return self._artifact_store._storage_provider_name
    
    @property
    def session_provider_name(self) -> str:
        return self._artifact_store._session_provider_name
    
    @property
    def max_retries(self) -> int:
        return self._artifact_store.max_retries
    
    def _check_closed(self):
        """Check if store is closed and raise error if so."""
        if self._artifact_store._closed:
            raise ArtifactStoreError("Store has been closed")
    
    async def _get_record(self, artifact_id: str) -> Dict[str, Any]:
        """
        Retrieve artifact metadata from session provider.
        
        This is a shared helper used by multiple operation modules.
        """
        try:
            session_ctx_mgr = self.session_factory()
            async with session_ctx_mgr as session:
                raw = await session.get(artifact_id)
        except Exception as e:
            raise SessionError(f"Session provider error retrieving {artifact_id}: {e}") from e
        
        if raw is None:
            raise ArtifactNotFoundError(f"Artifact {artifact_id} not found or expired")
        
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted metadata for artifact {artifact_id}: {e}")
            raise ArtifactCorruptedError(f"Corrupted metadata for artifact {artifact_id}") from e
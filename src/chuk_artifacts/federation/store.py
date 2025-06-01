# -*- coding: utf-8 -*-
# chuk_artifacts/federation/store.py
"""
Federated ArtifactStore using chuk_sessions providers.

Extends the base ArtifactStore to provide transparent federation,
allowing artifacts to be retrieved from remote sandboxes while
using the same Redis/memory infrastructure as sessions.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union, Tuple

from ..store import ArtifactStore
from ..exceptions import ArtifactStoreError, ArtifactNotFoundError, ProviderError
from .manager import create_federation_manager, FederationManager

logger = logging.getLogger(__name__)


class FederatedArtifactStore(ArtifactStore):
    """
    ArtifactStore with federation capabilities using chuk_sessions providers.
    
    Provides transparent cross-sandbox access while maintaining all the
    security and session management of the base store. Uses the same
    Redis/memory infrastructure as chuk_sessions for the federation index.
    """
    
    def __init__(
        self,
        *,
        federation_enabled: bool = True,
        federation_ttl_days: int = 30,
        **kwargs
    ):
        super().__init__(**kwargs)
        
        self.federation_enabled = federation_enabled
        
        if federation_enabled:
            # Use same session provider as the store for federation index
            self._federation = create_federation_manager(
                sandbox_id=self.sandbox_id,
                session_factory=self._session_factory,  # Reuse session provider!
                federation_ttl_days=federation_ttl_days
            )
        else:
            self._federation = None
        
        logger.info(
            f"FederatedArtifactStore initialized with federation {'enabled' if federation_enabled else 'disabled'} "
            f"using {self._session_provider_name} provider"
        )
    
    # ─────────────────────────────────────────────────────────────────
    # Enhanced core operations with federation
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
        ttl: int = 900,
    ) -> str:
        """Store artifact with automatic federation registration."""
        # Store locally using parent method
        artifact_id = await super().store(
            data=data,
            mime=mime,
            summary=summary,
            meta=meta,
            filename=filename,
            session_id=session_id,
            user_id=user_id,
            ttl=ttl
        )
        
        # Register in federation if enabled
        if self.federation_enabled and self._federation:
            try:
                # Get the metadata to register
                metadata = await self.metadata(artifact_id)
                actual_session_id = metadata["session_id"]
                grid_key = metadata["key"]
                
                await self._federation.register_artifact(
                    artifact_id=artifact_id,
                    session_id=actual_session_id,
                    grid_key=grid_key,
                    size=len(data),
                    mime=mime,
                    checksum=metadata.get("sha256")
                )
                
                logger.debug(f"Registered artifact {artifact_id} in federation")
                
            except Exception as e:
                logger.error(f"Failed to register artifact in federation: {e}")
                # Don't fail the store operation due to federation issues
        
        return artifact_id
    
    async def retrieve(self, artifact_id: str) -> bytes:
        """Retrieve artifact with federation fallback."""
        try:
            # Try local first (fastest path)
            return await super().retrieve(artifact_id)
            
        except ArtifactNotFoundError:
            # Fall back to federation if enabled
            if self.federation_enabled and self._federation:
                return await self._retrieve_federated(artifact_id)
            else:
                raise
    
    async def _retrieve_federated(self, artifact_id: str) -> bytes:
        """Retrieve artifact from remote sandbox via federation."""
        # Find artifact location
        location = await self._federation.get_artifact_location(artifact_id)
        
        if not location:
            raise ArtifactNotFoundError(f"Artifact {artifact_id} not found in federation")
        
        if location.sandbox_id == self.sandbox_id:
            # Should be local but wasn't found - data inconsistency
            logger.warning(f"Artifact {artifact_id} registered locally but not found")
            raise ArtifactNotFoundError(f"Local artifact {artifact_id} missing")
        
        # For this demo, we'll simulate remote retrieval
        # In production, this would involve:
        # 1. Request presigned URL from owning sandbox
        # 2. Stream data back to caller
        # 3. Optionally cache locally
        
        logger.info(f"Retrieving artifact {artifact_id} from remote sandbox {location.sandbox_id}")
        
        # Simulate remote data (in production, this would be actual remote fetch)
        remote_data = f"[Remote data from {location.sandbox_id}: {location.grid_key}]"
        return remote_data.encode()
    
    async def delete(self, artifact_id: str) -> bool:
        """Delete artifact and unregister from federation."""
        # Delete locally first
        success = await super().delete(artifact_id)
        
        # Unregister from federation if successful
        if success and self.federation_enabled and self._federation:
            try:
                await self._federation.unregister_artifact(artifact_id)
                logger.debug(f"Unregistered artifact {artifact_id} from federation")
            except Exception as e:
                logger.error(f"Failed to unregister artifact from federation: {e}")
                # Don't fail delete operation due to federation issues
        
        return success
    
    # ─────────────────────────────────────────────────────────────────
    # Federated session operations
    # ─────────────────────────────────────────────────────────────────
    
    async def list_session_federated(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """List artifacts in session across all sandboxes."""
        if not self.federation_enabled or not self._federation:
            # Fall back to local listing
            return await self.list_by_session(session_id, limit)
        
        try:
            # Get local artifacts
            local_artifacts = await self.list_by_session(session_id, limit)
            
            # Get federated view
            federated_locations = await self._federation.list_session_across_sandboxes(session_id)
            
            # Combine views, avoiding duplicates
            all_artifacts = []
            local_ids = {a["artifact_id"] for a in local_artifacts}
            
            # Add local artifacts (marked as local)
            for artifact in local_artifacts:
                artifact["federation_source"] = "local"
                artifact["federation_sandbox"] = self.sandbox_id
                all_artifacts.append(artifact)
            
            # Add remote artifacts
            for location in federated_locations:
                if location.artifact_id not in local_ids and location.sandbox_id != self.sandbox_id:
                    all_artifacts.append({
                        "artifact_id": location.artifact_id,
                        "sandbox_id": location.sandbox_id,
                        "session_id": location.session_id,
                        "key": location.grid_key,
                        "mime": location.mime,
                        "bytes": location.size,
                        "stored_at": location.stored_at,
                        "federation_source": "remote",
                        "federation_sandbox": location.sandbox_id,
                        "checksum": location.checksum
                    })
                    
                    if len(all_artifacts) >= limit:
                        break
            
            logger.debug(f"Listed {len(all_artifacts)} artifacts for session {session_id} (federated)")
            return all_artifacts[:limit]
            
        except Exception as e:
            logger.error(f"Federated session listing failed: {e}")
            # Fall back to local listing
            return await self.list_by_session(session_id, limit)
    
    async def get_session_distribution(self, session_id: str) -> Dict[str, List[str]]:
        """Get distribution of session artifacts across sandboxes."""
        if not self.federation_enabled or not self._federation:
            # Only local
            local_artifacts = await self.list_by_session(session_id)
            return {self.sandbox_id: [a["artifact_id"] for a in local_artifacts]}
        
        return await self._federation.get_session_distribution(session_id)
    
    async def find_session_home_sandbox(self, session_id: str) -> Optional[str]:
        """Find the primary sandbox for a session (most artifacts)."""
        if not self.federation_enabled or not self._federation:
            return self.sandbox_id
        
        return await self._federation.find_session_home_sandbox(session_id)
    
    # ─────────────────────────────────────────────────────────────────
    # Federation management operations
    # ─────────────────────────────────────────────────────────────────
    
    async def get_federation_stats(self) -> Dict[str, Any]:
        """Get comprehensive federation statistics."""
        if not self.federation_enabled or not self._federation:
            return {
                "federation_enabled": False,
                "current_sandbox": self.sandbox_id
            }
        
        stats = await self._federation.get_federation_stats()
        stats["federation_enabled"] = True
        stats["session_provider"] = self._session_provider_name
        return stats
    
    async def get_sandbox_artifacts(self, sandbox_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get all artifacts stored in a specific sandbox."""
        if not self.federation_enabled or not self._federation:
            if sandbox_id == self.sandbox_id:
                # Return local artifacts (limited way to get all local artifacts)
                # This is a simplified implementation
                return []
            else:
                return []
        
        locations = await self._federation.get_sandbox_artifacts(sandbox_id, limit)
        
        return [
            {
                "artifact_id": loc.artifact_id,
                "session_id": loc.session_id,
                "grid_key": loc.grid_key,
                "mime": loc.mime,
                "size": loc.size,
                "stored_at": loc.stored_at,
                "sandbox_id": loc.sandbox_id,
                "checksum": loc.checksum
            }
            for loc in locations
        ]
    
    async def locate_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """Find which sandbox contains an artifact."""
        if not self.federation_enabled or not self._federation:
            # Check local only
            try:
                await self.metadata(artifact_id)
                return {"sandbox_id": self.sandbox_id, "source": "local"}
            except:
                return None
        
        location = await self._federation.get_artifact_location(artifact_id)
        if location:
            return {
                "sandbox_id": location.sandbox_id,
                "session_id": location.session_id,
                "grid_key": location.grid_key,
                "size": location.size,
                "mime": location.mime,
                "stored_at": location.stored_at,
                "source": "local" if location.sandbox_id == self.sandbox_id else "remote"
            }
        
        return None
    
    # ─────────────────────────────────────────────────────────────────
    # Enhanced admin operations
    # ─────────────────────────────────────────────────────────────────
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics including federation info."""
        base_stats = await super().get_stats()
        
        if self.federation_enabled and self._federation:
            federation_stats = await self._federation.get_cache_stats()
            base_stats["federation"] = federation_stats
        else:
            base_stats["federation"] = {"enabled": False}
        
        return base_stats
    
    async def validate_configuration(self) -> Dict[str, Any]:
        """Validate store configuration including federation."""
        results = await super().validate_configuration()
        
        if self.federation_enabled and self._federation:
            try:
                # Test federation index
                test_stats = await self._federation.get_federation_stats()
                results["federation"] = {
                    "status": "ok",
                    "provider": self._session_provider_name,
                    "stats": test_stats
                }
            except Exception as e:
                results["federation"] = {
                    "status": "error",
                    "message": str(e),
                    "provider": self._session_provider_name
                }
        else:
            results["federation"] = {
                "status": "disabled"
            }
        
        return results
    
    # ─────────────────────────────────────────────────────────────────
    # Convenience methods
    # ─────────────────────────────────────────────────────────────────
    
    def is_federation_enabled(self) -> bool:
        """Check if federation is enabled."""
        return self.federation_enabled and self._federation is not None
    
    def get_federation_manager(self) -> Optional[FederationManager]:
        """Get the federation manager (for advanced operations)."""
        return self._federation if self.federation_enabled else None
    
    async def ping_federation(self) -> bool:
        """Test federation connectivity."""
        if not self.federation_enabled or not self._federation:
            return False
        
        try:
            await self._federation.get_federation_stats()
            return True
        except Exception:
            return False


# ─────────────────────────────────────────────────────────────────
# Factory functions
# ─────────────────────────────────────────────────────────────────

def create_federated_store(**kwargs) -> FederatedArtifactStore:
    """
    Create a FederatedArtifactStore with sensible defaults.
    
    Uses the same configuration system as regular ArtifactStore,
    but enables federation by default.
    """
    return FederatedArtifactStore(federation_enabled=True, **kwargs)


def create_local_store(**kwargs) -> FederatedArtifactStore:
    """
    Create a FederatedArtifactStore with federation disabled.
    
    Equivalent to regular ArtifactStore but with federation capability
    that can be enabled later.
    """
    return FederatedArtifactStore(federation_enabled=False, **kwargs)
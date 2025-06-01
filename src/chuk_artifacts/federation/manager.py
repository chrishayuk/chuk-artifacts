# -*- coding: utf-8 -*-
# chuk_artifacts/federation/manager.py
"""
Federation Manager using chuk_sessions providers for storage.

Leverages the robust session provider infrastructure from chuk_sessions
to store federation index data, providing consistent Redis/memory backends
with the same configuration and reliability.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncContextManager, Callable
from dataclasses import dataclass, asdict

# Use chuk_sessions providers for federation storage
from chuk_sessions.provider_factory import factory_for_env as session_factory_for_env

logger = logging.getLogger(__name__)


@dataclass
class ArtifactLocation:
    """Represents the location and metadata of an artifact in the federation."""
    artifact_id: str
    sandbox_id: str
    session_id: str
    grid_key: str
    size: int
    mime: str
    stored_at: str
    checksum: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ArtifactLocation':
        return cls(**data)


class FederationIndex:
    """
    Federation index using chuk_sessions providers for storage.
    
    Uses the same Redis/memory infrastructure as sessions but with
    federation-specific key patterns and TTLs.
    """
    
    def __init__(
        self,
        session_factory: Optional[Callable[[], AsyncContextManager]] = None,
        ttl_seconds: int = 86400 * 30  # 30 days default
    ):
        self.session_factory = session_factory or session_factory_for_env()
        self.ttl_seconds = ttl_seconds
    
    def _artifact_key(self, artifact_id: str) -> str:
        """Generate key for artifact location storage."""
        return f"federation:artifact:{artifact_id}"
    
    def _session_key(self, session_id: str) -> str:
        """Generate key for session artifact list."""
        return f"federation:session:{session_id}"
    
    def _sandbox_key(self, sandbox_id: str) -> str:
        """Generate key for sandbox artifact list.""" 
        return f"federation:sandbox:{sandbox_id}"
    
    def _stats_key(self) -> str:
        """Generate key for federation statistics."""
        return "federation:stats"
    
    async def register_artifact(self, location: ArtifactLocation) -> None:
        """Register an artifact location using session provider."""
        async with self.session_factory() as session:
            # Store main location record
            artifact_key = self._artifact_key(location.artifact_id)
            await session.setex(
                artifact_key, 
                self.ttl_seconds, 
                json.dumps(location.to_dict())
            )
            
            # Add to session index (using sets if supported, otherwise JSON lists)
            session_key = self._session_key(location.session_id)
            try:
                # Try set-based storage (Redis supports this)
                if hasattr(session, 'sadd'):
                    await session.sadd(session_key, location.artifact_id)
                    await session.expire(session_key, self.ttl_seconds)
                else:
                    # Fall back to JSON list storage (memory provider)
                    await self._add_to_json_set(session, session_key, location.artifact_id)
            except Exception as e:
                logger.warning(f"Failed to update session index: {e}")
            
            # Add to sandbox index
            sandbox_key = self._sandbox_key(location.sandbox_id)
            try:
                if hasattr(session, 'sadd'):
                    await session.sadd(sandbox_key, location.artifact_id)
                    await session.expire(sandbox_key, self.ttl_seconds)
                else:
                    await self._add_to_json_set(session, sandbox_key, location.artifact_id)
            except Exception as e:
                logger.warning(f"Failed to update sandbox index: {e}")
            
            # Update stats
            await self._update_stats(session, "artifacts_registered", 1)
        
        logger.debug(f"Registered artifact {location.artifact_id} in federation")
    
    async def _add_to_json_set(self, session, key: str, value: str) -> None:
        """Add value to a JSON-stored set (for providers without native sets)."""
        try:
            existing = await session.get(key)
            if existing:
                items = set(json.loads(existing))
            else:
                items = set()
            
            items.add(value)
            await session.setex(key, self.ttl_seconds, json.dumps(list(items)))
            
        except (json.JSONDecodeError, TypeError):
            # Start fresh if corrupted
            await session.setex(key, self.ttl_seconds, json.dumps([value]))
    
    async def _remove_from_json_set(self, session, key: str, value: str) -> None:
        """Remove value from a JSON-stored set."""
        try:
            existing = await session.get(key)
            if existing:
                items = set(json.loads(existing))
                items.discard(value)
                
                if items:
                    await session.setex(key, self.ttl_seconds, json.dumps(list(items)))
                else:
                    # Delete empty sets
                    if hasattr(session, 'delete'):
                        await session.delete(key)
        except (json.JSONDecodeError, TypeError):
            pass  # Ignore corrupted data
    
    async def _get_json_set(self, session, key: str) -> List[str]:
        """Get items from a JSON-stored set."""
        try:
            existing = await session.get(key)
            if existing:
                return json.loads(existing)
        except (json.JSONDecodeError, TypeError):
            pass
        return []
    
    async def locate_artifact(self, artifact_id: str) -> Optional[ArtifactLocation]:
        """Find the location of an artifact."""
        async with self.session_factory() as session:
            artifact_key = self._artifact_key(artifact_id)
            data = await session.get(artifact_key)
            
            if data:
                try:
                    location_dict = json.loads(data)
                    return ArtifactLocation.from_dict(location_dict)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Failed to decode artifact location {artifact_id}: {e}")
            
            return None
    
    async def unregister_artifact(self, artifact_id: str) -> bool:
        """Remove an artifact from the federation index."""
        async with self.session_factory() as session:
            # Get location first
            artifact_key = self._artifact_key(artifact_id)
            data = await session.get(artifact_key)
            
            if not data:
                return False
            
            try:
                location_dict = json.loads(data)
                location = ArtifactLocation.from_dict(location_dict)
            except (json.JSONDecodeError, TypeError):
                return False
            
            # Remove main record
            if hasattr(session, 'delete'):
                await session.delete(artifact_key)
            
            # Remove from session index
            session_key = self._session_key(location.session_id)
            if hasattr(session, 'srem'):
                await session.srem(session_key, artifact_id)
            else:
                await self._remove_from_json_set(session, session_key, artifact_id)
            
            # Remove from sandbox index
            sandbox_key = self._sandbox_key(location.sandbox_id)
            if hasattr(session, 'srem'):
                await session.srem(sandbox_key, artifact_id)
            else:
                await self._remove_from_json_set(session, sandbox_key, artifact_id)
            
            # Update stats
            await self._update_stats(session, "artifacts_unregistered", 1)
            
            return True
    
    async def list_session_locations(self, session_id: str) -> List[ArtifactLocation]:
        """List all artifact locations for a session."""
        async with self.session_factory() as session:
            session_key = self._session_key(session_id)
            
            # Get artifact IDs from session index
            if hasattr(session, 'smembers'):
                artifact_ids = await session.smembers(session_key)
            else:
                artifact_ids = await self._get_json_set(session, session_key)
            
            # Fetch full location data for each artifact
            locations = []
            for artifact_id in artifact_ids:
                location = await self.locate_artifact(artifact_id)
                if location:
                    locations.append(location)
            
            return locations
    
    async def get_sandbox_artifacts(self, sandbox_id: str, limit: int = 1000) -> List[ArtifactLocation]:
        """Get all artifacts stored in a specific sandbox."""
        async with self.session_factory() as session:
            sandbox_key = self._sandbox_key(sandbox_id)
            
            # Get artifact IDs from sandbox index
            if hasattr(session, 'smembers'):
                artifact_ids = await session.smembers(sandbox_key)
                artifact_ids = list(artifact_ids)[:limit]  # Apply limit
            else:
                all_ids = await self._get_json_set(session, sandbox_key)
                artifact_ids = all_ids[:limit]
            
            # Fetch full location data
            locations = []
            for artifact_id in artifact_ids:
                location = await self.locate_artifact(artifact_id)
                if location:
                    locations.append(location)
            
            return locations
    
    async def _update_stats(self, session, stat_name: str, increment: int = 1) -> None:
        """Update federation statistics."""
        try:
            stats_key = self._stats_key()
            existing = await session.get(stats_key)
            
            if existing:
                stats = json.loads(existing)
            else:
                stats = {"created_at": datetime.utcnow().isoformat() + "Z"}
            
            stats[stat_name] = stats.get(stat_name, 0) + increment
            stats["last_updated"] = datetime.utcnow().isoformat() + "Z"
            
            await session.setex(stats_key, self.ttl_seconds, json.dumps(stats))
            
        except Exception as e:
            logger.warning(f"Failed to update federation stats: {e}")
    
    async def get_federation_stats(self) -> Dict[str, Any]:
        """Get federation statistics."""
        async with self.session_factory() as session:
            # Get stored stats
            stats_key = self._stats_key()
            data = await session.get(stats_key)
            
            if data:
                try:
                    stats = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    stats = {}
            else:
                stats = {}
            
            # Add real-time counts if possible
            try:
                # Count artifacts (expensive for large datasets)
                if hasattr(session, 'keys'):
                    artifact_keys = await session.keys("federation:artifact:*")
                    stats["total_artifacts"] = len(artifact_keys)
                    
                    session_keys = await session.keys("federation:session:*")
                    stats["total_sessions"] = len(session_keys)
                    
                    sandbox_keys = await session.keys("federation:sandbox:*")
                    stats["total_sandboxes"] = len(sandbox_keys)
                
            except Exception as e:
                logger.warning(f"Failed to get real-time stats: {e}")
            
            stats["timestamp"] = datetime.utcnow().isoformat() + "Z"
            return stats


class FederationManager:
    """
    Manages artifact federation using chuk_sessions providers.
    
    Provides discovery, routing, and coordination for a distributed
    artifact storage system using the same infrastructure as sessions.
    """
    
    def __init__(
        self, 
        current_sandbox_id: str,
        session_factory: Optional[Callable[[], AsyncContextManager]] = None,
        federation_ttl_days: int = 30
    ):
        self.current_sandbox_id = current_sandbox_id
        self.index = FederationIndex(
            session_factory=session_factory,
            ttl_seconds=federation_ttl_days * 86400
        )
    
    async def register_artifact(
        self, 
        artifact_id: str,
        session_id: str,
        grid_key: str,
        size: int,
        mime: str,
        checksum: Optional[str] = None
    ) -> None:
        """Register a newly stored artifact in the federation."""
        location = ArtifactLocation(
            artifact_id=artifact_id,
            sandbox_id=self.current_sandbox_id,
            session_id=session_id,
            grid_key=grid_key,
            size=size,
            mime=mime,
            stored_at=datetime.utcnow().isoformat() + "Z",
            checksum=checksum
        )
        
        await self.index.register_artifact(location)
        logger.info(f"Registered artifact {artifact_id} in federation")
    
    async def locate_artifact(self, artifact_id: str) -> Optional[str]:
        """Find which sandbox contains an artifact."""
        location = await self.index.locate_artifact(artifact_id)
        return location.sandbox_id if location else None
    
    async def get_artifact_location(self, artifact_id: str) -> Optional[ArtifactLocation]:
        """Get full location information for an artifact."""
        return await self.index.locate_artifact(artifact_id)
    
    async def unregister_artifact(self, artifact_id: str) -> bool:
        """Remove an artifact from the federation (when deleted)."""
        success = await self.index.unregister_artifact(artifact_id)
        if success:
            logger.info(f"Unregistered artifact {artifact_id} from federation")
        return success
    
    async def list_session_across_sandboxes(self, session_id: str) -> List[ArtifactLocation]:
        """List all artifacts in a session across all sandboxes."""
        return await self.index.list_session_locations(session_id)
    
    async def get_session_distribution(self, session_id: str) -> Dict[str, List[str]]:
        """Get which sandboxes contain artifacts for a session."""
        locations = await self.list_session_across_sandboxes(session_id)
        
        distribution = {}
        for location in locations:
            if location.sandbox_id not in distribution:
                distribution[location.sandbox_id] = []
            distribution[location.sandbox_id].append(location.artifact_id)
        
        return distribution
    
    async def get_sandbox_artifacts(self, sandbox_id: str, limit: int = 1000) -> List[ArtifactLocation]:
        """Get all artifacts stored in a specific sandbox."""
        return await self.index.get_sandbox_artifacts(sandbox_id, limit)
    
    async def get_federation_stats(self) -> Dict[str, Any]:
        """Get comprehensive federation statistics."""
        base_stats = await self.index.get_federation_stats()
        base_stats["current_sandbox"] = self.current_sandbox_id
        return base_stats
    
    async def find_session_home_sandbox(self, session_id: str) -> Optional[str]:
        """Find the 'home' sandbox for a session (sandbox with most artifacts)."""
        distribution = await self.get_session_distribution(session_id)
        
        if not distribution:
            return None
        
        # Return sandbox with most artifacts
        return max(distribution.keys(), key=lambda s: len(distribution[s]))
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get federation cache statistics (compatible with session manager interface)."""
        stats = await self.get_federation_stats()
        return {
            "federation_artifacts": stats.get("total_artifacts", 0),
            "federation_sessions": stats.get("total_sessions", 0),
            "federation_sandboxes": stats.get("total_sandboxes", 0),
            "current_sandbox": self.current_sandbox_id,
        }


def create_federation_manager(
    sandbox_id: str,
    session_factory: Optional[Callable[[], AsyncContextManager]] = None,
    federation_ttl_days: int = 30
) -> FederationManager:
    """
    Factory function to create a FederationManager using chuk_sessions providers.
    
    Parameters
    ----------
    sandbox_id : str
        The current sandbox identifier
    session_factory : callable, optional
        Session provider factory (defaults to environment-based factory)
    federation_ttl_days : int
        How long to keep federation records (default 30 days)
        
    Returns
    -------
    FederationManager
        Configured federation manager using session providers
    """
    return FederationManager(
        current_sandbox_id=sandbox_id,
        session_factory=session_factory,
        federation_ttl_days=federation_ttl_days
    )
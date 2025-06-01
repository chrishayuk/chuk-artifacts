# -*- coding: utf-8 -*-
# chuk_artifacts//session_manager.py
"""
Clean session manager for grid architecture.

Simple rules:
- Always have a session (auto-allocate if needed)
- Grid paths: grid/{sandbox_id}/{session_id}/{artifact_id}
- No legacy compatibility, clean implementation
"""

from __future__ import annotations

import uuid
import time
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, AsyncContextManager, Callable
from dataclasses import dataclass, asdict

from ..exceptions import SessionError, ArtifactStoreError

logger = logging.getLogger(__name__)

_DEFAULT_SESSION_TTL_HOURS = 24


@dataclass
class SessionMetadata:
    """Session metadata for grid operations."""
    session_id: str
    sandbox_id: str
    user_id: Optional[str] = None
    created_at: str = None
    expires_at: str = None
    status: str = "active"
    artifact_count: int = 0
    total_bytes: int = 0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat() + "Z"
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        if not self.expires_at:
            return False
        expires = datetime.fromisoformat(self.expires_at.replace("Z", ""))
        return datetime.utcnow() > expires
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionMetadata':
        return cls(**data)


class SessionManager:
    """Simple session manager for grid architecture."""
    
    def __init__(
        self,
        sandbox_id: str,
        session_factory: Callable[[], AsyncContextManager],
        default_ttl_hours: int = _DEFAULT_SESSION_TTL_HOURS,
    ):
        self.sandbox_id = sandbox_id
        self.session_factory = session_factory
        self.default_ttl_hours = default_ttl_hours
        
        # Simple in-memory cache
        self._session_cache: Dict[str, SessionMetadata] = {}
        self._cache_lock = asyncio.Lock()
        
        logger.info(f"SessionManager initialized for sandbox: {sandbox_id}")
    
    async def allocate_session(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        ttl_hours: Optional[int] = None,
    ) -> str:
        """Allocate or validate a session."""
        ttl_hours = ttl_hours or self.default_ttl_hours
        
        if session_id:
            # Validate existing session
            metadata = await self._get_session_metadata(session_id)
            if metadata and not metadata.is_expired():
                await self._touch_session(session_id)
                return session_id
        
        # Create new session
        if not session_id:
            session_id = self._generate_session_id(user_id)
        
        expires_at = (datetime.utcnow() + timedelta(hours=ttl_hours)).isoformat() + "Z"
        
        metadata = SessionMetadata(
            session_id=session_id,
            sandbox_id=self.sandbox_id,
            user_id=user_id,
            expires_at=expires_at,
        )
        
        await self._store_session_metadata(metadata)
        
        async with self._cache_lock:
            self._session_cache[session_id] = metadata
        
        logger.info(f"Session allocated: {session_id} (user: {user_id})")
        return session_id
    
    async def validate_session(self, session_id: str) -> bool:
        """Check if session is valid."""
        try:
            metadata = await self._get_session_metadata(session_id)
            if metadata and not metadata.is_expired():
                await self._touch_session(session_id)
                return True
            return False
        except Exception:
            return False
    
    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information."""
        metadata = await self._get_session_metadata(session_id)
        return metadata.to_dict() if metadata else None
    
    def get_canonical_prefix(self, session_id: str) -> str:
        """Get grid path prefix."""
        return f"grid/{self.sandbox_id}/{session_id}/"
    
    def generate_artifact_key(self, session_id: str, artifact_id: str) -> str:
        """Generate grid artifact key."""
        return f"grid/{self.sandbox_id}/{session_id}/{artifact_id}"
    
    def _generate_session_id(self, user_id: Optional[str] = None) -> str:
        """Generate session ID."""
        timestamp = int(time.time())
        unique = uuid.uuid4().hex[:8]
        
        if user_id:
            safe_user = "".join(c for c in user_id if c.isalnum())[:8]
            return f"sess-{safe_user}-{timestamp}-{unique}"
        else:
            return f"sess-{timestamp}-{unique}"
    
    async def _get_session_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        """Get session metadata."""
        # Check cache
        async with self._cache_lock:
            if session_id in self._session_cache:
                return self._session_cache[session_id]
        
        # Query session provider
        try:
            session_ctx_mgr = self.session_factory()
            async with session_ctx_mgr as session:
                raw_data = await session.get(f"session:{session_id}")
                if raw_data:
                    data = json.loads(raw_data)
                    metadata = SessionMetadata.from_dict(data)
                    
                    # Cache it
                    async with self._cache_lock:
                        self._session_cache[session_id] = metadata
                    
                    return metadata
        except Exception as e:
            logger.warning(f"Failed to get session {session_id}: {e}")
        
        return None
    
    async def _store_session_metadata(self, metadata: SessionMetadata) -> None:
        """Store session metadata."""
        try:
            session_ctx_mgr = self.session_factory()
            async with session_ctx_mgr as session:
                key = f"session:{metadata.session_id}"
                ttl_seconds = int((datetime.fromisoformat(metadata.expires_at.replace("Z", "")) - datetime.utcnow()).total_seconds())
                data = json.dumps(metadata.to_dict())
                
                await session.setex(key, ttl_seconds, data)
        except Exception as e:
            raise SessionError(f"Session storage failed: {e}") from e
    
    async def _touch_session(self, session_id: str) -> None:
        """Update last accessed time."""
        metadata = await self._get_session_metadata(session_id)
        if metadata:
            # Simple touch - could update last_accessed if we add that field
            await self._store_session_metadata(metadata)
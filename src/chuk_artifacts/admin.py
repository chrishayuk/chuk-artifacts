# -*- coding: utf-8 -*-
# chuk_artifacts/admin.py
"""
Administrative and debugging operations.
Now includes chuk_sessions integration.
"""

from __future__ import annotations

import uuid, logging
from datetime import datetime
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .store import ArtifactStore

logger = logging.getLogger(__name__)


class AdminOperations:
    """Handles administrative and debugging operations."""

    def __init__(self, artifact_store: 'ArtifactStore'):
        # canonical reference
        self.artifact_store = artifact_store

        # backward-compat/consistency with other ops modules
        self.store = artifact_store

    async def validate_configuration(self) -> Dict[str, Any]:
        """Validate store configuration and connectivity."""
        results = {"timestamp": datetime.utcnow().isoformat() + "Z"}
        
        # Test session provider
        try:
            session_ctx_mgr = self.artifact_store._session_factory()
            async with session_ctx_mgr as session:
                # Test basic operations
                test_key = f"test_{uuid.uuid4().hex}"
                await session.setex(test_key, 10, "test_value")
                value = await session.get(test_key)
                
                if value == "test_value":
                    results["session"] = {
                        "status": "ok", 
                        "provider": self.artifact_store._session_provider_name
                    }
                else:
                    results["session"] = {
                        "status": "error", 
                        "message": "Session store test failed",
                        "provider": self.artifact_store._session_provider_name
                    }
        except Exception as e:
            results["session"] = {
                "status": "error", 
                "message": str(e),
                "provider": self.artifact_store._session_provider_name
            }
        
        # Test storage provider
        try:
            storage_ctx_mgr = self.artifact_store._s3_factory()
            async with storage_ctx_mgr as s3:
                await s3.head_bucket(Bucket=self.artifact_store.bucket)
            results["storage"] = {
                "status": "ok", 
                "bucket": self.artifact_store.bucket, 
                "provider": self.artifact_store._storage_provider_name
            }
        except Exception as e:
            results["storage"] = {
                "status": "error", 
                "message": str(e), 
                "provider": self.artifact_store._storage_provider_name
            }
        
        # Test session manager (chuk_sessions)
        try:
            # Try to allocate a test session
            test_session = await self.artifact_store._session_manager.allocate_session(
                user_id="test_admin_user"
            )
            # Validate it
            is_valid = await self.artifact_store._session_manager.validate_session(test_session)
            # Clean up
            await self.artifact_store._session_manager.delete_session(test_session)
            
            if is_valid:
                results["session_manager"] = {
                    "status": "ok",
                    "sandbox_id": self.artifact_store.sandbox_id,
                    "test_session": test_session
                }
            else:
                results["session_manager"] = {
                    "status": "error",
                    "message": "Session validation failed"
                }
        except Exception as e:
            results["session_manager"] = {
                "status": "error",
                "message": str(e)
            }
        
        return results

    async def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        base_stats = {
            "storage_provider": self.artifact_store._storage_provider_name,
            "session_provider": self.artifact_store._session_provider_name,
            "bucket": self.artifact_store.bucket,
            "max_retries": self.artifact_store.max_retries,
            "closed": self.artifact_store._closed,
            "sandbox_id": self.artifact_store.sandbox_id,
            "session_ttl_hours": self.artifact_store.session_ttl_hours,
        }
        
        # Add session manager stats from chuk_sessions
        try:
            session_stats = self.artifact_store._session_manager.get_cache_stats()
            base_stats["session_manager"] = session_stats
        except Exception as e:
            base_stats["session_manager"] = {
                "error": str(e),
                "status": "unavailable"
            }
        
        return base_stats

    async def cleanup_all_expired(self) -> Dict[str, int]:
        """Clean up all expired resources."""
        results = {"timestamp": datetime.utcnow().isoformat() + "Z"}
        
        # Clean up expired sessions using chuk_sessions
        try:
            expired_sessions = await self.artifact_store._session_manager.cleanup_expired_sessions()
            results["expired_sessions_cleaned"] = expired_sessions
        except Exception as e:
            results["session_cleanup_error"] = str(e)
            results["expired_sessions_cleaned"] = 0
        
        # TODO: Add artifact cleanup based on TTL
        # This would require scanning metadata to find expired artifacts
        results["expired_artifacts_cleaned"] = 0  # Placeholder
        
        return results

    async def get_sandbox_info(self) -> Dict[str, Any]:
        """Get information about the current sandbox."""
        return {
            "sandbox_id": self.artifact_store.sandbox_id,
            "session_prefix_pattern": self.artifact_store.get_session_prefix_pattern(),
            "grid_architecture": {
                "enabled": True,
                "pattern": "grid/{sandbox_id}/{session_id}/{artifact_id}",
                "mandatory_sessions": True,
                "federation_ready": True
            }
        }
# -*- coding: utf-8 -*-
# chuk_artifacts/admin.py
"""
Administrative and debugging operations
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
        self.store = artifact_store

    async def validate_configuration(self) -> Dict[str, Any]:
        """Validate store configuration and connectivity."""
        results = {"timestamp": datetime.utcnow().isoformat() + "Z"}
        
        # Test session provider
        try:
            session_ctx_mgr = self.store._session_factory()
            async with session_ctx_mgr as session:
                # Test basic operations
                test_key = f"test_{uuid.uuid4().hex}"
                await session.setex(test_key, 10, "test_value")
                value = await session.get(test_key)
                
                if value == "test_value":
                    results["session"] = {
                        "status": "ok", 
                        "provider": self.store._session_provider_name
                    }
                else:
                    results["session"] = {
                        "status": "error", 
                        "message": "Session store test failed",
                        "provider": self.store._session_provider_name
                    }
        except Exception as e:
            results["session"] = {
                "status": "error", 
                "message": str(e),
                "provider": self.store._session_provider_name
            }
        
        # Test storage provider
        try:
            storage_ctx_mgr = self.store._s3_factory()
            async with storage_ctx_mgr as s3:
                await s3.head_bucket(Bucket=self.store.bucket)
            results["storage"] = {
                "status": "ok", 
                "bucket": self.store.bucket, 
                "provider": self.store._storage_provider_name
            }
        except Exception as e:
            results["storage"] = {
                "status": "error", 
                "message": str(e), 
                "provider": self.store._storage_provider_name
            }
        
        return results

    async def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        return {
            "storage_provider": self.store._storage_provider_name,
            "session_provider": self.store._session_provider_name,
            "bucket": self.store.bucket,
            "max_retries": self.store.max_retries,
            "closed": self.store._closed,
            "sandbox_id": self.store.sandbox_id,
            "session_ttl_hours": self.store.session_ttl_hours,
        }
# -*- coding: utf-8 -*-
# chuk_artifacts/admin.py
"""
Administrative and debugging operations.
"""

from __future__ import annotations

import uuid, logging
from datetime import datetime
from typing import Any, Dict

from .base import BaseOperations

logger = logging.getLogger(__name__)


class AdminOperations(BaseOperations):
    """Handles administrative and debugging operations."""

    async def validate_configuration(self) -> Dict[str, Any]:
        """Validate store configuration and connectivity."""
        results = {"timestamp": datetime.utcnow().isoformat() + "Z"}
        
        # Test session provider
        try:
            session_ctx_mgr = self.session_factory()
            async with session_ctx_mgr as session:
                # Test basic operations
                test_key = f"test_{uuid.uuid4().hex}"
                await session.setex(test_key, 10, "test_value")
                value = await session.get(test_key)
                
                if value == "test_value":
                    results["session"] = {
                        "status": "ok", 
                        "provider": self.session_provider_name
                    }
                else:
                    results["session"] = {
                        "status": "error", 
                        "message": "Session store test failed",
                        "provider": self.session_provider_name
                    }
        except Exception as e:
            results["session"] = {
                "status": "error", 
                "message": str(e),
                "provider": self.session_provider_name
            }
        
        # Test storage provider
        try:
            storage_ctx_mgr = self.s3_factory()
            async with storage_ctx_mgr as s3:
                await s3.head_bucket(Bucket=self.bucket)
            results["storage"] = {
                "status": "ok", 
                "bucket": self.bucket, 
                "provider": self.storage_provider_name
            }
        except Exception as e:
            results["storage"] = {
                "status": "error", 
                "message": str(e), 
                "provider": self.storage_provider_name
            }
        
        return results

    async def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        return {
            "storage_provider": self.storage_provider_name,
            "session_provider": self.session_provider_name,
            "bucket": self.bucket,
            "max_retries": self.max_retries,
            "closed": self.store._closed,
        }
# -*- coding: utf-8 -*-
# chuk_artifacts/providers/ibm_cos_iam.py
"""
Async wrapper for IBM Cloud Object Storage using IAM API-key (oauth).

✓ Fits the aioboto3-style interface that ArtifactStore expects:
    • async put_object(...)
    • async get_object(...)
    • async head_object(...)
    • async delete_object(...)
    • async list_objects_v2(...)
    • async head_bucket(...)
    • async generate_presigned_url(...)
✓ No HMAC keys required - just IBM_COS_APIKEY + IBM_COS_INSTANCE_CRN.

Env vars
--------
IBM_COS_APIKEY           - value of "apikey" field
IBM_COS_INSTANCE_CRN     - value of "resource_instance_id"
IBM_COS_ENDPOINT         - regional data endpoint, e.g.
                           https://s3.us-south.cloud-object-storage.appdomain.cloud
"""

from __future__ import annotations
import os, asyncio
from contextlib import asynccontextmanager
from typing import AsyncContextManager, Any, Dict, Callable

import ibm_boto3
from ibm_botocore.client import Config


# ─────────────────────────────────────────────────────────────────────
def _sync_client():
    """Create synchronous IBM COS client with IAM authentication."""
    endpoint = os.getenv(
        "IBM_COS_ENDPOINT",
        "https://s3.us-south.cloud-object-storage.appdomain.cloud",
    )
    api_key = os.getenv("IBM_COS_APIKEY")
    instance = os.getenv("IBM_COS_INSTANCE_CRN")
    if not (api_key and instance):
        raise RuntimeError(
            "Set IBM_COS_APIKEY, IBM_COS_INSTANCE_CRN, IBM_COS_ENDPOINT "
            "for ibm_cos_iam provider."
        )
    return ibm_boto3.client(
        "s3",
        ibm_api_key_id=api_key,
        ibm_service_instance_id=instance,
        config=Config(signature_version="oauth"),
        endpoint_url=endpoint,
    )


# ─────────────────────────────────────────────────────────────────────
class _AsyncIBMClient:
    """Complete async façade over synchronous ibm_boto3 S3 client."""
    
    def __init__(self, sync_client):
        self._c = sync_client

    # ---- Core S3 operations used by ArtifactStore -------------------------
    async def put_object(self, **kwargs) -> Dict[str, Any]:
        """Store object in IBM COS."""
        return await asyncio.to_thread(self._c.put_object, **kwargs)

    async def get_object(self, **kwargs) -> Dict[str, Any]:
        """Retrieve object from IBM COS."""
        return await asyncio.to_thread(self._c.get_object, **kwargs)

    async def head_object(self, **kwargs) -> Dict[str, Any]:
        """Get object metadata from IBM COS."""
        return await asyncio.to_thread(self._c.head_object, **kwargs)

    async def delete_object(self, **kwargs) -> Dict[str, Any]:
        """Delete object from IBM COS."""
        return await asyncio.to_thread(self._c.delete_object, **kwargs)

    async def list_objects_v2(self, **kwargs) -> Dict[str, Any]:
        """List objects in IBM COS bucket."""
        return await asyncio.to_thread(self._c.list_objects_v2, **kwargs)

    async def head_bucket(self, **kwargs) -> Dict[str, Any]:
        """Check if bucket exists in IBM COS."""
        return await asyncio.to_thread(self._c.head_bucket, **kwargs)

    async def generate_presigned_url(self, *args, **kwargs) -> str:
        """Generate presigned URL for IBM COS object."""
        return await asyncio.to_thread(self._c.generate_presigned_url, *args, **kwargs)

    # ---- Additional operations for completeness ---------------------------
    async def copy_object(self, **kwargs) -> Dict[str, Any]:
        """Copy object within IBM COS."""
        return await asyncio.to_thread(self._c.copy_object, **kwargs)

    async def delete_objects(self, **kwargs) -> Dict[str, Any]:
        """Delete multiple objects from IBM COS."""
        return await asyncio.to_thread(self._c.delete_objects, **kwargs)

    # ---- Cleanup -----------------------------------------------------------
    async def close(self):
        """Close the underlying sync client."""
        await asyncio.to_thread(self._c.close)


# ─────────────────────────────────────────────────────────────────────
def factory() -> Callable[[], AsyncContextManager]:
    """
    Return a zero-arg callable that yields an async-context-manager.
    
    Returns
    -------
    Callable[[], AsyncContextManager]
        Factory function that creates IBM COS IAM client context managers
    """

    @asynccontextmanager
    async def _ctx():
        sync_client = _sync_client()
        try:
            yield _AsyncIBMClient(sync_client)
        finally:
            await asyncio.to_thread(sync_client.close)

    return _ctx  # Return the function, not the result of calling it
# -*- coding: utf-8 -*-
# chuk_artifacts/providers/ibm_cos_iam.py
"""
Async wrapper for IBM Cloud Object Storage using IAM API-key (oauth).

✓ Fits the aioboto3-style interface that ArtifactStore expects:
    • async put_object(...)
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
    """Minimal async façade over synchronous ibm_boto3 S3 client."""
    def __init__(self, sync_client):
        self._c = sync_client

    # ---- methods used by ArtifactStore -------------------------------------
    async def put_object(self, **kw) -> Dict[str, Any]:
        return await asyncio.to_thread(self._c.put_object, **kw)

    async def generate_presigned_url(self, *a, **kw) -> str:
        return await asyncio.to_thread(self._c.generate_presigned_url, *a, **kw)

    # ---- cleanup -----------------------------------------------------------
    async def close(self):
        await asyncio.to_thread(self._c.close)


# ─────────────────────────────────────────────────────────────────────
def factory() -> Callable[[], AsyncContextManager]:
    """
    Return a zero-arg callable that yields an async-context-manager.
    """

    @asynccontextmanager
    async def _ctx():
        sync_client = _sync_client()
        try:
            yield _AsyncIBMClient(sync_client)
        finally:
            await asyncio.to_thread(sync_client.close)

    return _ctx  # Return the function, not the result of calling it
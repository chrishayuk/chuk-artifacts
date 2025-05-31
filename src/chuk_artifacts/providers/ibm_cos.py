# -*- coding: utf-8 -*-
# chuk_artifacts/providers/ibm_cos.py
"""
Factory for an aioboto3 client wired for IBM Cloud Object Storage (COS).
Supports both IAM and HMAC auth.

aioboto3 ≥ 12 returns an *async-context* client, so we expose
    • factory() - preferred, used by provider_factory
    • client()  - retained for backward-compat tests/manual use
"""

from __future__ import annotations
import os, aioboto3
from aioboto3.session import AioConfig  # ✅ CRITICAL: Import AioConfig
from typing import Optional, Callable, AsyncContextManager

# ──────────────────────────────────────────────────────────────────
# internal helper that actually builds the client
# ──────────────────────────────────────────────────────────────────
def _build_client(
    *,
    endpoint_url: str,
    region: str,
    ibm_api_key: Optional[str],
    ibm_instance_crn: Optional[str],
    access_key: Optional[str],
    secret_key: Optional[str],
):
    session = aioboto3.Session()

    # IAM auth (preferred)
    if not access_key and not secret_key:
        return session.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            ibm_api_key_id=ibm_api_key,
            ibm_service_instance_id=ibm_instance_crn,
            # ✅ Use SigV2 for IBM COS IAM + path style
            config=AioConfig(
                signature_version='s3',
                s3={'addressing_style': 'path'}
            )
        )

    # HMAC auth
    return session.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        # ✅ Use SigV2 for IBM COS HMAC + path style
        config=AioConfig(
            signature_version='s3',
            s3={'addressing_style': 'path'}
        )
    )


# ──────────────────────────────────────────────────────────────────
# public factory  (provider_factory expects this)
# ──────────────────────────────────────────────────────────────────
def factory(
    *,
    endpoint_url: Optional[str] = None,
    region: str = "us-south",
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
):
    """
    Return an async-context S3 client for IBM COS (HMAC only).
    """
    endpoint_url = endpoint_url or os.getenv(
        "IBM_COS_ENDPOINT",
        "https://s3.us-south.cloud-object-storage.appdomain.cloud",
    )
    access_key = access_key or os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")
    
    # ✅ Extract region from endpoint to ensure they match
    if endpoint_url:
        if "us-south" in endpoint_url:
            region = "us-south"
        elif "us-east" in endpoint_url:
            region = "us-east-1"
        elif "eu-gb" in endpoint_url:
            region = "eu-gb"
        elif "eu-de" in endpoint_url:
            region = "eu-de"
    
    # Check AWS_REGION environment variable as override
    env_region = os.getenv('AWS_REGION')
    if env_region:
        region = env_region

    if not (access_key and secret_key):
        raise RuntimeError(
            "HMAC credentials missing. "
            "Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY "
            "or generate an HMAC key for your COS instance."
        )

    def _make() -> AsyncContextManager:
        session = aioboto3.Session()
        return session.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            # ✅ CRITICAL: IBM COS requires Signature Version 2 for writes AND presigned URLs
            config=AioConfig(
                signature_version='s3',
                s3={
                    'addressing_style': 'path'  # Also ensure path-style addressing
                }
            )
        )

    return _make
# -*- coding: utf-8 -*-
# chuk_artifacts/config.py
"""
Configuration helpers for ArtifactStore.

Provides convenient functions to set up common configurations
without needing to write .env files or remember all the variable names.
"""

import os
from typing import Dict, Optional
from .store import ArtifactStore


def configure_memory() -> Dict[str, str]:
    """
    Configure for in-memory storage (development/testing).
    
    Returns
    -------
    dict
        Environment variables that were set
    """
    env_vars = {
        "ARTIFACT_PROVIDER": "memory",
        "SESSION_PROVIDER": "memory",
        "ARTIFACT_BUCKET": "mcp-artifacts"
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    return env_vars


def configure_filesystem(root: str = "./artifacts") -> Dict[str, str]:
    """
    Configure for local filesystem storage.
    
    Parameters
    ----------
    root : str
        Root directory for artifact storage
        
    Returns
    -------
    dict
        Environment variables that were set
    """
    env_vars = {
        "ARTIFACT_PROVIDER": "filesystem", 
        "SESSION_PROVIDER": "memory",
        "ARTIFACT_FS_ROOT": root,
        "ARTIFACT_BUCKET": "mcp-artifacts"
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    return env_vars


def configure_s3(
    *,
    access_key: str,
    secret_key: str, 
    bucket: str,
    endpoint_url: Optional[str] = None,
    region: str = "us-east-1",
    session_provider: str = "memory"
) -> Dict[str, str]:
    """
    Configure for S3-compatible storage.
    
    Parameters
    ----------
    access_key : str
        AWS access key ID
    secret_key : str
        AWS secret access key
    bucket : str
        S3 bucket name
    endpoint_url : str, optional
        Custom S3 endpoint (for MinIO, DigitalOcean, etc.)
    region : str
        AWS region
    session_provider : str
        Session provider (memory or redis)
        
    Returns
    -------
    dict
        Environment variables that were set
    """
    env_vars = {
        "ARTIFACT_PROVIDER": "s3",
        "SESSION_PROVIDER": session_provider,
        "AWS_ACCESS_KEY_ID": access_key,
        "AWS_SECRET_ACCESS_KEY": secret_key,
        "AWS_REGION": region,
        "ARTIFACT_BUCKET": bucket
    }
    
    if endpoint_url:
        env_vars["S3_ENDPOINT_URL"] = endpoint_url
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    return env_vars


def configure_redis_session(redis_url: str = "redis://localhost:6379/0") -> Dict[str, str]:
    """
    Configure Redis for session storage.
    
    Parameters
    ----------
    redis_url : str
        Redis connection URL
        
    Returns
    -------
    dict
        Environment variables that were set
    """
    env_vars = {
        "SESSION_PROVIDER": "redis",
        "SESSION_REDIS_URL": redis_url
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    return env_vars


def configure_ibm_cos(
    *,
    access_key: str,
    secret_key: str,
    bucket: str,
    endpoint: str = "https://s3.us-south.cloud-object-storage.appdomain.cloud",
    region: str = "us-south",
    session_provider: str = "memory"
) -> Dict[str, str]:
    """
    Configure for IBM Cloud Object Storage (HMAC).
    
    Parameters
    ----------
    access_key : str
        HMAC access key
    secret_key : str
        HMAC secret key
    bucket : str
        COS bucket name
    endpoint : str
        IBM COS endpoint URL
    region : str
        IBM COS region
    session_provider : str
        Session provider (memory or redis)
        
    Returns
    -------
    dict
        Environment variables that were set
    """
    env_vars = {
        "ARTIFACT_PROVIDER": "ibm_cos",
        "SESSION_PROVIDER": session_provider,
        "AWS_ACCESS_KEY_ID": access_key,
        "AWS_SECRET_ACCESS_KEY": secret_key,
        "AWS_REGION": region,
        "IBM_COS_ENDPOINT": endpoint,
        "ARTIFACT_BUCKET": bucket
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    return env_vars


def configure_ibm_cos_iam(
    *,
    api_key: str,
    instance_crn: str,
    bucket: str,
    endpoint: str = "https://s3.us-south.cloud-object-storage.appdomain.cloud",
    session_provider: str = "memory"
) -> Dict[str, str]:
    """
    Configure for IBM Cloud Object Storage (IAM).
    
    Parameters
    ----------
    api_key : str
        IBM Cloud API key
    instance_crn : str
        COS instance CRN
    bucket : str
        COS bucket name
    endpoint : str
        IBM COS endpoint URL
    session_provider : str
        Session provider (memory or redis)
        
    Returns
    -------
    dict
        Environment variables that were set
    """
    env_vars = {
        "ARTIFACT_PROVIDER": "ibm_cos_iam",
        "SESSION_PROVIDER": session_provider,
        "IBM_COS_APIKEY": api_key,
        "IBM_COS_INSTANCE_CRN": instance_crn,
        "IBM_COS_ENDPOINT": endpoint,
        "ARTIFACT_BUCKET": bucket
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    return env_vars


def create_store() -> ArtifactStore:
    """
    Create a new ArtifactStore instance with current environment configuration.
    
    Returns
    -------
    ArtifactStore
        Configured store instance
    """
    return ArtifactStore()


# Convenience functions for common setups
def development_setup() -> ArtifactStore:
    """Set up for local development (memory storage)."""
    configure_memory()
    return create_store()


def testing_setup(artifacts_dir: str = "./test-artifacts") -> ArtifactStore:
    """Set up for testing (filesystem storage)."""
    configure_filesystem(artifacts_dir)
    return create_store()


def production_setup(
    *,
    storage_type: str,
    **kwargs
) -> ArtifactStore:
    """
    Set up for production use.
    
    Parameters
    ----------
    storage_type : str
        Storage type: 's3', 'ibm_cos', 'ibm_cos_iam'
    **kwargs
        Configuration parameters for the chosen storage type
        
    Returns
    -------
    ArtifactStore
        Configured store instance
    """
    if storage_type == "s3":
        configure_s3(**kwargs)
    elif storage_type == "ibm_cos":
        configure_ibm_cos(**kwargs)
    elif storage_type == "ibm_cos_iam":
        configure_ibm_cos_iam(**kwargs)
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")
    
    return create_store()


# Usage examples in docstring
__doc__ += """

Usage Examples
--------------

**Quick development setup:**
```python
from chuk_artifacts.config import development_setup

store = development_setup()  # Uses memory, no persistence
```

**Testing with filesystem:**
```python
from chuk_artifacts.config import testing_setup

store = testing_setup("./test-data")  # Persists to filesystem
```

**Production with S3:**
```python
from chuk_artifacts.config import production_setup

store = production_setup(
    storage_type="s3",
    access_key="AKIA...",
    secret_key="...", 
    bucket="prod-artifacts",
    session_provider="redis"
)
```

**Custom configuration:**
```python
from chuk_artifacts.config import configure_s3, configure_redis_session, create_store

# Set up S3 storage
configure_s3(
    access_key="AKIA...",
    secret_key="...",
    bucket="my-bucket",
    endpoint_url="https://nyc3.digitaloceanspaces.com"  # DigitalOcean Spaces
)

# Set up Redis sessions
configure_redis_session("redis://localhost:6379/1")

# Create store with this configuration
store = create_store()
```
"""
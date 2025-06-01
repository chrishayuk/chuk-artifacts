# -*- coding: utf-8 -*-
# chuk_artifacts/federation/__init__.py
"""
Federation module for cross-sandbox artifact discovery and access.

Provides transparent federation capabilities using chuk_sessions providers
for the federation index, enabling artifacts to be discovered and accessed
across multiple sandboxes while maintaining security and session isolation.

Key Features:
- Uses same Redis/memory infrastructure as chuk_sessions
- Transparent cross-sandbox discovery
- Session-based security model
- Grid-aware path management
- Zero-config federation setup

Example Usage:
    from chuk_artifacts.federation import FederatedArtifactStore
    
    # Create federated store (uses same providers as sessions)
    store = FederatedArtifactStore(
        sandbox_id="us-east-1",
        storage_provider="s3",
        session_provider="redis"  # Federation index uses same Redis
    )
    
    # Store artifacts (automatically registered in federation)
    session_id = await store.create_session(user_id="alice")
    artifact_id = await store.store(
        data=b"Global content",
        mime="text/plain",
        summary="Cross-sandbox file",
        session_id=session_id
    )
    
    # List session across all sandboxes
    all_files = await store.list_session_federated(session_id)
    
    # Retrieve from any sandbox (transparent)
    data = await store.retrieve(artifact_id)
"""

from .manager import (
    FederationManager,
    ArtifactLocation,
    create_federation_manager
)

from .store import (
    FederatedArtifactStore,
    create_federated_store,
    create_local_store
)

__all__ = [
    # Core classes
    "FederatedArtifactStore",
    "FederationManager", 
    "ArtifactLocation",
    
    # Factory functions
    "create_federated_store",
    "create_local_store",
    "create_federation_manager",
]

# Version info
__version__ = "1.0.0"

# Module metadata
__author__ = "Chris Hay"
__description__ = "Cross-sandbox federation for chuk_artifacts using chuk_sessions providers"
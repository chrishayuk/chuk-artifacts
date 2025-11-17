# ===========================================================================
# chuk_artifacts/providers/memory.py
# ===========================================================================
"""In-memory, process-local artefact store (non-persistent).

Intended for unit tests and ephemeral fixtures. Fully async-friendly, no
external deps. Thread-safe with proper instance isolation.
"""

from __future__ import annotations

import asyncio
import time
import uuid
import weakref
from contextlib import asynccontextmanager
from typing import Any, Dict, Callable, AsyncContextManager, Optional


class _MemoryS3Client:
    """
    Very small subset of aioboto3's S3Client surface used by ArtifactStore.

    Each instance maintains its own storage to avoid cross-contamination
    between different stores or test cases.
    """

    # Class-level registry for debugging/testing purposes (optional)
    _instances: weakref.WeakSet = weakref.WeakSet()

    def __init__(self, shared_store: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        Initialize memory client.

        Parameters
        ----------
        shared_store : dict, optional
            If provided, use this dict as storage backend.
            Useful for sharing state between multiple clients.
            If None, creates isolated per-instance storage.
        """
        self._store: Dict[str, Dict[str, Any]] = (
            shared_store if shared_store is not None else {}
        )
        self._is_shared_store = shared_store is not None
        self._lock = asyncio.Lock()
        self._closed = False

        # Register for debugging
        _MemoryS3Client._instances.add(self)

    # ------------------------------------------------------------
    async def put_object(
        self,
        *,
        Bucket: str,  # noqa: N803 – AWS naming convention
        Key: str,  # noqa: N803
        Body: bytes,  # noqa: N803
        ContentType: str,
        Metadata: Dict[str, str],  # noqa: N803
    ):
        """Store object in memory with metadata."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        full_key = f"{Bucket}/{Key}"

        async with self._lock:
            self._store[full_key] = {
                "data": Body,
                "content_type": ContentType,
                "metadata": Metadata,
                "timestamp": time.time(),
                "size": len(Body),
            }

        return {
            "ResponseMetadata": {"HTTPStatusCode": 200},
            "ETag": f'"{hash(Body) & 0x7FFFFFFF:08x}"',  # Fake ETag
        }

    async def get_object(
        self,
        *,
        Bucket: str,  # noqa: N803
        Key: str,  # noqa: N803
    ):
        """Retrieve object from memory (for testing purposes)."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        full_key = f"{Bucket}/{Key}"

        async with self._lock:
            if full_key not in self._store:
                # Mimic AWS S3 NoSuchKey error
                error = {
                    "Error": {
                        "Code": "NoSuchKey",
                        "Message": "The specified key does not exist.",
                        "Key": Key,
                        "BucketName": Bucket,
                    }
                }
                raise Exception(f"NoSuchKey: {error}")

            obj = self._store[full_key]
            return {
                "Body": obj["data"],
                "ContentType": obj["content_type"],
                "Metadata": obj["metadata"],
                "ContentLength": obj["size"],
                "LastModified": obj["timestamp"],
            }

    async def head_object(
        self,
        *,
        Bucket: str,  # noqa: N803
        Key: str,  # noqa: N803
    ):
        """Get object metadata without body."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        full_key = f"{Bucket}/{Key}"

        async with self._lock:
            if full_key not in self._store:
                raise Exception(f"NoSuchKey: {Key}")

            obj = self._store[full_key]
            return {
                "ContentType": obj["content_type"],
                "Metadata": obj["metadata"],
                "ContentLength": obj["size"],
                "LastModified": obj["timestamp"],
            }

    async def head_bucket(self, *, Bucket: str):  # noqa: N803
        """Check if bucket exists (always returns success in memory mode)."""
        if self._closed:
            raise RuntimeError("Client has been closed")
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    async def generate_presigned_url(
        self,
        operation: str,
        *,
        Params: Dict[str, str],  # noqa: N803
        ExpiresIn: int,  # noqa: N803
    ) -> str:
        """
        Generate fake presigned URLs for testing.

        URLs use memory:// scheme and include object validation.
        """
        if self._closed:
            raise RuntimeError("Client has been closed")

        bucket, key = Params["Bucket"], Params["Key"]
        full_key = f"{bucket}/{key}"

        async with self._lock:
            if full_key not in self._store:
                raise FileNotFoundError(f"Object not found: {full_key}")

            # Include object hash for validation
            obj = self._store[full_key]
            obj_hash = hash(obj["data"]) & 0x7FFFFFFF

        return (
            f"memory://{full_key}"
            f"?operation={operation}"
            f"&token={uuid.uuid4().hex}"
            f"&expires={int(time.time()) + ExpiresIn}"
            f"&hash={obj_hash:08x}"
        )

    async def list_objects_v2(
        self,
        *,
        Bucket: str,  # noqa: N803
        Prefix: str = "",  # noqa: N803
        MaxKeys: int = 1000,  # noqa: N803
    ):
        """List objects with optional prefix filtering."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        bucket_prefix = f"{Bucket}/"
        search_prefix = f"{bucket_prefix}{Prefix}"

        async with self._lock:
            matching_keys = [
                key for key in self._store.keys() if key.startswith(search_prefix)
            ]

            # Limit results
            matching_keys = matching_keys[:MaxKeys]

            contents = []
            for full_key in matching_keys:
                obj = self._store[full_key]
                # Remove bucket prefix to get just the key
                key = full_key[len(bucket_prefix) :]
                contents.append(
                    {
                        "Key": key,
                        "Size": obj["size"],
                        "LastModified": obj["timestamp"],
                        "ETag": f'"{hash(obj["data"]) & 0x7FFFFFFF:08x}"',
                    }
                )

            return {
                "Contents": contents,
                "KeyCount": len(contents),
                "IsTruncated": False,  # We don't implement pagination
            }

    async def delete_object(
        self,
        *,
        Bucket: str,  # noqa: N803
        Key: str,  # noqa: N803
    ):
        """Delete object from memory store."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        full_key = f"{Bucket}/{Key}"

        async with self._lock:
            self._store.pop(full_key, None)  # Don't error if key doesn't exist

        return {"ResponseMetadata": {"HTTPStatusCode": 204}}

    async def close(self):
        """Clean up resources and mark client as closed."""
        if not self._closed:
            # Only clear the store if it's NOT shared
            # If it's shared, other clients may still need the data
            if not self._is_shared_store:
                async with self._lock:
                    self._store.clear()
            self._closed = True

    # ------------------------------------------------------------
    # Debug/testing utilities
    # ------------------------------------------------------------

    async def _debug_list_all_keys(self) -> list[str]:
        """List all keys in storage (for debugging)."""
        async with self._lock:
            return list(self._store.keys())

    async def _debug_get_stats(self) -> Dict[str, Any]:
        """Get storage statistics (for debugging)."""
        async with self._lock:
            total_objects = len(self._store)
            total_bytes = sum(obj["size"] for obj in self._store.values())
            return {
                "total_objects": total_objects,
                "total_bytes": total_bytes,
                "closed": self._closed,
                "is_shared_store": self._is_shared_store,
                "store_id": id(self._store),  # Memory address for debugging
                "client_id": id(self),  # Client instance ID
                "store_keys": list(self._store.keys())[
                    :5
                ],  # First 5 keys for debugging
            }

    @classmethod
    def _debug_instance_count(cls) -> int:
        """Get count of active instances (for debugging)."""
        return len(cls._instances)


# ---- public factory -------------------------------------------------------

# Global shared storage for memory provider when used as default
_default_shared_store: Dict[str, Dict[str, Any]] = {}


def factory(
    shared_store: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Callable[[], AsyncContextManager]:
    """
    Return a **zero-arg** factory that yields an async-context client.

    Key behavior for memory provider:
    - If shared_store is provided, uses that specific storage
    - If shared_store is None, ALWAYS uses the global shared storage
    - This ensures all memory clients in the same process share data
    - Prevents issues where ArtifactStore operations can't see each other's data

    Parameters
    ----------
    shared_store : dict, optional
        If provided, all clients created by this factory will share
        the same storage dict. If None, will use a global shared store
        to ensure consistency across operations within the same process.
    """

    # CRITICAL: Always use global shared storage when none specified
    # This prevents the common issue where each ArtifactStore operation
    # gets a different isolated storage and can't see each other's data
    if shared_store is None:
        shared_store = _default_shared_store

    @asynccontextmanager
    async def _ctx():
        client = _MemoryS3Client(shared_store=shared_store)
        try:
            yield client  # ← hand the live client back to caller
        finally:
            await client.close()  # ← clean up when context exits

    return _ctx


# ---- convenience functions for testing ------------------------------------


def create_shared_memory_factory() -> tuple[
    Callable[[], AsyncContextManager], Dict[str, Dict[str, Any]]
]:
    """
    Create a factory that uses shared storage, returning both the factory
    and a reference to the storage dict for inspection.

    Returns
    -------
    tuple
        (factory_function, shared_storage_dict)
    """
    shared_store: Dict[str, Dict[str, Any]] = {}
    return factory(shared_store), shared_store


async def clear_all_memory_stores():
    """
    Emergency cleanup function that clears all active memory stores.
    Useful for test teardown.
    """
    # Clear the global shared store
    global _default_shared_store
    _default_shared_store.clear()

    # Close all active instances
    instances = list(_MemoryS3Client._instances)
    for instance in instances:
        try:
            await instance.close()
        except Exception:
            pass  # Best effort cleanup

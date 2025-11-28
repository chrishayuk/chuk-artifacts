# -*- coding: utf-8 -*-
# chuk_artifacts/providers/vfs_adapter.py
"""
VFS Adapter - Wraps chuk-virtual-fs to provide S3-compatible interface.

This adapter allows chuk-artifacts to use chuk-virtual-fs as a storage backend
while maintaining compatibility with the existing S3-like API.
"""

from __future__ import annotations

import time
import uuid
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Callable, AsyncContextManager, Optional, AsyncIterator

from chuk_virtual_fs import AsyncVirtualFileSystem

logger = logging.getLogger(__name__)


class VFSAdapter:
    """
    Adapter that makes chuk-virtual-fs look like an S3 client.

    This adapter bridges the gap between:
    - S3-style API (put_object, get_object, etc.)
    - VFS-style API (write_file, read_file, etc.)
    """

    def __init__(self, vfs: AsyncVirtualFileSystem):
        """
        Initialize adapter with a VFS instance.

        Parameters
        ----------
        vfs : AsyncVirtualFileSystem
            The virtual filesystem to wrap
        """
        self.vfs = vfs
        self._closed = False

    async def put_object(
        self,
        *,
        Bucket: str,  # noqa: N803
        Key: str,  # noqa: N803
        Body: bytes,  # noqa: N803
        ContentType: str,  # noqa: N803
        Metadata: Dict[str, str],  # noqa: N803
    ):
        """Store object using VFS write_binary."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        # Construct VFS path: /{bucket}/{key}
        vfs_path = f"/{Bucket}/{Key}"

        # Ensure bucket (parent directory) exists
        # S3 doesn't require directories, but VFS does
        bucket_path = f"/{Bucket}"
        if not await self.vfs.exists(bucket_path):
            await self.vfs.mkdir(bucket_path)

        # Handle nested keys (e.g., "folder/subfolder/file")
        # Create all parent directories
        key_parts = Key.rsplit("/", 1)
        if len(key_parts) > 1:
            parent_key = key_parts[0]
            # Create parent directories recursively
            path_parts = parent_key.split("/")
            current_path = f"/{Bucket}"
            for part in path_parts:
                current_path = f"{current_path}/{part}"
                if not await self.vfs.exists(current_path):
                    await self.vfs.mkdir(current_path)

        # Prepare metadata in VFS format
        # VFS expects metadata as custom_meta dict, not as direct kwargs
        metadata = {
            "mime_type": ContentType,
            "custom_meta": {
                **Metadata,
                "s3_content_type": ContentType,
                "s3_metadata": Metadata,
            },
        }

        # Write using VFS
        await self.vfs.write_binary(vfs_path, Body, **metadata)

        # Return S3-like response
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
        """Retrieve object using VFS read_binary."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        # Construct VFS path
        vfs_path = f"/{Bucket}/{Key}"

        # Check if exists
        if not await self.vfs.exists(vfs_path):
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

        # Read data
        data = await self.vfs.read_binary(vfs_path)

        # Get metadata
        metadata = await self.vfs.get_metadata(vfs_path)

        # Extract S3 metadata from custom_meta
        custom_meta = metadata.get("custom_meta", {})
        s3_metadata = custom_meta.get("s3_metadata", {})

        # Return S3-like response
        return {
            "Body": data,
            "ContentType": metadata.get("mime_type", "application/octet-stream"),
            "Metadata": s3_metadata,
            "ContentLength": metadata.get("size", len(data) if data else 0),
            "LastModified": metadata.get("modified_at", time.time()),
        }

    async def put_object_stream(
        self,
        *,
        Bucket: str,  # noqa: N803
        Key: str,  # noqa: N803
        Body: AsyncIterator[bytes],  # noqa: N803
        ContentType: str,  # noqa: N803
        Metadata: Dict[str, str],  # noqa: N803
        ContentLength: Optional[int] = None,  # noqa: N803
        ProgressCallback: Optional[Callable[[int, Optional[int]], None]] = None,  # noqa: N803
    ):
        """Stream upload object using VFS write_stream."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        # Construct VFS path: /{bucket}/{key}
        vfs_path = f"/{Bucket}/{Key}"

        # Ensure bucket (parent directory) exists
        bucket_path = f"/{Bucket}"
        if not await self.vfs.exists(bucket_path):
            await self.vfs.mkdir(bucket_path)

        # Handle nested keys (create parent directories)
        key_parts = Key.rsplit("/", 1)
        if len(key_parts) > 1:
            parent_key = key_parts[0]
            path_parts = parent_key.split("/")
            current_path = f"/{Bucket}"
            for part in path_parts:
                current_path = f"{current_path}/{part}"
                if not await self.vfs.exists(current_path):
                    await self.vfs.mkdir(current_path)

        # Prepare metadata in VFS format
        metadata = {
            "mime_type": ContentType,
            "custom_meta": {
                **Metadata,
                "s3_content_type": ContentType,
                "s3_metadata": Metadata,
            },
        }

        # Write using VFS streaming
        if hasattr(self.vfs, "write_stream"):
            # VFS supports streaming - use it
            bytes_written = await self.vfs.write_stream(
                vfs_path, Body, progress_callback=ProgressCallback, **metadata
            )
        else:
            # Fallback: collect all chunks and write
            chunks = []
            bytes_written = 0
            async for chunk in Body:
                chunks.append(chunk)
                bytes_written += len(chunk)
                if ProgressCallback:
                    ProgressCallback(bytes_written, ContentLength)

            data = b"".join(chunks)
            await self.vfs.write_binary(vfs_path, data, **metadata)

        # Return S3-like response
        return {
            "ResponseMetadata": {"HTTPStatusCode": 200},
            "ETag": f'"{uuid.uuid4().hex}"',  # Generate unique ETag
            "ContentLength": bytes_written,
        }

    async def get_object_stream(
        self,
        *,
        Bucket: str,  # noqa: N803
        Key: str,  # noqa: N803
        ChunkSize: int = 65536,  # noqa: N803 - 64KB default
        ProgressCallback: Optional[Callable[[int, Optional[int]], None]] = None,  # noqa: N803
    ) -> AsyncIterator[bytes]:
        """Stream download object using VFS read_stream."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        # Construct VFS path
        vfs_path = f"/{Bucket}/{Key}"

        # Check if exists
        if not await self.vfs.exists(vfs_path):
            error = {
                "Error": {
                    "Code": "NoSuchKey",
                    "Message": "The specified key does not exist.",
                    "Key": Key,
                    "BucketName": Bucket,
                }
            }
            raise Exception(f"NoSuchKey: {error}")

        # Get file size for progress reporting
        metadata = await self.vfs.get_metadata(vfs_path)
        total_size = metadata.get("size", None)
        bytes_read = 0

        # Stream using VFS if available
        if hasattr(self.vfs, "read_stream"):
            # VFS supports streaming - use it
            async for chunk in self.vfs.read_stream(vfs_path, chunk_size=ChunkSize):
                bytes_read += len(chunk)
                if ProgressCallback:
                    ProgressCallback(bytes_read, total_size)
                yield chunk
        else:
            # Fallback: read entire file and chunk it
            data = await self.vfs.read_binary(vfs_path)
            if data is None:
                raise FileNotFoundError(f"File not found: {vfs_path}")
            for i in range(0, len(data), ChunkSize):
                chunk = data[i : i + ChunkSize]
                bytes_read += len(chunk)
                if ProgressCallback:
                    ProgressCallback(bytes_read, total_size)
                yield chunk

    async def head_object(
        self,
        *,
        Bucket: str,  # noqa: N803
        Key: str,  # noqa: N803
    ):
        """Get object metadata without body."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        # Construct VFS path
        vfs_path = f"/{Bucket}/{Key}"

        # Check if exists
        if not await self.vfs.exists(vfs_path):
            raise Exception(f"NoSuchKey: {Key}")

        # Get metadata
        metadata = await self.vfs.get_metadata(vfs_path)

        # Extract S3 metadata from custom_meta
        custom_meta = metadata.get("custom_meta", {})
        s3_metadata = custom_meta.get("s3_metadata", {})

        # Return S3-like response
        return {
            "ContentType": metadata.get("mime_type", "application/octet-stream"),
            "Metadata": s3_metadata,
            "ContentLength": metadata.get("size", 0),
            "LastModified": metadata.get("modified_at", time.time()),
        }

    async def head_bucket(self, *, Bucket: str):  # noqa: N803
        """Check if bucket exists (always returns success - VFS doesn't have buckets)."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        # VFS doesn't have buckets, but we can create the directory if needed
        bucket_path = f"/{Bucket}"
        if not await self.vfs.exists(bucket_path):
            await self.vfs.mkdir(bucket_path)

        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    async def generate_presigned_url(
        self,
        operation: str,
        *,
        Params: Dict[str, str],  # noqa: N803
        ExpiresIn: int,  # noqa: N803
    ) -> str:
        """
        Generate presigned URLs.

        Note: VFS may support presigned URLs for S3 provider,
        otherwise returns a memory:// URL.
        """
        if self._closed:
            raise RuntimeError("Client has been closed")

        bucket, key = Params["Bucket"], Params["Key"]
        vfs_path = f"/{bucket}/{key}"

        # Check if VFS supports presigned URLs (S3 provider)
        if hasattr(self.vfs, "generate_presigned_url"):
            try:
                url = await self.vfs.generate_presigned_url(
                    vfs_path, expires_in=ExpiresIn
                )
                if url is not None:
                    return url
            except Exception as e:
                logger.debug(
                    f"VFS presigned URL failed, falling back to memory URL: {e}"
                )

        # Fallback: Generate fake presigned URL for non-S3 providers
        # For upload operations (put_object, upload_part), object doesn't exist yet
        # Only check existence for download operations (get_object)
        if operation == "get_object" and not await self.vfs.exists(vfs_path):
            raise FileNotFoundError(f"Object not found: {vfs_path}")

        return (
            f"memory://{vfs_path}"
            f"?operation={operation}"
            f"&token={uuid.uuid4().hex}"
            f"&expires={int(time.time()) + ExpiresIn}"
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

        # Start from bucket root
        bucket_path = f"/{Bucket}"

        # Ensure bucket exists
        if not await self.vfs.exists(bucket_path):
            return {
                "Contents": [],
                "KeyCount": 0,
                "IsTruncated": False,
            }

        # Use VFS find to recursively list files
        # find() only returns files, not directories
        all_files = await self.vfs.find(path=bucket_path, pattern="*", recursive=True)

        # Filter by prefix and convert to S3 format
        contents = []
        for file_path in all_files:
            # Remove bucket prefix to get key
            if file_path.startswith(f"{bucket_path}/"):
                key = file_path[len(f"{bucket_path}/") :]
            else:
                continue

            # Apply prefix filter
            if Prefix and not key.startswith(Prefix):
                continue

            # Get metadata
            try:
                metadata = await self.vfs.get_metadata(file_path)
                contents.append(
                    {
                        "Key": key,
                        "Size": metadata.get("size", 0),
                        "LastModified": metadata.get("modified_at", time.time()),
                        "ETag": f'"{hash(key) & 0x7FFFFFFF:08x}"',
                    }
                )
            except Exception as e:
                logger.debug(f"Skipping file {file_path}: {e}")
                continue

            # Limit results
            if len(contents) >= MaxKeys:
                break

        return {
            "Contents": contents,
            "KeyCount": len(contents),
            "IsTruncated": len(contents) >= MaxKeys,
        }

    async def delete_object(
        self,
        *,
        Bucket: str,  # noqa: N803
        Key: str,  # noqa: N803
    ):
        """Delete object using VFS rm."""
        if self._closed:
            raise RuntimeError("Client has been closed")

        # Construct VFS path
        vfs_path = f"/{Bucket}/{Key}"

        # Delete using VFS (don't error if doesn't exist)
        if await self.vfs.exists(vfs_path):
            await self.vfs.rm(vfs_path)

        return {"ResponseMetadata": {"HTTPStatusCode": 204}}

    async def close(self):
        """Clean up resources."""
        if not self._closed:
            # VFS will be closed by its own context manager
            self._closed = True


# ---- public factory -------------------------------------------------------

# Global shared VFS instances for memory provider
# This ensures data persists across multiple adapter instances
_shared_vfs_instances: Dict[str, AsyncVirtualFileSystem] = {}


def factory(
    provider: str = "memory",
    shared_key: Optional[str] = None,
    **provider_kwargs: Any,
) -> Callable[[], AsyncContextManager]:
    """
    Return a factory that yields VFS-backed S3-compatible clients.

    Parameters
    ----------
    provider : str
        VFS provider name ("memory", "filesystem", "s3", "sqlite")
    shared_key : str, optional
        Key for shared VFS instance (used for memory provider to persist data)
    **provider_kwargs
        Additional arguments for the VFS provider

    Returns
    -------
    Callable[[], AsyncContextManager]
        Factory function that returns adapter context managers
    """

    # For memory provider, use shared VFS instance by default
    if provider == "memory" and shared_key is None:
        shared_key = "default_memory_vfs"

    @asynccontextmanager
    async def _ctx():
        # Check if we should use a shared VFS instance
        if shared_key and shared_key in _shared_vfs_instances:
            vfs = _shared_vfs_instances[shared_key]
            # Wrap in adapter
            adapter = VFSAdapter(vfs)
            try:
                yield adapter
            finally:
                await adapter.close()
        else:
            # Create and initialize VFS
            vfs = AsyncVirtualFileSystem(provider=provider, **provider_kwargs)
            await vfs.initialize()

            # Store in shared instances if key provided
            if shared_key:
                _shared_vfs_instances[shared_key] = vfs

            # Wrap in adapter
            adapter = VFSAdapter(vfs)

            try:
                yield adapter
            finally:
                await adapter.close()
                # Don't close VFS if it's shared
                if not shared_key:
                    await vfs.close()

    return _ctx

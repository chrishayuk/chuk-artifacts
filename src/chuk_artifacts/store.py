# -*- coding: utf-8 -*-
# chuk_artifacts/store.py
"""
Asynchronous, object-store-backed artefact manager (aioboto3 ≥ 12).

Highlights
──────────
• Pure-async: every S3 call is wrapped in `async with s3_factory() as s3`.
• Back-end agnostic: set ARTIFACT_PROVIDER=memory/s3/ibm_cos/… or inject a factory.
• Metadata cached via session provider abstraction (Redis, memory, etc.).
• Presigned URLs on demand, configurable TTL for both data & metadata.
• Enhanced error handling, logging, and operational features.
• Memory defaults: both storage and session use memory by default for zero-config setup.
• Auto .env loading: automatically loads .env files so consumers don't need to.
"""

from __future__ import annotations

import os, uuid, json, hashlib, time, logging, asyncio
from datetime import datetime
from types import ModuleType
from typing import Any, Dict, List, Callable, AsyncContextManager, Optional, Union

try:
    import aioboto3
except ImportError as e:
    raise ImportError(f"Required dependency missing: {e}. Install with: pip install aioboto3") from e

# Auto-load .env files if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env from current directory and parent directories
    logger = logging.getLogger(__name__)
    logger.debug("Loaded environment variables from .env file")
except ImportError:
    # python-dotenv not installed, continue without it
    logger = logging.getLogger(__name__)
    logger.debug("python-dotenv not available, skipping .env file loading")

# Configure structured logging
logger = logging.getLogger(__name__)

_ANON_PREFIX = "anon"
_DEFAULT_TTL = 900  # seconds (15 minutes for metadata)
_DEFAULT_PRESIGN_EXPIRES = 3600  # seconds (1 hour for presigned URLs)

# ─────────────────────────────────────────────────────────────────────
# Default factories
# ─────────────────────────────────────────────────────────────────────
def _default_storage_factory() -> Callable[[], AsyncContextManager]:
    """Return a zero-arg callable that yields an async ctx-mgr S3 client."""
    from .provider_factory import factory_for_env
    return factory_for_env()  # Defaults to memory provider


def _default_session_factory() -> Callable[[], AsyncContextManager]:
    """Return a zero-arg callable that yields an async ctx-mgr session store."""
    from chuk_sessions.provider_factory import factory_for_env
    return factory_for_env()  # Defaults to memory provider


# ─────────────────────────────────────────────────────────────────────
class ArtifactStoreError(Exception):
    """Base exception for artifact store operations."""
    pass


class ArtifactNotFoundError(ArtifactStoreError):
    """Raised when an artifact cannot be found."""
    pass


class ArtifactExpiredError(ArtifactStoreError):
    """Raised when an artifact has expired."""
    pass


class ArtifactCorruptedError(ArtifactStoreError):
    """Raised when artifact metadata is corrupted."""
    pass


class ProviderError(ArtifactStoreError):
    """Raised when the storage provider encounters an error."""
    pass


class SessionError(ArtifactStoreError):
    """Raised when the session provider encounters an error."""
    pass


# ─────────────────────────────────────────────────────────────────────
class ArtifactStore:
    """
    Asynchronous artifact storage with session provider abstraction.
    
    Parameters
    ----------
    bucket : str
        Storage bucket/container name
    s3_factory : Callable[[], AsyncContextManager], optional
        Custom S3 client factory
    storage_provider : str, optional   
        Storage provider name (memory, s3, ibm_cos, filesystem, etc.)
    session_factory : Callable[[], AsyncContextManager], optional
        Custom session store factory
    session_provider : str, optional
        Session provider name (memory, redis, etc.)
    max_retries : int, optional
        Maximum retry attempts for storage operations (default: 3)
        
    Notes
    -----
    Uses session provider abstraction instead of direct Redis connection.
    This allows for pluggable metadata storage (Redis, memory, etc.).
    
    Defaults to memory for both storage and session providers for zero-config setup.
    """

    def __init__(
        self,
        *,
        bucket: Optional[str] = None,
        s3_factory: Optional[Callable[[], AsyncContextManager]] = None,
        storage_provider: Optional[str] = None,
        session_factory: Optional[Callable[[], AsyncContextManager]] = None,
        session_provider: Optional[str] = None,
        max_retries: int = 3,
        # Backward compatibility - deprecated but still supported
        redis_url: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        # Read from environment variables with memory as defaults
        bucket = bucket or os.getenv("ARTIFACT_BUCKET", "mcp-bucket")
        storage_provider = storage_provider or os.getenv("ARTIFACT_PROVIDER", "memory")
        session_provider = session_provider or os.getenv("SESSION_PROVIDER", "memory")
        
        # Handle backward compatibility
        if redis_url is not None:
            import warnings
            warnings.warn(
                "redis_url parameter is deprecated. Use session_provider='redis' "
                "and set SESSION_REDIS_URL environment variable instead.",
                DeprecationWarning,
                stacklevel=2
            )
            os.environ["SESSION_REDIS_URL"] = redis_url  # Force set, don't use setdefault
            session_provider = "redis"  # Force redis when redis_url is provided
            
        if provider is not None:
            import warnings
            warnings.warn(
                "provider parameter is deprecated. Use storage_provider instead.",
                DeprecationWarning,
                stacklevel=2
            )
            storage_provider = provider

        # Validate factory/provider combinations
        if s3_factory and storage_provider:
            raise ValueError("Specify either s3_factory or storage_provider—not both")
        if session_factory and session_provider:
            raise ValueError("Specify either session_factory or session_provider—not both")

        # Initialize storage factory
        if s3_factory:
            self._s3_factory = s3_factory
        elif storage_provider:
            self._s3_factory = self._load_storage_provider(storage_provider)
        else:
            self._s3_factory = _default_storage_factory()

        # Initialize session factory
        if session_factory:
            self._session_factory = session_factory
        elif session_provider:
            self._session_factory = self._load_session_provider(session_provider)
        else:
            self._session_factory = _default_session_factory()

        self.bucket = bucket
        self.max_retries = max_retries
        self._storage_provider_name = storage_provider or "memory"
        self._session_provider_name = session_provider or "memory"
        self._closed = False

        logger.info(
            "ArtifactStore initialized",
            extra={
                "bucket": bucket,
                "storage_provider": self._storage_provider_name,
                "session_provider": self._session_provider_name,
            }
        )

    # ─────────────────────────────────────────────────────────────────
    # Core storage operations
    # ─────────────────────────────────────────────────────────────────

    async def store(
        self,
        data: bytes,
        *,
        mime: str,
        summary: str,
        meta: Dict[str, Any] | None = None,
        filename: str | None = None,
        session_id: str | None = None,
        ttl: int = _DEFAULT_TTL,
    ) -> str:
        """
        Store artifact data with metadata.
        
        Parameters
        ----------
        data : bytes
            The artifact data to store
        mime : str
            MIME type of the artifact
        summary : str
            Human-readable description
        meta : dict, optional
            Additional metadata
        filename : str, optional
            Original filename
        session_id : str, optional
            Session identifier for organization
        ttl : int, optional
            Metadata TTL in seconds
            
        Returns
        -------
        str
            Unique artifact identifier
            
        Raises
        ------
        ProviderError
            If storage operation fails
        SessionError
            If metadata caching fails
        """
        if self._closed:
            raise ArtifactStoreError("Store has been closed")
            
        start_time = time.time()
        artifact_id = uuid.uuid4().hex
        
        # ✅ FIX: Use underscore instead of colon for IBM COS presigned URL compatibility
        scope = session_id or f"{_ANON_PREFIX}_{artifact_id}"
        key = f"sess/{scope}/{artifact_id}"

        try:
            # Store in object storage with retries
            await self._store_with_retry(data, key, mime, filename, scope)

            # Build metadata record
            record = {
                "scope": scope,
                "key": key,
                "mime": mime,
                "summary": summary,
                "meta": meta or {},
                "filename": filename,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "stored_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "ttl": ttl,
                "storage_provider": self._storage_provider_name,
                "session_provider": self._session_provider_name,
            }

            # Cache metadata using session provider
            session_ctx_mgr = self._session_factory()
            async with session_ctx_mgr as session:
                await session.setex(artifact_id, ttl, json.dumps(record))

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "Artifact stored successfully",
                extra={
                    "artifact_id": artifact_id,
                    "bytes": len(data),
                    "mime": mime,
                    "duration_ms": duration_ms,
                    "storage_provider": self._storage_provider_name,
                }
            )

            return artifact_id

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Artifact storage failed",
                extra={
                    "artifact_id": artifact_id,
                    "error": str(e),
                    "duration_ms": duration_ms,
                    "storage_provider": self._storage_provider_name,
                },
                exc_info=True
            )
            
            if "session" in str(e).lower() or "redis" in str(e).lower():
                raise SessionError(f"Metadata caching failed: {e}") from e
            else:
                raise ProviderError(f"Storage operation failed: {e}") from e

    async def _store_with_retry(self, data: bytes, key: str, mime: str, filename: str, scope: str):
        """Store data with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                storage_ctx_mgr = self._s3_factory()
                async with storage_ctx_mgr as s3:
                    await s3.put_object(
                        Bucket=self.bucket,
                        Key=key,
                        Body=data,
                        ContentType=mime,
                        Metadata={"filename": filename or "", "scope": scope},
                    )
                return  # Success
                
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        f"Storage attempt {attempt + 1} failed, retrying in {wait_time}s",
                        extra={"error": str(e), "attempt": attempt + 1}
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All {self.max_retries} storage attempts failed")
        
        raise last_exception

    async def retrieve(self, artifact_id: str) -> bytes:
        """
        Retrieve artifact data directly.
        
        Parameters
        ----------
        artifact_id : str
            The artifact identifier
            
        Returns
        -------
        bytes
            The artifact data
            
        Raises
        ------
        ArtifactNotFoundError
            If artifact doesn't exist or has expired
        ProviderError
            If retrieval fails
        """
        if self._closed:
            raise ArtifactStoreError("Store has been closed")
            
        start_time = time.time()
        
        try:
            record = await self._get_record(artifact_id)
            
            storage_ctx_mgr = self._s3_factory()
            async with storage_ctx_mgr as s3:
                response = await s3.get_object(Bucket=self.bucket, Key=record["key"])
                
                # Handle different response formats from different providers
                if hasattr(response["Body"], "read"):
                    # For aioboto3, Body is a StreamingBody
                    data = await response["Body"].read()
                elif isinstance(response["Body"], bytes):
                    # For some providers, Body is already bytes
                    data = response["Body"]
                else:
                    # Convert to bytes if needed
                    data = bytes(response["Body"])
                
                # Verify integrity if SHA256 is available
                if "sha256" in record:
                    computed_hash = hashlib.sha256(data).hexdigest()
                    if computed_hash != record["sha256"]:
                        raise ArtifactCorruptedError(
                            f"SHA256 mismatch: expected {record['sha256']}, got {computed_hash}"
                        )
                
                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    "Artifact retrieved successfully",
                    extra={
                        "artifact_id": artifact_id,
                        "bytes": len(data),
                        "duration_ms": duration_ms,
                    }
                )
                
                return data
                
        except (ArtifactNotFoundError, ArtifactExpiredError, ArtifactCorruptedError):
            raise
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Artifact retrieval failed",
                extra={
                    "artifact_id": artifact_id,
                    "error": str(e),
                    "duration_ms": duration_ms,
                }
            )
            raise ProviderError(f"Retrieval failed: {e}") from e

    # ─────────────────────────────────────────────────────────────────
    # Presigned URL operations
    # ─────────────────────────────────────────────────────────────────

    async def presign(self, artifact_id: str, expires: int = _DEFAULT_PRESIGN_EXPIRES) -> str:
        """
        Generate a presigned URL for artifact download.
        
        Parameters
        ----------
        artifact_id : str
            The artifact identifier
        expires : int, optional
            URL expiration time in seconds (default: 1 hour)
            
        Returns
        -------
        str
            Presigned URL for downloading the artifact
            
        Raises
        ------
        ArtifactNotFoundError
            If artifact doesn't exist or has expired
        NotImplementedError
            If provider doesn't support presigned URLs
        """
        if self._closed:
            raise ArtifactStoreError("Store has been closed")
            
        start_time = time.time()
        
        try:
            record = await self._get_record(artifact_id)
            
            storage_ctx_mgr = self._s3_factory()
            async with storage_ctx_mgr as s3:
                url = await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": record["key"]},
                    ExpiresIn=expires,
                )
                
                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    "Presigned URL generated",
                    extra={
                        "artifact_id": artifact_id,
                        "expires_in": expires,
                        "duration_ms": duration_ms,
                    }
                )
                
                return url
                
        except (ArtifactNotFoundError, ArtifactExpiredError):
            raise
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Presigned URL generation failed",
                extra={
                    "artifact_id": artifact_id,
                    "error": str(e),
                    "duration_ms": duration_ms,
                }
            )
            
            if "oauth" in str(e).lower() or "credential" in str(e).lower():
                raise NotImplementedError(
                    "This provider cannot generate presigned URLs with the "
                    "current credential type (e.g. OAuth). Use HMAC creds instead."
                ) from e
            else:
                raise ProviderError(f"Presigned URL generation failed: {e}") from e

    async def presign_short(self, artifact_id: str) -> str:
        """Generate a short-lived presigned URL (15 minutes)."""
        return await self.presign(artifact_id, expires=900)
    
    async def presign_medium(self, artifact_id: str) -> str:
        """Generate a medium-lived presigned URL (1 hour)."""
        return await self.presign(artifact_id, expires=3600)
    
    async def presign_long(self, artifact_id: str) -> str:
        """Generate a long-lived presigned URL (24 hours)."""
        return await self.presign(artifact_id, expires=86400)

    # ─────────────────────────────────────────────────────────────────
    # Metadata and utility operations
    # ─────────────────────────────────────────────────────────────────

    async def metadata(self, artifact_id: str) -> Dict[str, Any]:
        """
        Get artifact metadata.
        
        Parameters
        ----------
        artifact_id : str
            The artifact identifier
            
        Returns
        -------
        dict
            Artifact metadata
            
        Raises
        ------
        ArtifactNotFoundError
            If artifact doesn't exist or has expired
        """
        return await self._get_record(artifact_id)

    async def exists(self, artifact_id: str) -> bool:
        """
        Check if artifact exists and hasn't expired.
        
        Parameters
        ----------
        artifact_id : str
            The artifact identifier
            
        Returns
        -------
        bool
            True if artifact exists, False otherwise
        """
        try:
            await self._get_record(artifact_id)
            return True
        except (ArtifactNotFoundError, ArtifactExpiredError):
            return False

    async def delete(self, artifact_id: str) -> bool:
        """
        Delete artifact and its metadata.
        
        Parameters
        ----------
        artifact_id : str
            The artifact identifier
            
        Returns
        -------
        bool
            True if deleted, False if not found
        """
        if self._closed:
            raise ArtifactStoreError("Store has been closed")
            
        try:
            record = await self._get_record(artifact_id)
            
            # Delete from object storage
            storage_ctx_mgr = self._s3_factory()
            async with storage_ctx_mgr as s3:
                await s3.delete_object(Bucket=self.bucket, Key=record["key"])
            
            # Delete metadata from session store
            session_ctx_mgr = self._session_factory()
            async with session_ctx_mgr as session:
                if hasattr(session, 'delete'):
                    await session.delete(artifact_id)
                else:
                    logger.warning(
                        "Session provider doesn't support delete operation",
                        extra={"artifact_id": artifact_id, "provider": self._session_provider_name}
                    )
            
            logger.info("Artifact deleted", extra={"artifact_id": artifact_id})
            return True
            
        except (ArtifactNotFoundError, ArtifactExpiredError):
            logger.warning("Attempted to delete non-existent artifact", extra={"artifact_id": artifact_id})
            return False
        except Exception as e:
            logger.error(
                "Artifact deletion failed",
                extra={"artifact_id": artifact_id, "error": str(e)}
            )
            raise ProviderError(f"Deletion failed: {e}") from e

    # ─────────────────────────────────────────────────────────────────
    # Batch operations
    # ─────────────────────────────────────────────────────────────────

    async def store_batch(
        self,
        items: List[Dict[str, Any]],
        session_id: str | None = None,
        ttl: int = _DEFAULT_TTL,
    ) -> List[str]:
        """
        Store multiple artifacts in a batch operation.
        
        Parameters
        ----------
        items : list
            List of dicts with keys: data, mime, summary, meta, filename
        session_id : str, optional
            Session identifier for all artifacts
        ttl : int, optional
            Metadata TTL for all artifacts
            
        Returns
        -------
        list
            List of artifact IDs
            
        Notes
        -----
        This method doesn't use session provider batching since our session
        interface doesn't define batch operations. Each metadata record is
        stored individually through the session provider.
        """
        if self._closed:
            raise ArtifactStoreError("Store has been closed")
            
        artifact_ids = []
        failed_items = []
        
        for i, item in enumerate(items):
            try:
                artifact_id = uuid.uuid4().hex
                scope = session_id or f"{_ANON_PREFIX}_{artifact_id}"
                key = f"sess/{scope}/{artifact_id}"
                
                # Store in object storage
                await self._store_with_retry(
                    item["data"], key, item["mime"], 
                    item.get("filename"), scope
                )
                
                # Prepare metadata record
                record = {
                    "scope": scope,
                    "key": key,
                    "mime": item["mime"],
                    "summary": item["summary"],
                    "meta": item.get("meta", {}),
                    "filename": item.get("filename"),
                    "bytes": len(item["data"]),
                    "sha256": hashlib.sha256(item["data"]).hexdigest(),
                    "stored_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    "ttl": ttl,
                    "storage_provider": self._storage_provider_name,
                    "session_provider": self._session_provider_name,
                }
                
                # Store metadata via session provider
                session_ctx_mgr = self._session_factory()
                async with session_ctx_mgr as session:
                    await session.setex(artifact_id, ttl, json.dumps(record))
                
                artifact_ids.append(artifact_id)
                
            except Exception as e:
                logger.error(f"Batch item {i} failed: {e}")
                failed_items.append(i)
                artifact_ids.append(None)  # Placeholder
        
        if failed_items:
            logger.warning(f"Batch operation completed with {len(failed_items)} failures")
        
        return artifact_ids

    # ─────────────────────────────────────────────────────────────────
    # Administrative and debugging
    # ─────────────────────────────────────────────────────────────────

    async def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate store configuration and connectivity.
        
        Returns
        -------
        dict
            Validation results for session provider and storage provider
        """
        results = {"timestamp": datetime.utcnow().isoformat() + "Z"}
        
        # Test session provider
        try:
            session_ctx_mgr = self._session_factory()
            async with session_ctx_mgr as session:
                # Test basic operations
                test_key = f"test_{uuid.uuid4().hex}"
                await session.setex(test_key, 10, "test_value")
                value = await session.get(test_key)
                
                if value == "test_value":
                    results["session"] = {
                        "status": "ok", 
                        "provider": self._session_provider_name
                    }
                else:
                    results["session"] = {
                        "status": "error", 
                        "message": "Session store test failed",
                        "provider": self._session_provider_name
                    }
        except Exception as e:
            results["session"] = {
                "status": "error", 
                "message": str(e),
                "provider": self._session_provider_name
            }
        
        # Test storage provider
        try:
            storage_ctx_mgr = self._s3_factory()
            async with storage_ctx_mgr as s3:
                await s3.head_bucket(Bucket=self.bucket)
            results["storage"] = {
                "status": "ok", 
                "bucket": self.bucket, 
                "provider": self._storage_provider_name
            }
        except Exception as e:
            results["storage"] = {
                "status": "error", 
                "message": str(e), 
                "provider": self._storage_provider_name
            }
        
        return results

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns
        -------
        dict
            Statistics about the store
            
        Notes
        -----
        Statistics are limited since session providers don't expose
        detailed metrics in a standardized way.
        """
        return {
            "storage_provider": self._storage_provider_name,
            "session_provider": self._session_provider_name,
            "bucket": self.bucket,
            "max_retries": self.max_retries,
            "closed": self._closed,
        }

    # ─────────────────────────────────────────────────────────────────
    # Resource management
    # ─────────────────────────────────────────────────────────────────

    async def close(self):
        """Mark store as closed."""
        if not self._closed:
            self._closed = True
            logger.info("ArtifactStore closed")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # ─────────────────────────────────────────────────────────────────
    # Helper functions
    # ─────────────────────────────────────────────────────────────────

    def _load_storage_provider(self, name: str) -> Callable[[], AsyncContextManager]:
        """Load storage provider by name."""
        from importlib import import_module

        try:
            mod: ModuleType = import_module(f"chuk_artifacts.providers.{name}")
        except ModuleNotFoundError as exc:
            raise ValueError(f"Unknown storage provider '{name}'") from exc

        if not hasattr(mod, "factory"):
            raise AttributeError(f"Storage provider '{name}' lacks factory()")
        
        logger.info(f"Loaded storage provider: {name}")
        # For storage providers, factory() returns a factory function, so we call it
        return mod.factory()  # type: ignore[return-value]

    def _load_session_provider(self, name: str) -> Callable[[], AsyncContextManager]:
        """Load session provider by name."""
        from importlib import import_module

        try:
            mod: ModuleType = import_module(f"chuk_sessions.providers.{name}")
        except ModuleNotFoundError as exc:
            raise ValueError(f"Unknown session provider '{name}'") from exc

        if not hasattr(mod, "factory"):
            raise AttributeError(f"Session provider '{name}' lacks factory()")
        
        logger.info(f"Loaded session provider: {name}")
        # Call the factory to get the actual context manager factory
        return mod.factory()  # type: ignore[return-value]

    async def _get_record(self, artifact_id: str) -> Dict[str, Any]:
        """
        Retrieve artifact metadata from session provider with enhanced error handling.
        
        Parameters
        ----------
        artifact_id : str
            The artifact identifier
            
        Returns
        -------
        dict
            Artifact metadata record
            
        Raises
        ------
        ArtifactNotFoundError
            If artifact doesn't exist
        ArtifactExpiredError  
            If artifact has expired
        ArtifactCorruptedError
            If metadata is corrupted
        SessionError
            If session provider fails
        """
        try:
            session_ctx_mgr = self._session_factory()
            async with session_ctx_mgr as session:
                raw = await session.get(artifact_id)
        except Exception as e:
            raise SessionError(f"Session provider error retrieving {artifact_id}: {e}") from e
        
        if raw is None:
            # Could be expired or never existed - we can't distinguish without additional metadata
            raise ArtifactNotFoundError(f"Artifact {artifact_id} not found or expired")
        
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted metadata for artifact {artifact_id}: {e}")
            # Note: We can't clean up corrupted entries since session providers
            # don't expose delete in their interface. This would need to be
            # handled by the session provider implementation.
            raise ArtifactCorruptedError(f"Corrupted metadata for artifact {artifact_id}") from e
        

    async def presign_upload(
        self, 
        session_id: str | None = None,
        filename: str | None = None,
        mime_type: str = "application/octet-stream",
        expires: int = _DEFAULT_PRESIGN_EXPIRES
    ) -> tuple[str, str]:
        """
        Generate a presigned URL for uploading a new artifact.
        
        Parameters
        ----------
        session_id : str, optional
            Session identifier for organization
        filename : str, optional
            Suggested filename for the artifact
        mime_type : str, optional
            Expected MIME type of the upload
        expires : int, optional
            URL expiration time in seconds (default: 1 hour)
            
        Returns
        -------
        tuple
            (presigned_upload_url, artifact_id) - Use the artifact_id to reference the uploaded file
            
        Raises
        ------
        NotImplementedError
            If provider doesn't support presigned URLs
        ProviderError
            If presigned URL generation fails
        """
        if self._closed:
            raise ArtifactStoreError("Store has been closed")
            
        start_time = time.time()
        
        # Generate artifact ID and key path
        artifact_id = uuid.uuid4().hex
        scope = session_id or f"{_ANON_PREFIX}_{artifact_id}"
        key = f"sess/{scope}/{artifact_id}"
        
        try:
            storage_ctx_mgr = self._s3_factory()
            async with storage_ctx_mgr as s3:
                url = await s3.generate_presigned_url(
                    "put_object",
                    Params={
                        "Bucket": self.bucket, 
                        "Key": key,
                        "ContentType": mime_type
                    },
                    ExpiresIn=expires,
                )
                
                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    "Upload presigned URL generated",
                    extra={
                        "artifact_id": artifact_id,
                        "key": key,
                        "mime_type": mime_type,
                        "expires_in": expires,
                        "duration_ms": duration_ms,
                    }
                )
                
                return url, artifact_id
                
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Upload presigned URL generation failed",
                extra={
                    "artifact_id": artifact_id,
                    "error": str(e),
                    "duration_ms": duration_ms,
                }
            )
            
            if "oauth" in str(e).lower() or "credential" in str(e).lower():
                raise NotImplementedError(
                    "This provider cannot generate presigned URLs with the "
                    "current credential type (e.g. OAuth). Use HMAC creds instead."
                ) from e
            else:
                raise ProviderError(f"Upload presigned URL generation failed: {e}") from e

    async def register_uploaded_artifact(
        self,
        artifact_id: str,
        *,
        mime: str,
        summary: str,
        meta: Dict[str, Any] | None = None,
        filename: str | None = None,
        session_id: str | None = None,
        ttl: int = _DEFAULT_TTL,
    ) -> bool:
        """
        Register metadata for an artifact that was uploaded via presigned URL.
        
        Call this after a successful upload using a presigned URL to make the
        artifact discoverable through the normal store methods.
        
        Parameters
        ----------
        artifact_id : str
            The artifact ID returned from presign_upload()
        mime : str
            MIME type of the uploaded artifact
        summary : str
            Human-readable description
        meta : dict, optional
            Additional metadata
        filename : str, optional
            Original filename
        session_id : str, optional
            Session identifier (should match presign_upload call)
        ttl : int, optional
            Metadata TTL in seconds
            
        Returns
        -------
        bool
            True if registration succeeded, False if artifact not found
            
        Raises
        ------
        ProviderError
            If metadata registration fails
        """
        if self._closed:
            raise ArtifactStoreError("Store has been closed")
            
        start_time = time.time()
        
        # Reconstruct the key path
        scope = session_id or f"{_ANON_PREFIX}_{artifact_id}"
        key = f"sess/{scope}/{artifact_id}"
        
        try:
            # Verify the object exists and get its size
            storage_ctx_mgr = self._s3_factory()
            async with storage_ctx_mgr as s3:
                try:
                    response = await s3.head_object(Bucket=self.bucket, Key=key)
                    file_size = response.get('ContentLength', 0)
                except Exception:
                    logger.warning(f"Artifact {artifact_id} not found in storage")
                    return False
            
            # For verification, we could download and hash the file, but that defeats 
            # the purpose of presigned uploads. Instead, we'll compute hash later if needed.
            
            # Build metadata record
            record = {
                "scope": scope,
                "key": key,
                "mime": mime,
                "summary": summary,
                "meta": meta or {},
                "filename": filename,
                "bytes": file_size,
                "sha256": None,  # We don't have the hash since we didn't upload it directly
                "stored_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "ttl": ttl,
                "storage_provider": self._storage_provider_name,
                "session_provider": self._session_provider_name,
                "uploaded_via_presigned": True,  # Flag to indicate upload method
            }

            # Cache metadata using session provider
            session_ctx_mgr = self._session_factory()
            async with session_ctx_mgr as session:
                await session.setex(artifact_id, ttl, json.dumps(record))

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "Artifact metadata registered after presigned upload",
                extra={
                    "artifact_id": artifact_id,
                    "bytes": file_size,
                    "mime": mime,
                    "duration_ms": duration_ms,
                }
            )

            return True

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Artifact metadata registration failed",
                extra={
                    "artifact_id": artifact_id,
                    "error": str(e),
                    "duration_ms": duration_ms,
                }
            )
            
            if "session" in str(e).lower() or "redis" in str(e).lower():
                raise SessionError(f"Metadata registration failed: {e}") from e
            else:
                raise ProviderError(f"Metadata registration failed: {e}") from e

    async def presign_upload_and_register(
        self,
        *,
        mime: str,
        summary: str,
        meta: Dict[str, Any] | None = None,
        filename: str | None = None,
        session_id: str | None = None,
        ttl: int = _DEFAULT_TTL,
        expires: int = _DEFAULT_PRESIGN_EXPIRES
    ) -> tuple[str, str]:
        """
        Convenience method that combines presign_upload and pre-registers metadata.
        
        This creates the presigned URL and immediately registers the metadata,
        so the artifact becomes discoverable as soon as it's uploaded.
        
        Returns
        -------
        tuple
            (presigned_upload_url, artifact_id)
        """
        # Generate presigned URL
        upload_url, artifact_id = await self.presign_upload(
            session_id=session_id,
            filename=filename,
            mime_type=mime,
            expires=expires
        )
        
        # Pre-register metadata (with unknown file size)
        await self.register_uploaded_artifact(
            artifact_id,
            mime=mime,
            summary=summary,
            meta=meta,
            filename=filename,
            session_id=session_id,
            ttl=ttl
        )
        
        return upload_url, artifact_id
# -*- coding: utf-8 -*-
# chuk_artifacts/models.py
from typing import Any, Dict, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class ArtifactEnvelope(BaseModel):
    """
    A tiny, model-friendly wrapper describing a stored artefact.

    The *bytes*, *mime_type*, etc. let the UI reason about the file
    without ever uploading the raw payload into the chat context.
    """

    success: bool = True
    artifact_id: str  # opaque handle for look-ups
    mime_type: str  # e.g. "image/png", "text/csv"
    bytes: int  # size on disk
    summary: str  # human-readable description / alt
    meta: Dict[str, Any] = Field(default_factory=dict)

    # Pydantic V2 configuration using ConfigDict
    model_config = ConfigDict(extra="allow")  # future-proof: lets tools add keys


class ArtifactMetadata(BaseModel):
    """
    Complete metadata record for a stored artifact.

    This is the canonical structure stored in the session provider (Redis/memory)
    and used throughout the system for artifact tracking.

    Supports both attribute access (metadata.key) and dict-style access (metadata["key"])
    for backwards compatibility.

    Storage Scopes:
    - session: Ephemeral, tied to a session (default, 15min-24h TTL)
    - user: Persistent, tied to a user (long/no TTL)
    - sandbox: Shared across sandbox (long/no TTL)
    """

    artifact_id: str
    session_id: str
    sandbox_id: str
    key: str  # Storage key (grid path)
    mime: str  # MIME type
    summary: str  # Human-readable description
    meta: Dict[str, Any] = Field(default_factory=dict)  # User-defined metadata
    filename: Optional[str] = None
    bytes: int = Field(ge=0)  # File size in bytes (must be >= 0)
    sha256: Optional[str] = None  # SHA-256 hash (optional for presigned uploads)
    stored_at: str  # ISO 8601 datetime string
    ttl: int = Field(gt=0)  # Time-to-live in seconds (must be > 0)
    storage_provider: str  # e.g., "s3", "filesystem", "memory"
    session_provider: str  # e.g., "redis", "memory"

    # Scope-based storage (Phase 1 expansion)
    scope: Literal["session", "user", "sandbox"] = Field(
        default="session",
        description="Storage scope: session (ephemeral), user (persistent), or sandbox (shared)",
    )
    owner_id: Optional[str] = Field(
        None,
        description="Owner identifier - user_id for user scope, None for session/sandbox scope",
    )

    # Optional fields for specific upload methods
    batch_operation: Optional[bool] = None
    batch_index: Optional[int] = None
    uploaded_via_presigned: Optional[bool] = None
    updated_at: Optional[str] = None  # ISO 8601 datetime string

    model_config = ConfigDict(
        extra="allow"
    )  # Allow additional fields for extensibility

    @field_validator("bytes")
    @classmethod
    def validate_bytes(cls, v: int) -> int:
        """Ensure bytes is non-negative."""
        if v < 0:
            raise ValueError("bytes must be non-negative")
        return v

    @field_validator("ttl")
    @classmethod
    def validate_ttl(cls, v: int) -> int:
        """Ensure TTL is positive."""
        if v <= 0:
            raise ValueError("ttl must be positive")
        return v

    # Backwards compatibility: dict-like access
    def __getitem__(self, key: str) -> Any:
        """Support dict-style access for backwards compatibility."""
        try:
            return getattr(self, key)
        except AttributeError:
            # Check in extra fields (allowed by extra="allow")
            extra = getattr(self, "__pydantic_extra__", None)
            if extra and key in extra:
                return extra[key]
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        """Support dict.get() for backwards compatibility."""
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        """Support dict.keys() for backwards compatibility."""
        return self.model_dump().keys()

    def values(self):
        """Support dict.values() for backwards compatibility."""
        return self.model_dump().values()

    def items(self):
        """Support dict.items() for backwards compatibility."""
        return self.model_dump().items()


class GridKeyComponents(BaseModel):
    """
    Parsed components of a grid storage key.

    Grid keys follow the pattern: grid/{sandbox_id}/{session_id}/{artifact_id}[/{subpath}]

    Supports both attribute access (components.sandbox_id) and dict-style access
    (components["sandbox_id"]) for backwards compatibility.
    """

    sandbox_id: str = Field(min_length=1, description="Sandbox identifier")
    session_id: str = Field(min_length=1, description="Session identifier")
    artifact_id: str = Field(min_length=1, description="Artifact identifier")
    subpath: Optional[str] = Field(None, description="Optional subpath within artifact")

    model_config = ConfigDict(frozen=True)  # Make immutable

    @field_validator("sandbox_id", "session_id", "artifact_id")
    @classmethod
    def validate_no_slashes(cls, v: str) -> str:
        """Ensure components don't contain slashes."""
        if "/" in v:
            raise ValueError(f"Grid component cannot contain '/': {v!r}")
        return v

    # Backwards compatibility: dict-like access
    def __getitem__(self, key: str) -> Any:
        """Support dict-style access for backwards compatibility."""
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        """Support dict.get() for backwards compatibility."""
        try:
            return self[key]
        except KeyError:
            return default


class BatchStoreItem(BaseModel):
    """
    Input item for batch store operations.

    Defines the required structure for each item in a batch upload.
    """

    data: bytes = Field(description="Raw file data")
    mime: str = Field(min_length=1, description="MIME type (e.g., 'image/png')")
    summary: str = Field(description="Human-readable description")
    meta: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")
    filename: Optional[str] = Field(None, description="Optional filename")

    model_config = ConfigDict(arbitrary_types_allowed=True)  # Allow bytes type

    @field_validator("data")
    @classmethod
    def validate_data(cls, v: bytes) -> bytes:
        """Ensure data is not empty."""
        if len(v) == 0:
            raise ValueError("data cannot be empty")
        return v


class AccessContext(BaseModel):
    """
    Context for access control checks.

    Represents the identity of the requestor attempting to access an artifact.
    """

    user_id: Optional[str] = Field(None, description="User ID of the requestor")
    session_id: Optional[str] = Field(None, description="Session ID of the requestor")
    sandbox_id: str = Field(description="Sandbox ID (must match artifact's sandbox)")

    model_config = ConfigDict(frozen=True)  # Immutable for security

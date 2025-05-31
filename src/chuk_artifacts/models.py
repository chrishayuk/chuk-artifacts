# -*- coding: utf-8 -*-
# chuk_artifacts/models.py
from typing import Any, Dict
from pydantic import BaseModel, Field


class ArtifactEnvelope(BaseModel):
    """
    A tiny, model-friendly wrapper describing a stored artefact.

    The *bytes*, *mime_type*, etc. let the UI reason about the file
    without ever uploading the raw payload into the chat context.
    """

    success: bool = True
    artifact_id: str                        # opaque handle for look-ups
    mime_type: str                          # e.g. "image/png", "text/csv"
    bytes: int                              # size on disk
    summary: str                            # human-readable description / alt
    meta: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"                     # future-proof: lets tools add keys

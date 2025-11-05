# CHUK Artifacts

> **Scope-based artifact storage with persistent user files, secure sessions, and presigned uploads—built for AI apps and MCP servers**

[![PyPI version](https://img.shields.io/pypi/v/chuk-artifacts)](https://pypi.org/project/chuk-artifacts/)
[![Python](https://img.shields.io/pypi/pyversions/chuk-artifacts.svg)](https://pypi.org/project/chuk-artifacts/)
[![Tests](https://img.shields.io/badge/tests-742%20passing-success.svg)](#testing)
[![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen.svg)](#testing)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Async](https://img.shields.io/badge/async-await-green.svg)](https://docs.python.org/3/library/asyncio.html)

CHUK Artifacts provides a unified, async API for storing and retrieving files ("artifacts") across local development and production cloud environments. Store ephemeral session files, persistent user documents, and shared resources—all with automatic access control, grid-based organization, and presigned upload/download URLs for secure client-side storage interaction.

---

## Table of Contents

- [Architecture at a Glance](#architecture-at-a-glance)
  - [Layered Architecture](#layered-architecture)
- [Why This Exists](#why-this-exists)
- [Design Guarantees](#design-guarantees)
- [Install](#install)
- [Quick Start](#quick-start)
- [Providers & Sessions](#providers--sessions)
- [Core Concepts](#core-concepts)
- [Storage Scopes](#storage-scopes)
- [Common Recipes](#common-recipes)
- [Streaming Operations](#streaming-operations)
- [Multipart Uploads](#multipart-uploads)
- [Configuration](#configuration)
- [Advanced Features](#advanced-features)
- [Error Handling](#error-handling)
- [Security](#security)
- [Performance](#performance)
- [Testing](#testing)
- [Configuration Reference](#configuration-reference)
- [FAQ](#faq)
- [Roadmap](#roadmap)

---

## Architecture at a Glance

Your app talks to `ArtifactStore`; it enforces session rules and issues presigned URLs. The **Virtual Filesystem (VFS)** layer provides a unified storage interface with streaming, progress tracking, and security features. Clients upload/download directly to storage—no credentials exposed, no proxying large file streams.

```
                         (Your App / MCP Server)
                                     │
                                     │  ArtifactStore API (async)
                                     ▼
┌───────────────────────────────────────────────────────────────┐
│                        ArtifactStore                           │
│                   (Policy & Access Control)                   │
│                                                               │
│  • Enforces session boundaries & user permissions             │
│  • Manages scopes (session/user/sandbox)                      │
│  • Issues presigned upload/download URLs                       │
└───────────────┬───────────────────────────┬────────────────────┘
                │                           │
                │ session lookup            │ read/write files
                │                           │
                ▼                           ▼
        ┌────────────┐       ┌──────────────────────────────────┐
        │  Sessions  │       │      Virtual Filesystem (VFS)     │
        │  (Redis)   │       │   (Unified Storage Interface)     │
        └─────┬──────┘       │                                   │
              │              │  • Streaming support               │
              │ authz        │  • Progress callbacks              │
              │              │  • Security profiles               │
              ▼              │  • Quota management                │
        (session_id)         └────────┬──────────┬───────┬───────┘
                                      │          │       │
                                      │ storage  │       │
                                      ▼          ▼       ▼
                          ┌─────────────────────────────────────┐
                          │      Storage Backends                │
                          │                                      │
                          │  Memory  │  Filesystem  │  S3  │  SQLite │
                          └──────────────────────────────────────┘
                                      │
                                      ▼
                          grid/{sandbox}/{session}/{artifact}
```

**Caption**: The application calls ArtifactStore (policy layer); the store consults the session provider for authz and uses the VFS layer for unified storage operations. VFS provides streaming, progress tracking, and security features across all storage backends. Clients use short-lived presigned URLs for direct uploads/downloads.

### Layered Architecture

CHUK Artifacts uses a clean **separation of concerns** across three layers:

**1. Policy Layer (ArtifactStore)**
- Access control and user permissions
- Session isolation and scope management
- TTL enforcement and cleanup
- Presigned URL generation
- Grid path organization

**2. Storage Abstraction Layer ([chuk-virtual-fs](https://github.com/chrishayuk/chuk-virtual-fs))**
- Unified interface across storage backends
- Streaming support for large files
- Progress callbacks for uploads/downloads
- Security profiles and quota management
- Atomic operations and safety guarantees

**3. Storage Backends**
- `vfs-memory`: In-memory (development/testing)
- `vfs-filesystem`: Local disk (small deployments)
- `vfs-s3`: AWS S3 or S3-compatible (production)
- `vfs-sqlite`: SQLite with structured queries

**Benefits of this architecture:**
- 🔒 **Security**: Policy decisions separate from storage mechanics
- 🔄 **Portability**: Swap backends without code changes
- 🚀 **Performance**: Streaming and progress tracking built-in
- 🧪 **Testability**: Memory backend for instant tests
- 📈 **Scalability**: Production backends (S3) ready out of the box

---

## Why This Exists

Most platforms offer object storage (S3, COS, FS)—but not a **security boundary** or a **unified storage interface**.

**What CHUK Artifacts is (and isn't):**

CHUK Artifacts is **not**:
- ❌ A CDN or media processing pipeline
- ❌ A local file syncing tool
- ❌ A database for blobs
- ❌ A framework-specific storage layer (Django, Supabase, Firebase)

CHUK Artifacts **is**:
- ✅ A multi-scope storage system (ephemeral, persistent, shared)
- ✅ A security and access control layer over object storage
- ✅ A unified API across Memory / FS / S3 / SQLite (via [chuk-virtual-fs](https://github.com/chrishayuk/chuk-virtual-fs))
- ✅ A presigned upload workflow system with streaming support
- ✅ A grid-based storage architecture for multi-tenant AI apps

---

**Why not just use S3 directly?**

- ❌ No session isolation—files from different users/tenants can collide
- ❌ No consistent API across dev (memory) → staging (filesystem) → prod (S3)
- ❌ Grid paths must be manually constructed and enforced
- ❌ Presigned URL generation requires understanding each provider's SDK
- ❌ No built-in metadata tracking with TTL expiration

**CHUK Artifacts provides:**
- ✅ **Three storage scopes** - Session (ephemeral), User (persistent), Sandbox (shared)
- ✅ **Access control** - User-based permissions with automatic enforcement
- ✅ **Search functionality** - Find artifacts by user, MIME type, or custom metadata
- ✅ **Predictable grid paths** - Scope-based organization for infinite scale
- ✅ **Unified API** - Same code works across Memory, Filesystem, S3, IBM COS
- ✅ **Presigned URLs** - Secure direct upload/download without exposing credentials
- ✅ **Async-first** - Built for FastAPI, MCP servers, and modern Python apps
- ✅ **Zero-config defaults** - Memory provider works immediately; production via env vars

### Design Guarantees

CHUK Artifacts provides strong guarantees for production systems:

- 🔒 **Every artifact belongs to exactly one session** - No ambiguity, no collisions
- 🚫 **Cross-session access is blocked at the API layer** - Enforced by design, not configuration
- 📍 **Grid paths are deterministic and auditable** - `grid/{sandbox}/{session}/{artifact}` always
- 🔄 **Storage backend is swappable with zero code changes** - Environment variables only
- 🔗 **Presigned URLs enable secure client uploads without trust** - No credentials exposed to clients

These guarantees make CHUK Artifacts safe for multi-tenant AI applications, MCP servers, and enterprise deployments.

---

## Install

```bash
pip install chuk-artifacts
```

or with uv:

```bash
uv add chuk-artifacts
```

---

## Quick Start

```python
from chuk_artifacts import ArtifactStore

async with ArtifactStore() as store:
    # Store a file (session auto-created from user_id)
    file_id = await store.store(
        data=b"Hello, world!",
        mime="text/plain",
        summary="greeting",
        filename="hello.txt",
        user_id="alice",  # Auto-generates session like "sess-alice-123-abc"
        ttl=900  # 15 minutes (omit to use default)
    )

    # Generate secure download URL (15 minutes)
    url = await store.presign_short(file_id)

    # Read file content
    text = await store.read_file(file_id, as_text=True)
    assert text == "Hello, world!"

    # Update the file
    await store.update_file(
        file_id,
        data=b"Hello, updated world!",
        summary="Updated greeting"
    )
```

**That's it!** Uses memory provider by default (no AWS credentials, no Redis setup, no configuration files). Perfect for development and testing.

**Session handling**: Pass `user_id` for auto-generated session IDs, or `session_id` for custom formats (see [Sessions](#sessions--security-boundaries) below).

---

## Providers & Sessions

### Storage Providers

CHUK Artifacts supports two types of storage providers:

**🆕 VFS Providers** (Recommended) - Powered by [chuk-virtual-fs](https://github.com/chrishayuk/chuk-virtual-fs)

| Feature                  | vfs-memory | vfs-filesystem | vfs-s3 | vfs-sqlite |
|-------------------------|-----------|----------------|--------|------------|
| **Persistence**         | No        | Yes            | Yes    | Yes        |
| **Horizontal scale**    | No        | Limited        | Yes    | No         |
| **Streaming support**   | ✅ Ready  | ✅ Ready       | ✅ Ready | ✅ Ready  |
| **Progress callbacks**  | ✅ Ready  | ✅ Ready       | ✅ Ready | ✅ Ready  |
| **Virtual mounts**      | ✅ Ready  | ✅ Ready       | ✅ Ready | ✅ Ready  |
| **Setup complexity**    | None      | Minimal        | Moderate | Minimal  |
| **Best use**            | Dev/Test  | Small deploys  | Production | Structured data |

**Legacy Providers** (Backward compatible)

| Feature                  | memory | filesystem | s3 | ibm_cos |
|-------------------------|--------|------------|----|---------|
| **Persistence**         | No     | Yes        | Yes| Yes     |
| **Horizontal scale**    | No     | Limited    | Yes| Yes     |
| **Presigned URLs**      | Virtual* | file://** | HTTPS | HTTPS |
| **Multipart uploads**   | N/A    | No         | Yes (≥5MB) | Yes (≥5MB) |
| **Setup complexity**    | None   | Minimal    | Moderate | Moderate |
| **Best use**            | Dev/Test | Small deploys | Production | Enterprise |

\* Memory URLs are in-process only, not network-accessible.
\*\* Filesystem presigns are local paths; expose via your app (e.g., signed route). Not directly internet-accessible.

### VFS Providers Configuration

**VFS providers offer a unified interface with future-ready features like streaming and virtual mounts:**

```bash
# Development (VFS memory - default with legacy fallback)
export ARTIFACT_PROVIDER=vfs-memory

# VFS Filesystem
export ARTIFACT_PROVIDER=vfs-filesystem
export ARTIFACT_FS_ROOT=./my-artifacts

# VFS S3 (AWS or S3-compatible)
export ARTIFACT_PROVIDER=vfs-s3
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export ARTIFACT_BUCKET=my-bucket

# VFS SQLite (for structured metadata queries)
export ARTIFACT_PROVIDER=vfs-sqlite
export ARTIFACT_SQLITE_PATH=./artifacts.db
```

**Benefits of VFS Providers:**
- 🚀 **Future-ready**: Built-in support for streaming large files (Phase 2+)
- 🎯 **Progress tracking**: Upload/download progress callbacks
- 🔧 **Virtual mounts**: Mix providers per scope (memory for sessions, S3 for users)
- 🗄️ **SQLite support**: Structured queries for metadata
- 🔒 **Security profiles**: Quota management and path validation

### Legacy Providers Configuration

**Legacy providers remain fully supported for backward compatibility:**

```bash
# Development (default) - no configuration needed!
# Uses legacy memory provider

# Filesystem
export ARTIFACT_PROVIDER=filesystem
export ARTIFACT_FS_ROOT=./my-artifacts

# S3
export ARTIFACT_PROVIDER=s3
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export ARTIFACT_BUCKET=my-bucket

# IBM COS
export ARTIFACT_PROVIDER=ibm_cos
export IBM_COS_ACCESS_KEY=...
export IBM_COS_SECRET_KEY=...
export IBM_COS_ENDPOINT=https://s3.us-south.cloud-object-storage.appdomain.cloud
export ARTIFACT_BUCKET=my-bucket
```

**Migration Note:** Both legacy and VFS providers work identically from the API perspective. VFS providers are recommended for new projects to access future streaming and mount features.

---

## Core Concepts

### Grid Architecture = Infinite Scale

Files are organized in a predictable, hierarchical **grid** structure with three storage scopes:

```
grid/
├── {sandbox_id}/
│   ├── sessions/{session_id}/    # Session-scoped (ephemeral)
│   │   ├── {artifact_id}
│   │   └── {artifact_id}
│   ├── users/{user_id}/           # User-scoped (persistent)
│   │   ├── {artifact_id}
│   │   └── {artifact_id}
│   └── shared/                    # Sandbox-scoped (shared)
│       ├── {artifact_id}
│       └── {artifact_id}
└── {sandbox_id}/
    └── ...
```

**Why Grid Architecture?**
- 🔒 **Security**: Natural isolation between applications and users
- 📈 **Scalability**: Supports billions of files across thousands of sessions
- 🌐 **Federation**: Easily distribute across multiple storage regions
- 🛠️ **Operations**: Predictable paths for backup, monitoring, and cleanup
- 🔍 **Debugging**: Clear hierarchical organization for troubleshooting

```python
# Grid paths are generated automatically
session_id = "example-session"
file_id = await store.store(data, mime="text/plain", summary="Test", session_id=session_id)

# Inspect the grid path
metadata = await store.metadata(file_id)
print(metadata.key)  # grid/my-app/session-abc123/artifact-def456

# Parse any grid path
parsed = store.parse_grid_key(metadata.key)
print(f"Sandbox: {parsed.sandbox_id}")
print(f"Session: {parsed.session_id}")
print(f"Artifact: {parsed.artifact_id}")
```

### Sessions = Security Boundaries

Every file belongs to a **session**. Sessions prevent users from accessing each other's files.

**Two ways to manage sessions:**

**Option A: Auto-generated sessions (recommended for most apps)**
```python
# Pass user_id → gets auto-generated session like "sess-alice-123-abc"
file_id = await store.store(
    data=b"Alice's private data",
    mime="text/plain",
    summary="Private file",
    user_id="alice"  # Session auto-created
)
```

**Option B: Custom session IDs (for specific naming requirements)**
```python
# Use your own session ID format
session_id = f"user_{user.id}"  # Or any format you prefer

file_id = await store.store(
    data=b"Alice's private data",
    mime="text/plain",
    summary="Private file",
    session_id=session_id  # Custom ID used directly
)
```

**Custom session ID patterns:**

```python
# User-based sessions
session_id = f"user_{user.id}"

# Organization-based sessions
session_id = f"org_{organization.id}"

# Multi-tenant sessions (tenant + user isolation)
session_id = f"tenant_{tenant_id}_user_{user.id}"

# Workflow-based sessions (temporary workspaces)
session_id = f"workflow_{workflow_id}"
```

**Example: Session isolation in action**

```python
# Alice and Bob each get their own sessions
alice_file = await store.store(
    data=b"Alice's private data",
    mime="text/plain",
    summary="Private file",
    user_id="alice"  # Separate session
)

bob_file = await store.store(
    data=b"Bob's private data",
    mime="text/plain",
    summary="Private file",
    user_id="bob"  # Different session
)

# Cross-session operations are blocked for security
alice_meta = await store.metadata(alice_file)
bob_meta = await store.metadata(bob_file)

try:
    await store.copy_file(alice_file, target_session_id=bob_meta.session_id)
except ArtifactStoreError:
    print("🔒 Cross-session access denied!")  # Security enforced
```

---

## Storage Scopes

**New in v0.5**: Persistent user storage and shared resources alongside ephemeral session files.

CHUK Artifacts supports three storage scopes with different lifecycles and access patterns:

| Scope | Lifecycle | Use Case | Access Control |
|-------|-----------|----------|----------------|
| **session** | Ephemeral (15min-24h) | Temporary work files, caches | Session-isolated |
| **user** | Persistent (long/unlimited) | User's saved files, documents | User-owned |
| **sandbox** | Shared (long/unlimited) | Templates, shared resources | Read-only (admin writes) |

### Session-Scoped Storage (Default)

Ephemeral files that expire after a short time. Perfect for temporary work files and caches.

```python
# Default behavior - no changes needed
file_id = await store.store(
    data=b"Temporary work file",
    mime="text/plain",
    summary="Work in progress",
    user_id="alice",
    # scope="session" is default
    ttl=900  # 15 minutes
)

# Access requires same session
data = await store.retrieve(file_id, session_id=session_id)
```

### User-Scoped Storage (Persistent)

**Persistent files that belong to a user** and survive across all their sessions.

```python
# Store persistently for user
document_id = await store.store(
    data=pdf_bytes,
    mime="application/pdf",
    summary="Q4 Sales Report",
    user_id="alice",
    scope="user",  # Persists across sessions!
    ttl=86400 * 365  # 1 year (or None for unlimited)
)

# Retrieve from any session - just need user_id
data = await store.retrieve(document_id, user_id="alice")

# Search all user's artifacts
alice_files = await store.search(user_id="alice", scope="user")

# Filter by MIME type
alice_pdfs = await store.search(
    user_id="alice",
    scope="user",
    mime_prefix="application/pdf"
)

# Filter by custom metadata
q4_docs = await store.search(
    user_id="alice",
    scope="user",
    meta_filter={"quarter": "Q4"}
)
```

### Sandbox-Scoped Storage (Shared)

**Shared resources accessible to all users** in the sandbox. Read-only for regular users.

```python
# Store shared template (admin operation)
template_id = await store.store(
    data=template_bytes,
    mime="image/png",
    summary="Company logo",
    scope="sandbox",
    ttl=None  # No expiry
)

# Anyone in sandbox can read
logo_data = await store.retrieve(template_id)  # No user/session needed

# Search shared resources
templates = await store.search(scope="sandbox")
```

### Access Control

**Read access:**
- **Session scope**: Only the owning session
- **User scope**: Only the owning user (across all sessions)
- **Sandbox scope**: Anyone in the sandbox

**Write/delete access:**
- **Session scope**: Only the owning session
- **User scope**: Only the owning user
- **Sandbox scope**: Admin operations only (not via regular API)

**Example: Access control in action**

```python
# Alice stores a private document
doc_id = await store.store(
    data=b"Private data",
    mime="text/plain",
    summary="Alice's private doc",
    user_id="alice",
    scope="user"
)

# Alice can access it ✅
data = await store.retrieve(doc_id, user_id="alice")

# Bob cannot access it ❌
try:
    data = await store.retrieve(doc_id, user_id="bob")
except AccessDeniedError:
    print("Access denied!")
```

### MCP Server Example with Persistent Storage

```python
from chuk_artifacts import ArtifactStore

store = ArtifactStore()

# Session 1: User creates a presentation
deck_id = await store.store(
    data=pptx_bytes,
    mime="application/vnd.ms-powerpoint",
    summary="Q4 Sales Deck",
    user_id="alice",
    scope="user",  # Persists beyond session!
    ttl=None  # No expiry
)

# Session 2: Different MCP server retrieves and processes
# (works because it's user-scoped, not session-scoped!)
deck_data = await store.retrieve(deck_id, user_id="alice")
video_id = await remotion_server.render(deck_data)

# Session 3: User finds all their work across all sessions
artifacts = await store.search(user_id="alice", scope="user")
print(f"Found {len(artifacts)} files")
```

### Migration from Session-Only Storage

✅ **Backward compatible** - existing code works without changes.

To enable persistent user storage, simply add `scope="user"`:

```python
# Before (session-scoped, ephemeral)
file_id = await store.store(data, mime="text/plain", user_id="alice")

# After (user-scoped, persistent)
file_id = await store.store(
    data, mime="text/plain",
    user_id="alice",
    scope="user",  # Add this line
    ttl=None  # Optional: no expiry
)
```

---

## Common Recipes

### Upload with Presigned URL

For large files, let clients upload directly to storage:

```python
# Generate presigned upload URL
session_id = f"user_{user_id}"
url, artifact_id = await store.presign_upload(
    session_id=session_id,
    filename="photo.jpg",
    mime_type="image/jpeg",
    expires=1800  # 30 minutes
)

# Client uploads to URL (HTTP PUT)
# Example with curl:
# curl -X PUT -H "Content-Type: image/jpeg" --data-binary @photo.jpg "$url"

# Register the uploaded file
await store.register_uploaded_artifact(
    artifact_id,
    mime="image/jpeg",
    summary="Profile pic",
    filename="photo.jpg"
)
```

**Complete client upload example:**

```bash
# 1. Request upload URL from your API
UPLOAD_DATA=$(curl -X POST https://api.example.com/request-upload \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"filename": "photo.jpg", "mime_type": "image/jpeg"}')

# Extract URL and artifact ID
UPLOAD_URL=$(echo $UPLOAD_DATA | jq -r '.upload_url')
ARTIFACT_ID=$(echo $UPLOAD_DATA | jq -r '.artifact_id')

# 2. Upload directly to storage (no server proxying!)
curl -X PUT "$UPLOAD_URL" \
  -H "Content-Type: image/jpeg" \
  --data-binary @photo.jpg

# 3. Confirm upload completion
curl -X POST https://api.example.com/confirm-upload \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"artifact_id\": \"$ARTIFACT_ID\"}"
```

### Batch Store

Upload multiple files in one operation:

```python
# Create session for catalog
session_id = f"catalog_{catalog_id}"

files = [
    {
        "data": image1_bytes,
        "mime": "image/jpeg",
        "filename": f"products/img-{i}.jpg",
        "summary": f"Product image {i}",
        "meta": {"product_id": "LPT-001"}
    }
    for i in range(10)
]

file_ids = await store.store_batch(files, session_id=session_id)
print(f"Uploaded {len([id for id in file_ids if id])} images")
```

### Directory-Like Operations

```python
# List files in a session
files = await store.list_by_session("session-123")
for f in files:
    print(f"{f.filename}: {f.bytes} bytes")

# Get directory contents
docs = await store.get_directory_contents("session-123", "docs/")
images = await store.get_directory_contents("session-123", "images/")

# Copy within same session (security enforced)
backup_id = await store.copy_file(
    doc_id,
    new_filename="docs/README_backup.md"
)
```

### Web Framework Integration

```python
from fastapi import FastAPI, UploadFile
from chuk_artifacts import ArtifactStore

app = FastAPI()
store = ArtifactStore(storage_provider="s3", session_provider="redis")

@app.post("/upload")
async def handle_upload(file: UploadFile, user_id: str):
    content = await file.read()

    # Get or create session for user
    session_id = f"user_{user_id}"

    file_id = await store.store(
        data=content,
        mime=file.content_type,
        summary=f"Uploaded: {file.filename}",
        filename=file.filename,
        session_id=session_id
    )

    # Generate download URL
    url = await store.presign_medium(file_id)
    return {"file_id": file_id, "download_url": url}

@app.get("/files/{user_id}")
async def list_files(user_id: str):
    session_id = f"user_{user_id}"
    files = await store.list_by_session(session_id)
    return [
        {
            "id": f.artifact_id,
            "name": f.filename,
            "size": f.bytes,
            "created": f.stored_at
        }
        for f in files
    ]
```

See complete example: [`examples/usage_examples_demo.py`](./examples/usage_examples_demo.py) ([GitHub](https://github.com/chrishayuk/chuk-artifacts/blob/main/examples/usage_examples_demo.py))

### MCP Server Integration

```python
from mcp import Server
from chuk_artifacts import ArtifactStore
import base64

server = Server("artifacts-mcp")
store = ArtifactStore()

@server.tool("upload_file")
async def upload_file(data_b64: str, filename: str, user_id: str):
    """MCP tool for file uploads.

    Args:
        data_b64: Base64-encoded raw bytes (not data URL format)
    """
    data = base64.b64decode(data_b64)
    session_id = f"user_{user_id}"

    file_id = await store.store(
        data=data,
        mime="application/octet-stream",
        summary=f"Uploaded: {filename}",
        filename=filename,
        session_id=session_id
    )

    url = await store.presign_medium(file_id)
    return {
        "file_id": file_id,
        "filename": filename,
        "size": len(data),
        "download_url": url
    }

@server.tool("list_files")
async def list_files(user_id: str):
    """List files for user"""
    session_id = f"user_{user_id}"
    files = await store.list_by_session(session_id)
    return {
        "files": [
            {
                "id": f.artifact_id,
                "name": f.filename,
                "size": f.bytes,
                "type": f.mime
            }
            for f in files
        ]
    }
```

See complete example: [`examples/mcp_test_demo.py`](./examples/mcp_test_demo.py) ([GitHub](https://github.com/chrishayuk/chuk-artifacts/blob/main/examples/mcp_test_demo.py))

---

## Streaming Operations

**New in v0.6**: Memory-efficient streaming for large files with progress tracking.

Streaming operations allow you to upload and download large files without loading them entirely into memory. Perfect for video files, datasets, and backups.

### Streaming Upload

Upload large files efficiently with progress callbacks:

```python
from chuk_artifacts import ArtifactStore, StreamUploadRequest

async with ArtifactStore() as store:
    # Open file and create streaming generator
    async def file_chunks():
        with open("large_video.mp4", "rb") as f:
            while chunk := f.read(65536):  # 64KB chunks
                yield chunk

    # Optional: Track upload progress
    def progress_callback(bytes_sent, total_bytes):
        if total_bytes:
            percent = (bytes_sent / total_bytes) * 100
            print(f"Upload progress: {percent:.1f}%")

    # Create streaming upload request
    request = StreamUploadRequest(
        data_stream=file_chunks(),
        mime="video/mp4",
        summary="Product demo video",
        filename="demo.mp4",
        user_id="alice",
        content_length=os.path.getsize("large_video.mp4"),  # Optional but recommended
        progress_callback=progress_callback  # Optional
    )

    # Upload with streaming
    artifact_id = await store.stream_upload(request)
    print(f"Uploaded: {artifact_id}")
```

### Streaming Download

Download large files in chunks:

```python
from chuk_artifacts import StreamDownloadRequest

async with ArtifactStore() as store:
    # Optional: Track download progress
    def progress_callback(bytes_received, total_bytes):
        if total_bytes:
            percent = (bytes_received / total_bytes) * 100
            print(f"Download progress: {percent:.1f}%")

    # Create streaming download request
    request = StreamDownloadRequest(
        artifact_id=artifact_id,
        user_id="alice",  # For access control
        chunk_size=65536,  # 64KB chunks (default)
        progress_callback=progress_callback  # Optional
    )

    # Stream download to file
    with open("downloaded.mp4", "wb") as f:
        async for chunk in store.stream_download(request):
            f.write(chunk)

    print("Download complete!")
```

### Memory-Efficient Processing

Process large files without loading into memory:

```python
import hashlib

async with ArtifactStore() as store:
    # Stream download and compute hash on-the-fly
    sha256 = hashlib.sha256()
    bytes_processed = 0

    request = StreamDownloadRequest(artifact_id=artifact_id)

    async for chunk in store.stream_download(request):
        sha256.update(chunk)
        bytes_processed += len(chunk)

    print(f"SHA256: {sha256.hexdigest()}")
    print(f"Processed {bytes_processed / 1024 / 1024:.1f} MB")
```

### Streaming with Access Control

Streaming respects all access control rules:

```python
# User-scoped streaming upload (persistent)
request = StreamUploadRequest(
    data_stream=data_generator(),
    mime="application/pdf",
    summary="User document",
    user_id="alice",
    scope="user",  # Persistent, user-owned
    ttl=None  # No expiry
)

artifact_id = await store.stream_upload(request)

# Only Alice can download (access control enforced)
request = StreamDownloadRequest(
    artifact_id=artifact_id,
    user_id="alice"  # Required for user-scoped artifacts
)

async for chunk in store.stream_download(request):
    process_chunk(chunk)
```

### Concurrent Streaming

Upload or download multiple files in parallel:

```python
import asyncio

async with ArtifactStore() as store:
    async def upload_file(file_path):
        async def file_chunks():
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    yield chunk

        request = StreamUploadRequest(
            data_stream=file_chunks(),
            mime="application/octet-stream",
            summary=f"Upload: {file_path}",
            user_id="alice"
        )
        return await store.stream_upload(request)

    # Upload 5 files concurrently
    files = ["file1.bin", "file2.bin", "file3.bin", "file4.bin", "file5.bin"]
    artifact_ids = await asyncio.gather(*[upload_file(f) for f in files])

    print(f"Uploaded {len(artifact_ids)} files concurrently")
```

### Performance Characteristics

Streaming operations provide excellent performance for large files:

```
✅ Upload speed:   ~380 MB/s (10MB file, memory provider)
✅ Download speed: ~2,124 MB/s (10MB file, memory provider)
✅ Memory usage:   Constant (only chunk size, default 64KB)
✅ Progress tracking: Real-time callbacks every chunk
✅ Concurrent ops: Full async/await support
```

**When to use streaming:**
- Files larger than 1MB
- Video/audio uploads
- Dataset uploads (CSV, JSON, Parquet)
- Backup operations
- Progress tracking required
- Memory-constrained environments

**When to use regular upload:**
- Small files (<1MB)
- In-memory data (already loaded)
- Simple operations without progress tracking

See complete example: [`examples/streaming_demo.py`](./examples/streaming_demo.py) ([GitHub](https://github.com/chrishayuk/chuk-artifacts/blob/main/examples/streaming_demo.py))

---

## Multipart Uploads

**New in v1.0**: Presigned multipart uploads for large files (>5MB) with client-side direct uploads.

Multipart uploads enable efficient uploading of very large files by splitting them into chunks that can be uploaded independently and in parallel. Perfect for video rendering, datasets, generated documents, and media pipelines.

### Why Multipart Uploads?

- **Large Files**: Handle files from 5MB to 5TB
- **Resumable**: Upload parts independently—resume after failures
- **Parallel**: Client can upload multiple parts simultaneously
- **Secure**: Presigned URLs expire after use—no credential exposure
- **Production-Ready**: Used by Remotion, PPTX generators, image pipelines

### Basic Multipart Upload Workflow

1. **Initiate** upload to get `upload_id`
2. **Get presigned URLs** for each part (minimum 5MB except last)
3. **Client uploads parts** directly to storage using presigned URLs
4. **Complete** upload with part ETags to finalize

```python
from chuk_artifacts import (
    ArtifactStore,
    MultipartUploadInitRequest,
    MultipartUploadCompleteRequest,
    MultipartUploadPart,
)

async with ArtifactStore() as store:
    # Step 1: Initiate multipart upload
    init_request = MultipartUploadInitRequest(
        filename="large_video.mp4",
        mime_type="video/mp4",
        user_id="alice",
        scope="user",
        ttl=3600,  # 1 hour
        meta={"project": "Q4-demo", "resolution": "4K"}
    )

    result = await store.initiate_multipart_upload(init_request)
    upload_id = result["upload_id"]
    artifact_id = result["artifact_id"]

    print(f"Upload initiated: {upload_id}")

    # Step 2: Get presigned URLs for each part
    # Client will upload parts to these URLs
    num_parts = 3  # Divide file into 3 parts
    parts = []

    for part_num in range(1, num_parts + 1):
        # Get presigned URL for this part
        presigned_url = await store.get_part_upload_url(
            upload_id=upload_id,
            part_number=part_num,
            expires=3600  # URL valid for 1 hour
        )

        # Client uploads part via HTTP PUT to presigned_url
        # and receives ETag in response headers
        print(f"Part {part_num} URL: {presigned_url}")

        # Mock ETag from upload response (in real scenario from HTTP response)
        etag = f"etag-part-{part_num}"
        parts.append(MultipartUploadPart(PartNumber=part_num, ETag=etag))

    # Step 3: Complete the multipart upload
    complete_request = MultipartUploadCompleteRequest(
        upload_id=upload_id,
        parts=parts,
        summary="4K video upload (multipart)"
    )

    final_artifact_id = await store.complete_multipart_upload(complete_request)

    print(f"Upload completed! Artifact ID: {final_artifact_id}")

    # Verify artifact exists
    metadata = await store.metadata(final_artifact_id)
    print(f"Size: {metadata.bytes / 1024 / 1024:.1f} MB")
    print(f"Scope: {metadata.scope}")
```

### Aborting Multipart Uploads

Cancel incomplete uploads and clean up resources:

```python
async with ArtifactStore() as store:
    # Initiate upload
    init_request = MultipartUploadInitRequest(
        filename="large_file.mp4",
        mime_type="video/mp4"
    )
    result = await store.initiate_multipart_upload(init_request)
    upload_id = result["upload_id"]

    try:
        # Get part URLs and upload...
        url = await store.get_part_upload_url(upload_id, 1)
        # ... upload fails ...
    except Exception as e:
        # Abort and cleanup
        await store.abort_multipart_upload(upload_id)
        print(f"Upload aborted: {e}")
```

### Multipart with Different Scopes

Upload large files to different storage scopes:

```python
# Session-scoped (ephemeral, 15 minutes)
init_request = MultipartUploadInitRequest(
    filename="temp_render.mp4",
    mime_type="video/mp4",
    scope="session",
    ttl=900  # 15 minutes
)

# User-scoped (persistent, 30 days)
init_request = MultipartUploadInitRequest(
    filename="profile_video.mp4",
    mime_type="video/mp4",
    user_id="alice",
    scope="user",
    ttl=86400 * 30  # 30 days
)

# Sandbox-scoped (shared, 90 days)
init_request = MultipartUploadInitRequest(
    filename="shared_assets.zip",
    mime_type="application/zip",
    scope="sandbox",
    ttl=86400 * 90  # 90 days
)
```

### Real-World Use Cases

#### Video Rendering (Remotion)

```python
# Upload rendered 4K video
init_request = MultipartUploadInitRequest(
    filename="rendered_video_4k.mp4",
    mime_type="video/mp4",
    user_id="render-bot",
    scope="user",
    meta={
        "renderer": "remotion",
        "fps": 60,
        "resolution": "3840x2160",
        "duration_seconds": 120
    }
)

result = await store.initiate_multipart_upload(init_request)
# ... upload 250MB video in 10MB parts ...
```

#### Dataset Uploads

```python
# Upload large ML training dataset
init_request = MultipartUploadInitRequest(
    filename="training_data.tar.gz",
    mime_type="application/gzip",
    user_id="data-scientist",
    scope="user",
    ttl=86400 * 7,  # 1 week
    meta={
        "dataset": "ml-training",
        "version": "v2.1",
        "samples": 1000000
    }
)

result = await store.initiate_multipart_upload(init_request)
# ... upload 500MB dataset in 50MB parts ...
```

#### Generated Documents (PPTX)

```python
# Upload generated presentation
init_request = MultipartUploadInitRequest(
    filename="quarterly_report.pptx",
    mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    user_id="report-generator",
    scope="user",
    meta={
        "slides": 150,
        "template": "corporate",
        "quarter": "Q4-2024"
    }
)

result = await store.initiate_multipart_upload(init_request)
# ... upload 50MB presentation in 5MB parts ...
```

#### Image Pipeline Outputs

```python
# Upload batch processed images
init_request = MultipartUploadInitRequest(
    filename="processed_images.zip",
    mime_type="application/zip",
    user_id="image-pipeline",
    scope="sandbox",
    meta={
        "count": 1000,
        "format": "png",
        "dimensions": "4096x4096",
        "pipeline": "batch-resize-v2"
    }
)

result = await store.initiate_multipart_upload(init_request)
# ... upload 300MB archive in 30MB parts ...
```

### Multipart Upload Constraints

- **Minimum part size**: 5MB (except last part, which can be smaller)
- **Maximum parts**: 10,000 per upload
- **Maximum file size**: 5TB (S3 limit)
- **Part number range**: 1-10,000 (sequential)
- **Upload window**: 24 hours (configurable via TTL)
- **ETag required**: Must be captured from upload response

### Client-Side Implementation

Example client-side JavaScript for uploading parts:

```javascript
// After getting presigned URL from server
const uploadPart = async (url, partData, partNumber) => {
    const response = await fetch(url, {
        method: 'PUT',
        body: partData,
        headers: {
            'Content-Type': 'application/octet-stream'
        }
    });

    // Get ETag from response headers
    const etag = response.headers.get('ETag');

    return {
        PartNumber: partNumber,
        ETag: etag
    };
};

// Upload all parts
const parts = await Promise.all(
    fileParts.map((data, i) =>
        uploadPart(presignedUrls[i], data, i + 1)
    )
);

// Send parts to server to complete upload
await fetch('/api/complete-multipart', {
    method: 'POST',
    body: JSON.stringify({
        upload_id: uploadId,
        parts: parts
    })
});
```

### Performance Characteristics

Multipart uploads provide excellent performance for large files:

```
✅ File size range:   5MB to 5TB
✅ Part size:         5MB minimum (except last)
✅ Maximum parts:     10,000 per upload
✅ Parallel uploads:  Client can upload parts concurrently
✅ Resumable:         Failed parts can be re-uploaded
✅ Upload window:     24 hours (default)
✅ Security:          Presigned URLs with expiry
```

**When to use multipart uploads:**
- Files larger than 5MB
- Video rendering outputs (Remotion, FFmpeg)
- Dataset uploads (CSV, Parquet, TFRecord)
- Generated documents (PPTX, PDF)
- Media pipeline outputs
- Batch processed images
- Resumable uploads required
- Client-side direct uploads needed

**When to use streaming uploads:**
- Server-side file processing
- Progress tracking required
- Files 1MB-50MB
- Simpler upload workflow

**When to use regular uploads:**
- Small files (<1MB)
- In-memory data
- Simple operations

See complete example: [`examples/multipart_demo.py`](./examples/multipart_demo.py) ([GitHub](https://github.com/chrishayuk/chuk-artifacts/blob/main/examples/multipart_demo.py))

---

## Configuration

### Development (Zero-Config Defaults)

```python
from chuk_artifacts import ArtifactStore

# Just works! Uses memory providers
store = ArtifactStore()
```

### Filesystem (Local Persistence)

```python
from chuk_artifacts.config import configure_filesystem

configure_filesystem(root="./my-artifacts")
store = ArtifactStore()
```

### S3 (Production)

```python
from chuk_artifacts.config import configure_s3

configure_s3(
    access_key="AKIA...",
    secret_key="...",
    bucket="production-artifacts",
    region="us-east-1"
)
store = ArtifactStore()
```

### Docker Compose

```yaml
version: '3.8'
services:
  app:
    image: myapp
    environment:
      ARTIFACT_PROVIDER: s3
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
      ARTIFACT_BUCKET: myapp-artifacts
      SESSION_PROVIDER: redis
      SESSION_REDIS_URL: redis://redis:6379/0
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

---

## Advanced Features

### Presigned URLs

```python
# API signature:
# presign(file_id: str, *, expires: int = 3600) -> str
# Wrappers: presign_short (15m), presign_medium (60m), presign_long (24h)

# Different durations
url = await store.presign(file_id, expires=3600)  # Custom: 1 hour
short = await store.presign_short(file_id)        # 15 minutes
medium = await store.presign_medium(file_id)      # 1 hour (default)
long = await store.presign_long(file_id)          # 24 hours
```

### Rich Metadata

```python
file_id = await store.store(
    data=image_bytes,
    mime="image/jpeg",
    summary="Product photo",
    filename="products/laptop-pro.jpg",
    session_id=session_id,
    meta={
        "product_id": "LPT-001",
        "tags": ["laptop", "professional"],
        "dimensions": {"width": 1920, "height": 1080}
    }
)

# Update metadata without changing content
await store.update_metadata(
    file_id,
    summary="Updated product photo",
    meta={"tags": ["laptop", "professional", "workspace"]},
    merge=True
)
```

### File Operations

```python
# Update file content
await store.update_file(file_id, data=new_content)

# Copy (same session only)
copy_id = await store.copy_file(file_id, new_filename="backup.txt")

# Move/rename
moved = await store.move_file(file_id, new_filename="renamed.txt")

# Check existence
if await store.exists(file_id):
    print("File exists!")

# Delete
deleted = await store.delete(file_id)
```

### Monitoring

```python
# Validate configuration
status = await store.validate_configuration()
print(f"Storage: {status['storage']['status']}")
print(f"Sessions: {status['session']['status']}")

# Get statistics
stats = await store.get_stats()
print(f"Provider: {stats['storage_provider']}")
print(f"Bucket: {stats['bucket']}")

# Cleanup expired sessions
cleaned = await store.cleanup_expired_sessions()
```

---

## Error Handling

### Exception Types

| Exception | Typical Cause | Suggested HTTP Status |
|-----------|--------------|----------------------|
| `ArtifactNotFoundError` | Missing or expired artifact | 404 Not Found |
| `ArtifactExpiredError` | TTL exceeded | 410 Gone |
| `AccessDeniedError` | Cross-user/session access attempt | 403 Forbidden |
| `ArtifactStoreError` | Generic store errors | 400 Bad Request |
| `ProviderError` | S3/COS transient failure | 502/503 Service Unavailable |
| `SessionError` | Session system error | 500 Internal Server Error |

### Example

```python
from chuk_artifacts import (
    ArtifactStoreError,
    ArtifactNotFoundError,
    ArtifactExpiredError,
    AccessDeniedError,
    ProviderError
)

try:
    data = await store.retrieve(file_id, user_id="alice")
except ArtifactNotFoundError:
    return {"error": "File not found"}, 404
except ArtifactExpiredError:
    return {"error": "File has expired"}, 410
except AccessDeniedError:
    return {"error": "Access denied"}, 403
except ProviderError as e:
    logger.error(f"Storage error: {e}")
    return {"error": "Storage unavailable"}, 502
except ArtifactStoreError as e:
    return {"error": "Bad request"}, 400
```

---

## Security

### Security Posture

**Built-in protections:**
- ✅ **Session isolation** - Cross-session operations blocked by default
- ✅ **TTL enforcement** - Files expire automatically (default: 15 minutes)
- ✅ **Presigned URL scoping** - Short-lived URLs (15min-24h)
- ✅ **Grid path validation** - No directory traversal attacks

**Production recommendations:**

1. **Enable server-side encryption:**
   ```bash
   # S3: Use SSE-S3 or SSE-KMS
   export S3_SSE_ALGORITHM=AES256

   # IBM COS: Encryption enabled by default
   ```

2. **Use IAM roles** (no hardcoded credentials):
   ```python
   # AWS ECS/Lambda/EC2 with IAM role - no credentials needed!
   store = ArtifactStore(storage_provider="s3")
   ```

3. **Session isolation best practices:**
   ```python
   # ✅ Good: Each user gets their own session
   session_id = f"user_{user.id}"

   # ✅ Good: Organization-level isolation
   session_id = f"org_{org.id}_user_{user.id}"

   # ❌ Bad: Shared sessions across users
   session_id = "global"  # All users can see each other's files!
   ```

4. **Presigned URL expiration:**
   ```python
   # Use short-lived URLs for sensitive files
   url = await store.presign_short(file_id)  # 15 minutes

   # Or custom expiration
   url = await store.presign(file_id, expires=900)  # 15 minutes
   ```

5. **Access control verification:**
   ```python
   async def secure_download(file_id: str, user_id: str):
       """Verify ownership before serving"""
       metadata = await store.metadata(file_id)
       expected_session = f"user_{user_id}"

       if metadata.session_id != expected_session:
           raise HTTPException(403, "Access denied")

       return await store.presign(file_id)
   ```

---

## Performance

### Benchmarks

Typical performance with S3 + Redis:

```
✅ File Storage:     3,083 files/sec
✅ File Retrieval:   4,693 reads/sec
✅ File Updates:     2,156 updates/sec
✅ Batch Operations: 1,811 batch items/sec
✅ Session Listing:  ~2ms for 20+ files
✅ Metadata Access:  <1ms with Redis
```

**Benchmark setup:**
- Environment: AWS S3 (us-east-1), Redis 7, c6i.4xlarge instance
- Dataset: 1MB objects per operation
- Concurrency: 128 concurrent tasks
- Client: aioboto3 with connection pooling
- Results: Average over 5 runs
- Reproducible: `./benchmarks/run.py` (see [benchmarks/](https://github.com/chrishayuk/chuk-artifacts/tree/main/benchmarks) directory)

**Performance tips:**
- ✅ Use batch operations for multiple files
- ✅ Reuse store instances (connection pooling)
- ✅ Use presigned URLs for large files (>5MB)
- ✅ Choose appropriate TTL values (shorter = faster cleanup)
- ✅ Enable Redis for production (sub-millisecond metadata access)

---

## Testing

### Run Smoke Tests

```bash
# Comprehensive test suite (97% coverage)
python examples/smoke_run.py

# Expected: 32/33 tests passing (97%)
```

### Run Integration Demos

```bash
# VFS provider demo (Memory, Filesystem, S3, SQLite)
python examples/vfs_provider_demo.py

# Streaming operations with progress tracking
python examples/streaming_demo.py

# Grid architecture demo
python examples/artifact_grid_demo.py

# Session operations and security
python examples/session_operations_demo.py

# Web framework patterns
python examples/usage_examples_demo.py
```

See all examples: [`examples/`](./examples/) ([GitHub](https://github.com/chrishayuk/chuk-artifacts/tree/main/examples))

### Unit Tests

```bash
# Run full test suite (715 tests)
uv run pytest tests/ -v

# With coverage report (87-90% on core modules)
uv run pytest tests/ --cov=src/chuk_artifacts --cov-report=term-missing

# Run specific test modules
uv run pytest tests/test_store.py -v  # Core store tests
uv run pytest tests/test_streaming.py -v  # Streaming operations tests
uv run pytest tests/test_access_control.py -v  # Access control tests
uv run pytest tests/test_grid.py -v  # Grid path tests
uv run pytest tests/providers/test_vfs_adapter.py -v  # VFS adapter tests
```

```python
# Quick test
import asyncio
from chuk_artifacts import ArtifactStore

async def test_basic():
    async with ArtifactStore() as store:
        # Store (session auto-created from user_id)
        file_id = await store.store(
            data=b"test",
            mime="text/plain",
            summary="Test",
            user_id="test"  # Session auto-generated
        )

        # Verify
        assert await store.exists(file_id)
        content = await store.read_file(file_id)
        assert content == b"test"

        print("✅ Tests passed!")

asyncio.run(test_basic())
```

---

## Configuration Reference

### Core Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `ARTIFACT_PROVIDER` | Storage backend | `memory` | `vfs-memory`, `vfs-s3`, `s3`, `filesystem` |
| `ARTIFACT_BUCKET` | Bucket/container name | `artifacts` | `my-files`, `prod-storage` |
| `ARTIFACT_SANDBOX_ID` | Sandbox identifier | Auto-generated | `myapp`, `prod-env` |
| `SESSION_PROVIDER` | Session metadata storage | `memory` | `redis` |

### VFS Configuration (Recommended)

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `ARTIFACT_PROVIDER` | VFS provider | `vfs-memory` | `vfs-filesystem`, `vfs-s3`, `vfs-sqlite` |
| `ARTIFACT_FS_ROOT` | VFS filesystem root | `./artifacts` | `/data/files`, `~/storage` |
| `ARTIFACT_SQLITE_PATH` | VFS SQLite database | `artifacts.db` | `/data/artifacts.db` |

### Filesystem Configuration (Legacy)

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `ARTIFACT_FS_ROOT` | Root directory | `./artifacts` | `/data/files`, `~/storage` |

### Session Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `SESSION_REDIS_URL` | Redis connection URL | - | `redis://localhost:6379/0` |

### AWS/S3 Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `AWS_ACCESS_KEY_ID` | AWS access key | - | `AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | - | `abc123...` |
| `AWS_REGION` | AWS region | `us-east-1` | `us-west-2`, `eu-west-1` |
| `S3_ENDPOINT_URL` | Custom S3 endpoint | - | `https://minio.example.com` |
| `S3_SSE_ALGORITHM` | Server-side encryption | - | `AES256`, `aws:kms` |

### IBM COS Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `IBM_COS_ACCESS_KEY` | HMAC access key | - | `abc123...` |
| `IBM_COS_SECRET_KEY` | HMAC secret key | - | `xyz789...` |
| `IBM_COS_ENDPOINT` | IBM COS endpoint | Auto-detected | `https://s3.us-south.cloud-object-storage.appdomain.cloud` |

---

## FAQ

### Q: Do I need Redis for development?

**A:** No! Memory providers work great for development. Only use Redis for production when you need persistence or multi-instance deployment.

### Q: Can I switch storage providers without code changes?

**A:** Yes! Just change the `ARTIFACT_PROVIDER` environment variable. The API is identical across all providers.

### Q: How do sessions map to my users?

**A:** Two approaches:

**1. Auto-generated (simplest):**
```python
# Pass user_id → session auto-created like "sess-alice-123-abc"
await store.store(data, mime="text/plain", user_id=user.id)
```

**2. Custom format (for specific naming needs):**
```python
# Define your own session ID format
session_id = f"user_{user.id}"  # Or any format

# Pass it directly
await store.store(data, mime="text/plain", session_id=session_id)
```

**Custom format examples:**
- User-based: `f"user_{user.id}"`
- Organization: `f"org_{org.id}"`
- Multi-tenant: `f"tenant_{tenant_id}_user_{user_id}"`
- Workflow: `f"workflow_{workflow_id}"`

**Rule:** Keep your format consistent. CHUK Artifacts enforces that session boundaries are never crossed.

### Q: How do I handle large files?

**A:** Use presigned upload URLs for client-side uploads:

```python
url, artifact_id = await store.presign_upload(
    session_id=session_id,
    filename="video.mp4",
    mime_type="video/mp4",
    expires=1800  # 30 min
)
# Client uploads directly to URL (no server proxying!)
```

### Q: What happens when files expire?

**A:** Files and metadata are automatically cleaned up based on TTL:

```python
# Set TTL when storing (default: 900s / 15 minutes)
await store.store(data, mime="text/plain", ttl=3600)  # 1 hour

# Manual cleanup
expired = await store.cleanup_expired_sessions()
```

### Q: Is it production ready?

**A:** Yes! Features for production:
- High performance (3,000+ ops/sec)
- Multiple storage backends (S3, IBM COS)
- Session-based security
- Redis support for distributed deployments
- Comprehensive error handling
- Health checks and monitoring
- Docker/K8s ready

---

## Roadmap

✅ **Phase 1 Complete (v0.5)**:
- Scope-based storage (session, user, sandbox)
- Access control with user_id
- Search functionality for user artifacts
- **VFS integration** - [chuk-virtual-fs](https://github.com/chrishayuk/chuk-virtual-fs) as unified storage layer
- **SQLite support** - Structured storage via VFS
- 95% test coverage

✅ **Phase 2 Complete (v0.6)**:
- ✅ **Streaming uploads/downloads** - Memory-efficient large file handling
- ✅ **Progress callbacks** - Real-time upload/download tracking
- ✅ **Async generators** - Native Python async/await streaming
- ✅ **Access control** - Streaming respects all scope rules
- 715 tests passing (87-90% coverage on streaming modules)

**Phase 3 (Planned)**:
- [ ] **Virtual mounts** - Mix providers per scope (VFS feature)
- [ ] **Metadata search index** - Elasticsearch/Typesense integration
- [ ] **Share links** - Temporary shareable URLs with expiry
- [ ] **User quotas** - Storage limits and usage tracking (VFS security profiles)

**Future Enhancements**:
- [ ] **GCS backend** - Google Cloud Storage via VFS
- [ ] **Azure Blob Storage** - Microsoft Azure via VFS
- [ ] **Client-side encryption** - Optional end-to-end encryption
- [ ] **Audit logging** - Detailed access logs for compliance
- [ ] **CDN integration** - CloudFront/Cloudflare integration
- [ ] **Multi-region** - Automatic replication across regions

---

## Next Steps

1. **Install**: `pip install chuk-artifacts`
2. **Try it**: Copy the [Quick Start](#quick-start) example
3. **Development**: Use default memory providers
4. **Production**: Configure S3 + Redis
5. **Integration**: Add to your FastAPI/MCP server

**Ready to build with enterprise-grade file storage?** 🚀

---

## Links

- **Examples**: [`./examples/`](./examples/)
- **Storage Layer**: [chuk-virtual-fs](https://github.com/chrishayuk/chuk-virtual-fs) - Unified virtual filesystem
- **Tests**: Run `python examples/smoke_run.py`
- **Issues**: [GitHub Issues](https://github.com/chrishayuk/chuk-artifacts/issues)
- **License**: MIT

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

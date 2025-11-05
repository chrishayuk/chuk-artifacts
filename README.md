# CHUK Artifacts

> **Session-scoped, grid-based artifact storage for AI apps and MCP servers**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Async](https://img.shields.io/badge/async-await-green.svg)](https://docs.python.org/3/library/asyncio.html)

CHUK Artifacts provides a unified, async API for storing and retrieving files ("artifacts") across local development and production cloud environments—while enforcing session boundaries and issuing presigned upload/download URLs so clients interact with storage directly and securely.

---

## Architecture at a Glance

Your app talks to `ArtifactStore`; it enforces session rules and issues presigned URLs. Clients upload/download directly to storage—no credentials exposed, no proxying large file streams.

```
                         (Your App / MCP Server)
                                     │
                                     │  ArtifactStore API (async)
                                     ▼
┌───────────────────────────────────────────────────────────────┐
│                        ArtifactStore                           │
│                                                               │
│  • Enforces session boundaries                                │
│  • Talks to storage providers                                 │
│  • Issues presigned upload/download URLs                       │
└───────────────┬───────────────────────────┬────────────────────┘
                │                           │
                │ session lookup            │ read/write files
                │                           │
                ▼                           ▼
        ┌────────────┐              ┌────────────────────────────┐
        │  Sessions  │              │        Storage             │
        │  (Redis)   │              │ (Memory / FS / S3 / COS)   │
        └─────┬──────┘              └───────┬─────────┬──────────┘
              │                              │         │
              │ authz                        │         │
              │                              │         │
              ▼                              ▼         ▼
        (session_id)                  grid/{sandbox}/{session}/{artifact}
```

**Caption**: The application calls ArtifactStore; the store consults the session provider for authz and talks to the configured storage backend. Clients use short-lived presigned URLs for direct uploads/downloads.

---

## Why This Exists

Most platforms offer object storage (S3, COS, FS)—but not a **security boundary**.

CHUK Artifacts ensures every object belongs to a **session** and is accessed only through that session.

**Highlights:**
- 🔒 **Session isolation** - Every file belongs to a session, preventing data leaks
- 🏗️ **Predictable grid paths** - `grid/{sandbox}/{session}/{artifact}` for infinite scale
- 🔗 **Presigned URLs** - Secure direct upload/download without exposing credentials
- 🌐 **Multiple backends** - Memory, Filesystem, S3, IBM COS (same API)
- ⚡ **Async-first** - Built for FastAPI, MCP servers, and modern Python apps
- 🎯 **Zero config** - Works out of the box, configure only what you need

---

## Install

```bash
pip install chuk-artifacts
```

or:

```bash
uv add chuk-artifacts
```

---

## Quick Start

```python
from chuk_artifacts import ArtifactStore

async with ArtifactStore() as store:
    # Store a file
    file_id = await store.store(
        data=b"Hello, world!",
        mime="text/plain",
        summary="greeting",
        filename="hello.txt",
        user_id="alice"
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

That's it! No AWS credentials, no Redis setup, no configuration files. Perfect for development and testing.

---

## Providers & Sessions

| Feature                  | Memory | Filesystem | S3 | IBM COS |
|-------------------------|--------|------------|----|---------|
| **Persistence**         | No     | Yes        | Yes| Yes     |
| **Horizontal scale**    | No     | Limited    | Yes| Yes     |
| **Presigned URLs**      | Yes*   | Yes        | Yes| Yes     |
| **Setup complexity**    | None   | Minimal    | Moderate | Moderate |
| **Best use**            | Dev/Test | Small deploys | Production | Enterprise |

\* Memory URLs are virtual.

**Quick config:**

```bash
# Development (default)
# No configuration needed!

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

---

## Core Concepts

### Grid Architecture = Infinite Scale

Files are organized in a predictable, hierarchical **grid** structure:

```
grid/
├── {sandbox_id}/          # Application/environment isolation
│   ├── {session_id}/      # User/workflow grouping
│   │   ├── {artifact_id}  # Individual files
│   │   └── {artifact_id}
│   └── {session_id}/
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
file_id = await store.store(data, mime="text/plain", summary="Test")

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

Every file belongs to a **session**. Sessions prevent users from accessing each other's files:

```python
# Files are isolated by session
alice_file = await store.store(
    data=b"Alice's private data",
    mime="text/plain",
    summary="Private file",
    user_id="alice"  # Auto-creates session for Alice
)

bob_file = await store.store(
    data=b"Bob's private data",
    mime="text/plain",
    summary="Private file",
    user_id="bob"  # Auto-creates session for Bob
)

# Cross-session operations are blocked for security
try:
    await store.copy_file(alice_file, target_session_id="bob_session")
except ArtifactStoreError:
    print("🔒 Cross-session access denied!")  # Security enforced
```

---

## Common Recipes

### Upload with Presigned URL

For large files, let clients upload directly to storage:

```python
# Generate presigned upload URL
url, temp_id = await store.presign_upload(
    session_id="alice",
    filename="photo.jpg",
    mime_type="image/jpeg",
    expires=1800  # 30 minutes
)

# Client uploads to URL (HTTP PUT)
# No server proxying needed!

# Register the uploaded file
await store.register_uploaded_artifact(
    temp_id,
    mime="image/jpeg",
    summary="Profile pic",
    filename="photo.jpg"
)
```

### Batch Store

Upload multiple files in one operation:

```python
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

file_ids = await store.store_batch(files, session_id="catalog")
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

    file_id = await store.store(
        data=content,
        mime=file.content_type,
        summary=f"Uploaded: {file.filename}",
        filename=file.filename,
        user_id=user_id
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

### MCP Server Integration

```python
from mcp import Server
from chuk_artifacts import ArtifactStore
import base64

server = Server("artifacts-mcp")
store = ArtifactStore()

@server.tool("upload_file")
async def upload_file(data_b64: str, filename: str, session_id: str):
    """MCP tool for file uploads"""
    data = base64.b64decode(data_b64)

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
async def list_files(session_id: str):
    """List files in session"""
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

---

## Configuration

### Development (Zero Config)

```python
from chuk_artifacts import ArtifactStore

# Just works!
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
# Different durations
url = await store.presign(file_id, expires=3600)  # Custom
short = await store.presign_short(file_id)        # 15 min
medium = await store.presign_medium(file_id)      # 1 hour
long = await store.presign_long(file_id)          # 24 hours
```

### Rich Metadata

```python
file_id = await store.store(
    data=image_bytes,
    mime="image/jpeg",
    summary="Product photo",
    filename="products/laptop-pro.jpg",
    user_id="marketing",
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

```python
from chuk_artifacts import (
    ArtifactStoreError,
    ArtifactNotFoundError,
    ArtifactExpiredError,
    ProviderError
)

try:
    data = await store.retrieve(file_id)
except ArtifactNotFoundError:
    print("File not found")
except ArtifactExpiredError:
    print("File has expired")
except ProviderError as e:
    print(f"Storage error: {e}")
except ArtifactStoreError as e:
    print(f"Access denied: {e}")
```

---

## Security Best Practices

### Session Isolation

```python
# ✅ Good: Each user gets their own session
user_session = f"user_{user.id}"
await store.store(data, mime="text/plain", session_id=user_session)

# ✅ Good: Organization-level isolation
org_session = f"org_{org.id}"

# ❌ Bad: Shared sessions across users
shared_session = "global"  # All users can see each other's files!
```

### Access Control

```python
async def secure_download(file_id: str, user_id: str):
    """Verify ownership before serving"""
    metadata = await store.metadata(file_id)
    expected_session = f"user_{user_id}"

    if metadata.session_id != expected_session:
        raise HTTPException(403, "Access denied")

    return await store.presign(file_id)
```

### Secure Configuration

```python
# ✅ Good: Environment variables
store = ArtifactStore(
    storage_provider=os.getenv("ARTIFACT_PROVIDER", "memory")
)

# ✅ Good: IAM roles (AWS/IBM)
# No credentials needed!

# ❌ Bad: Hardcoded credentials
store = ArtifactStore(
    access_key="AKIA123...",  # Never do this!
)
```

---

## Performance

Typical benchmarks with S3 + Redis:

```
✅ File Storage:     3,083 files/sec
✅ File Retrieval:   4,693 reads/sec
✅ File Updates:     2,156 updates/sec
✅ Batch Operations: 1,811 batch items/sec
✅ Session Listing:  ~2ms for 20+ files
✅ Metadata Access:  <1ms with Redis
```

**Performance tips:**
- Use batch operations for multiple files
- Reuse store instances (connection pooling)
- Use presigned URLs for large files
- Choose appropriate TTL values

---

## Testing

### Run Smoke Tests

```bash
# Comprehensive test suite
python examples/smoke_run.py

# Expected: 32/33 tests passing (97%)
```

### Integration Demo

```bash
python examples/artifact_grid_demo.py
python examples/grid_demo.py
python examples/usage_examples_demo.py
```

### Unit Tests

```python
import asyncio
from chuk_artifacts import ArtifactStore

async def test_basic_operations():
    async with ArtifactStore() as store:
        # Store
        file_id = await store.store(
            data=b"test",
            mime="text/plain",
            summary="Test"
        )

        # Verify
        assert await store.exists(file_id)
        content = await store.retrieve(file_id)
        assert content == b"test"

        # Metadata
        meta = await store.metadata(file_id)
        assert meta.bytes == 4

        print("✅ Tests passed!")

asyncio.run(test_basic_operations())
```

---

## FAQ

### Q: Do I need Redis for development?

**A:** No! Memory providers work great for development. Only use Redis for production when you need persistence or multi-instance deployment.

### Q: Can I switch storage providers without code changes?

**A:** Yes! Just change the `ARTIFACT_PROVIDER` environment variable. The API is identical across all providers.

### Q: How do I handle large files?

**A:** Use presigned upload URLs for client-side uploads:

```python
url, artifact_id = await store.presign_upload(
    session_id="user",
    filename="video.mp4",
    mime_type="video/mp4",
    expires=1800  # 30 min
)
# Client uploads directly to URL
```

### Q: What happens when files expire?

**A:** Files and metadata are automatically cleaned up based on TTL:

```python
# Set TTL when storing
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

- [ ] **GCS backend** - Google Cloud Storage support
- [ ] **Azure Blob Storage** - Microsoft Azure support
- [ ] **Checksums** - SHA-256 validation on all operations
- [ ] **Client-side encryption** - Optional end-to-end encryption
- [ ] **Audit logging** - Detailed access logs for compliance
- [ ] **Lifecycle policies** - Automated archival and deletion rules
- [ ] **CDN integration** - CloudFront/Cloudflare integration
- [ ] **Multi-region** - Automatic replication across regions

---

## Next Steps

1. **Install**: `pip install chuk-artifacts`
2. **Try it**: Copy the Quick Start example
3. **Development**: Use default memory providers
4. **Production**: Configure S3 + Redis
5. **Integration**: Add to your FastAPI/MCP server

**Ready to build with enterprise-grade file storage?** 🚀

---

## Links

- **Examples**: [./examples/](./examples/)
- **Tests**: Run `python examples/smoke_run.py`
- **Issues**: [GitHub Issues](https://github.com/chuk-artifacts/issues)
- **License**: MIT

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

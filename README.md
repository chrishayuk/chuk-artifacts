# Chuk Artifacts

> **Async artifact storage with session-based security and multi-backend support**

A production-ready Python library for storing and managing files across multiple storage backends (S3, IBM COS, filesystem, memory) with Redis-based metadata caching and strict session isolation.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Async](https://img.shields.io/badge/async-await-green.svg)](https://docs.python.org/3/library/asyncio.html)

## Why Chuk Artifacts?

- 🔒 **Session-based security** - Every file belongs to a session, preventing data leaks
- 🌐 **Multiple backends** - Switch between S3, filesystem, memory without code changes  
- ⚡ **High performance** - 3,000+ operations/second with async/await
- 🎯 **Zero config** - Works out of the box, configure only what you need
- 🔗 **Presigned URLs** - Secure file access without exposing credentials
- 📦 **Grid architecture** - Organized paths for scalability and federation

## Quick Start

### Installation

```bash
pip install chuk-artifacts
```

### 30-Second Example

```python
from chuk_artifacts import ArtifactStore

# Works immediately - no configuration needed
async with ArtifactStore() as store:
    # Store a file
    file_id = await store.store(
        data=b"Hello, world!",
        mime="text/plain", 
        summary="My first file",
        filename="hello.txt"
    )
    
    # Get it back
    content = await store.retrieve(file_id)
    print(content.decode())  # "Hello, world!"
    
    # Share with a secure URL
    url = await store.presign(file_id)
    print(f"Download: {url}")
```

That's it! No AWS credentials, no Redis setup, no configuration files. Perfect for development and testing.

## Core Concepts

### Sessions = Security Boundaries

Every file belongs to a **session**. Sessions prevent users from accessing each other's files:

```python
# Files are isolated by session
alice_file = await store.store(
    data=b"Alice's private data",
    mime="text/plain",
    summary="Private file",
    session_id="user_alice"  # Alice's session
)

bob_file = await store.store(
    data=b"Bob's private data", 
    mime="text/plain",
    summary="Private file",
    session_id="user_bob"  # Bob's session
)

# Alice can't access Bob's files
alice_files = await store.list_by_session("user_alice")  # Only Alice's files
bob_files = await store.list_by_session("user_bob")      # Only Bob's files

# Cross-session operations are blocked
await store.copy_file(alice_file, target_session_id="user_bob")  # ❌ Denied
```

### Grid Architecture

Files are organized in a predictable hierarchy:
```
grid/
├── sandbox_id/
│   ├── session_alice/
│   │   ├── file_1
│   │   └── file_2
│   └── session_bob/
│       ├── file_3
│       └── file_4
```

This makes the system **multi-tenant safe** and **federation-ready**.

## File Operations

### Basic Operations

```python
# Store a file
file_id = await store.store(
    data=file_bytes,
    mime="image/jpeg",
    summary="Profile photo",
    filename="avatar.jpg",
    session_id="user_123"
)

# Read file content directly  
content = await store.read_file(file_id, as_text=True)

# Write text files easily
doc_id = await store.write_file(
    content="# My Document\n\nHello world!",
    filename="docs/readme.md",
    mime="text/markdown",
    session_id="user_123"
)

# Check if file exists
if await store.exists(file_id):
    print("File found!")

# Delete file
await store.delete(file_id)
```

### Directory-Like Operations

```python
# List files in a session
files = await store.list_by_session("user_123")

# List files in a "directory"
docs = await store.get_directory_contents("user_123", "docs/")
images = await store.get_directory_contents("user_123", "images/")

# Copy files (within same session only)
backup_id = await store.copy_file(
    file_id,
    new_filename="docs/readme_backup.md"
)
```

### Metadata and Updates

```python
# Get file metadata
meta = await store.metadata(file_id)
print(f"Size: {meta['bytes']} bytes")
print(f"Created: {meta['stored_at']}")

# Update metadata
await store.update_metadata(
    file_id,
    summary="Updated description",
    meta={"version": 2, "author": "Alice"}
)

# Update file content
await store.update_file(
    file_id,
    data=b"New content",
    summary="Updated file"
)
```

## Storage Providers

### Memory Provider (Default)

Perfect for development and testing:

```python
# Automatic - no configuration needed
store = ArtifactStore()
```

- ✅ Zero setup
- ✅ Fast
- ❌ Non-persistent (lost on restart)

### Filesystem Provider

Local disk storage:

```python
store = ArtifactStore(storage_provider="filesystem")

# Or via environment
export ARTIFACT_PROVIDER=filesystem
export ARTIFACT_FS_ROOT=./my-files
```

- ✅ Persistent
- ✅ Good for development
- ✅ Easy debugging
- ❌ Not suitable for production clustering

### AWS S3 Provider

Production-ready cloud storage:

```python
store = ArtifactStore(storage_provider="s3")

# Configure via environment
export ARTIFACT_PROVIDER=s3
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret  
export AWS_REGION=us-east-1
export ARTIFACT_BUCKET=my-bucket
```

- ✅ Highly scalable
- ✅ Durable (99.999999999%)  
- ✅ Native presigned URLs
- ✅ Production ready

### IBM Cloud Object Storage

Enterprise object storage:

```python
# HMAC credentials
store = ArtifactStore(storage_provider="ibm_cos")

export ARTIFACT_PROVIDER=ibm_cos
export AWS_ACCESS_KEY_ID=your_hmac_key
export AWS_SECRET_ACCESS_KEY=your_hmac_secret
export IBM_COS_ENDPOINT=https://s3.us-south.cloud-object-storage.appdomain.cloud

# Or IAM credentials  
store = ArtifactStore(storage_provider="ibm_cos_iam")

export ARTIFACT_PROVIDER=ibm_cos_iam
export IBM_COS_APIKEY=your_api_key
export IBM_COS_INSTANCE_CRN=crn:v1:bluemix:public:cloud-object-storage:...
```

## Session Providers

### Memory Sessions (Default)

Fast, in-memory metadata storage:

```python
store = ArtifactStore(session_provider="memory")
```

- ✅ Fast
- ✅ No setup
- ❌ Non-persistent
- ❌ Single instance only

### Redis Sessions

Persistent, shared metadata storage:

```python
store = ArtifactStore(session_provider="redis")

# Configure via environment
export SESSION_PROVIDER=redis
export SESSION_REDIS_URL=redis://localhost:6379/0
```

- ✅ Persistent
- ✅ Shared across instances
- ✅ Production ready
- ✅ High performance

## Environment Variables

| Variable | Description | Default | Examples |
|----------|-------------|---------|----------|
| **Storage Configuration** |
| `ARTIFACT_PROVIDER` | Storage backend | `memory` | `s3`, `filesystem`, `ibm_cos` |
| `ARTIFACT_BUCKET` | Bucket/container name | `artifacts` | `my-files`, `prod-storage` |
| `ARTIFACT_FS_ROOT` | Filesystem root directory | `./artifacts` | `/data/files`, `~/storage` |
| `ARTIFACT_SANDBOX_ID` | Sandbox identifier | Auto-generated | `myapp`, `prod-env` |
| **Session Configuration** |
| `SESSION_PROVIDER` | Session metadata storage | `memory` | `redis` |
| `SESSION_REDIS_URL` | Redis connection URL | - | `redis://localhost:6379/0` |
| **AWS/S3 Configuration** |
| `AWS_ACCESS_KEY_ID` | AWS access key | - | `AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | - | `abc123...` |
| `AWS_REGION` | AWS region | `us-east-1` | `us-west-2`, `eu-west-1` |
| `S3_ENDPOINT_URL` | Custom S3 endpoint | - | `https://minio.example.com` |
| **IBM COS Configuration** |
| `IBM_COS_ENDPOINT` | IBM COS endpoint | - | `https://s3.us-south.cloud-object-storage.appdomain.cloud` |
| `IBM_COS_APIKEY` | IBM Cloud API key (IAM) | - | `abc123...` |
| `IBM_COS_INSTANCE_CRN` | COS instance CRN (IAM) | - | `crn:v1:bluemix:public:...` |

## Configuration Examples

### Development Setup

```python
# Zero configuration - uses memory providers
from chuk_artifacts import ArtifactStore

store = ArtifactStore()
```

### Local Development with Persistence

```python
import os
from chuk_artifacts import ArtifactStore

# Use filesystem for persistence
os.environ["ARTIFACT_PROVIDER"] = "filesystem"
os.environ["ARTIFACT_FS_ROOT"] = "./dev-storage"

store = ArtifactStore()
```

### Production with S3 + Redis

```python
import os
from chuk_artifacts import ArtifactStore

# Configure S3 storage
os.environ.update({
    "ARTIFACT_PROVIDER": "s3",
    "AWS_ACCESS_KEY_ID": "AKIA...",
    "AWS_SECRET_ACCESS_KEY": "...", 
    "AWS_REGION": "us-east-1",
    "ARTIFACT_BUCKET": "prod-artifacts"
})

# Configure Redis sessions  
os.environ.update({
    "SESSION_PROVIDER": "redis",
    "SESSION_REDIS_URL": "redis://prod-redis:6379/0"
})

store = ArtifactStore()
```

### Docker Compose Example

```yaml
version: '3.8'
services:
  app:
    image: myapp
    environment:
      # Storage
      ARTIFACT_PROVIDER: s3
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
      AWS_REGION: us-east-1
      ARTIFACT_BUCKET: myapp-artifacts
      
      # Sessions  
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

## Presigned URLs

Generate secure, time-limited URLs for file access without exposing your storage credentials:

```python
# Generate download URLs
url = await store.presign(file_id)                    # 1 hour (default)
short_url = await store.presign_short(file_id)        # 15 minutes  
medium_url = await store.presign_medium(file_id)      # 1 hour
long_url = await store.presign_long(file_id)          # 24 hours

# Generate upload URLs
upload_url, artifact_id = await store.presign_upload(
    session_id="user_123",
    filename="upload.jpg",
    mime_type="image/jpeg"
)

# Client uploads to upload_url, then register the file
await store.register_uploaded_artifact(
    artifact_id,
    mime="image/jpeg",
    summary="User uploaded image",
    filename="upload.jpg"
)
```

## Common Use Cases

### Web Application File Uploads

```python
from chuk_artifacts import ArtifactStore

store = ArtifactStore(
    storage_provider="s3",
    session_provider="redis"
)

async def handle_upload(file_data: bytes, filename: str, user_id: str):
    """Handle file upload with user isolation"""
    file_id = await store.store(
        data=file_data,
        mime="application/octet-stream",
        summary=f"Uploaded: {filename}",
        filename=filename,
        session_id=f"user_{user_id}"  # User-specific session
    )
    
    # Return download URL  
    download_url = await store.presign_medium(file_id)
    return {"file_id": file_id, "download_url": download_url}

async def list_user_files(user_id: str):
    """List all files for a user"""
    return await store.list_by_session(f"user_{user_id}")
```

### MCP Server Integration

```python
async def mcp_upload_file(data_b64: str, filename: str, session_id: str):
    """MCP tool for file uploads"""
    import base64
    
    data = base64.b64decode(data_b64)
    file_id = await store.store(
        data=data,
        mime="application/octet-stream",
        summary=f"Uploaded via MCP: {filename}",
        filename=filename,
        session_id=session_id
    )
    
    return {"file_id": file_id, "message": f"Uploaded {filename}"}

async def mcp_list_files(session_id: str, directory: str = ""):
    """MCP tool for listing files"""
    files = await store.get_directory_contents(session_id, directory)
    return {"files": [{"name": f["filename"], "size": f["bytes"]} for f in files]}
```

### Document Management

```python
async def create_document(content: str, path: str, user_id: str):
    """Create a text document"""
    doc_id = await store.write_file(
        content=content,
        filename=path,
        mime="text/plain",
        summary=f"Document: {path}",
        session_id=f"user_{user_id}"
    )
    return doc_id

async def get_document(doc_id: str):
    """Read document content"""
    return await store.read_file(doc_id, as_text=True)

async def list_documents(user_id: str, folder: str = ""):
    """List documents in a folder"""
    return await store.get_directory_contents(f"user_{user_id}", folder)
```

## Batch Operations

Process multiple files efficiently:

```python
# Prepare batch data
files = [
    {
        "data": file1_bytes,
        "mime": "image/jpeg",
        "summary": "Product image 1", 
        "filename": "products/img1.jpg"
    },
    {
        "data": file2_bytes,
        "mime": "image/jpeg",
        "summary": "Product image 2",
        "filename": "products/img2.jpg"  
    }
]

# Store all files at once
file_ids = await store.store_batch(files, session_id="product_catalog")
```

## Error Handling

```python
from chuk_artifacts import (
    ArtifactStoreError,
    ArtifactNotFoundError,
    ProviderError,
    SessionError
)

try:
    data = await store.retrieve(file_id)
except ArtifactNotFoundError:
    print("File not found or expired")
except ProviderError as e:
    print(f"Storage error: {e}")
except SessionError as e:  
    print(f"Session error: {e}")
except ArtifactStoreError as e:
    # This catches security violations like cross-session operations
    print(f"Operation denied: {e}")
```

## Performance

Chuk Artifacts is built for high performance:

- **3,000+ operations/second** in benchmarks
- **Async/await** throughout for non-blocking I/O
- **Connection pooling** with aioboto3
- **Redis caching** for sub-millisecond metadata lookups
- **Batch operations** to reduce overhead

### Benchmark Results
```
✅ File Creation: 3,083 files/sec
✅ File Reading: 4,693 reads/sec  
✅ File Copying: 1,811 copies/sec
✅ Session Listing: ~2ms for 20+ files
```

## Testing

Run the included examples to verify everything works:

```bash
# Basic functionality test
python -c "
import asyncio
from chuk_artifacts import ArtifactStore

async def test():
    async with ArtifactStore() as store:
        file_id = await store.store(
            data=b'Hello, world!',
            mime='text/plain',
            summary='Test file'
        )
        content = await store.retrieve(file_id)
        print(f'Success! Retrieved: {content.decode()}')

asyncio.run(test())
"
```

For development, use the filesystem provider for easy debugging:

```python
import tempfile
from chuk_artifacts import ArtifactStore

async def test_with_filesystem():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ArtifactStore(
            storage_provider="filesystem",
            fs_root=tmpdir
        )
        
        file_id = await store.store(
            data=b"Test content",
            mime="text/plain", 
            summary="Test file"
        )
        
        # Files are visible in tmpdir for debugging
        print(f"Files stored in: {tmpdir}")
```

## Security

### Session Isolation

Sessions provide strict security boundaries:

```python
# Each user gets their own session
alice_session = "user_alice"  
bob_session = "user_bob"

# Users can only access their own files
alice_files = await store.list_by_session(alice_session)
bob_files = await store.list_by_session(bob_session)

# Cross-session operations are blocked
try:
    await store.copy_file(alice_file_id, target_session_id=bob_session)
except ArtifactStoreError:
    print("✅ Cross-session access denied!")
```

### Secure Defaults

- Files expire automatically (configurable TTL)
- Presigned URLs have time limits  
- No sensitive data in error messages
- Environment-based credential configuration
- Session-based access control

## Migration Guide

### From Local Storage

```python
# Before: Simple file operations
with open("file.txt", "rb") as f:
    data = f.read()

# After: Session-based storage
file_id = await store.store(
    data=data,
    mime="text/plain",
    summary="Migrated file",
    filename="file.txt",
    session_id="migration_session"
)
```

### From Basic S3

```python
# Before: Direct S3 operations
s3.put_object(Bucket="bucket", Key="key", Body=data)

# After: Managed artifact storage
file_id = await store.store(
    data=data,
    mime="application/octet-stream", 
    summary="File description",
    filename="myfile.dat"
)
```

## FAQ

### Q: Do I need Redis for development?

**A:** No! The default memory providers work great for development and testing. Only use Redis for production or when you need persistence.

### Q: Can I switch storage providers later?

**A:** Yes! Change the `ARTIFACT_PROVIDER` environment variable. The API stays the same.

### Q: How do sessions work with authentication?

**A:** Sessions are just strings. Map them to your users however you want:

```python
# Example mappings
session_id = f"user_{user.id}"           # User-based
session_id = f"org_{org.id}"             # Organization-based  
session_id = f"project_{project.uuid}"   # Project-based
```

### Q: What happens when files expire?

**A:** Expired files are automatically cleaned up during session cleanup operations. You can also run manual cleanup:

```python
expired_count = await store.cleanup_expired_sessions()
```

### Q: Can I use this with Django/FastAPI/Flask?

**A:** Absolutely! Chuk Artifacts is framework-agnostic. Initialize the store at startup and use it in your request handlers.

### Q: Is it production ready?

**A:** Yes! It's designed for production with:
- High performance (3,000+ ops/sec)
- Multiple storage backends
- Session-based security
- Comprehensive error handling
- Redis support for clustering

---

## Next Steps

1. **Try it out**: `pip install chuk-artifacts`
2. **Start simple**: Use the default memory providers
3. **Add persistence**: Switch to filesystem or S3
4. **Scale up**: Add Redis for production
5. **Secure it**: Use session-based isolation

**Ready to build something awesome?** 🚀
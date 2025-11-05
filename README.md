# Chuk Artifacts

> **Enterprise-grade async artifact storage with grid architecture and session-based security**

A production-ready Python library for storing and managing files across multiple storage backends (S3, IBM COS, filesystem, memory) with Redis-based metadata caching, strict session isolation, and grid-based federation architecture.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Async](https://img.shields.io/badge/async-await-green.svg)](https://docs.python.org/3/library/asyncio.html)
[![Grid Architecture](https://img.shields.io/badge/architecture-grid-purple.svg)](https://github.com/chuk-artifacts)

## Why Chuk Artifacts?

- 🔒 **Session-based security** - Every file belongs to a session, preventing data leaks
- 🏗️ **Grid architecture** - Organized hierarchical storage for infinite scalability
- 🌐 **Multiple backends** - Switch between S3, filesystem, memory without code changes  
- ⚡ **High performance** - 3,000+ operations/second with async/await
- 🎯 **Zero config** - Works out of the box, configure only what you need
- 🔗 **Presigned URLs** - Secure file access without exposing credentials
- 🔄 **Integration ready** - Built-in support for chuk_sessions
- 📊 **Production ready** - Comprehensive monitoring, error handling, and batch operations

## Quick Start

### Installation

```bash
pip install chuk-artifacts
# Or with UV (recommended)
uv add chuk-artifacts
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
    
    # Share with a secure URL (15 minutes)
    url = await store.presign_short(file_id)
    print(f"Download: {url}")
    
    # Update the file
    await store.update_file(
        file_id,
        data=b"Hello, updated world!",
        summary="Updated greeting"
    )
```

That's it! No AWS credentials, no Redis setup, no configuration files. Perfect for development and testing.

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
- **🔒 Security**: Natural isolation between applications and users
- **📈 Scalability**: Supports billions of files across thousands of sessions
- **🌐 Federation**: Easily distribute across multiple storage regions
- **🛠️ Operations**: Predictable paths for backup, monitoring, and cleanup
- **🔍 Debugging**: Clear hierarchical organization for troubleshooting

```python
# Grid paths are generated automatically
file_id = await store.store(data, mime="text/plain", summary="Test")

# But you can inspect them
metadata = await store.metadata(file_id)
print(metadata['key'])  # grid/my-app/session-abc123/artifact-def456

# Parse any grid path
parsed = store.parse_grid_key(metadata['key'])
print(parsed)
# {
#   'sandbox_id': 'my-app',
#   'session_id': 'session-abc123', 
#   'artifact_id': 'artifact-def456',
#   'subpath': None
# }
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

# Users can only access their own files
alice_meta = await store.metadata(alice_file)
alice_files = await store.list_by_session(alice_meta['session_id'])  # Only Alice's files

# Cross-session operations are blocked for security
try:
    await store.copy_file(alice_file, target_session_id="bob_session")
except ArtifactStoreError:
    print("🔒 Cross-session access denied!")  # Security enforced
```

### Integration with chuk_sessions

Chuk Artifacts integrates seamlessly with `chuk_sessions` for advanced session management:

```python
# Automatic session allocation with user mapping
file_id = await store.store(
    data=b"User document",
    mime="application/pdf",
    summary="Important document",
    user_id="alice@company.com",  # Maps to session automatically
    meta={"department": "engineering", "confidential": True}
)

# Access session information
metadata = await store.metadata(file_id)
session_info = await store.get_session_info(metadata['session_id'])
print(f"User: {session_info['user_id']}")
print(f"Custom data: {session_info['custom_metadata']}")

# Extend session lifetime
await store.extend_session_ttl(metadata['session_id'], additional_hours=24)
```

## File Operations

### Basic Operations

```python
# Store various file types
pdf_id = await store.store(
    data=pdf_bytes,
    mime="application/pdf",
    summary="Q4 Financial Report",
    filename="reports/q4-2024.pdf",
    user_id="finance_team",
    meta={"department": "finance", "quarter": "Q4", "year": 2024}
)

# Read file content directly  
content = await store.read_file(pdf_id, as_text=False)  # Returns bytes

# Write text files easily
doc_id = await store.write_file(
    content="# Project Documentation\n\nThis project implements...",
    filename="docs/README.md",
    mime="text/markdown",
    user_id="dev_team",
    meta={"project": "chuk-artifacts", "version": "1.0"}
)

# Update files and metadata
await store.update_file(
    doc_id,
    data=b"# Updated Documentation\n\nThis project now supports...",
    summary="Updated project documentation",
    meta={"version": "1.1", "last_updated": "2024-01-15"}
)

# Check if file exists
if await store.exists(pdf_id):
    print("File found!")

# Safe deletion
deleted = await store.delete(pdf_id)
if deleted:
    print("File deleted successfully")
```

### Directory-Like Operations

```python
# List files in a session
files = await store.list_by_session("session-123")
for file in files:
    print(f"{file['filename']}: {file['bytes']} bytes")

# List files with directory-like structure
docs = await store.list_files("session-123", prefix="docs/")
images = await store.list_files("session-123", prefix="images/")

# Get directory contents (more detailed)
reports = await store.get_directory_contents("session-123", "reports/")
for report in reports:
    print(f"{report['filename']}: {report['summary']}")

# Copy files (within same session only - security enforced)
backup_id = await store.copy_file(
    doc_id,
    new_filename="docs/README_backup.md",
    new_meta={"backup": True, "original_id": doc_id}
)

# Move/rename files
await store.move_file(
    backup_id,
    new_filename="backups/README_v1.md"
)
```

### Advanced Metadata Operations

```python
# Rich metadata support
file_id = await store.store(
    data=image_bytes,
    mime="image/jpeg",
    summary="Product photo",
    filename="products/laptop-pro.jpg",
    user_id="marketing",
    meta={
        "product_id": "LPT-001",
        "category": "electronics", 
        "tags": ["laptop", "professional", "portable"],
        "dimensions": {"width": 1920, "height": 1080},
        "camera_info": {"model": "Canon EOS R5", "iso": 100},
        "photographer": "john@company.com"
    }
)

# Update metadata without changing file content
await store.update_metadata(
    file_id,
    summary="Updated product photo with new angle",
    meta={
        "tags": ["laptop", "professional", "portable", "workspace"],
        "last_edited": "2024-01-15T10:30:00Z"
    },
    merge=True  # Merge with existing metadata
)

# Extend TTL for important files
await store.extend_ttl(file_id, additional_seconds=86400)  # +24 hours
```

## Storage Providers

### Memory Provider (Default)

Perfect for development and testing:

```python
# Automatic - no configuration needed
store = ArtifactStore()

# Or explicitly
from chuk_artifacts.config import configure_memory
configure_memory()
store = ArtifactStore()
```

**Pros:**
- ✅ Zero setup required
- ✅ Fastest performance
- ✅ Perfect for testing

**Cons:**
- ❌ Non-persistent (lost on restart)
- ❌ Memory usage scales with file size
- ❌ Single process only

### Filesystem Provider

Local disk storage with full persistence:

```python
from chuk_artifacts.config import configure_filesystem
configure_filesystem(root="./my-artifacts")
store = ArtifactStore()

# Or via environment
export ARTIFACT_PROVIDER=filesystem
export ARTIFACT_FS_ROOT=/data/artifacts
```

**Pros:**
- ✅ Persistent storage
- ✅ Easy debugging (files visible on disk)
- ✅ Good for development and small deployments
- ✅ Supports file:// presigned URLs

**Cons:**
- ❌ Not suitable for distributed systems
- ❌ No built-in redundancy
- ❌ Limited scalability

### AWS S3 Provider

Production-ready cloud storage:

```python
from chuk_artifacts.config import configure_s3
configure_s3(
    access_key="AKIA...",
    secret_key="...",
    bucket="production-artifacts",
    region="us-east-1"
)
store = ArtifactStore()

# Or via environment
export ARTIFACT_PROVIDER=s3
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1
export ARTIFACT_BUCKET=my-bucket
```

**Pros:**
- ✅ Unlimited scalability
- ✅ 99.999999999% durability
- ✅ Native presigned URLs
- ✅ Global CDN integration
- ✅ Lifecycle policies

**Cons:**
- ❌ Requires AWS account
- ❌ Network latency
- ❌ Pay-per-use pricing

### IBM Cloud Object Storage

Enterprise object storage with multiple authentication methods:

```python
# HMAC Authentication (recommended)
from chuk_artifacts.config import configure_ibm_cos
configure_ibm_cos(
    access_key="your_hmac_key",
    secret_key="your_hmac_secret",
    bucket="enterprise-artifacts",
    endpoint="https://s3.us-south.cloud-object-storage.appdomain.cloud"
)
```

**Pros:**
- ✅ Enterprise-grade security
- ✅ GDPR/compliance friendly
- ✅ Multiple regions globally
- ✅ Competitive pricing

**Cons:**
- ❌ IBM Cloud account required
- ❌ More complex setup than S3

## Session Providers

### Memory Sessions (Default)

Fast, in-memory metadata storage:

```python
store = ArtifactStore(session_provider="memory")
```

**Pros:**
- ✅ Fastest metadata access
- ✅ No external dependencies
- ✅ Perfect for development

**Cons:**
- ❌ Non-persistent
- ❌ Single instance only
- ❌ Memory usage scales with metadata

### Redis Sessions

Persistent, distributed metadata storage:

```python
from chuk_artifacts.config import configure_redis_session
configure_redis_session("redis://localhost:6379/0")
store = ArtifactStore()

# Or via environment
export SESSION_PROVIDER=redis
export SESSION_REDIS_URL=redis://prod-redis:6379/0
```

**Pros:**
- ✅ Persistent metadata
- ✅ Shared across multiple instances
- ✅ Sub-millisecond access times
- ✅ Production ready
- ✅ Automatic expiration

**Cons:**
- ❌ Requires Redis server
- ❌ Additional infrastructure

## Environment Variables Reference

| Variable | Description | Default | Examples |
|----------|-------------|---------|----------|
| **Core Configuration** |
| `ARTIFACT_PROVIDER` | Storage backend | `memory` | `s3`, `filesystem`, `ibm_cos` |
| `ARTIFACT_BUCKET` | Bucket/container name | `artifacts` | `my-files`, `prod-storage` |
| `ARTIFACT_SANDBOX_ID` | Sandbox identifier | Auto-generated | `myapp`, `prod-env`, `user-portal` |
| `SESSION_PROVIDER` | Session metadata storage | `memory` | `redis` |
| **Filesystem Configuration** |
| `ARTIFACT_FS_ROOT` | Filesystem root directory | `./artifacts` | `/data/files`, `~/storage` |
| **Session Configuration** |
| `SESSION_REDIS_URL` | Redis connection URL | - | `redis://localhost:6379/0` |
| **AWS/S3 Configuration** |
| `AWS_ACCESS_KEY_ID` | AWS access key | - | `AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | - | `abc123...` |
| `AWS_REGION` | AWS region | `us-east-1` | `us-west-2`, `eu-west-1` |
| `S3_ENDPOINT_URL` | Custom S3 endpoint | - | `https://minio.example.com` |
| **IBM COS Configuration** |
| `IBM_COS_ENDPOINT` | IBM COS endpoint | Auto-detected | `https://s3.us-south.cloud-object-storage.appdomain.cloud` |

## Configuration Examples

### Development Setup

```python
# Zero configuration - uses memory providers
from chuk_artifacts import ArtifactStore
store = ArtifactStore()

# Or use helper functions
from chuk_artifacts.config import development_setup
store = development_setup()
```

### Local Development with Persistence

```python
from chuk_artifacts.config import testing_setup
store = testing_setup("./dev-storage")  # Filesystem + metadata persistence
```

### Production with S3 + Redis

```python
from chuk_artifacts.config import production_setup
store = production_setup(
    storage_type="s3",
    access_key="AKIA...",
    secret_key="...",
    bucket="prod-artifacts",
    region="us-east-1",
    session_provider="redis"
)
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
      ARTIFACT_SANDBOX_ID: myapp-prod
      
      # Sessions  
      SESSION_PROVIDER: redis
      SESSION_REDIS_URL: redis://redis:6379/0
    depends_on:
      - redis
      
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

volumes:
  redis_data:
```

### Kubernetes Configuration

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: artifacts-config
data:
  ARTIFACT_PROVIDER: "s3"
  AWS_REGION: "us-east-1"
  ARTIFACT_BUCKET: "k8s-artifacts"
  SESSION_PROVIDER: "redis"
  SESSION_REDIS_URL: "redis://redis-service:6379/0"
---
apiVersion: v1
kind: Secret
metadata:
  name: artifacts-secrets
type: Opaque
data:
  AWS_ACCESS_KEY_ID: <base64-encoded>
  AWS_SECRET_ACCESS_KEY: <base64-encoded>
```

## Presigned URLs

Generate secure, time-limited URLs for file access without exposing your storage credentials:

```python
# Generate download URLs with different durations
url = await store.presign(file_id, expires=3600)      # Custom duration
short_url = await store.presign_short(file_id)        # 15 minutes  
medium_url = await store.presign_medium(file_id)      # 1 hour (default)
long_url = await store.presign_long(file_id)          # 24 hours

# URLs work with all storage providers
print(f"S3 URL: https://bucket.s3.amazonaws.com/grid/...")
print(f"Filesystem URL: file:///data/artifacts/grid/...")
print(f"Memory URL: memory://grid/...")

# Generate upload URLs for client-side uploads
upload_url, artifact_id = await store.presign_upload(
    session_id="user_session",
    filename="large-video.mp4",
    mime_type="video/mp4",
    expires=1800  # 30 minutes for large uploads
)

# Client uploads directly to storage
# POST upload_url with file data

# Register the uploaded file
await store.register_uploaded_artifact(
    artifact_id,
    mime="video/mp4",
    summary="User uploaded video",
    filename="large-video.mp4",
    meta={"uploaded_by": "alice", "file_size_mb": 150}
)

# Combined upload + registration
upload_url, artifact_id = await store.presign_upload_and_register(
    mime="image/jpeg",
    summary="Profile picture",
    filename="avatar.jpg",
    session_id="user_session",
    meta={"avatar": True}
)
```

## Batch Operations

Process multiple files efficiently:

```python
# Prepare batch data
files = [
    {
        "data": image1_bytes,
        "mime": "image/jpeg",
        "summary": "Product image 1", 
        "filename": "products/laptop-front.jpg",
        "meta": {"product_id": "LPT-001", "angle": "front"}
    },
    {
        "data": image2_bytes,
        "mime": "image/jpeg",
        "summary": "Product image 2",
        "filename": "products/laptop-side.jpg",
        "meta": {"product_id": "LPT-001", "angle": "side"}
    },
    {
        "data": spec_bytes,
        "mime": "application/pdf",
        "summary": "Product specifications",
        "filename": "products/laptop-specs.pdf",
        "meta": {"product_id": "LPT-001", "type": "specification"}
    }
]

# Store all files atomically
file_ids = await store.store_batch(
    files, 
    session_id="product_catalog",
    ttl=86400  # 24 hours
)

# All files share the same session and metadata TTL
print(f"Stored {len([id for id in file_ids if id])} files successfully")
```

## Common Use Cases

### Web Application File Uploads

```python
from fastapi import FastAPI, UploadFile, HTTPException
from chuk_artifacts import ArtifactStore, ArtifactEnvelope

app = FastAPI()
store = ArtifactStore(
    storage_provider="s3",
    session_provider="redis"
)

@app.post("/upload", response_model=ArtifactEnvelope)
async def handle_upload(file: UploadFile, user_id: str):
    """Handle file upload with automatic session management"""
    content = await file.read()
    
    file_id = await store.store(
        data=content,
        mime=file.content_type or "application/octet-stream",
        summary=f"Uploaded: {file.filename}",
        filename=file.filename,
        user_id=user_id,  # Auto-creates and manages session
        meta={
            "original_name": file.filename,
            "upload_timestamp": datetime.utcnow().isoformat(),
            "user_agent": request.headers.get("user-agent")
        }
    )
    
    return ArtifactEnvelope(
        artifact_id=file_id,
        mime_type=file.content_type,
        bytes=len(content),
        summary=f"Uploaded: {file.filename}",
        meta={"status": "uploaded"}
    )

@app.get("/files/{user_id}")
async def list_user_files(user_id: str):
    """List all files for a user"""
    # Get user's session
    session_id = f"user_{user_id}"  # Or use your session mapping
    files = await store.list_by_session(session_id)
    
    return [
        {
            "file_id": f["artifact_id"],
            "filename": f["filename"],
            "size": f["bytes"],
            "uploaded": f["stored_at"]
        }
        for f in files
    ]

@app.get("/download/{file_id}")
async def get_download_url(file_id: str, user_id: str):
    """Generate secure download URL"""
    try:
        # Verify file belongs to user (optional security check)
        metadata = await store.metadata(file_id)
        expected_session = f"user_{user_id}"
        if metadata["session_id"] != expected_session:
            raise HTTPException(403, "Access denied")
        
        url = await store.presign_medium(file_id)
        return {"download_url": url, "expires_in": 3600}
    except ArtifactNotFoundError:
        raise HTTPException(404, "File not found")
```

### MCP Server Integration

```python
from mcp import Server
from chuk_artifacts import ArtifactStore

# MCP Server with artifact support
server = Server("artifacts-mcp")
store = ArtifactStore()

@server.tool("upload_file")
async def mcp_upload_file(
    data_b64: str, 
    filename: str, 
    session_id: str,
    mime_type: str = "application/octet-stream"
):
    """MCP tool for file uploads"""
    import base64
    
    try:
        data = base64.b64decode(data_b64)
        file_id = await store.store(
            data=data,
            mime=mime_type,
            summary=f"Uploaded via MCP: {filename}",
            filename=filename,
            session_id=session_id,
            meta={"upload_method": "mcp", "tool": "upload_file"}
        )
        
        # Generate immediate download URL
        download_url = await store.presign_medium(file_id)
        
        return {
            "file_id": file_id,
            "filename": filename,
            "size": len(data),
            "download_url": download_url,
            "message": f"Successfully uploaded {filename}"
        }
    except Exception as e:
        return {"error": f"Upload failed: {str(e)}"}

@server.tool("list_files")
async def mcp_list_files(session_id: str, directory: str = ""):
    """MCP tool for listing files"""
    try:
        if directory:
            files = await store.get_directory_contents(session_id, directory)
        else:
            files = await store.list_by_session(session_id)
            
        return {
            "files": [
                {
                    "id": f["artifact_id"],
                    "name": f["filename"],
                    "size": f["bytes"],
                    "type": f["mime"],
                    "created": f["stored_at"],
                    "summary": f["summary"]
                }
                for f in files
            ],
            "total": len(files)
        }
    except Exception as e:
        return {"error": f"List failed: {str(e)}"}

@server.tool("get_file_content")
async def mcp_get_file_content(file_id: str, as_text: bool = True):
    """MCP tool for reading file content"""
    try:
        if as_text:
            content = await store.read_file(file_id, as_text=True)
            return {"content": content, "type": "text"}
        else:
            import base64
            content = await store.read_file(file_id, as_text=False)
            return {
                "content": base64.b64encode(content).decode(),
                "type": "base64",
                "size": len(content)
            }
    except Exception as e:
        return {"error": f"Read failed: {str(e)}"}
```

### Document Management System

```python
class DocumentManager:
    def __init__(self):
        self.store = ArtifactStore(
            storage_provider="s3",
            session_provider="redis"
        )
    
    async def create_document(
        self, 
        content: str, 
        path: str, 
        user_id: str,
        doc_type: str = "text"
    ):
        """Create a new document"""
        doc_id = await self.store.write_file(
            content=content,
            filename=path,
            mime="text/plain" if doc_type == "text" else "text/markdown",
            summary=f"Document: {path}",
            user_id=user_id,
            meta={
                "document_type": doc_type,
                "version": 1,
                "created_by": user_id,
                "last_modified": datetime.utcnow().isoformat()
            }
        )
        return doc_id
    
    async def update_document(self, doc_id: str, content: str, user_id: str):
        """Update document content and bump version"""
        # Get current metadata
        metadata = await self.store.metadata(doc_id)
        current_version = metadata.get("meta", {}).get("version", 1)
        
        # Update with new content and metadata
        await self.store.update_file(
            doc_id,
            data=content.encode(),
            meta={
                **metadata.get("meta", {}),
                "version": current_version + 1,
                "last_modified": datetime.utcnow().isoformat(),
                "last_modified_by": user_id
            }
        )
    
    async def get_document(self, doc_id: str) -> dict:
        """Get document content and metadata"""
        content = await self.store.read_file(doc_id, as_text=True)
        metadata = await self.store.metadata(doc_id)
        
        return {
            "content": content,
            "filename": metadata["filename"],
            "version": metadata.get("meta", {}).get("version", 1),
            "created": metadata["stored_at"],
            "modified": metadata.get("meta", {}).get("last_modified"),
            "size": metadata["bytes"]
        }
    
    async def list_user_documents(self, user_id: str, folder: str = ""):
        """List documents for a user, optionally in a folder"""
        # Get user's session - you'd implement your own user->session mapping
        session_id = f"user_{user_id}"
        
        if folder:
            docs = await self.store.get_directory_contents(session_id, folder)
        else:
            docs = await self.store.list_by_session(session_id)
        
        return [
            {
                "id": doc["artifact_id"],
                "filename": doc["filename"],
                "version": doc.get("meta", {}).get("version", 1),
                "size": doc["bytes"],
                "modified": doc.get("meta", {}).get("last_modified")
            }
            for doc in docs
        ]
```

## Error Handling

Comprehensive error handling for production applications:

```python
from chuk_artifacts import (
    ArtifactStoreError,
    ArtifactNotFoundError,
    ArtifactExpiredError,
    ArtifactCorruptedError,
    ProviderError,
    SessionError
)

async def robust_file_operation(store, file_id):
    """Example of comprehensive error handling"""
    try:
        # Attempt file operation
        data = await store.retrieve(file_id)
        return {"success": True, "data": data}
        
    except ArtifactNotFoundError:
        return {"success": False, "error": "File not found or expired"}
        
    except ArtifactExpiredError:
        return {"success": False, "error": "File has expired"}
        
    except ArtifactCorruptedError:
        # Log for investigation
        logger.error(f"Corrupted metadata for file {file_id}")
        return {"success": False, "error": "File metadata corrupted"}
        
    except ProviderError as e:
        # Storage backend error
        logger.error(f"Storage provider error: {e}")
        return {"success": False, "error": "Storage system temporarily unavailable"}
        
    except SessionError as e:
        # Session/metadata system error
        logger.error(f"Session error: {e}")
        return {"success": False, "error": "Session system error"}
        
    except ArtifactStoreError as e:
        # This includes security violations like cross-session access
        logger.warning(f"Access denied for file {file_id}: {e}")
        return {"success": False, "error": "Access denied"}
        
    except Exception as e:
        # Unexpected error
        logger.exception(f"Unexpected error accessing file {file_id}")
        return {"success": False, "error": "Internal system error"}

# Usage in web handlers
@app.get("/api/files/{file_id}")
async def download_file(file_id: str):
    result = await robust_file_operation(store, file_id)
    if result["success"]:
        return {"download_url": await store.presign(file_id)}
    else:
        raise HTTPException(500, result["error"])
```

## Performance & Monitoring

### Performance Characteristics

Chuk Artifacts is built for high performance:

```python
# Performance benchmarks (typical results)
"""
✅ File Storage:     3,083 files/sec
✅ File Retrieval:   4,693 reads/sec  
✅ File Updates:     2,156 updates/sec
✅ Batch Operations: 1,811 batch items/sec
✅ Session Listing:  ~2ms for 20+ files
✅ Metadata Access:  <1ms with Redis
"""

# Performance tips
async def optimized_operations():
    # Use batch operations for multiple files
    file_ids = await store.store_batch(multiple_files)  # Much faster than individual stores
    
    # Prefer read_file for text content (avoids encoding overhead)
    content = await store.read_file(file_id, as_text=True)  # vs retrieve + decode
    
    # Use appropriate TTL values
    await store.store(data, mime="text/plain", summary="Temp file", ttl=300)  # 5 minutes
    
    # Reuse store instances (connection pooling)
    async with ArtifactStore() as store:  # Connection pool maintained
        for file in files:
            await store.store(...)  # Reuses connections
```

### Monitoring & Observability

```python
# Built-in monitoring capabilities
async def monitor_store_health():
    # Validate configuration and connectivity
    status = await store.validate_configuration()
    print(f"Storage: {status['storage']['status']}")
    print(f"Sessions: {status['session']['status']}")
    print(f"Session Manager: {status['session_manager']['status']}")
    
    # Get operational statistics
    stats = await store.get_stats()
    print(f"Provider: {stats['storage_provider']}")
    print(f"Bucket: {stats['bucket']}")
    print(f"Session Stats: {stats['session_manager']}")
    
    # Get sandbox information
    sandbox_info = await store.get_sandbox_info()
    print(f"Sandbox: {sandbox_info['sandbox_id']}")
    print(f"Grid Pattern: {sandbox_info['grid_prefix_pattern']}")
    
    # Clean up expired sessions
    cleaned = await store.cleanup_expired_sessions()
    print(f"Cleaned up {cleaned} expired sessions")

# Integration with monitoring systems
import logging

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# The library logs important events automatically:
# - File storage/retrieval operations
# - Session management
# - Error conditions
# - Performance metrics
```

## Testing

### Running the Test Suite

```bash
# Run comprehensive smoke tests
python examples/smoke_run.py

# Expected output:
"""
🚀 Comprehensive Artifact Store Smoke Test
==================================================
🧪 Testing: Memory sessions + filesystem storage
   ✅ Configuration validated
   ✅ Basic operations for test-hello.txt (16 bytes)
   ✅ Generated presigned URLs (short/medium/long)
   ✅ Batch storage of 3 items
   ✅ Session listing (2 files)
   ✅ Statistics: filesystem/memory

📊 Test Summary: 34/34 passed
🎉 All tests passed! Artifact Store is working perfectly.
"""

# Run integration demo
python examples/integration_demo.py

# Run grid architecture demo
python examples/grid_demo.py
```

### Custom Testing

```python
import asyncio
import tempfile
from pathlib import Path
from chuk_artifacts import ArtifactStore

async def test_your_use_case():
    """Test your specific use case"""
    # Use temporary directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ArtifactStore(
            storage_provider="filesystem",
            fs_root=tmpdir,
            session_provider="memory"
        )
        
        # Test file operations
        file_id = await store.store(
            data=b"test content",
            mime="text/plain",
            summary="Test file",
            user_id="test_user"
        )
        
        # Verify storage
        assert await store.exists(file_id)
        content = await store.retrieve(file_id)
        assert content == b"test content"
        
        # Test metadata
        metadata = await store.metadata(file_id)
        assert metadata["bytes"] == 12
        assert metadata["mime"] == "text/plain"
        
        # Test session isolation
        files = await store.list_by_session(metadata["session_id"])
        assert len(files) == 1
        assert files[0]["artifact_id"] == file_id
        
        print("✅ All tests passed!")

# Run your tests
asyncio.run(test_your_use_case())
```

### Integration Testing

```python
# Test with different provider combinations
async def test_provider_combinations():
    providers = [
        ("memory", "memory"),
        ("memory", "filesystem"), 
        ("redis", "filesystem"),
        ("redis", "s3")  # Requires credentials
    ]
    
    for session_provider, storage_provider in providers:
        print(f"Testing {session_provider} + {storage_provider}")
        
        store = ArtifactStore(
            session_provider=session_provider,
            storage_provider=storage_provider
        )
        
        # Basic functionality test
        file_id = await store.store(
            data=b"test",
            mime="text/plain",
            summary="Provider test"
        )
        
        data = await store.retrieve(file_id)
        assert data == b"test"
        
        await store.close()
        print(f"✅ {session_provider} + {storage_provider} works!")
```

## Security Best Practices

### Session Isolation

```python
# ✅ Good: Each user gets their own session
user_session = f"user_{user.id}"
await store.store(data, mime="text/plain", session_id=user_session)

# ✅ Good: Organization-level isolation
org_session = f"org_{organization.id}"
await store.store(data, mime="application/pdf", session_id=org_session)

# ❌ Bad: Shared sessions across users
shared_session = "global"  # All users can see each other's files
```

### Access Controls

```python
async def secure_file_access(file_id: str, requesting_user_id: str):
    """Verify user can access file before serving"""
    try:
        metadata = await store.metadata(file_id)
        expected_session = f"user_{requesting_user_id}"
        
        if metadata["session_id"] != expected_session:
            raise HTTPException(403, "Access denied")
            
        return await store.presign(file_id)
        
    except ArtifactNotFoundError:
        raise HTTPException(404, "File not found")
```

### Secure Configuration

```python
# ✅ Good: Use environment variables for secrets
import os
store = ArtifactStore(
    storage_provider=os.getenv("ARTIFACT_PROVIDER", "memory"),
    # Credentials come from environment
)

# ✅ Good: Use IAM roles in production (AWS/IBM)
# No hardcoded credentials needed

# ❌ Bad: Hardcoded credentials
store = ArtifactStore(
    storage_provider="s3",
    access_key="AKIA123...",  # Never do this!
    secret_key="secret123"
)
```

## Migration Guide

### From Basic File Storage

```python
# Before: Simple file operations
import os
import shutil

def save_file(content: bytes, filename: str):
    os.makedirs("uploads", exist_ok=True)
    with open(f"uploads/{filename}", "wb") as f:
        f.write(content)
    return f"uploads/{filename}"

def load_file(filepath: str):
    with open(filepath, "rb") as f:
        return f.read()

# After: Session-based artifact storage
from chuk_artifacts import ArtifactStore

store = ArtifactStore()

async def save_file(content: bytes, filename: str, user_id: str):
    file_id = await store.store(
        data=content,
        mime="application/octet-stream",
        summary=f"Uploaded: {filename}",
        filename=filename,
        user_id=user_id  # Automatic session management
    )
    return file_id

async def load_file(file_id: str):
    return await store.retrieve(file_id)
```

### From Direct S3 Usage

```python
# Before: Direct S3 operations
import boto3

s3 = boto3.client("s3")

def upload_to_s3(data: bytes, key: str):
    s3.put_object(Bucket="mybucket", Key=key, Body=data)
    return key

def download_from_s3(key: str):
    response = s3.get_object(Bucket="mybucket", Key=key)
    return response["Body"].read()

# After: Managed artifact storage with metadata
from chuk_artifacts import ArtifactStore

store = ArtifactStore(storage_provider="s3")

async def upload_file(data: bytes, filename: str, user_id: str):
    file_id = await store.store(
        data=data,
        mime="application/octet-stream",
        summary=f"User upload: {filename}",
        filename=filename,
        user_id=user_id,
        meta={"original_name": filename}
    )
    return file_id

async def download_file(file_id: str):
    return await store.retrieve(file_id)

# Benefits:
# - Automatic grid organization
# - Session-based security  
# - Rich metadata support
# - Presigned URL generation
# - Multiple provider support
```

## FAQ

### Q: Do I need Redis for development?

**A:** No! The default memory providers work great for development and testing. Only use Redis for production when you need persistence or multi-instance deployment.

### Q: Can I switch storage providers without code changes?

**A:** Yes! Just change the `ARTIFACT_PROVIDER` environment variable. The API stays identical across all providers.

### Q: How do I map sessions to my users?

**A:** Sessions are just strings. Create any mapping that makes sense:

```python
# User-based sessions
session_id = f"user_{user.id}"

# Organization-based sessions  
session_id = f"org_{organization.id}"

# Project-based sessions
session_id = f"project_{project.uuid}"

# Multi-tenant sessions
session_id = f"tenant_{tenant_id}_user_{user_id}"
```

### Q: What happens when files expire?

**A:** Files and their metadata are automatically cleaned up:

```python
# Manual cleanup
expired_count = await store.cleanup_expired_sessions()

# Files expire based on TTL when stored
await store.store(data, mime="text/plain", ttl=3600)  # 1 hour
```

### Q: Can I use this with Django/FastAPI/Flask?

**A:** Absolutely! Initialize the store at application startup:

```python
# FastAPI example
from fastapi import FastAPI
from chuk_artifacts import ArtifactStore

app = FastAPI()
store = None

@app.on_event("startup")
async def startup():
    global store
    store = ArtifactStore()

@app.on_event("shutdown") 
async def shutdown():
    await store.close()

@app.post("/upload")
async def upload(file: UploadFile):
    file_id = await store.store(...)
    return {"file_id": file_id}
```

### Q: How do I handle large files?

**A:** Use presigned upload URLs for client-side uploads:

```python
# Generate upload URL
upload_url, artifact_id = await store.presign_upload(
    session_id="user_session",
    filename="large-video.mp4", 
    mime_type="video/mp4",
    expires=1800  # 30 minutes for large files
)

# Client uploads directly to storage
# Then register the uploaded file
await store.register_uploaded_artifact(
    artifact_id,
    mime="video/mp4",
    summary="Large video file"
)
```

### Q: Is it production ready?

**A:** Yes! Features for production deployment:

- **High performance**: 3,000+ operations/second
- **Multiple storage backends**: S3, IBM COS, filesystem
- **Session-based security**: Prevent cross-user access
- **Redis support**: For distributed deployments
- **Grid architecture**: Infinite scalability
- **Comprehensive error handling**: Graceful failure modes
- **Monitoring**: Built-in health checks and statistics
- **Docker/K8s ready**: Environment-based configuration

### Q: How does grid architecture help with scale?

**A:** Grid paths provide natural organization and distribution:

```
grid/
├── app-prod/           # Production environment
│   ├── user-alice/     # Alice's files
│   └── user-bob/       # Bob's files  
├── app-staging/        # Staging environment
│   └── test-session/   # Test files
└── app-analytics/      # Analytics application
    └── batch-001/      # Batch processing
```

Benefits:
- **Federation**: Distribute sandboxes across regions
- **Backup**: Backup specific sandboxes or sessions
- **Cleanup**: Remove entire environments cleanly
- **Monitoring**: Monitor per-application usage
- **Security**: Clear isolation boundaries

---

## Next Steps

1. **Quick Start**: `pip install chuk-artifacts` and try the 30-second example
2. **Development**: Use memory providers for fast iteration
3. **Testing**: Switch to filesystem provider for debugging
4. **Production**: Configure S3 + Redis for scale
5. **Integration**: Add to your web framework of choice

**Ready to build something awesome with enterprise-grade file storage?** 🚀

---

## Links

- **Documentation**: [Full API Reference](./docs/)
- **Examples**: [./examples/](./examples/)
- **Tests**: Run `python examples/smoke_run.py`
- **Issues**: [GitHub Issues](https://github.com/chuk-artifacts/issues)
- **Discussions**: [GitHub Discussions](https://github.com/chuk-artifacts/discussions)
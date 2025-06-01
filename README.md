# Chuk Artifacts

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](https://github.com/your-org/chuk-artifacts)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Asynchronous, multi-backend artifact storage with mandatory session-based security and grid architecture**

Chuk Artifacts provides a production-ready, modular artifact storage system that works seamlessly across multiple storage backends (memory, filesystem, AWS S3, IBM Cloud Object Storage) with Redis or memory-based metadata caching and **strict session-based security**.

## ✨ Key Features

- 🏗️ **Modular Architecture**: 5 specialized operation modules for clean separation of concerns
- 🔒 **Mandatory Session Security**: Strict isolation with no anonymous artifacts or cross-session operations
- 🌐 **Grid Architecture**: `grid/{sandbox_id}/{session_id}/{artifact_id}` paths for federation-ready organization
- 🔄 **Multi-Backend Support**: Memory, filesystem, S3, IBM COS with seamless switching
- ⚡ **High Performance**: Built with async/await for high throughput (3,000+ ops/sec)
- 🔗 **Presigned URLs**: Secure, time-limited access without credential exposure
- 📊 **Batch Operations**: Efficient multi-file uploads and processing
- 🗃️ **Metadata Caching**: Fast lookups with Redis or memory-based sessions
- 📁 **Directory-Like Operations**: Organize files with path-based prefixes
- 🔧 **Zero Configuration**: Works out of the box with sensible defaults
- 🌍 **Production Ready**: Battle-tested with comprehensive error handling

## 🚀 Quick Start

### Installation

```bash
pip install chuk-artifacts
# or with uv
uv add chuk-artifacts
```

### Basic Usage

```python
from chuk_artifacts import ArtifactStore

# Zero-config setup (uses memory provider)
async with ArtifactStore() as store:
    # Store an artifact (session auto-allocated)
    artifact_id = await store.store(
        data=b"Hello, world!",
        mime="text/plain",
        summary="A simple greeting",
        filename="hello.txt"
        # session_id auto-allocated if not provided
    )
    
    # Retrieve it
    data = await store.retrieve(artifact_id)
    print(data.decode())  # "Hello, world!"
    
    # Generate a presigned URL
    download_url = await store.presign_medium(artifact_id)  # 1 hour
```

### Session-Based File Management

```python
async with ArtifactStore() as store:
    # Create files in user sessions
    doc_id = await store.write_file(
        content="# User's Document\n\nPrivate content here.",
        filename="docs/private.md",
        mime="text/markdown",
        session_id="user_alice"
    )
    
    # List files in a session
    files = await store.list_by_session("user_alice")
    print(f"Alice has {len(files)} files")
    
    # List directory-like contents
    docs = await store.get_directory_contents("user_alice", "docs/")
    print(f"Alice's docs: {len(docs)} files")
    
    # Copy within same session (allowed)
    backup_id = await store.copy_file(
        doc_id,
        new_filename="docs/private_backup.md"
    )
    
    # Cross-session operations are BLOCKED for security
    try:
        await store.copy_file(
            doc_id, 
            target_session_id="user_bob"  # This will fail
        )
    except ArtifactStoreError:
        print("✅ Cross-session operations blocked!")
```

### Configuration

```python
# Production setup with S3 and Redis
store = ArtifactStore(
    storage_provider="s3",
    session_provider="redis",
    bucket="my-artifacts"
)

# Or use environment variables
# ARTIFACT_PROVIDER=s3
# SESSION_PROVIDER=redis
# AWS_ACCESS_KEY_ID=your_key
# AWS_SECRET_ACCESS_KEY=your_secret
# ARTIFACT_BUCKET=my-artifacts

store = ArtifactStore()  # Auto-loads configuration
```

## 🏗️ Modular Architecture

Chuk Artifacts uses a clean modular architecture with specialized operation modules:

```
ArtifactStore (Main Coordinator)
├── CoreStorageOperations     # store() and retrieve()
├── MetadataOperations        # metadata, exists, delete, update, list operations
├── PresignedURLOperations    # URL generation and upload workflows  
├── BatchOperations          # store_batch() for multiple files
└── AdminOperations          # validate_configuration, get_stats
```

### Grid Architecture

All artifacts are organized using a consistent grid structure:

```
grid/{sandbox_id}/{session_id}/{artifact_id}
```

**Benefits:**
- **Federation Ready**: Cross-sandbox discovery and routing
- **Session Isolation**: Clear boundaries for security
- **Predictable Paths**: Easy to understand and manage
- **Scalable**: Handles multi-tenant applications

This design provides:
- **Better testability**: Each module can be tested independently
- **Enhanced maintainability**: Clear separation of concerns
- **Easy extensibility**: Add new operation types without touching core
- **Improved debugging**: Isolated functionality for easier troubleshooting

## 🔒 Session-Based Security

### Mandatory Sessions
```python
# Every artifact belongs to a session - no anonymous artifacts
artifact_id = await store.store(
    data=b"content",
    mime="text/plain",
    summary="description"
    # session_id auto-allocated if not provided
)

# Get the session it was allocated to
metadata = await store.metadata(artifact_id)
session_id = metadata["session_id"]
```

### Strict Session Isolation
```python
# Users can only access their own files
alice_files = await store.list_by_session("user_alice")
bob_files = await store.list_by_session("user_bob")

# Cross-session operations are blocked
await store.copy_file(alice_file_id, target_session_id="user_bob")  # ❌ Blocked
await store.move_file(alice_file_id, new_session_id="user_bob")     # ❌ Blocked
```

### Multi-Tenant Safe
```python
# Perfect for SaaS applications
company_a_files = await store.list_by_session("company_a")
company_b_files = await store.list_by_session("company_b")

# Companies cannot access each other's data
# Compliance-ready: GDPR, SOX, HIPAA
```

## 📦 Storage Providers

### Memory Provider
```python
store = ArtifactStore(storage_provider="memory")
```
- Perfect for development and testing
- Zero configuration required
- Non-persistent (data lost on restart)
- **Note**: Provider isolation limitations for testing

### Filesystem Provider
```python
store = ArtifactStore(storage_provider="filesystem")
# Set root directory
os.environ["ARTIFACT_FS_ROOT"] = "./my-artifacts"
```
- Local disk storage
- Persistent across restarts
- `file://` URLs for local access
- **Full session listing support**
- Great for development and staging

### AWS S3 Provider
```python
store = ArtifactStore(storage_provider="s3")
# Configure via environment
os.environ.update({
    "AWS_ACCESS_KEY_ID": "your_key",
    "AWS_SECRET_ACCESS_KEY": "your_secret",
    "AWS_REGION": "us-east-1",
    "ARTIFACT_BUCKET": "my-bucket"
})
```
- Industry-standard cloud storage
- Native presigned URL support
- Highly scalable and durable
- **Full session listing support**
- Perfect for production workloads

### IBM Cloud Object Storage
```python
# HMAC authentication
store = ArtifactStore(storage_provider="ibm_cos")
os.environ.update({
    "AWS_ACCESS_KEY_ID": "your_hmac_key",
    "AWS_SECRET_ACCESS_KEY": "your_hmac_secret",
    "IBM_COS_ENDPOINT": "https://s3.us-south.cloud-object-storage.appdomain.cloud"
})

# IAM authentication
store = ArtifactStore(storage_provider="ibm_cos_iam")
os.environ.update({
    "IBM_COS_APIKEY": "your_api_key",
    "IBM_COS_INSTANCE_CRN": "crn:v1:bluemix:public:cloud-object-storage:..."
})
```

## 🗃️ Session Providers

### Memory Sessions
```python
store = ArtifactStore(session_provider="memory")
```
- In-memory metadata storage
- Fast but non-persistent
- Perfect for testing

### Redis Sessions
```python
store = ArtifactStore(session_provider="redis")
os.environ["SESSION_REDIS_URL"] = "redis://localhost:6379/0"
```
- Persistent metadata storage
- Shared across multiple instances
- Production-ready caching

## 🎯 Common Use Cases

### MCP Server Integration

```python
from chuk_artifacts import ArtifactStore

# Initialize for MCP server
store = ArtifactStore(
    storage_provider="filesystem",  # or "s3" for production
    session_provider="redis"
)

# MCP tool: Upload file
async def upload_file(data_base64: str, filename: str, mime: str, session_id: str):
    data = base64.b64decode(data_base64)
    artifact_id = await store.store(
        data=data,
        mime=mime,
        summary=f"Uploaded: {filename}",
        filename=filename,
        session_id=session_id  # Session isolation
    )
    return {"artifact_id": artifact_id}

# MCP tool: List session files
async def list_session_files(session_id: str, prefix: str = ""):
    files = await store.get_directory_contents(session_id, prefix)
    return {"files": files}

# MCP tool: Copy file (within session only)
async def copy_file(artifact_id: str, new_filename: str):
    new_id = await store.copy_file(artifact_id, new_filename=new_filename)
    return {"new_artifact_id": new_id}
```

### Web Framework Integration

```python
from chuk_artifacts import ArtifactStore

# Initialize once at startup
store = ArtifactStore(
    storage_provider="s3",
    session_provider="redis"
)

async def upload_file(file_content: bytes, filename: str, content_type: str, user_id: str):
    """Handle file upload in FastAPI/Flask with user isolation"""
    artifact_id = await store.store(
        data=file_content,
        mime=content_type,
        summary=f"Uploaded: {filename}",
        filename=filename,
        session_id=f"user_{user_id}"  # User-specific session
    )
    
    # Return download URL
    download_url = await store.presign_medium(artifact_id)
    return {
        "artifact_id": artifact_id,
        "download_url": download_url
    }

async def list_user_files(user_id: str, directory: str = ""):
    """List files for a specific user"""
    return await store.get_directory_contents(f"user_{user_id}", directory)
```

### Advanced File Operations

```python
# Read file content directly
content = await store.read_file(artifact_id, as_text=True)
print(f"File content: {content}")

# Write file with content
new_id = await store.write_file(
    content="# New Document\n\nThis is a new file.",
    filename="documents/new_doc.md",
    mime="text/markdown",
    session_id="user_123"
)

# Move/rename file within session
await store.move_file(
    artifact_id,
    new_filename="documents/renamed_doc.md"
)

# Update metadata
await store.update_metadata(
    artifact_id,
    summary="Updated summary",
    meta={"version": 2, "updated_by": "user_123"}
)

# Extend TTL
await store.extend_ttl(artifact_id, additional_seconds=3600)
```

### Batch Processing

```python
# Prepare multiple files
items = [
    {
        "data": file1_content,
        "mime": "image/png",
        "summary": "Product image 1",
        "filename": "images/product1.png"
    },
    {
        "data": file2_content,
        "mime": "image/png", 
        "summary": "Product image 2",
        "filename": "images/product2.png"
    }
]

# Store all at once with session isolation
artifact_ids = await store.store_batch(items, session_id="product-catalog")
```

## 🧪 Testing

### Run All Tests
```bash
# MCP server scenarios (recommended)
uv run examples/mcp_test_demo.py

# Session security testing
uv run examples/session_operations_demo.py

# Grid architecture demo
uv run examples/grid_demo.py

# Complete verification
uv run examples/complete_verification.py
```

### Test Results
Recent test results show excellent performance:
```
📤 Test 1: Rapid file creation...
✅ Created 20 files in 0.006s (3,083 files/sec)

📋 Test 2: Session listing performance...
✅ Listed 20 files in 0.002s

📁 Test 3: Directory operations...
✅ Listed uploads/ directory (20 files) in 0.002s

📖 Test 4: Batch read operations...
✅ Read 10 files in 0.002s (4,693 reads/sec)

📋 Test 5: Copy operations...
✅ Copied 5 files in 0.003s (1,811 copies/sec)
```

### Development Setup
```python
from chuk_artifacts.config import development_setup

store = development_setup()  # Uses memory providers
```

### Testing Setup
```python
from chuk_artifacts.config import testing_setup

store = testing_setup("./test-artifacts")  # Uses filesystem
```

## 🔧 Configuration

### Environment Variables

```bash
# Storage configuration
ARTIFACT_PROVIDER=s3              # memory, filesystem, s3, ibm_cos, ibm_cos_iam
ARTIFACT_BUCKET=my-artifacts       # Bucket/container name
ARTIFACT_FS_ROOT=./artifacts       # Filesystem root (filesystem provider)
ARTIFACT_SANDBOX_ID=my-app         # Sandbox identifier for multi-tenancy

# Session configuration  
SESSION_PROVIDER=redis             # memory, redis
SESSION_REDIS_URL=redis://localhost:6379/0

# AWS/S3 configuration
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
S3_ENDPOINT_URL=https://custom-s3.com  # Optional: custom S3 endpoint

# IBM COS configuration
IBM_COS_ENDPOINT=https://s3.us-south.cloud-object-storage.appdomain.cloud
IBM_COS_APIKEY=your_api_key        # For IAM auth
IBM_COS_INSTANCE_CRN=crn:v1:...    # For IAM auth
```

### Programmatic Configuration

```python
from chuk_artifacts.config import configure_s3, configure_redis_session

# Configure S3 storage
configure_s3(
    access_key="AKIA...",
    secret_key="...",
    bucket="prod-artifacts",
    region="us-west-2"
)

# Configure Redis sessions
configure_redis_session("redis://prod-redis:6379/1")

# Create store with this configuration
store = ArtifactStore()
```

## 🚀 Performance

- **High Throughput**: 3,000+ file operations per second
- **Async/Await**: Non-blocking I/O for high concurrency
- **Connection Pooling**: Efficient resource usage with aioboto3
- **Metadata Caching**: Sub-millisecond lookups with Redis
- **Batch Operations**: Reduced overhead for multiple files
- **Grid Architecture**: Optimized session-based queries

### Performance Benchmarks
```
✅ File Creation: 3,083 files/sec
✅ File Reading: 4,693 reads/sec  
✅ File Copying: 1,811 copies/sec
✅ Session Listing: ~0.002s for 20+ files
✅ Directory Listing: ~0.002s for filtered results
```

## 🔒 Security

- **Mandatory Sessions**: No anonymous artifacts allowed
- **Session Isolation**: Strict boundaries prevent cross-session access
- **No Cross-Session Operations**: Copy, move, overwrite blocked across sessions
- **Grid Architecture**: Clear audit trail in paths
- **Presigned URLs**: Time-limited access without credential sharing
- **Secure Defaults**: Conservative TTL and expiration settings
- **Credential Isolation**: Environment-based configuration
- **Error Handling**: No sensitive data in logs or exceptions

### Security Validation
```python
# All these operations are blocked for security
await store.copy_file(user_a_file, target_session_id="user_b")  # ❌ Blocked
await store.move_file(user_a_file, new_session_id="user_b")     # ❌ Blocked  

# Security test results:
# ✅ Cross-session copy correctly blocked
# ✅ Cross-session move correctly blocked  
# ✅ Cross-session overwrite correctly blocked
# 🛡️ ALL SECURITY TESTS PASSED!
```

## 📝 API Reference

### Core Methods

#### `store(data, *, mime, summary, meta=None, filename=None, session_id=None, user_id=None, ttl=900)`
Store artifact data with metadata. Session auto-allocated if not provided.

#### `retrieve(artifact_id)`
Retrieve artifact data by ID.

#### `metadata(artifact_id)`
Get artifact metadata.

#### `exists(artifact_id)` / `delete(artifact_id)`
Check existence or delete artifacts.

### Session Operations

#### `create_session(user_id=None, ttl_hours=None)`
Create a new session explicitly.

#### `validate_session(session_id)` / `get_session_info(session_id)`
Session validation and information retrieval.

#### `list_by_session(session_id, limit=100)`
List all artifacts in a session.

#### `get_directory_contents(session_id, directory_prefix="", limit=100)`
Get files in a directory-like structure.

### File Operations

#### `write_file(content, *, filename, mime="text/plain", session_id=None, ...)`
Write content to new file.

#### `read_file(artifact_id, *, encoding="utf-8", as_text=True)`
Read file content directly as text or binary.

#### `copy_file(artifact_id, *, new_filename=None, new_meta=None, summary=None)`
Copy file within same session only (cross-session blocked).

#### `move_file(artifact_id, *, new_filename=None, new_meta=None)`
Move/rename file within same session only (cross-session blocked).

#### `list_files(session_id, prefix="", limit=100)`
List files with optional prefix filtering.

### Metadata Operations

#### `update_metadata(artifact_id, *, summary=None, meta=None, merge=True, **kwargs)`
Update artifact metadata.

#### `extend_ttl(artifact_id, additional_seconds)`
Extend artifact TTL.

### Presigned URLs

#### `presign(artifact_id, expires=3600)`
Generate presigned URL for download.

#### `presign_short(artifact_id)` / `presign_medium(artifact_id)` / `presign_long(artifact_id)`
Generate URLs with predefined durations (15min/1hr/24hr).

#### `presign_upload(session_id=None, filename=None, mime_type="application/octet-stream", expires=3600)`
Generate presigned URL for upload.

#### `register_uploaded_artifact(artifact_id, *, mime, summary, ...)`
Register metadata for presigned uploads.

### Batch Operations

#### `store_batch(items, session_id=None, ttl=900)`
Store multiple artifacts efficiently.

### Admin Operations

#### `validate_configuration()`
Validate storage and session provider connectivity.

#### `get_stats()`
Get storage statistics and configuration info.

### Grid Operations

#### `get_canonical_prefix(session_id)`
Get grid path prefix for session.

#### `generate_artifact_key(session_id, artifact_id)`
Generate grid artifact key.

## 🛠️ Advanced Features

### Error Handling
```python
from chuk_artifacts import (
    ArtifactNotFoundError,
    ArtifactExpiredError, 
    ProviderError,
    SessionError,
    ArtifactStoreError  # For session security violations
)

try:
    await store.copy_file(artifact_id, target_session_id="other_session")
except ArtifactStoreError as e:
    print(f"Security violation: {e}")
except ArtifactNotFoundError:
    print("Artifact not found or expired")
except ProviderError as e:
    print(f"Storage provider error: {e}")
```

### Validation and Monitoring
```python
# Validate configuration
config_status = await store.validate_configuration()
print(f"Storage: {config_status['storage']['status']}")
print(f"Session: {config_status['session']['status']}")

# Get statistics
stats = await store.get_stats()
print(f"Provider: {stats['storage_provider']}")
print(f"Bucket: {stats['bucket']}")
print(f"Sandbox: {stats['sandbox_id']}")
```

### Context Manager Usage
```python
async with ArtifactStore() as store:
    artifact_id = await store.store(
        data=b"Temporary data",
        mime="text/plain",
        summary="Auto-cleanup example"
    )
    # Store automatically closed on exit
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Run tests: `uv run examples/mcp_test_demo.py`
5. Test session operations: `uv run examples/session_operations_demo.py`
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🎯 Roadmap

- [x] **Session-based security** with strict isolation
- [x] **Grid architecture** with federation-ready paths
- [x] **Modular design** with specialized operation modules
- [x] **High-performance operations** (3,000+ ops/sec)
- [x] **Directory-like operations** with prefix filtering
- [x] **Comprehensive testing** with real-world scenarios
- [ ] Azure Blob Storage provider
- [ ] Google Cloud Storage provider  
- [ ] Encryption at rest
- [ ] Artifact versioning
- [ ] Webhook notifications
- [ ] Prometheus metrics export
- [ ] Federation implementation

---

**Made with ❤️ for secure, scalable artifact storage**

*Production-ready artifact storage with mandatory session security and grid architecture*
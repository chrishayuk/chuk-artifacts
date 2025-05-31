# Chuk Artifacts

[![Tests](https://img.shields.io/badge/tests-64%2F64%20passing-brightgreen)](https://github.com/your-org/chuk-artifacts)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Asynchronous, multi-backend artifact storage with session-based security and presigned URLs**

Chuk Artifacts provides a production-ready, modular artifact storage system that works seamlessly across multiple storage backends (memory, filesystem, AWS S3, IBM Cloud Object Storage) with Redis or memory-based metadata caching and **strict session-based security**.

## ✨ Key Features

- 🏗️ **Modular Architecture**: 6 specialized operation modules for clean separation of concerns
- 🔒 **Session-Based Security**: Strict isolation with no cross-session operations allowed
- 🔄 **Multi-Backend Support**: Memory, filesystem, S3, IBM COS with seamless switching
- ⚡ **Fully Async**: Built with async/await for high performance (3,000+ ops/sec)
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
store = ArtifactStore()

# Store an artifact
artifact_id = await store.store(
    data=b"Hello, world!",
    mime="text/plain",
    summary="A simple greeting",
    filename="hello.txt",
    session_id="user_123"  # Session-based isolation
)

# Retrieve it
data = await store.retrieve(artifact_id)
print(data.decode())  # "Hello, world!"

# Generate a presigned URL
download_url = await store.presign_medium(artifact_id)  # 1 hour
```

### Session-Based File Management

```python
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
    print("Cross-session operations blocked!")
```

### With Configuration

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

## 🏗️ Architecture

Chuk Artifacts uses a modular architecture with specialized operation modules:

```
ArtifactStore (Main Coordinator)
├── CoreStorageOperations     # store() and retrieve()
├── PresignedURLOperations    # URL generation and upload workflows
├── MetadataOperations        # metadata, exists, delete, update, list_by_session
├── SessionOperations         # session-based file operations (NEW)
├── BatchOperations          # store_batch() for multiple files
└── AdminOperations          # validate_configuration, get_stats
```

This design provides:
- **Better testability**: Each module can be tested independently
- **Enhanced maintainability**: Clear separation of concerns
- **Easy extensibility**: Add new operation types without touching core
- **Improved debugging**: Isolated functionality for easier troubleshooting
- **Session security**: Dedicated module for secure session operations

## 🔒 Session-Based Security

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

### Directory-Like Organization
```python
# Organize files with path-like prefixes
await store.write_file(content, filename="docs/reports/q1_sales.pdf", session_id="user_123")
await store.write_file(content, filename="docs/contracts/client_a.pdf", session_id="user_123")
await store.write_file(content, filename="images/profile.jpg", session_id="user_123")

# List by directory
docs = await store.get_directory_contents("user_123", "docs/")
reports = await store.get_directory_contents("user_123", "docs/reports/")
images = await store.get_directory_contents("user_123", "images/")
```

## 📦 Storage Providers

### Memory Provider
```python
store = ArtifactStore(storage_provider="memory")
```
- Perfect for development and testing
- Zero configuration required
- Non-persistent (data lost on restart)
- Session listing returns empty (graceful degradation)

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
- Great for development and small deployments

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
    files = await store.list_by_prefix(session_id, prefix)
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

### Multi-Tenant SaaS Application

```python
# Tenant isolation
async def create_tenant_workspace(tenant_id: str):
    """Create isolated workspace for tenant"""
    
    # Create tenant directory structure
    directories = ["documents/", "images/", "reports/", "config/"]
    
    for directory in directories:
        # Create a marker file for the directory
        await store.write_file(
            content=f"# {directory.rstrip('/')} Directory\n\nTenant workspace created.",
            filename=f"{directory}README.md",
            session_id=f"tenant_{tenant_id}"
        )
    
    return {"tenant_id": tenant_id, "directories": directories}

async def get_tenant_usage(tenant_id: str):
    """Get storage usage for a tenant"""
    files = await store.list_by_session(f"tenant_{tenant_id}")
    total_bytes = sum(file.get('bytes', 0) for file in files)
    
    return {
        "tenant_id": tenant_id,
        "file_count": len(files),
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / 1024 / 1024, 2)
    }
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

# Update file content (overwrite)
updated_id = await store.write_file(
    content="# Updated Document\n\nThis content replaces the old file.",
    filename="documents/updated_doc.md",
    session_id="user_123",
    overwrite_artifact_id=old_artifact_id
)
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

### Context Manager Usage

```python
async with ArtifactStore() as store:
    artifact_id = await store.store(
        data=b"Temporary data",
        mime="text/plain",
        summary="Auto-cleanup example",
        session_id="temp_session"
    )
    # Store automatically closed on exit
```

## 🧪 Testing

### Run All Tests
```bash
# Comprehensive smoke test (64+ test scenarios)
uv run examples/artifact_smoke_test.py

# Usage examples with all providers
uv run examples/artifact_usage_examples.py

# Session operations demo (NEW)
uv run examples/session_operations_demo.py
```

### Session Security Testing
```bash
# Run secure session operations demo
uv run examples/session_operations_demo.py

# Output shows:
# ✅ Cross-session copy correctly blocked
# ✅ Cross-session move correctly blocked  
# ✅ Cross-session overwrite correctly blocked
# 🛡️ ALL SECURITY TESTS PASSED!
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
- **Streaming**: Large file support with streaming reads/writes
- **Session Listing**: Optimized prefix-based queries

### Performance Benchmarks
```
✅ Created 50 files in 0.02 seconds (2,933 files/sec)
✅ Listed 50 files in 0.006 seconds
✅ Listed directory (50 files) in 0.005 seconds  
✅ Read 10 files in 0.002 seconds (5,375 reads/sec)
```

## 🔒 Security

- **Session Isolation**: Strict boundaries prevent cross-session access
- **No Cross-Session Operations**: Copy, move, overwrite blocked across sessions
- **Presigned URLs**: Time-limited access without credential sharing
- **Secure Defaults**: Conservative TTL and expiration settings
- **Credential Isolation**: Environment-based configuration
- **Error Handling**: No sensitive data in logs or exceptions
- **Multi-Tenant Ready**: Perfect for SaaS applications

### Security Validation
```python
# All these operations are blocked for security
await store.copy_file(user_a_file, target_session_id="user_b")  # ❌ Blocked
await store.move_file(user_a_file, new_session_id="user_b")     # ❌ Blocked  
await store.write_file(content, session_id="user_b", 
                      overwrite_artifact_id=user_a_file)       # ❌ Blocked
```

## 📝 API Reference

### Core Methods

#### `store(data, *, mime, summary, meta=None, filename=None, session_id=None, ttl=900)`
Store artifact data with metadata.

#### `retrieve(artifact_id)`
Retrieve artifact data by ID.

#### `metadata(artifact_id)`
Get artifact metadata.

#### `exists(artifact_id)` / `delete(artifact_id)`
Check existence or delete artifacts.

### Session Operations (NEW)

#### `list_by_session(session_id, limit=100)`
List all artifacts in a session.

#### `list_by_prefix(session_id, prefix="", limit=100)`
List artifacts with filename prefix (directory-like).

#### `get_directory_contents(session_id, directory_prefix="", limit=100)`
Get files in a directory-like structure.

#### `copy_file(artifact_id, *, new_filename=None, target_session_id=None, new_meta=None)`
Copy file within same session only (cross-session blocked).

#### `move_file(artifact_id, *, new_filename=None, new_session_id=None, new_meta=None)`
Move/rename file within same session only (cross-session blocked).

#### `read_file(artifact_id, *, encoding="utf-8", as_text=True)`
Read file content directly as text or binary.

#### `write_file(content, *, filename, mime="text/plain", session_id=None, overwrite_artifact_id=None)`
Write content to new file or overwrite existing (within same session).

### Presigned URLs

#### `presign(artifact_id, expires=3600)`
Generate presigned URL for download.

#### `presign_short(artifact_id)` / `presign_medium(artifact_id)` / `presign_long(artifact_id)`
Generate URLs with predefined durations (15min/1hr/24hr).

#### `presign_upload(session_id=None, filename=None, mime_type="application/octet-stream", expires=3600)`
Generate presigned URL for upload.

### Batch Operations

#### `store_batch(items, session_id=None, ttl=900)`
Store multiple artifacts efficiently.

### Admin Operations

#### `validate_configuration()`
Validate storage and session provider connectivity.

#### `get_stats()`
Get storage statistics and configuration info.

## 🛠️ Advanced Features

### Custom Providers
```python
# Create custom storage provider
def my_custom_factory():
    @asynccontextmanager
    async def _ctx():
        client = MyCustomClient()
        try:
            yield client
        finally:
            await client.close()
    return _ctx

store = ArtifactStore(s3_factory=my_custom_factory())
```

### Error Handling
```python
from chuk_artifacts import (
    ArtifactNotFoundError,
    ArtifactExpiredError, 
    ProviderError,
    ArtifactStoreError  # NEW: for session security violations
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
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Run tests: `uv run examples/artifact_smoke_test.py`
5. Test session operations: `uv run examples/session_operations_demo.py`
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- **Documentation**: [docs.example.com](https://docs.example.com)
- **Issue Tracker**: [github.com/your-org/chuk-artifacts/issues](https://github.com/your-org/chuk-artifacts/issues)
- **PyPI**: [pypi.org/project/chuk-artifacts](https://pypi.org/project/chuk-artifacts)

## 🎯 Roadmap

- [x] **Session-based security** with strict isolation
- [x] **Directory-like operations** with prefix filtering
- [x] **High-performance operations** (3,000+ ops/sec)
- [ ] Azure Blob Storage provider
- [ ] Google Cloud Storage provider
- [ ] Encryption at rest
- [ ] Artifact versioning
- [ ] Webhook notifications
- [ ] Prometheus metrics export

---

**Made with ❤️ by the Chuk team**

*Secure, fast, and reliable artifact storage for modern applications*
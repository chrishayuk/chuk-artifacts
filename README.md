# Chuk Artifacts

[![Tests](https://img.shields.io/badge/tests-64%2F64%20passing-brightgreen)](https://github.com/your-org/chuk-artifacts)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Asynchronous, multi-backend artifact storage with metadata caching and presigned URLs**

Chuk Artifacts provides a production-ready, modular artifact storage system that works seamlessly across multiple storage backends (memory, filesystem, AWS S3, IBM Cloud Object Storage) with Redis or memory-based metadata caching.

## ✨ Key Features

- 🏗️ **Modular Architecture**: 5 specialized operation modules for clean separation of concerns
- 🔄 **Multi-Backend Support**: Memory, filesystem, S3, IBM COS with seamless switching
- ⚡ **Fully Async**: Built with async/await for high performance
- 🔗 **Presigned URLs**: Secure, time-limited access without credential exposure
- 📊 **Batch Operations**: Efficient multi-file uploads and processing
- 🗃️ **Metadata Caching**: Fast lookups with Redis or memory-based sessions
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
    filename="hello.txt"
)

# Retrieve it
data = await store.retrieve(artifact_id)
print(data.decode())  # "Hello, world!"

# Generate a presigned URL
download_url = await store.presign_medium(artifact_id)  # 1 hour
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
├── MetadataOperations        # metadata, exists, delete, update
├── BatchOperations          # store_batch() for multiple files
└── AdminOperations          # validate_configuration, get_stats
```

This design provides:
- **Better testability**: Each module can be tested independently
- **Enhanced maintainability**: Clear separation of concerns
- **Easy extensibility**: Add new operation types without touching core
- **Improved debugging**: Isolated functionality for easier troubleshooting

## 📦 Storage Providers

### Memory Provider
```python
store = ArtifactStore(storage_provider="memory")
```
- Perfect for development and testing
- Zero configuration required
- Non-persistent (data lost on restart)
- Isolation between async contexts

### Filesystem Provider
```python
store = ArtifactStore(storage_provider="filesystem")
# Set root directory
os.environ["ARTIFACT_FS_ROOT"] = "./my-artifacts"
```
- Local disk storage
- Persistent across restarts
- `file://` URLs for local access
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

### Web Framework Integration

```python
from chuk_artifacts import ArtifactStore

# Initialize once at startup
store = ArtifactStore(
    storage_provider="s3",
    session_provider="redis"
)

async def upload_file(file_content: bytes, filename: str, content_type: str):
    """Handle file upload in FastAPI/Flask"""
    artifact_id = await store.store(
        data=file_content,
        mime=content_type,
        summary=f"Uploaded: {filename}",
        filename=filename
    )
    
    # Return download URL
    download_url = await store.presign_medium(artifact_id)
    return {
        "artifact_id": artifact_id,
        "download_url": download_url
    }
```

### Batch Processing

```python
# Prepare multiple files
items = [
    {
        "data": file1_content,
        "mime": "image/png",
        "summary": "Product image 1",
        "filename": "product1.png"
    },
    {
        "data": file2_content,
        "mime": "image/png", 
        "summary": "Product image 2",
        "filename": "product2.png"
    }
]

# Store all at once
artifact_ids = await store.store_batch(items, session_id="product-images")
```

### Advanced Metadata Management

```python
# Store with custom metadata
artifact_id = await store.store(
    data=image_data,
    mime="image/png",
    summary="Product photo",
    filename="product.png",
    meta={
        "product_id": "12345",
        "photographer": "John Doe",
        "category": "electronics"
    }
)

# Update metadata later
await store.update_metadata(
    artifact_id,
    summary="Updated product photo",
    meta={"edited": True, "version": 2}
)

# Extend TTL
await store.extend_ttl(artifact_id, 3600)  # Add 1 hour
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

## 🧪 Testing

### Run All Tests
```bash
# Comprehensive smoke test (64 test scenarios)
uv run examples/artifact_smoke_test.py

# Usage examples
uv run examples/artifact_usage_examples.py
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

## 🚀 Performance

- **Async/Await**: Non-blocking I/O for high concurrency
- **Connection Pooling**: Efficient resource usage with aioboto3
- **Metadata Caching**: Fast lookups with Redis
- **Batch Operations**: Reduced overhead for multiple files
- **Streaming**: Large file support with streaming reads/writes

## 🔒 Security

- **Presigned URLs**: Time-limited access without credential sharing
- **Secure Defaults**: Conservative TTL and expiration settings
- **Credential Isolation**: Environment-based configuration
- **Error Handling**: No sensitive data in logs or exceptions

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
    ProviderError
)

try:
    data = await store.retrieve("invalid-id")
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

## 📝 API Reference

### Core Methods

#### `store(data, *, mime, summary, meta=None, filename=None, session_id=None, ttl=900)`
Store artifact data with metadata.

**Parameters:**
- `data` (bytes): The artifact data
- `mime` (str): MIME type (e.g., "text/plain", "image/png")
- `summary` (str): Human-readable description
- `meta` (dict, optional): Additional metadata
- `filename` (str, optional): Original filename
- `session_id` (str, optional): Session identifier for organization
- `ttl` (int, optional): Metadata TTL in seconds (default: 900)

**Returns:** `str` - Unique artifact identifier

#### `retrieve(artifact_id)`
Retrieve artifact data by ID.

**Parameters:**
- `artifact_id` (str): The artifact identifier

**Returns:** `bytes` - The artifact data

#### `metadata(artifact_id)`
Get artifact metadata.

**Returns:** `dict` - Metadata including size, MIME type, timestamps, etc.

#### `exists(artifact_id)`
Check if artifact exists and hasn't expired.

**Returns:** `bool`

#### `delete(artifact_id)`
Delete artifact and its metadata.

**Returns:** `bool` - True if deleted, False if not found

### Presigned URLs

#### `presign(artifact_id, expires=3600)`
Generate presigned URL for download.

#### `presign_short(artifact_id)` / `presign_medium(artifact_id)` / `presign_long(artifact_id)`
Generate URLs with predefined durations (15min/1hr/24hr).

#### `presign_upload(session_id=None, filename=None, mime_type="application/octet-stream", expires=3600)`
Generate presigned URL for upload.

**Returns:** `tuple[str, str]` - (upload_url, artifact_id)

### Batch Operations

#### `store_batch(items, session_id=None, ttl=900)`
Store multiple artifacts efficiently.

**Parameters:**
- `items` (list): List of dicts with keys: data, mime, summary, meta, filename

**Returns:** `list[str]` - List of artifact IDs

### Admin Operations

#### `validate_configuration()`
Validate storage and session provider connectivity.

#### `get_stats()`
Get storage statistics and configuration info.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Run tests: `uv run examples/artifact_smoke_test.py`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- **Documentation**: [docs.example.com](https://docs.example.com)
- **Issue Tracker**: [github.com/your-org/chuk-artifacts/issues](https://github.com/your-org/chuk-artifacts/issues)
- **PyPI**: [pypi.org/project/chuk-artifacts](https://pypi.org/project/chuk-artifacts)

## 🎯 Roadmap

- [ ] Azure Blob Storage provider
- [ ] Google Cloud Storage provider
- [ ] Encryption at rest
- [ ] Artifact versioning
- [ ] Webhook notifications
- [ ] Prometheus metrics export

---

**Made with ❤️ by the Chuk team**
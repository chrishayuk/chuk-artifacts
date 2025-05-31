# examples/artifact_comprehensive_smoke_test.py
# =============================================================================
# Usage Examples: Clean ArtifactStore with Auto .env Loading
# =============================================================================

# =============================================================================
# Example 1: Zero-config usage (memory storage)
# =============================================================================
"""
No .env file needed - works out of the box!
"""
from chuk_artifacts. import STORE

async def basic_usage():
    # Store a simple text file
    artifact_id = await STORE.store(
        data=b"Hello, world!",
        mime="text/plain", 
        summary="A simple greeting"
    )
    
    # Retrieve it
    data = await STORE.retrieve(artifact_id)
    print(f"Retrieved: {data.decode()}")
    
    # Get metadata
    meta = await STORE.metadata(artifact_id)
    print(f"Stored at: {meta['stored_at']}")

# =============================================================================
# Example 2: With .env configuration
# =============================================================================
"""
Create a .env file:
    ARTIFACT_PROVIDER=filesystem
    SESSION_PROVIDER=redis
    ARTIFACT_FS_ROOT=./my-artifacts
    SESSION_REDIS_URL=redis://localhost:6379/0
"""
from chuk_artifacts import STORE  # Auto-loads .env!

async def configured_usage():
    # Store an image
    with open("diagram.png", "rb") as f:
        image_data = f.read()
    
    artifact_id = await STORE.store(
        data=image_data,
        mime="image/png",
        summary="System architecture diagram",
        filename="diagram.png",
        meta={"author": "engineering", "version": "1.0"}
    )
    
    # Generate a presigned URL (works with filesystem too!)
    url = await STORE.presign_short(artifact_id)  # 15 minutes
    print(f"Download URL: {url}")

# =============================================================================
# Example 3: Multiple stores with different configs
# =============================================================================
from chuk_artifacts import ArtifactStore

async def multi_store_usage():
    # Default store (uses .env)
    default_store = ArtifactStore()
    
    # Temporary in-memory store
    temp_store = ArtifactStore(
        storage_provider="memory",
        session_provider="memory"
    )
    
    # Production store with explicit config
    prod_store = ArtifactStore(
        storage_provider="s3",
        session_provider="redis",
        bucket="prod-artifacts"
    )
    
    # Use them independently
    await default_store.store(b"dev data", mime="text/plain", summary="Development artifact")
    await temp_store.store(b"temp data", mime="text/plain", summary="Temporary artifact") 
    await prod_store.store(b"prod data", mime="text/plain", summary="Production artifact")

# =============================================================================
# Example 4: Batch operations
# =============================================================================
async def batch_usage():
    from chuk_artifacts import STORE
    
    # Prepare multiple files
    items = [
        {
            "data": b"File 1 content",
            "mime": "text/plain",
            "summary": "First file",
            "filename": "file1.txt"
        },
        {
            "data": b"File 2 content", 
            "mime": "text/plain",
            "summary": "Second file",
            "filename": "file2.txt"
        }
    ]
    
    # Store all at once
    artifact_ids = await STORE.store_batch(items, session_id="batch-upload")
    print(f"Stored {len(artifact_ids)} artifacts")

# =============================================================================
# Example 5: Error handling and validation
# =============================================================================
async def robust_usage():
    from chuk_artifacts import STORE, ArtifactNotFoundError
    
    # Validate configuration
    validation = await STORE.validate_configuration()
    print(f"Storage: {validation['storage']['status']}")
    print(f"Session: {validation['session']['status']}")
    
    # Store with error handling
    try:
        artifact_id = await STORE.store(
            data=b"Important data",
            mime="application/octet-stream",
            summary="Critical business data"
        )
        
        # Check if it exists
        if await STORE.exists(artifact_id):
            print("Artifact stored successfully")
            
        # Retrieve with error handling
        data = await STORE.retrieve(artifact_id)
        
    except ArtifactNotFoundError:
        print("Artifact not found or expired")
    except Exception as e:
        print(f"Storage error: {e}")

# =============================================================================
# Example 6: Context manager usage
# =============================================================================
async def context_manager_usage():
    from chuk_artifacts import ArtifactStore
    
    async with ArtifactStore() as store:
        artifact_id = await store.store(
            data=b"Context managed data",
            mime="text/plain",
            summary="Automatically cleaned up"
        )
        
        data = await store.retrieve(artifact_id)
        print(f"Data: {data.decode()}")
    # Store is automatically closed here

# =============================================================================
# Example 7: Integration with web frameworks
# =============================================================================
"""
Flask/FastAPI integration example
"""
from chuk_artifacts import STORE

# FastAPI example
async def upload_file(file_content: bytes, filename: str, content_type: str):
    artifact_id = await STORE.store(
        data=file_content,
        mime=content_type,
        summary=f"Uploaded file: {filename}",
        filename=filename
    )
    
    # Return a download URL
    download_url = await STORE.presign_medium(artifact_id)  # 1 hour
    
    return {
        "artifact_id": artifact_id,
        "download_url": download_url,
        "filename": filename
    }

# =============================================================================
# Example 8: Development vs Production patterns
# =============================================================================

# Development: No .env file needed
"""
from chuk_artifacts import STORE
# Uses memory by default - perfect for development!
"""

# Staging: Simple .env file
"""
# .env
ARTIFACT_PROVIDER=filesystem
ARTIFACT_FS_ROOT=./staging-artifacts
"""

# Production: Full .env configuration  
"""
# .env
ARTIFACT_PROVIDER=s3
SESSION_PROVIDER=redis
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
SESSION_REDIS_URL=redis://prod-redis:6379/0
ARTIFACT_BUCKET=prod-artifacts
"""

# All environments use the same code:
from chuk_artifacts import STORE  # Auto-configures based on environment!
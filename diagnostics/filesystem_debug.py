#!/usr/bin/env python3
"""
Simple test to debug the filesystem issue step by step.
"""

import asyncio
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chuk_artifacts.store import ArtifactStore


async def simple_filesystem_test():
    """Simple test to debug the issue."""
    print("🔧 Simple Filesystem Debug Test")
    print("=" * 50)
    
    temp_dir = Path(tempfile.mkdtemp(prefix="simple_fs_test_"))
    
    try:
        # Set ALL environment variables explicitly
        env_vars = {
            "ARTIFACT_FS_ROOT": str(temp_dir),
            "SESSION_PROVIDER": "memory",
            "ARTIFACT_BUCKET": "chuk-sandbox-2",
            "CHUK_SESSION_PROVIDER": "memory",
            "ARTIFACT_PROVIDER": "filesystem",
        }
        
        original_env = {}
        for key, value in env_vars.items():
            original_env[key] = os.getenv(key)
            os.environ[key] = value
            print(f"  🔧 {key}: {value}")
        
        try:
            print(f"\n📁 Temp directory: {temp_dir}")
            
            # Create store with explicit parameters
            store = ArtifactStore(
                storage_provider="filesystem",
                session_provider="memory",
                bucket="chuk-sandbox-2",
                sandbox_id="debug-sandbox"
            )
            
            print(f"📊 Store created:")
            print(f"  bucket: {store.bucket}")
            print(f"  sandbox_id: {store.sandbox_id}")
            print(f"  storage_provider: {store._storage_provider_name}")
            print(f"  session_provider: {store._session_provider_name}")
            
            # Create session
            session_id = await store.create_session(user_id="debug_user")
            print(f"\n🔗 Created session: {session_id}")
            
            # Store artifact
            artifact_id = await store.store(
                data=b"Simple debug test",
                mime="text/plain",
                summary="Debug test",
                filename="debug.txt",
                session_id=session_id
            )
            print(f"📦 Stored artifact: {artifact_id}")
            
            # Show complete filesystem structure
            print(f"\n📁 Complete filesystem structure:")
            def show_tree(path, prefix=""):
                if not path.exists():
                    print(f"{prefix}❌ Directory doesn't exist: {path}")
                    return
                    
                items = sorted(path.iterdir())
                for i, item in enumerate(items):
                    is_last = i == len(items) - 1
                    if item.is_dir():
                        print(f"{prefix}{'└── ' if is_last else '├── '}📁 {item.name}/")
                        show_tree(item, prefix + ("    " if is_last else "│   "))
                    else:
                        size = item.stat().st_size
                        print(f"{prefix}{'└── ' if is_last else '├── '}📄 {item.name} ({size}b)")
            
            show_tree(temp_dir)
            
            # Check expected bucket
            expected_bucket = temp_dir / store.bucket
            print(f"\n🔍 Expected bucket: {expected_bucket}")
            print(f"    Exists: {expected_bucket.exists()}")
            
            if expected_bucket.exists():
                artifact_files = list(expected_bucket.rglob(artifact_id))
                print(f"    Artifact files found: {len(artifact_files)}")
                for file in artifact_files:
                    rel_path = file.relative_to(temp_dir)
                    print(f"      📄 {rel_path}")
            
            # Search entire filesystem for artifact
            all_artifact_files = list(temp_dir.rglob(artifact_id))
            print(f"\n🔍 All files matching artifact ID:")
            if all_artifact_files:
                for file in all_artifact_files:
                    rel_path = file.relative_to(temp_dir)
                    print(f"    📄 {rel_path}")
            else:
                print("    ❌ No files found matching artifact ID!")
            
            # Try to retrieve to see if it works
            try:
                data = await store.retrieve(artifact_id)
                print(f"\n✅ Retrieved data: {data.decode()}")
            except Exception as e:
                print(f"\n❌ Failed to retrieve: {e}")
            
            await store.close()
            
        finally:
            # Restore environment
            for key, original_value in original_env.items():
                if original_value is not None:
                    os.environ[key] = original_value
                else:
                    os.environ.pop(key, None)
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(simple_filesystem_test())
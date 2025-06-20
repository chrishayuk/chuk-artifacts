#!/usr/bin/env python3
"""
Simple test to verify the filesystem provider fix works.
"""

import asyncio
import sys
import tempfile
import shutil
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chuk_artifacts.store import ArtifactStore
from chuk_artifacts.providers.filesystem import factory, create_temp_filesystem_factory


async def debug_filesystem_state(label: str, temp_dir: Path):
    """Debug helper to show filesystem state."""
    print(f"\n🔍 DEBUG - {label}:")
    print(f"  Root directory: {temp_dir}")
    print(f"  Root exists: {temp_dir.exists()}")
    
    if temp_dir.exists():
        all_files = list(temp_dir.rglob("*"))
        print(f"  Total items: {len(all_files)}")
        
        for item in all_files[:10]:  # Show first 10 items
            item_type = "📁" if item.is_dir() else "📄"
            rel_path = item.relative_to(temp_dir)
            print(f"    {item_type} {rel_path}")
        
        if len(all_files) > 10:
            print(f"    ... and {len(all_files) - 10} more items")


async def test_filesystem_provider_direct():
    """Test filesystem provider directly without ArtifactStore."""
    print("🧪 Testing filesystem provider directly...")
    
    temp_dir = Path(tempfile.mkdtemp(prefix="fs_direct_"))
    
    try:
        await debug_filesystem_state("Before creating factory", temp_dir)
        
        # Test 1: Create factory and store data
        factory1 = factory(temp_dir)
        
        async with factory1() as client1:
            await client1.put_object(
                Bucket="test-bucket",
                Key="test-key", 
                Body=b"test data from client1",
                ContentType="text/plain",
                Metadata={"test": "true"}
            )
            
            stats1 = await client1._debug_get_stats()
            print(f"  📊 Client1 stats: {stats1}")
        
        await debug_filesystem_state("After client1 stores data", temp_dir)
        
        # Test 2: Create different factory and retrieve data
        factory2 = factory(temp_dir)
        
        async with factory2() as client2:
            stats2 = await client2._debug_get_stats()
            print(f"  📊 Client2 stats: {stats2}")
            
            # This should work since same filesystem
            response = await client2.get_object(Bucket="test-bucket", Key="test-key")
            assert response["Body"] == b"test data from client1"
            print(f"  ✅ Client2 retrieved data: {response['Body'].decode()}")
        
        await debug_filesystem_state("After client2 retrieves data", temp_dir)
        
        print("✅ Filesystem provider direct test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Filesystem provider direct test FAILED: {e}")
        import traceback
        traceback.print_exc()
        await debug_filesystem_state("After failure", temp_dir)
        return False
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def test_artifactstore_filesystem():
    """Test ArtifactStore with filesystem provider."""
    print("\n🧪 Testing ArtifactStore with filesystem provider...")
    
    temp_dir = Path(tempfile.mkdtemp(prefix="fs_artifactstore_"))
    
    try:
        import os
        
        # Override environment to force filesystem and memory providers
        original_fs_root = os.getenv("ARTIFACT_FS_ROOT")
        original_session_provider = os.getenv("SESSION_PROVIDER")
        os.environ["ARTIFACT_FS_ROOT"] = str(temp_dir)
        os.environ["SESSION_PROVIDER"] = "memory"
        
        try:
            await debug_filesystem_state("Before creating ArtifactStore", temp_dir)
            
            # Create ArtifactStore with filesystem provider
            store = ArtifactStore(
                storage_provider="filesystem", 
                session_provider="memory"
            )
            
            await debug_filesystem_state("After creating ArtifactStore", temp_dir)
            
            # Create a session
            session_id = await store.create_session(user_id="test_user")
            print(f"  ✅ Created session: {session_id}")
            
            await debug_filesystem_state("After creating session", temp_dir)
            
            # Store an artifact
            artifact_id = await store.store(
                data=b"Hello from filesystem ArtifactStore!",
                mime="text/plain",
                summary="Test artifact",
                filename="test.txt",
                session_id=session_id
            )
            print(f"  ✅ Stored artifact: {artifact_id}")
            
            await debug_filesystem_state("After storing artifact", temp_dir)
            
            # Verify file exists in correct bucket
            bucket_dir = temp_dir / store.bucket  # Use actual bucket name
            found_files = list(bucket_dir.rglob(artifact_id))
            if len(found_files) > 0:
                print(f"  📁 Artifact found in bucket {store.bucket}: {found_files[0]}")
            else:
                print(f"  ⚠️ Artifact not found in expected bucket {store.bucket}")
            
            # Retrieve the artifact
            data = await store.retrieve(artifact_id)
            assert data == b"Hello from filesystem ArtifactStore!"
            print(f"  ✅ Retrieved artifact: {data.decode()}")
            
            # Get metadata
            metadata = await store.metadata(artifact_id)
            assert metadata["session_id"] == session_id
            print(f"  ✅ Got metadata: {metadata['summary']}")
            
            await store.close()
            
            await debug_filesystem_state("After closing store", temp_dir)
            
            print("✅ ArtifactStore filesystem test PASSED!")
            return True
            
        finally:
            # Restore original environment
            if original_fs_root is not None:
                os.environ["ARTIFACT_FS_ROOT"] = original_fs_root
            else:
                os.environ.pop("ARTIFACT_FS_ROOT", None)
                
            if original_session_provider is not None:
                os.environ["SESSION_PROVIDER"] = original_session_provider
            else:
                os.environ.pop("SESSION_PROVIDER", None)
                
            if original_session_provider is not None:
                os.environ["SESSION_PROVIDER"] = original_session_provider
            else:
                os.environ.pop("SESSION_PROVIDER", None)
        
    except Exception as e:
        print(f"❌ ArtifactStore filesystem test FAILED: {e}")
        import traceback
        traceback.print_exc()
        await debug_filesystem_state("After failure", temp_dir)
        return False
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def test_filesystem_persistence():
    """Test filesystem persistence across store instances."""
    print("\n🧪 Testing filesystem persistence...")
    
    temp_dir = Path(tempfile.mkdtemp(prefix="fs_persistence_"))
    
    try:
        import os
        
        original_fs_root = os.getenv("ARTIFACT_FS_ROOT")
        original_session_provider = os.getenv("SESSION_PROVIDER")
        os.environ["ARTIFACT_FS_ROOT"] = str(temp_dir)
        os.environ["SESSION_PROVIDER"] = "memory"
        
        try:
            # Phase 1: Store data
            print("  📝 Phase 1: Storing data...")
            store1 = ArtifactStore(storage_provider="filesystem", session_provider="memory")
            session_id = await store1.create_session(user_id="persist_user")
            
            artifact_id = await store1.store(
                data=b"Persistent filesystem data",
                mime="text/plain",
                summary="Persistence test",
                session_id=session_id
            )
            print(f"  ✅ Stored artifact: {artifact_id}")
            
            await store1.close()
            print("  ✅ Closed first store")
            
            await debug_filesystem_state("After first store closes", temp_dir)
            
            # Phase 2: Create new store and retrieve data
            print("  📖 Phase 2: Retrieving data with new store...")
            store2 = ArtifactStore(storage_provider="filesystem", session_provider="memory")
            
            # Data should still be accessible
            data = await store2.retrieve(artifact_id)
            assert data == b"Persistent filesystem data"
            print(f"  ✅ Retrieved persisted data: {data.decode()}")
            
            # Metadata should still be accessible
            metadata = await store2.metadata(artifact_id)
            assert metadata["summary"] == "Persistence test"
            print(f"  ✅ Retrieved persisted metadata: {metadata['summary']}")
            
            await store2.close()
            
            print("✅ Filesystem persistence test PASSED!")
            return True
            
        finally:
            # Restore original environment
            if original_fs_root is not None:
                os.environ["ARTIFACT_FS_ROOT"] = original_fs_root
            else:
                os.environ.pop("ARTIFACT_FS_ROOT", None)
        
    except Exception as e:
        print(f"❌ Filesystem persistence test FAILED: {e}")
        import traceback
        traceback.print_exc()
        await debug_filesystem_state("After persistence failure", temp_dir)
        return False
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def test_filesystem_temp_factory():
    """Test temporary filesystem factory."""
    print("\n🧪 Testing temporary filesystem factory...")
    
    try:
        # Create temp factory
        temp_factory, temp_path = create_temp_filesystem_factory()
        print(f"  📁 Temp directory: {temp_path}")
        
        async with temp_factory() as client:
            await client.put_object(
                Bucket="temp-bucket",
                Key="temp-file",
                Body=b"Temporary filesystem data",
                ContentType="text/plain",
                Metadata={"temp": "true"}
            )
            
            response = await client.get_object(Bucket="temp-bucket", Key="temp-file")
            assert response["Body"] == b"Temporary filesystem data"
            print(f"  ✅ Temp factory works: {response['Body'].decode()}")
        
        # Verify temp directory exists and has files
        assert temp_path.exists(), "Temp directory should exist"
        files = list(temp_path.rglob("*"))
        assert len(files) > 0, "Temp directory should have files"
        print(f"  📁 Temp directory has {len(files)} items")
        
        # Cleanup temp directory
        from chuk_artifacts.providers.filesystem import cleanup_filesystem_store
        await cleanup_filesystem_store(temp_path)
        assert not temp_path.exists(), "Temp directory should be cleaned up"
        print("  🧹 Temp directory cleaned up successfully")
        
        print("✅ Temporary filesystem factory test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Temporary filesystem factory test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("🚀 Simple Filesystem Provider Verification\n")
    print("=" * 60)
    
    tests = [
        test_filesystem_provider_direct,
        test_artifactstore_filesystem,
        test_filesystem_persistence,
        test_filesystem_temp_factory,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            success = await test()
            if success:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test.__name__} CRASHED: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! Filesystem provider is working!")
    else:
        print("⚠️ Some tests failed. More investigation needed.")
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Simple test to verify the memory provider fix works without session dependencies.
"""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chuk_artifacts.providers.memory import factory, _default_shared_store


async def test_memory_provider_direct():
    """Test memory provider directly without ArtifactStore."""
    print("🧪 Testing memory provider directly...")
    
    try:
        print(f"  🔍 Initial global store: {len(_default_shared_store)} items")
        
        # Test 1: Create factory and store data
        factory1 = factory()
        
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
        
        print(f"  🔍 After client1: {len(_default_shared_store)} items")
        
        # Test 2: Create different factory and retrieve data
        factory2 = factory()
        
        async with factory2() as client2:
            stats2 = await client2._debug_get_stats()
            print(f"  📊 Client2 stats: {stats2}")
            
            # This should work if sharing is working
            response = await client2.get_object(Bucket="test-bucket", Key="test-key")
            assert response["Body"] == b"test data from client1"
            print(f"  ✅ Client2 retrieved data: {response['Body'].decode()}")
        
        print("✅ Memory provider direct test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Memory provider direct test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_artifactstore_core_only():
    """Test ArtifactStore core operations without session creation."""
    print("\n🧪 Testing ArtifactStore core operations...")
    
    try:
        from chuk_artifacts.store import ArtifactStore
        
        # Create ArtifactStore
        store = ArtifactStore(storage_provider="memory", session_provider="memory")
        
        # Test the S3 factory directly
        async with store._s3_factory() as s3_client:
            stats = await s3_client._debug_get_stats()
            print(f"  📊 ArtifactStore S3 client stats: {stats}")
            
            # Store something directly via S3 client
            await s3_client.put_object(
                Bucket="mcp-artifacts",
                Key="grid/sandbox-test/sess-test/artifact-test",
                Body=b"Direct S3 test data",
                ContentType="text/plain",
                Metadata={"direct": "true"}
            )
            
            print("  ✅ Stored data via ArtifactStore S3 client")
        
        # Try to retrieve with a new S3 client from same store
        async with store._s3_factory() as s3_client2:
            stats2 = await s3_client2._debug_get_stats()
            print(f"  📊 Second S3 client stats: {stats2}")
            
            response = await s3_client2.get_object(
                Bucket="mcp-artifacts",
                Key="grid/sandbox-test/sess-test/artifact-test"
            )
            assert response["Body"] == b"Direct S3 test data"
            print(f"  ✅ Retrieved data: {response['Body'].decode()}")
        
        await store.close()
        print("✅ ArtifactStore core test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ ArtifactStore core test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_environment_override():
    """Test using environment variables to force memory session provider."""
    print("\n🧪 Testing with environment override...")
    
    try:
        import os
        
        # Override environment to force memory session provider
        original_session_provider = os.getenv("SESSION_PROVIDER")
        os.environ["SESSION_PROVIDER"] = "memory"
        
        try:
            from chuk_artifacts.store import ArtifactStore
            
            # Create ArtifactStore with explicit memory providers
            store = ArtifactStore(
                storage_provider="memory", 
                session_provider="memory"
            )
            
            # Try to create a session (this might still fail if chuk_sessions doesn't have memory provider)
            try:
                session_id = await store.create_session(user_id="test_user")
                print(f"  ✅ Created session: {session_id}")
                
                # If session creation works, try full workflow
                artifact_id = await store.store(
                    data=b"Full workflow test",
                    mime="text/plain",
                    summary="Test artifact",
                    session_id=session_id
                )
                print(f"  ✅ Stored artifact: {artifact_id}")
                
                data = await store.retrieve(artifact_id)
                assert data == b"Full workflow test"
                print(f"  ✅ Retrieved data: {data.decode()}")
                
                await store.close()
                print("✅ Full workflow test PASSED!")
                return True
                
            except Exception as session_error:
                print(f"  ⚠️ Session creation failed: {session_error}")
                print("  ℹ️ This is expected if chuk_sessions doesn't have memory provider")
                await store.close()
                return False
                
        finally:
            # Restore original environment
            if original_session_provider is not None:
                os.environ["SESSION_PROVIDER"] = original_session_provider
            else:
                os.environ.pop("SESSION_PROVIDER", None)
        
    except Exception as e:
        print(f"❌ Environment override test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("🚀 Simple Memory Provider Verification\n")
    print("=" * 60)
    
    tests = [
        test_memory_provider_direct,
        test_artifactstore_core_only,
        test_environment_override,
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
    
    # Analysis
    if passed >= 2:  # Memory provider and core S3 should work
        print("🎉 Memory provider fix is working!")
        print("💡 The remaining issues are with session provider configuration")
        print("   - The memory storage fix is successful")
        print("   - Session provider needs to be configured for memory")
    else:
        print("⚠️ Memory provider fix needs more work")
    
    return passed >= 2


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
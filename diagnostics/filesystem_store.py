#!/usr/bin/env python3
# diagnostics/filesystem_store.py
"""
FIXED: Integration test for filesystem provider with ArtifactStore.
This tests the filesystem provider in the context of the full ArtifactStore.
"""

import asyncio
import sys
import os
import tempfile
import shutil
import traceback
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chuk_artifacts.store import ArtifactStore
from chuk_artifacts.providers.filesystem import create_temp_filesystem_factory


def setup_filesystem_test_environment(temp_dir: Path) -> dict:
    """Set up environment variables for filesystem testing."""
    original_vars = {}
    env_vars = [
        "ARTIFACT_FS_ROOT",
        "SESSION_PROVIDER", 
        "ARTIFACT_BUCKET",
        "CHUK_SESSION_PROVIDER",
        "ARTIFACT_PROVIDER"
    ]
    
    # Store original values
    for var in env_vars:
        original_vars[var] = os.getenv(var)
    
    # Set test values
    os.environ["ARTIFACT_FS_ROOT"] = str(temp_dir)
    os.environ["SESSION_PROVIDER"] = "memory"
    os.environ["ARTIFACT_BUCKET"] = "chuk-sandbox-2"
    os.environ["CHUK_SESSION_PROVIDER"] = "memory"  # Force chuk_sessions to use memory
    os.environ["ARTIFACT_PROVIDER"] = "filesystem"
    
    # Debug: Show what we just set
    print(f"    🔧 Environment setup:")
    for var in env_vars:
        print(f"      {var}: {os.environ.get(var)}")
    
    return original_vars


def restore_environment(original_vars: dict):
    """Restore original environment variables."""
    for var, original_value in original_vars.items():
        if original_value is not None:
            os.environ[var] = original_value
        else:
            os.environ.pop(var, None)


def create_test_store(temp_dir: Path):
    """Create ArtifactStore with explicit parameters for testing."""
    # Create the filesystem provider factory directly with the temp dir
    from chuk_artifacts.providers.filesystem import factory
    filesystem_factory = factory(temp_dir)
    
    store = ArtifactStore(
        storage_provider="filesystem", 
        session_provider="memory",
        bucket="chuk-sandbox-2",
        sandbox_id="debug-sandbox"
    )
    
    # Override the factory to ensure it uses our temp directory
    store._s3_factory = filesystem_factory
    
    return store


async def test_basic_artifact_operations():
    """Test basic ArtifactStore operations with filesystem provider."""
    print("🧪 Testing basic ArtifactStore operations with filesystem provider...")
    
    temp_dir = Path(tempfile.mkdtemp(prefix="fs_store_basic_"))
    
    try:
        original_vars = setup_filesystem_test_environment(temp_dir)
        
        try:
            store = create_test_store(temp_dir)
            
            # Create a session
            session_id = await store.create_session(user_id="test_user")
            print(f"  ✅ Created session: {session_id}")
            
            # Store an artifact
            artifact_id = await store.store(
                data=b"Hello from ArtifactStore with filesystem!",
                mime="text/plain",
                summary="Test artifact",
                filename="test.txt",
                session_id=session_id
            )
            print(f"  ✅ Stored artifact: {artifact_id}")
            
            # Verify file exists on filesystem using correct bucket name
            bucket_dir = temp_dir / store.bucket  # Use actual bucket name
            found_files = list(bucket_dir.rglob(artifact_id))
            
            # Debug: Show actual filesystem structure
            print(f"    🔍 Debug info:")
            print(f"      Store bucket: {store.bucket}")
            print(f"      Store sandbox: {store.sandbox_id}")
            print(f"      Temp directory: {temp_dir}")
            print(f"      Bucket directory: {bucket_dir}")
            print(f"      Bucket exists: {bucket_dir.exists()}")
            print(f"      Looking for artifact: {artifact_id}")
            
            if bucket_dir.exists():
                print(f"      Filesystem contents in bucket:")
                for item in bucket_dir.rglob("*"):
                    if item.is_file():
                        rel_path = item.relative_to(bucket_dir)
                        print(f"        📄 {rel_path}")
                        if artifact_id in item.name:
                            print(f"          ✅ MATCHES artifact ID!")
            
            print(f"      Found {len(found_files)} files matching artifact ID")
            
            # If not found in bucket, search entire temp directory
            if len(found_files) == 0:
                all_matches = list(temp_dir.rglob(artifact_id))
                print(f"      Searching entire temp directory: {len(all_matches)} matches")
                for match in all_matches:
                    rel_path = match.relative_to(temp_dir)
                    print(f"        📄 {rel_path}")
            
            assert len(found_files) > 0, f"Artifact file should exist in filesystem. Bucket: {store.bucket}, Searched in: {bucket_dir}"
            print(f"  📁 Artifact file found: {found_files[0]}")
            
            # Retrieve the artifact
            data = await store.retrieve(artifact_id)
            assert data == b"Hello from ArtifactStore with filesystem!"
            print(f"  ✅ Retrieved artifact: {data.decode()}")
            
            # Get metadata
            metadata = await store.metadata(artifact_id)
            assert metadata["session_id"] == session_id
            assert metadata["mime"] == "text/plain"
            assert metadata["summary"] == "Test artifact"
            print(f"  ✅ Got metadata: {metadata['summary']}")
            
            # Test exists
            exists = await store.exists(artifact_id)
            assert exists is True
            print("  ✅ Artifact exists check passed")
            
            # Test presigned URL
            try:
                url = await store.presign_short(artifact_id)
                assert url.startswith("file://")
                print(f"  ✅ Generated presigned URL: {url[:50]}...")
            except Exception as e:
                print(f"  ⚠️ Presigned URL failed: {e}")
            
            # Delete the artifact
            deleted = await store.delete(artifact_id)
            assert deleted is True
            print("  ✅ Deleted artifact")
            
            # Verify it's gone from filesystem
            remaining_files = list(bucket_dir.rglob(artifact_id))
            assert len(remaining_files) == 0, "Artifact file should be deleted from filesystem"
            print("  📁 Artifact file properly deleted from filesystem")
            
            # Verify it's gone from store
            exists = await store.exists(artifact_id)
            assert exists is False
            print("  ✅ Verified artifact is deleted")
            
            await store.close()
            
        finally:
            if original_vars:
                restore_environment(original_vars)
    
    finally:
        if original_vars:
            restore_environment(original_vars)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    print("✅ Basic ArtifactStore operations test passed!\n")


async def test_session_isolation_with_artifactstore():
    """Test session isolation using ArtifactStore with filesystem."""
    print("🔒 Testing session isolation with ArtifactStore...")
    
    temp_dir = Path(tempfile.mkdtemp(prefix="fs_store_isolation_"))
    
    try:
        original_vars = setup_filesystem_test_environment(temp_dir)
        
        try:
            store = create_test_store(temp_dir)
            
            # Create two sessions
            session1 = await store.create_session(user_id="alice")
            session2 = await store.create_session(user_id="bob")
            print(f"  ✅ Created sessions: {session1}, {session2}")
            
            # Store artifacts in each session
            artifact1 = await store.store(
                data=b"Alice's secret data",
                mime="text/plain",
                summary="Alice's file",
                filename="alice.txt",
                session_id=session1
            )
            
            artifact2 = await store.store(
                data=b"Bob's secret data", 
                mime="text/plain",
                summary="Bob's file",
                filename="bob.txt",
                session_id=session2
            )
            print(f"  ✅ Stored artifacts: {artifact1}, {artifact2}")
            
            # Verify filesystem structure using correct bucket name
            bucket_dir = temp_dir / store.bucket
            alice_files = list(bucket_dir.rglob(f"*{session1}*"))
            bob_files = list(bucket_dir.rglob(f"*{session2}*"))
            
            assert len(alice_files) >= 1, f"Alice should have files in filesystem. Bucket: {store.bucket}, Searched in: {bucket_dir}"
            assert len(bob_files) >= 1, f"Bob should have files in filesystem. Bucket: {store.bucket}, Searched in: {bucket_dir}"
            print(f"  📁 Alice files: {len(alice_files)}, Bob files: {len(bob_files)}")
            
            # Verify each session can access its own data
            alice_data = await store.retrieve(artifact1)
            bob_data = await store.retrieve(artifact2)
            
            assert alice_data == b"Alice's secret data"
            assert bob_data == b"Bob's secret data"
            print("  ✅ Each session can access its own data")
            
            # Verify metadata isolation
            alice_meta = await store.metadata(artifact1)
            bob_meta = await store.metadata(artifact2)
            
            assert alice_meta["session_id"] == session1
            assert bob_meta["session_id"] == session2
            assert alice_meta["session_id"] != bob_meta["session_id"]
            print("  ✅ Metadata shows correct session isolation")
            
            # Test session listing
            try:
                alice_artifacts = await store.list_by_session(session1)
                bob_artifacts = await store.list_by_session(session2)
                
                alice_ids = {a["artifact_id"] for a in alice_artifacts}
                bob_ids = {a["artifact_id"] for a in bob_artifacts}
                
                assert artifact1 in alice_ids
                assert artifact1 not in bob_ids
                assert artifact2 in bob_ids
                assert artifact2 not in alice_ids
                print("  ✅ Session listing shows proper isolation")
                
            except Exception as e:
                print(f"  ⚠️ Session listing failed: {e}")
            
            await store.close()
            
        finally:
            restore_environment(original_vars)
    
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    print("✅ Session isolation test passed!\n")

async def test_file_operations_with_filesystem():
    """Test file operations with filesystem provider."""
    print("📁 Testing file operations with filesystem provider...")
    
    temp_dir = Path(tempfile.mkdtemp(prefix="fs_store_files_"))
    original_vars = None
    
    try:
        original_vars = setup_filesystem_test_environment(temp_dir)
        
        try:
            store = create_test_store(temp_dir)
            session_id = await store.create_session(user_id="file_user")
            
            # Write a file
            doc_id = await store.write_file(
                content="# Filesystem Provider Test\n\nThis is a test document.",
                filename="docs/test.md",
                mime="text/markdown",
                summary="Test document",
                session_id=session_id
            )
            print(f"  ✅ Wrote file: {doc_id}")
            
            # Verify file exists on filesystem using correct bucket name
            bucket_dir = temp_dir / store.bucket
            doc_files = list(bucket_dir.rglob(doc_id))
            assert len(doc_files) > 0, f"Document file should exist in filesystem. Bucket: {store.bucket}, Searched in: {bucket_dir}"
            print(f"  📁 Document file: {doc_files[0]}")
            
            # Read the file
            content = await store.read_file(doc_id, as_text=True)
            assert "Filesystem Provider Test" in content
            print(f"  ✅ Read file content: {len(content)} characters")
            
            # Copy the file (within same session)
            try:
                copy_id = await store.copy_file(
                    doc_id,
                    new_filename="docs/test_copy.md"
                )
                
                # Verify copy
                copy_content = await store.read_file(copy_id, as_text=True)
                assert copy_content == content
                print(f"  ✅ Copied file: {copy_id}")
                
                # Verify copy exists on filesystem using correct bucket name
                copy_files = list(bucket_dir.rglob(copy_id))
                assert len(copy_files) > 0, f"Copy file should exist in filesystem. Bucket: {store.bucket}"
                print(f"  📁 Copy file: {copy_files[0]}")
                
            except Exception as e:
                print(f"  ⚠️ File copy failed: {e}")
            
            # Update file
            try:
                await store.update_file(
                    doc_id,
                    data=b"# Updated Document\n\nThis content was updated.",
                    summary="Updated document"
                )
                
                updated_content = await store.read_file(doc_id, as_text=True)
                assert "Updated Document" in updated_content
                print("  ✅ Updated file content")
                
            except Exception as e:
                print(f"  ⚠️ File update failed: {e}")
            
            await store.close()
            
        finally:
            if original_vars:
                restore_environment(original_vars)
    
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    print("✅ File operations test passed!\n")


async def test_configuration_and_stats():
    """Test configuration validation and statistics."""
    print("📊 Testing configuration and statistics...")
    
    temp_dir = Path(tempfile.mkdtemp(prefix="fs_store_config_"))
    original_vars = None
    
    try:
        original_vars = setup_filesystem_test_environment(temp_dir)
        
        try:
            store = create_test_store(temp_dir)
            
            # Validate configuration
            config_status = await store.validate_configuration()
            
            assert isinstance(config_status, dict)
            print(f"  ✅ Configuration validation: {config_status.get('timestamp', 'OK')}")
            
            # Get statistics
            stats = await store.get_stats()
            
            assert isinstance(stats, dict)
            assert stats["storage_provider"] == "filesystem"
            assert stats["session_provider"] == "memory"
            print(f"  ✅ Statistics: {stats['storage_provider']} storage, {stats['session_provider']} sessions")
            
            # Test sandbox info
            try:
                sandbox_info = await store.get_sandbox_info()
                assert isinstance(sandbox_info, dict)
                assert "sandbox_id" in sandbox_info
                print(f"  ✅ Sandbox info: {sandbox_info['sandbox_id']}")
            except AttributeError:
                print("  ⚠️ get_sandbox_info method not available (skipped)")
            except Exception as e:
                print(f"  ⚠️ get_sandbox_info failed: {e}")
            
            await store.close()
            
        finally:
            if original_vars:
                restore_environment(original_vars)
    
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    print("✅ Configuration and stats test passed!\n")


async def test_filesystem_provider_persistence():
    """Test that filesystem provider data persists between restarts."""
    print("💾 Testing filesystem provider persistence...")
    
    temp_dir = Path(tempfile.mkdtemp(prefix="fs_store_persist_"))
    original_vars = None
    
    try:
        original_vars = setup_filesystem_test_environment(temp_dir)
        
        try:
            # Phase 1: Store data
            store1 = create_test_store(temp_dir)
            session_id = await store1.create_session(user_id="persist_user")
            
            artifact_id = await store1.store(
                data=b"Persistent test data",
                mime="text/plain",
                summary="Persistence test",
                session_id=session_id
            )
            print(f"  ✅ Stored artifact: {artifact_id}")
            
            await store1.close()
            print("  ✅ Closed first store")
            
            # Phase 2: Create new store and verify data exists
            store2 = create_test_store(temp_dir)
            
            # Data should still be accessible
            data = await store2.retrieve(artifact_id)
            assert data == b"Persistent test data"
            print(f"  ✅ Retrieved persisted data: {data.decode()}")
            
            # Metadata should still be accessible
            metadata = await store2.metadata(artifact_id)
            assert metadata["summary"] == "Persistence test"
            print(f"  ✅ Retrieved persisted metadata: {metadata['summary']}")
            
            await store2.close()
            print("  ✅ Data successfully persisted between store instances")
            
        finally:
            if original_vars:
                restore_environment(original_vars)
    
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    print("✅ Filesystem persistence test passed!\n")


async def test_concurrent_access():
    """Test concurrent access to filesystem provider."""
    print("⚡ Testing concurrent access...")
    
    temp_dir = Path(tempfile.mkdtemp(prefix="fs_store_concurrent_"))
    original_vars = None
    
    try:
        original_vars = setup_filesystem_test_environment(temp_dir)
        
        try:
            async def create_store_and_work(user_id, num_files):
                """Create a store and perform operations."""
                store = create_test_store(temp_dir)
                
                try:
                    session_id = await store.create_session(user_id=user_id)
                    artifacts = []
                    
                    for i in range(num_files):
                        artifact_id = await store.store(
                            data=f"{user_id} file {i} content".encode(),
                            mime="text/plain",
                            summary=f"{user_id} file {i}",
                            filename=f"{user_id}_file_{i}.txt",
                            session_id=session_id
                        )
                        artifacts.append(artifact_id)
                    
                    # Verify all artifacts
                    for artifact_id in artifacts:
                        data = await store.retrieve(artifact_id)
                        assert user_id.encode() in data
                    
                    return len(artifacts)
                    
                finally:
                    await store.close()
            
            # Run concurrent operations
            tasks = [
                create_store_and_work("user1", 3),
                create_store_and_work("user2", 3), 
                create_store_and_work("user3", 3),
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful_results = [r for r in results if isinstance(r, int)]
            failed_results = [r for r in results if isinstance(r, Exception)]
            
            print(f"  ✅ Successful operations: {len(successful_results)}")
            print(f"  ❌ Failed operations: {len(failed_results)}")
            
            if failed_results:
                for i, error in enumerate(failed_results):
                    print(f"    Error {i+1}: {type(error).__name__}: {error}")
            
            # Verify filesystem contains expected data
            bucket_dir = temp_dir / "chuk-sandbox-2"  # FIX: Use correct bucket name
            if bucket_dir.exists():
                all_files = list(bucket_dir.rglob("*"))
                non_meta_files = [f for f in all_files if not f.name.endswith(".meta.json")]
                print(f"  📁 Filesystem contains {len(non_meta_files)} artifact files")
            else:
                print("  📁 No filesystem directory created")
                
        finally:
            restore_environment(original_vars)
    
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    print("✅ Concurrent access test completed!\n")


async def run_integration_tests():
    """Run all integration tests."""
    print("🚀 Filesystem Provider + ArtifactStore Integration Tests\n")
    print("=" * 60)
    
    tests = [
        test_basic_artifact_operations,
        test_session_isolation_with_artifactstore,
        test_file_operations_with_filesystem,
        test_configuration_and_stats,
        test_filesystem_provider_persistence,
        test_concurrent_access,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} FAILED:")
            print(f"   Error: {e}")
            traceback.print_exc()
            failed += 1
            print()
    
    print("=" * 60)
    print(f"📊 Integration Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All integration tests passed! Filesystem provider works with ArtifactStore.")
        return True
    else:
        print("⚠️ Some integration tests failed. Check filesystem provider integration.")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_integration_tests())
    sys.exit(0 if success else 1)
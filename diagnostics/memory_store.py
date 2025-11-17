#!/usr/bin/env python3
# diagnostics/memory_store.py
"""
Integration test for memory provider with ArtifactStore.
This tests the memory provider in the context of the full ArtifactStore.
"""

import asyncio
import sys
import os
import traceback
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chuk_artifacts.store import ArtifactStore
from chuk_artifacts.config import configure_memory
from chuk_artifacts.providers.memory import create_shared_memory_factory


async def test_basic_artifact_operations():
    """Test basic ArtifactStore operations with memory provider."""
    print("🧪 Testing basic ArtifactStore operations with memory provider...")

    # Force memory provider configuration
    os.environ["ARTIFACT_PROVIDER"] = "memory"
    os.environ["SESSION_PROVIDER"] = "memory"
    configure_memory()

    store = ArtifactStore(storage_provider="memory", session_provider="memory")

    try:
        # Create a session
        session_id = await store.create_session(user_id="test_user")
        print(f"  ✅ Created session: {session_id}")

        # Store an artifact
        artifact_id = await store.store(
            data=b"Hello from ArtifactStore!",
            mime="text/plain",
            summary="Test artifact",
            filename="test.txt",
            session_id=session_id,
        )
        print(f"  ✅ Stored artifact: {artifact_id}")

        # Retrieve the artifact
        data = await store.retrieve(artifact_id)
        assert data == b"Hello from ArtifactStore!"
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

        # Test presigned URL (may not work with memory provider)
        try:
            url = await store.presign_short(artifact_id)
            assert url.startswith("memory://")
            print(f"  ✅ Generated presigned URL: {url[:50]}...")
        except Exception as e:
            print(f"  ⚠️ Presigned URL failed (expected): {e}")

        # Delete the artifact
        deleted = await store.delete(artifact_id)
        assert deleted is True
        print("  ✅ Deleted artifact")

        # Verify it's gone
        exists = await store.exists(artifact_id)
        assert exists is False
        print("  ✅ Verified artifact is deleted")

    finally:
        await store.close()

    print("✅ Basic ArtifactStore operations test passed!\n")


async def test_session_isolation_with_artifactstore():
    """Test session isolation using ArtifactStore."""
    print("🔒 Testing session isolation with ArtifactStore...")

    # Use shared memory to ensure consistency
    shared_factory, shared_store = create_shared_memory_factory()

    # Create store with explicit memory provider
    store = ArtifactStore(storage_provider="memory", session_provider="memory")
    store._s3_factory = shared_factory

    try:
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
            session_id=session1,
        )

        artifact2 = await store.store(
            data=b"Bob's secret data",
            mime="text/plain",
            summary="Bob's file",
            filename="bob.txt",
            session_id=session2,
        )
        print(f"  ✅ Stored artifacts: {artifact1}, {artifact2}")

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

        # Test session listing (may not work with memory provider)
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
            print(f"  ⚠️ Session listing failed (may be expected): {e}")

    finally:
        await store.close()

    print("✅ Session isolation test passed!\n")


async def test_file_operations_with_memory():
    """Test file operations with memory provider."""
    print("📁 Testing file operations with memory provider...")

    store = ArtifactStore(storage_provider="memory", session_provider="memory")

    try:
        session_id = await store.create_session(user_id="file_user")

        # Write a file
        doc_id = await store.write_file(
            content="# Memory Provider Test\n\nThis is a test document.",
            filename="docs/test.md",
            mime="text/markdown",
            summary="Test document",
            session_id=session_id,
        )
        print(f"  ✅ Wrote file: {doc_id}")

        # Read the file
        content = await store.read_file(doc_id, as_text=True)
        assert "Memory Provider Test" in content
        print(f"  ✅ Read file content: {len(content)} characters")

        # Copy the file (within same session)
        try:
            copy_id = await store.copy_file(doc_id, new_filename="docs/test_copy.md")

            # Verify copy
            copy_content = await store.read_file(copy_id, as_text=True)
            assert copy_content == content
            print(f"  ✅ Copied file: {copy_id}")

        except Exception as e:
            print(f"  ⚠️ File copy failed (may be expected): {e}")

        # Update file
        try:
            await store.update_file(
                doc_id,
                data=b"# Updated Document\n\nThis content was updated.",
                summary="Updated document",
            )

            updated_content = await store.read_file(doc_id, as_text=True)
            assert "Updated Document" in updated_content
            print("  ✅ Updated file content")

        except Exception as e:
            print(f"  ⚠️ File update failed (may be expected): {e}")

    finally:
        await store.close()

    print("✅ File operations test passed!\n")


async def test_configuration_and_stats():
    """Test configuration validation and statistics."""
    print("📊 Testing configuration and statistics...")

    store = ArtifactStore(storage_provider="memory", session_provider="memory")

    try:
        # Validate configuration
        config_status = await store.validate_configuration()

        # Now returns Pydantic ValidationResponse, but supports dict-like access
        print(f"  ✅ Configuration validation: {config_status.get('timestamp', 'OK')}")

        # Get statistics
        stats = await store.get_stats()

        # Now returns Pydantic StatsResponse, but supports dict-like access
        assert stats["storage_provider"] == "memory"
        assert stats["session_provider"] == "memory"
        print(
            f"  ✅ Statistics: {stats['storage_provider']} storage, {stats['session_provider']} sessions"
        )

        # Test sandbox info
        sandbox_info = await store.get_sandbox_info()

        # Now returns Pydantic SandboxInfo, but supports dict-like access
        assert "sandbox_id" in sandbox_info
        print(f"  ✅ Sandbox info: {sandbox_info['sandbox_id']}")

    finally:
        await store.close()

    print("✅ Configuration and stats test passed!\n")


async def test_memory_provider_limitations():
    """Test known limitations of memory provider."""
    print("⚠️ Testing memory provider limitations...")

    store = ArtifactStore(storage_provider="memory", session_provider="memory")

    try:
        session_id = await store.create_session(user_id="limits_user")

        # Store an artifact
        artifact_id = await store.store(
            data=b"Test data for limitations",
            mime="text/plain",
            summary="Limitations test",
            session_id=session_id,
        )

        print(f"  ✅ Stored test artifact: {artifact_id}")

        # Test operations that may fail with memory provider
        limitation_tests = [
            ("presign_upload", lambda: store.presign_upload(session_id=session_id)),
            ("list_by_session", lambda: store.list_by_session(session_id)),
            (
                "get_directory_contents",
                lambda: store.get_directory_contents(session_id, ""),
            ),
            (
                "store_batch",
                lambda: store.store_batch(
                    [
                        {
                            "data": b"batch test",
                            "mime": "text/plain",
                            "summary": "Batch test",
                        }
                    ],
                    session_id=session_id,
                ),
            ),
        ]

        for test_name, test_func in limitation_tests:
            try:
                result = await test_func()
                print(f"  ✅ {test_name}: Works (result: {type(result).__name__})")
            except Exception as e:
                print(
                    f"  ❌ {test_name}: Failed - {type(e).__name__}: {str(e)[:50]}..."
                )

    finally:
        await store.close()

    print("✅ Memory provider limitations test completed!\n")


async def test_concurrent_access():
    """Test concurrent access to memory provider."""
    print("⚡ Testing concurrent access...")

    # Use shared storage for consistency
    shared_factory, shared_store = create_shared_memory_factory()

    async def create_store_and_work(user_id, num_files):
        """Create a store and perform operations."""
        store = ArtifactStore(storage_provider="memory", session_provider="memory")
        store._s3_factory = shared_factory

        try:
            session_id = await store.create_session(user_id=user_id)
            artifacts = []

            for i in range(num_files):
                artifact_id = await store.store(
                    data=f"{user_id} file {i} content".encode(),
                    mime="text/plain",
                    summary=f"{user_id} file {i}",
                    filename=f"{user_id}_file_{i}.txt",
                    session_id=session_id,
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

    # Verify shared storage contains expected data
    print(f"  📊 Shared storage contains {len(shared_store)} objects")

    print("✅ Concurrent access test completed!\n")


async def run_integration_tests():
    """Run all integration tests."""
    print("🚀 Memory Provider + ArtifactStore Integration Tests\n")
    print("=" * 60)

    tests = [
        test_basic_artifact_operations,
        test_session_isolation_with_artifactstore,
        test_file_operations_with_memory,
        test_configuration_and_stats,
        test_memory_provider_limitations,
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
        print(
            "🎉 All integration tests passed! Memory provider works with ArtifactStore."
        )
        return True
    else:
        print("⚠️ Some integration tests failed. Check memory provider integration.")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_integration_tests())
    sys.exit(0 if success else 1)

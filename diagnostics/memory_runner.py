#!/usr/bin/env python3
# diagnostics/memory_runner.py
"""
Quick test runner for memory provider to understand its behavior.
Run this to test the memory provider independently.
"""

import asyncio
import sys
import traceback
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chuk_artifacts.providers.memory import (
    _MemoryS3Client,
    factory,
    create_shared_memory_factory,
)


async def test_basic_operations():
    """Test basic memory provider operations."""
    print("🧪 Testing basic memory provider operations...")

    client = _MemoryS3Client()

    try:
        # Test put/get
        print("  📤 Testing put_object...")
        await client.put_object(
            Bucket="test-bucket",
            Key="test-file.txt",
            Body=b"Hello, memory provider!",
            ContentType="text/plain",
            Metadata={"filename": "test-file.txt", "test": "true"},
        )
        print("  ✅ put_object successful")

        print("  📥 Testing get_object...")
        response = await client.get_object(Bucket="test-bucket", Key="test-file.txt")

        assert response["Body"] == b"Hello, memory provider!"
        assert response["ContentType"] == "text/plain"
        assert response["Metadata"]["filename"] == "test-file.txt"
        print(f"  ✅ get_object successful: {response['Body'].decode()}")

        # Test list
        print("  📋 Testing list_objects_v2...")
        list_response = await client.list_objects_v2(Bucket="test-bucket")
        assert list_response["KeyCount"] == 1
        assert list_response["Contents"][0]["Key"] == "test-file.txt"
        print(f"  ✅ Found {list_response['KeyCount']} objects")

        # Test presigned URL
        print("  🔗 Testing presigned URL...")
        url = await client.generate_presigned_url(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": "test-file.txt"},
            ExpiresIn=3600,
        )
        assert url.startswith("memory://test-bucket/test-file.txt")
        print(f"  ✅ Generated URL: {url[:50]}...")

        # Test delete
        print("  🗑️ Testing delete_object...")
        await client.delete_object(Bucket="test-bucket", Key="test-file.txt")

        try:
            await client.get_object(Bucket="test-bucket", Key="test-file.txt")
            assert False, "Should have raised exception"
        except Exception as e:
            assert "NoSuchKey" in str(e)
            print("  ✅ delete_object successful")

    finally:
        await client.close()

    print("✅ Basic operations test passed!\n")


async def test_isolation():
    """Test isolation between different clients."""
    print("🔒 Testing client isolation...")

    client1 = _MemoryS3Client()
    client2 = _MemoryS3Client()

    try:
        # Store in client1
        await client1.put_object(
            Bucket="isolation-test",
            Key="client1-file",
            Body=b"Client 1 data",
            ContentType="text/plain",
            Metadata={},
        )

        # Store in client2
        await client2.put_object(
            Bucket="isolation-test",
            Key="client2-file",
            Body=b"Client 2 data",
            ContentType="text/plain",
            Metadata={},
        )

        # client1 should only see its own file
        response1 = await client1.get_object(
            Bucket="isolation-test", Key="client1-file"
        )
        assert response1["Body"] == b"Client 1 data"
        print("  ✅ Client 1 can access its own data")

        try:
            await client1.get_object(Bucket="isolation-test", Key="client2-file")
            assert False, "Client 1 should not see Client 2's data"
        except Exception:
            print("  ✅ Client 1 cannot access Client 2's data")

        # client2 should only see its own file
        response2 = await client2.get_object(
            Bucket="isolation-test", Key="client2-file"
        )
        assert response2["Body"] == b"Client 2 data"
        print("  ✅ Client 2 can access its own data")

        try:
            await client2.get_object(Bucket="isolation-test", Key="client1-file")
            assert False, "Client 2 should not see Client 1's data"
        except Exception:
            print("  ✅ Client 2 cannot access Client 1's data")

    finally:
        await client1.close()
        await client2.close()

    print("✅ Isolation test passed!\n")


async def test_shared_storage():
    """Test shared storage functionality."""
    print("🤝 Testing shared storage...")

    shared_store = {}
    client1 = _MemoryS3Client(shared_store=shared_store)
    client2 = _MemoryS3Client(shared_store=shared_store)

    try:
        # Store via client1
        await client1.put_object(
            Bucket="shared-bucket",
            Key="shared-file",
            Body=b"Shared data",
            ContentType="text/plain",
            Metadata={"shared": "true"},
        )

        # Access via client2
        response = await client2.get_object(Bucket="shared-bucket", Key="shared-file")
        assert response["Body"] == b"Shared data"
        assert response["Metadata"]["shared"] == "true"
        print("  ✅ Client 2 can access data stored by Client 1")

        # Modify via client2
        await client2.put_object(
            Bucket="shared-bucket",
            Key="shared-file",
            Body=b"Modified shared data",
            ContentType="text/plain",
            Metadata={"modified": "true"},
        )

        # Check via client1
        response = await client1.get_object(Bucket="shared-bucket", Key="shared-file")
        assert response["Body"] == b"Modified shared data"
        assert response["Metadata"]["modified"] == "true"
        print("  ✅ Client 1 can see modifications by Client 2")

        # Verify shared_store directly
        assert "shared-bucket/shared-file" in shared_store
        assert (
            shared_store["shared-bucket/shared-file"]["data"] == b"Modified shared data"
        )
        print("  ✅ Data is correctly stored in shared storage")

    finally:
        await client1.close()
        await client2.close()

    print("✅ Shared storage test passed!\n")


async def test_factory_functionality():
    """Test factory functions."""
    print("🏭 Testing factory functionality...")

    # Test basic factory
    factory_func = factory()

    async with factory_func() as client:
        await client.put_object(
            Bucket="factory-bucket",
            Key="factory-file",
            Body=b"Factory created data",
            ContentType="text/plain",
            Metadata={},
        )

        response = await client.get_object(Bucket="factory-bucket", Key="factory-file")
        assert response["Body"] == b"Factory created data"
        print("  ✅ Basic factory works")

    # Test shared factory
    shared_factory, shared_store = create_shared_memory_factory()

    async with shared_factory() as client1:
        await client1.put_object(
            Bucket="shared-factory-bucket",
            Key="shared-factory-file",
            Body=b"Shared factory data",
            ContentType="text/plain",
            Metadata={},
        )

    async with shared_factory() as client2:
        response = await client2.get_object(
            Bucket="shared-factory-bucket", Key="shared-factory-file"
        )
        assert response["Body"] == b"Shared factory data"
        print("  ✅ Shared factory works")

    # Verify data is in shared_store
    assert "shared-factory-bucket/shared-factory-file" in shared_store
    print("  ✅ Shared store contains expected data")

    print("✅ Factory functionality test passed!\n")


async def test_grid_pattern():
    """Test grid architecture pattern like ArtifactStore uses."""
    print("🗂️ Testing grid architecture pattern...")

    shared_store = {}
    factory_func = factory(shared_store)

    async with factory_func() as s3:
        bucket = "mcp-artifacts"

        # Store files in grid pattern
        test_files = [
            ("grid/sandbox-1/sess-alice/file1", b"Alice file 1"),
            ("grid/sandbox-1/sess-alice/file2", b"Alice file 2"),
            ("grid/sandbox-1/sess-bob/file1", b"Bob file 1"),
            ("grid/sandbox-2/sess-charlie/file1", b"Charlie file 1"),
        ]

        for key, body in test_files:
            await s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                ContentType="text/plain",
                Metadata={"grid_test": "true"},
            )

        print(f"  📤 Stored {len(test_files)} files in grid pattern")

        # Test session-based listing
        alice_files = await s3.list_objects_v2(
            Bucket=bucket, Prefix="grid/sandbox-1/sess-alice/"
        )

        assert alice_files["KeyCount"] == 2
        alice_keys = [obj["Key"] for obj in alice_files["Contents"]]
        assert "grid/sandbox-1/sess-alice/file1" in alice_keys
        assert "grid/sandbox-1/sess-alice/file2" in alice_keys
        print(f"  ✅ Alice has {alice_files['KeyCount']} files")

        bob_files = await s3.list_objects_v2(
            Bucket=bucket, Prefix="grid/sandbox-1/sess-bob/"
        )

        assert bob_files["KeyCount"] == 1
        bob_keys = [obj["Key"] for obj in bob_files["Contents"]]
        assert "grid/sandbox-1/sess-bob/file1" in bob_keys
        print(f"  ✅ Bob has {bob_files['KeyCount']} files")

        # Test sandbox-based listing
        sandbox1_files = await s3.list_objects_v2(
            Bucket=bucket, Prefix="grid/sandbox-1/"
        )

        assert sandbox1_files["KeyCount"] == 3  # Alice(2) + Bob(1)
        print(f"  ✅ Sandbox 1 has {sandbox1_files['KeyCount']} files total")

        sandbox2_files = await s3.list_objects_v2(
            Bucket=bucket, Prefix="grid/sandbox-2/"
        )

        assert sandbox2_files["KeyCount"] == 1  # Charlie(1)
        print(f"  ✅ Sandbox 2 has {sandbox2_files['KeyCount']} files total")

        # Verify session isolation
        for alice_key in alice_keys:
            assert alice_key not in bob_keys
        print("  ✅ Session isolation maintained")

    print("✅ Grid architecture test passed!\n")


async def test_concurrent_operations():
    """Test concurrent operations."""
    print("⚡ Testing concurrent operations...")

    client = _MemoryS3Client()

    try:
        # Concurrent puts
        async def put_file(index):
            await client.put_object(
                Bucket="concurrent-bucket",
                Key=f"file_{index}",
                Body=f"Content {index}".encode(),
                ContentType="text/plain",
                Metadata={"index": str(index)},
            )
            return index

        # Run 10 concurrent operations
        tasks = [put_file(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert sorted(results) == list(range(10))
        print("  ✅ 10 concurrent puts completed successfully")

        # Verify all files exist
        list_response = await client.list_objects_v2(Bucket="concurrent-bucket")
        assert list_response["KeyCount"] == 10
        print(f"  ✅ All {list_response['KeyCount']} files are accessible")

        # Concurrent gets
        async def get_file(index):
            response = await client.get_object(
                Bucket="concurrent-bucket", Key=f"file_{index}"
            )
            return response["Body"]

        get_tasks = [get_file(i) for i in range(10)]
        get_results = await asyncio.gather(*get_tasks)

        for i, result in enumerate(get_results):
            assert result == f"Content {i}".encode()
        print("  ✅ 10 concurrent gets completed successfully")

    finally:
        await client.close()

    print("✅ Concurrent operations test passed!\n")


async def run_all_tests():
    """Run all memory provider tests."""
    print("🚀 Memory Provider Test Suite\n")
    print("=" * 50)

    tests = [
        test_basic_operations,
        test_isolation,
        test_shared_storage,
        test_factory_functionality,
        test_grid_pattern,
        test_concurrent_operations,
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

    print("=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed! Memory provider is working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Memory provider may have issues.")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
# diagnostics/filesystem_runner.py
"""
Quick test runner for filesystem provider to understand its behavior.
Run this to test the filesystem provider independently.
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

from chuk_artifacts.providers.filesystem import (
    _FilesystemClient, 
    factory, 
    create_temp_filesystem_factory,
    cleanup_filesystem_store
)


async def test_basic_operations():
    """Test basic filesystem provider operations."""
    print("🧪 Testing basic filesystem provider operations...")
    
    temp_dir = Path(tempfile.mkdtemp(prefix="fs_basic_"))
    
    # Set up environment variables to ensure proper filesystem root
    original_fs_root = os.getenv("ARTIFACT_FS_ROOT")
    os.environ["ARTIFACT_FS_ROOT"] = str(temp_dir)
    
    try:
        client = _FilesystemClient(temp_dir)  # Explicit root for consistency
        
        # Test put/get
        print("  📤 Testing put_object...")
        await client.put_object(
            Bucket="test-bucket",
            Key="test-file.txt",
            Body=b"Hello, filesystem provider!",
            ContentType="text/plain",
            Metadata={"filename": "test-file.txt", "test": "true"}
        )
        print("  ✅ put_object successful")
        
        # Verify files exist
        object_path = temp_dir / "test-bucket" / "test-file.txt"
        meta_path = temp_dir / "test-bucket" / "test-file.txt.meta.json"
        assert object_path.exists(), f"Object file should exist: {object_path}"
        assert meta_path.exists(), f"Metadata file should exist: {meta_path}"
        print(f"  📁 Files created: {object_path.name}, {meta_path.name}")
        
        print("  📥 Testing get_object...")
        response = await client.get_object(
            Bucket="test-bucket",
            Key="test-file.txt"
        )
        
        assert response["Body"] == b"Hello, filesystem provider!"
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
            ExpiresIn=3600
        )
        assert url.startswith("file://")
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
        
        # Verify files are gone
        assert not object_path.exists(), "Object file should be deleted"
        assert not meta_path.exists(), "Metadata file should be deleted"
        print("  🗂️ Files properly cleaned up")
            
        await client.close()
    
    finally:
        # Restore environment
        if original_fs_root is not None:
            os.environ["ARTIFACT_FS_ROOT"] = original_fs_root
        else:
            os.environ.pop("ARTIFACT_FS_ROOT", None)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    print("✅ Basic operations test passed!\n")


async def test_multiple_clients():
    """Test multiple clients accessing same filesystem."""
    print("🔒 Testing multiple client access...")
    
    temp_dir = Path(tempfile.mkdtemp(prefix="fs_multi_"))
    
    # Set up environment variables
    original_fs_root = os.getenv("ARTIFACT_FS_ROOT")
    os.environ["ARTIFACT_FS_ROOT"] = str(temp_dir)
    
    try:
        client1 = _FilesystemClient(temp_dir)  # Explicit root
        client2 = _FilesystemClient(temp_dir)  # Explicit root
        
        # Store with client1
        await client1.put_object(
            Bucket="shared-bucket",
            Key="shared-file",
            Body=b"Shared data",
            ContentType="text/plain",
            Metadata={"shared": "true"}
        )
        print("  ✅ Client 1 stored data")
        
        # Access with client2 (should work since same filesystem)
        response = await client2.get_object(Bucket="shared-bucket", Key="shared-file")
        assert response["Body"] == b"Shared data"
        assert response["Metadata"]["shared"] == "true"
        print("  ✅ Client 2 can access data stored by Client 1")
        
        # Modify with client2
        await client2.put_object(
            Bucket="shared-bucket",
            Key="shared-file",
            Body=b"Modified shared data",
            ContentType="text/plain",
            Metadata={"modified": "true"}
        )
        print("  ✅ Client 2 modified the data")
        
        # Check with client1
        response = await client1.get_object(Bucket="shared-bucket", Key="shared-file")
        assert response["Body"] == b"Modified shared data"
        assert response["Metadata"]["modified"] == "true"
        print("  ✅ Client 1 can see modifications by Client 2")
        
        await client1.close()
        await client2.close()
    
    finally:
        # Restore environment
        if original_fs_root is not None:
            os.environ["ARTIFACT_FS_ROOT"] = original_fs_root
        else:
            os.environ.pop("ARTIFACT_FS_ROOT", None)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    print("✅ Multiple client test passed!\n")


async def test_factory_functionality():
    """Test factory functions."""
    print("🏭 Testing factory functionality...")
    
    temp_dir = Path(tempfile.mkdtemp(prefix="fs_factory_"))
    
    # Set up environment variables
    original_fs_root = os.getenv("ARTIFACT_FS_ROOT")
    os.environ["ARTIFACT_FS_ROOT"] = str(temp_dir)
    
    try:
        # Test basic factory
        factory_func = factory(temp_dir)  # Explicit root
        
        async with factory_func() as client:
            await client.put_object(
                Bucket="factory-bucket",
                Key="factory-file",
                Body=b"Factory created data",
                ContentType="text/plain",
                Metadata={}
            )
            
            response = await client.get_object(Bucket="factory-bucket", Key="factory-file")
            assert response["Body"] == b"Factory created data"
            print("  ✅ Basic factory works")
        
        # Test that data persists after client closes
        async with factory_func() as client2:
            response = await client2.get_object(Bucket="factory-bucket", Key="factory-file")
            assert response["Body"] == b"Factory created data"
            print("  ✅ Data persists between client sessions")
        
        # Test temp factory
        temp_factory, temp_path = create_temp_filesystem_factory()
        
        async with temp_factory() as temp_client:
            await temp_client.put_object(
                Bucket="temp-bucket",
                Key="temp-file",
                Body=b"Temp factory data",
                ContentType="text/plain",
                Metadata={}
            )
            
            response = await temp_client.get_object(Bucket="temp-bucket", Key="temp-file")
            assert response["Body"] == b"Temp factory data"
            print("  ✅ Temp factory works")
        
        # Verify temp directory exists and has files
        assert temp_path.exists(), "Temp directory should exist"
        assert any(temp_path.rglob("*")), "Temp directory should have files"
        print(f"  📁 Temp directory: {temp_path}")
        
        # Cleanup temp directory
        await cleanup_filesystem_store(temp_path)
        assert not temp_path.exists(), "Temp directory should be cleaned up"
        print("  🧹 Temp directory cleaned up")
    
    finally:
        # Restore environment
        if original_fs_root is not None:
            os.environ["ARTIFACT_FS_ROOT"] = original_fs_root
        else:
            os.environ.pop("ARTIFACT_FS_ROOT", None)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    print("✅ Factory functionality test passed!\n")


async def test_grid_pattern():
    """Test grid architecture pattern like ArtifactStore uses."""
    print("🗂️ Testing grid architecture pattern...")
    
    temp_dir = Path(tempfile.mkdtemp(prefix="fs_grid_"))
    
    # Set up environment variables
    original_fs_root = os.getenv("ARTIFACT_FS_ROOT")
    os.environ["ARTIFACT_FS_ROOT"] = str(temp_dir)
    
    try:
        factory_func = factory(temp_dir)  # Explicit root
        
        async with factory_func() as client:
            bucket = "mcp-artifacts"
            
            # Store files in grid pattern
            test_files = [
                ("grid/sandbox-1/sess-alice/file1", b"Alice file 1"),
                ("grid/sandbox-1/sess-alice/file2", b"Alice file 2"), 
                ("grid/sandbox-1/sess-bob/file1", b"Bob file 1"),
                ("grid/sandbox-2/sess-charlie/file1", b"Charlie file 1"),
            ]
            
            for key, body in test_files:
                await client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=body,
                    ContentType="text/plain",
                    Metadata={"grid_test": "true"}
                )
            
            print(f"  📤 Stored {len(test_files)} files in grid pattern")
            
            # Verify directory structure
            expected_paths = [
                temp_dir / bucket / "grid" / "sandbox-1" / "sess-alice" / "file1",
                temp_dir / bucket / "grid" / "sandbox-1" / "sess-alice" / "file2",
                temp_dir / bucket / "grid" / "sandbox-1" / "sess-bob" / "file1",
                temp_dir / bucket / "grid" / "sandbox-2" / "sess-charlie" / "file1",
            ]
            
            for path in expected_paths:
                assert path.exists(), f"Expected file should exist: {path}"
            print("  📁 Directory structure created correctly")
            
            # Test session-based listing
            alice_files = await client.list_objects_v2(
                Bucket=bucket,
                Prefix="grid/sandbox-1/sess-alice/"
            )
            
            assert alice_files["KeyCount"] == 2
            alice_keys = [obj["Key"] for obj in alice_files["Contents"]]
            assert "grid/sandbox-1/sess-alice/file1" in alice_keys
            assert "grid/sandbox-1/sess-alice/file2" in alice_keys
            print(f"  ✅ Alice has {alice_files['KeyCount']} files")
            
            bob_files = await client.list_objects_v2(
                Bucket=bucket,
                Prefix="grid/sandbox-1/sess-bob/"
            )
            
            assert bob_files["KeyCount"] == 1
            bob_keys = [obj["Key"] for obj in bob_files["Contents"]]
            assert "grid/sandbox-1/sess-bob/file1" in bob_keys
            print(f"  ✅ Bob has {bob_files['KeyCount']} files")
            
            # Test sandbox-based listing
            sandbox1_files = await client.list_objects_v2(
                Bucket=bucket,
                Prefix="grid/sandbox-1/"
            )
            
            assert sandbox1_files["KeyCount"] == 3  # Alice(2) + Bob(1)
            print(f"  ✅ Sandbox 1 has {sandbox1_files['KeyCount']} files total")
            
            sandbox2_files = await client.list_objects_v2(
                Bucket=bucket,
                Prefix="grid/sandbox-2/"
            )
            
            assert sandbox2_files["KeyCount"] == 1  # Charlie(1)
            print(f"  ✅ Sandbox 2 has {sandbox2_files['KeyCount']} files total")
            
            # Verify session isolation
            for alice_key in alice_keys:
                assert alice_key not in bob_keys
            print("  ✅ Session isolation maintained")
    
    finally:
        # Restore environment
        if original_fs_root is not None:
            os.environ["ARTIFACT_FS_ROOT"] = original_fs_root
        else:
            os.environ.pop("ARTIFACT_FS_ROOT", None)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    print("✅ Grid architecture test passed!\n")


async def test_concurrent_operations():
    """Test concurrent operations."""
    print("⚡ Testing concurrent operations...")
    
    temp_dir = Path(tempfile.mkdtemp(prefix="fs_concurrent_"))
    
    # Set up environment variables
    original_fs_root = os.getenv("ARTIFACT_FS_ROOT")
    os.environ["ARTIFACT_FS_ROOT"] = str(temp_dir)
    
    try:
        factory_func = factory(temp_dir)  # Explicit root
        
        async with factory_func() as client:
            # Concurrent puts
            async def put_file(index):
                await client.put_object(
                    Bucket="concurrent-bucket",
                    Key=f"file_{index}",
                    Body=f"Content {index}".encode(),
                    ContentType="text/plain",
                    Metadata={"index": str(index)}
                )
                return index
            
            # Run 10 concurrent operations
            tasks = [put_file(i) for i in range(10)]
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 10
            assert sorted(results) == list(range(10))
            print("  ✅ 10 concurrent puts completed successfully")
            
            # Verify all files exist on filesystem
            for i in range(10):
                file_path = temp_dir / "concurrent-bucket" / f"file_{i}"
                assert file_path.exists(), f"File {i} should exist on filesystem"
            print("  📁 All files exist on filesystem")
            
            # Verify all files accessible via client
            list_response = await client.list_objects_v2(Bucket="concurrent-bucket")
            assert list_response["KeyCount"] == 10
            print(f"  ✅ All {list_response['KeyCount']} files are accessible")
            
            # Concurrent gets
            async def get_file(index):
                response = await client.get_object(
                    Bucket="concurrent-bucket",
                    Key=f"file_{index}"
                )
                return response["Body"]
            
            get_tasks = [get_file(i) for i in range(10)]
            get_results = await asyncio.gather(*get_tasks)
            
            for i, result in enumerate(get_results):
                assert result == f"Content {i}".encode()
            print("  ✅ 10 concurrent gets completed successfully")
    
    finally:
        # Restore environment
        if original_fs_root is not None:
            os.environ["ARTIFACT_FS_ROOT"] = original_fs_root
        else:
            os.environ.pop("ARTIFACT_FS_ROOT", None)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    print("✅ Concurrent operations test passed!\n")


async def test_error_handling():
    """Test error handling and edge cases."""
    print("🚨 Testing error handling...")
    
    temp_dir = Path(tempfile.mkdtemp(prefix="fs_errors_"))
    
    # Set up environment variables
    original_fs_root = os.getenv("ARTIFACT_FS_ROOT")
    os.environ["ARTIFACT_FS_ROOT"] = str(temp_dir)
    
    try:
        factory_func = factory(temp_dir)  # Explicit root
        
        async with factory_func() as client:
            # Test nonexistent object
            try:
                await client.get_object(Bucket="test-bucket", Key="nonexistent")
                assert False, "Should have raised exception"
            except Exception as e:
                assert "NoSuchKey" in str(e)
                print("  ✅ NoSuchKey error handled correctly")
            
            # Test head_object for nonexistent
            try:
                await client.head_object(Bucket="test-bucket", Key="nonexistent")
                assert False, "Should have raised exception"
            except Exception as e:
                assert "NoSuchKey" in str(e)
                print("  ✅ head_object NoSuchKey error handled correctly")
            
            # Test presigned URL for nonexistent
            try:
                await client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": "test-bucket", "Key": "nonexistent"},
                    ExpiresIn=3600
                )
                assert False, "Should have raised exception"
            except FileNotFoundError:
                print("  ✅ Presigned URL error handled correctly")
            
            # Test delete nonexistent (should not error)
            result = await client.delete_object(Bucket="test-bucket", Key="nonexistent")
            assert result["ResponseMetadata"]["HTTPStatusCode"] == 204
            print("  ✅ Delete nonexistent object handled correctly")
            
            # Test empty bucket listing
            empty_response = await client.list_objects_v2(Bucket="empty-bucket")
            assert empty_response["KeyCount"] == 0
            assert empty_response["Contents"] == []
            print("  ✅ Empty bucket listing handled correctly")
            
            # Test special characters in keys
            special_key = "path/with spaces/special-chars_123.txt"
            await client.put_object(
                Bucket="test-bucket",
                Key=special_key,
                Body=b"Special chars test",
                ContentType="text/plain",
                Metadata={}
            )
            
            response = await client.get_object(Bucket="test-bucket", Key=special_key)
            assert response["Body"] == b"Special chars test"
            print("  ✅ Special characters in keys handled correctly")
    
    finally:
        # Restore environment
        if original_fs_root is not None:
            os.environ["ARTIFACT_FS_ROOT"] = original_fs_root
        else:
            os.environ.pop("ARTIFACT_FS_ROOT", None)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    print("✅ Error handling test passed!\n")


async def run_all_tests():
    """Run all filesystem provider tests."""
    print("🚀 Filesystem Provider Test Suite\n")
    print("=" * 50)
    
    tests = [
        test_basic_operations,
        test_multiple_clients,
        test_factory_functionality,
        test_grid_pattern,
        test_concurrent_operations,
        test_error_handling,
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
        print("🎉 All tests passed! Filesystem provider is working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Filesystem provider may have issues.")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
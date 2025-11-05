#!/usr/bin/env python3
"""
Test script for the fixed filesystem provider.
"""

import asyncio
import sys
import tempfile
import shutil
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chuk_artifacts.providers.filesystem import (
    factory,
)


async def test_basic_filesystem_operations():
    """Test basic filesystem provider operations."""
    print("🧪 Testing basic filesystem operations...")

    # Create temporary directory for testing
    temp_dir = Path(tempfile.mkdtemp(prefix="filesystem_test_"))

    try:
        factory_func = factory(temp_dir)

        async with factory_func() as client:
            # Test put_object
            await client.put_object(
                Bucket="test-bucket",
                Key="test-file.txt",
                Body=b"Hello filesystem provider!",
                ContentType="text/plain",
                Metadata={"filename": "test-file.txt", "author": "test"},
            )
            print("  ✅ put_object successful")

            # Test get_object
            response = await client.get_object(
                Bucket="test-bucket", Key="test-file.txt"
            )
            assert response["Body"] == b"Hello filesystem provider!"
            assert response["ContentType"] == "text/plain"
            assert response["Metadata"]["author"] == "test"
            print(f"  ✅ get_object successful: {response['Body'].decode()}")

            # Test head_object
            head_response = await client.head_object(
                Bucket="test-bucket", Key="test-file.txt"
            )
            assert head_response["ContentType"] == "text/plain"
            assert "Body" not in head_response
            print("  ✅ head_object successful")

            # Test list_objects_v2
            list_response = await client.list_objects_v2(Bucket="test-bucket")
            assert list_response["KeyCount"] == 1
            assert list_response["Contents"][0]["Key"] == "test-file.txt"
            print(
                f"  ✅ list_objects_v2 successful: found {list_response['KeyCount']} objects"
            )

            # Test presigned URL
            url = await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": "test-bucket", "Key": "test-file.txt"},
                ExpiresIn=3600,
            )
            assert url.startswith("file://")
            print(f"  ✅ presigned URL successful: {url[:50]}...")

            # Test delete_object
            await client.delete_object(Bucket="test-bucket", Key="test-file.txt")

            # Verify deletion
            try:
                await client.get_object(Bucket="test-bucket", Key="test-file.txt")
                assert False, "Should have raised exception"
            except Exception as e:
                assert "NoSuchKey" in str(e)
                print("  ✅ delete_object successful")

        print("✅ Basic filesystem operations test PASSED!")
        return True

    except Exception as e:
        print(f"❌ Basic filesystem operations test FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


async def test_filesystem_with_artifactstore():
    """Test filesystem provider with ArtifactStore."""
    print("\n🧪 Testing filesystem provider with ArtifactStore...")

    temp_dir = Path(tempfile.mkdtemp(prefix="filesystem_artifactstore_"))

    try:
        # Set environment variable for filesystem root
        import os

        original_root = os.getenv("ARTIFACT_FS_ROOT")
        os.environ["ARTIFACT_FS_ROOT"] = str(temp_dir)

        try:
            from chuk_artifacts.store import ArtifactStore

            # Create ArtifactStore with filesystem provider
            store = ArtifactStore(
                storage_provider="filesystem",
                session_provider="memory",  # Use memory for sessions to avoid Redis dependency
            )

            # Test basic workflow
            session_id = await store.create_session(user_id="filesystem_test_user")
            print(f"  ✅ Created session: {session_id}")

            artifact_id = await store.store(
                data=b"Filesystem test data",
                mime="text/plain",
                summary="Filesystem test artifact",
                filename="filesystem_test.txt",
                session_id=session_id,
            )
            print(f"  ✅ Stored artifact: {artifact_id}")

            # Retrieve the artifact
            data = await store.retrieve(artifact_id)
            assert data == b"Filesystem test data"
            print(f"  ✅ Retrieved artifact: {data.decode()}")

            # Test metadata
            metadata = await store.metadata(artifact_id)
            assert metadata["summary"] == "Filesystem test artifact"
            print(f"  ✅ Got metadata: {metadata['summary']}")

            # Test file operations
            doc_id = await store.write_file(
                content="# Filesystem Test Document\n\nThis is a test.",
                filename="test_doc.md",
                mime="text/markdown",
                summary="Test document",
                session_id=session_id,
            )
            print(f"  ✅ Wrote file: {doc_id}")

            content = await store.read_file(doc_id, as_text=True)
            assert "Filesystem Test Document" in content
            print(f"  ✅ Read file: {len(content)} characters")

            await store.close()
            print("✅ Filesystem ArtifactStore test PASSED!")
            return True

        finally:
            # Restore environment
            if original_root is not None:
                os.environ["ARTIFACT_FS_ROOT"] = original_root
            else:
                os.environ.pop("ARTIFACT_FS_ROOT", None)

    except Exception as e:
        print(f"❌ Filesystem ArtifactStore test FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


async def test_filesystem_grid_pattern():
    """Test filesystem provider with grid pattern like ArtifactStore uses."""
    print("\n🧪 Testing filesystem grid pattern...")

    temp_dir = Path(tempfile.mkdtemp(prefix="filesystem_grid_"))

    try:
        factory_func = factory(temp_dir)

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
                    Metadata={"grid_test": "true"},
                )

            print(f"  ✅ Stored {len(test_files)} files in grid pattern")

            # Test session-based listing
            alice_files = await client.list_objects_v2(
                Bucket=bucket, Prefix="grid/sandbox-1/sess-alice/"
            )

            assert alice_files["KeyCount"] == 2
            alice_keys = [obj["Key"] for obj in alice_files["Contents"]]
            assert "grid/sandbox-1/sess-alice/file1" in alice_keys
            assert "grid/sandbox-1/sess-alice/file2" in alice_keys
            print(f"  ✅ Alice has {alice_files['KeyCount']} files")

            # Test sandbox-based listing
            sandbox1_files = await client.list_objects_v2(
                Bucket=bucket, Prefix="grid/sandbox-1/"
            )

            assert sandbox1_files["KeyCount"] == 3  # Alice(2) + Bob(1)
            print(f"  ✅ Sandbox 1 has {sandbox1_files['KeyCount']} files total")

            # Test file retrieval
            response = await client.get_object(
                Bucket=bucket, Key="grid/sandbox-1/sess-alice/file1"
            )
            assert response["Body"] == b"Alice file 1"
            print("  ✅ Grid file retrieval working")

            # Check directory structure
            expected_dirs = [
                temp_dir / bucket / "grid" / "sandbox-1" / "sess-alice",
                temp_dir / bucket / "grid" / "sandbox-1" / "sess-bob",
                temp_dir / bucket / "grid" / "sandbox-2" / "sess-charlie",
            ]

            for expected_dir in expected_dirs:
                assert expected_dir.exists(), f"Directory {expected_dir} should exist"

            print("  ✅ Directory structure correct")

        print("✅ Filesystem grid pattern test PASSED!")
        return True

    except Exception as e:
        print(f"❌ Filesystem grid pattern test FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


async def test_filesystem_error_handling():
    """Test filesystem provider error handling."""
    print("\n🧪 Testing filesystem error handling...")

    temp_dir = Path(tempfile.mkdtemp(prefix="filesystem_errors_"))

    try:
        factory_func = factory(temp_dir)

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
                    ExpiresIn=3600,
                )
                assert False, "Should have raised exception"
            except FileNotFoundError:
                print("  ✅ Presigned URL error handled correctly")

            # Test delete nonexistent (should not error)
            result = await client.delete_object(Bucket="test-bucket", Key="nonexistent")
            assert result["ResponseMetadata"]["HTTPStatusCode"] == 204
            print("  ✅ Delete nonexistent object handled correctly")

        print("✅ Filesystem error handling test PASSED!")
        return True

    except Exception as e:
        print(f"❌ Filesystem error handling test FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


async def main():
    """Run all filesystem provider tests."""
    print("🚀 Filesystem Provider Test Suite\n")
    print("=" * 60)

    tests = [
        test_basic_filesystem_operations,
        test_filesystem_grid_pattern,
        test_filesystem_error_handling,
        test_filesystem_with_artifactstore,
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
        print("🎉 All filesystem provider tests passed!")
    else:
        print("⚠️ Some filesystem provider tests failed.")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

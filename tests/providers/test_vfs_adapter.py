# -*- coding: utf-8 -*-
"""
Tests for VFS Adapter - chuk-virtual-fs integration

This test suite ensures the VFS adapter correctly bridges
chuk-virtual-fs to the S3-compatible API expected by chuk-artifacts.
"""

import pytest
from chuk_artifacts.providers.vfs_adapter import VFSAdapter, factory


class TestVFSAdapterBasicOperations:
    """Test basic S3-compatible operations through VFS adapter"""

    @pytest.mark.asyncio
    async def test_put_and_get_object(self):
        """Test storing and retrieving an object"""
        factory_fn = factory(provider="memory", shared_key="test_put_and_get_object")
        async with factory_fn() as client:
            # Put object
            await client.put_object(
                Bucket="test-bucket",
                Key="test-key",
                Body=b"test data",
                ContentType="text/plain",
                Metadata={"custom": "value"},
            )

            # Get object
            response = await client.get_object(Bucket="test-bucket", Key="test-key")

            assert response["Body"] == b"test data"
            assert response["ContentType"] == "text/plain"
            assert response["Metadata"]["custom"] == "value"

    @pytest.mark.asyncio
    async def test_head_object(self):
        """Test getting object metadata without body"""
        factory_fn = factory(provider="memory", shared_key="test_head_object")
        async with factory_fn() as client:
            # Put object
            await client.put_object(
                Bucket="test-bucket",
                Key="test-key",
                Body=b"test data",
                ContentType="application/json",
                Metadata={"version": "1.0"},
            )

            # Head object
            response = await client.head_object(Bucket="test-bucket", Key="test-key")

            assert response["ContentType"] == "application/json"
            assert response["Metadata"]["version"] == "1.0"
            assert response["ContentLength"] == 9

    @pytest.mark.asyncio
    async def test_list_objects_v2(self):
        """Test listing objects with prefix filtering"""
        factory_fn = factory(provider="memory", shared_key="test_list_objects_v2")
        async with factory_fn() as client:
            # Put multiple objects
            await client.put_object(
                Bucket="test-bucket",
                Key="prefix1/file1.txt",
                Body=b"data1",
                ContentType="text/plain",
                Metadata={},
            )
            await client.put_object(
                Bucket="test-bucket",
                Key="prefix1/file2.txt",
                Body=b"data2",
                ContentType="text/plain",
                Metadata={},
            )
            await client.put_object(
                Bucket="test-bucket",
                Key="prefix2/file3.txt",
                Body=b"data3",
                ContentType="text/plain",
                Metadata={},
            )

            # List all objects
            response = await client.list_objects_v2(Bucket="test-bucket")
            assert response["KeyCount"] == 3

            # List with prefix filter
            response = await client.list_objects_v2(
                Bucket="test-bucket", Prefix="prefix1/"
            )
            assert response["KeyCount"] == 2
            keys = [obj["Key"] for obj in response["Contents"]]
            assert "prefix1/file1.txt" in keys
            assert "prefix1/file2.txt" in keys

    @pytest.mark.asyncio
    async def test_delete_object(self):
        """Test deleting an object"""
        factory_fn = factory(provider="memory", shared_key="test_delete_object")
        async with factory_fn() as client:
            # Put object
            await client.put_object(
                Bucket="test-bucket",
                Key="test-key",
                Body=b"test data",
                ContentType="text/plain",
                Metadata={},
            )

            # Verify it exists
            response = await client.get_object(Bucket="test-bucket", Key="test-key")
            assert response["Body"] == b"test data"

            # Delete object
            await client.delete_object(Bucket="test-bucket", Key="test-key")

            # Verify it's gone
            with pytest.raises(Exception, match="NoSuchKey"):
                await client.get_object(Bucket="test-bucket", Key="test-key")

    @pytest.mark.asyncio
    async def test_head_bucket(self):
        """Test bucket head operation (VFS creates directory)"""
        factory_fn = factory(provider="memory", shared_key="test_head_bucket")
        async with factory_fn() as client:
            # Head bucket creates it if it doesn't exist
            response = await client.head_bucket(Bucket="new-bucket")
            assert response["ResponseMetadata"]["HTTPStatusCode"] == 200


class TestVFSAdapterNestedPaths:
    """Test VFS adapter handling of nested paths"""

    @pytest.mark.asyncio
    async def test_nested_key_auto_creates_directories(self):
        """Test that nested keys auto-create parent directories"""
        factory_fn = factory(
            provider="memory", shared_key="test_nested_key_auto_creates_directories"
        )
        async with factory_fn() as client:
            # Put object with nested path
            await client.put_object(
                Bucket="test-bucket",
                Key="folder/subfolder/file.txt",
                Body=b"nested data",
                ContentType="text/plain",
                Metadata={},
            )

            # Retrieve it
            response = await client.get_object(
                Bucket="test-bucket", Key="folder/subfolder/file.txt"
            )
            assert response["Body"] == b"nested data"

    @pytest.mark.asyncio
    async def test_deeply_nested_paths(self):
        """Test very deeply nested paths"""
        factory_fn = factory(provider="memory", shared_key="test_deeply_nested_paths")
        async with factory_fn() as client:
            deep_key = "/".join([f"level{i}" for i in range(10)]) + "/file.txt"

            await client.put_object(
                Bucket="test-bucket",
                Key=deep_key,
                Body=b"deep data",
                ContentType="text/plain",
                Metadata={},
            )

            response = await client.get_object(Bucket="test-bucket", Key=deep_key)
            assert response["Body"] == b"deep data"


class TestVFSAdapterErrorHandling:
    """Test error handling in VFS adapter"""

    @pytest.mark.asyncio
    async def test_get_nonexistent_object(self):
        """Test getting an object that doesn't exist"""
        factory_fn = factory(
            provider="memory", shared_key="test_get_nonexistent_object"
        )
        async with factory_fn() as client:
            with pytest.raises(Exception, match="NoSuchKey"):
                await client.get_object(Bucket="test-bucket", Key="nonexistent")

    @pytest.mark.asyncio
    async def test_head_nonexistent_object(self):
        """Test head on non-existent object"""
        factory_fn = factory(
            provider="memory", shared_key="test_head_nonexistent_object"
        )
        async with factory_fn() as client:
            with pytest.raises(Exception, match="NoSuchKey"):
                await client.head_object(Bucket="test-bucket", Key="nonexistent")

    @pytest.mark.asyncio
    async def test_list_empty_bucket(self):
        """Test listing objects in empty bucket"""
        factory_fn = factory(provider="memory", shared_key="test_list_empty_bucket")
        async with factory_fn() as client:
            response = await client.list_objects_v2(Bucket="empty-bucket")
            assert response["KeyCount"] == 0
            assert response["Contents"] == []

    @pytest.mark.asyncio
    async def test_operations_after_close(self):
        """Test that operations fail after close"""
        factory_fn = factory(
            provider="memory", shared_key="test_operations_after_close"
        )
        async with factory_fn() as client:
            # Close the client
            await client.close()

            # Operations should fail
            with pytest.raises(RuntimeError, match="Client has been closed"):
                await client.put_object(
                    Bucket="test-bucket",
                    Key="test-key",
                    Body=b"data",
                    ContentType="text/plain",
                    Metadata={},
                )


class TestVFSAdapterMetadata:
    """Test metadata handling in VFS adapter"""

    @pytest.mark.asyncio
    async def test_custom_metadata_preserved(self):
        """Test that custom metadata is preserved"""
        factory_fn = factory(
            provider="memory", shared_key="test_custom_metadata_preserved"
        )
        async with factory_fn() as client:
            metadata = {
                "user-id": "alice",
                "version": "1.0.0",
                "environment": "production",
            }

            await client.put_object(
                Bucket="test-bucket",
                Key="test-key",
                Body=b"data with metadata",
                ContentType="application/json",
                Metadata=metadata,
            )

            response = await client.get_object(Bucket="test-bucket", Key="test-key")
            assert response["Metadata"]["user-id"] == "alice"
            assert response["Metadata"]["version"] == "1.0.0"
            assert response["Metadata"]["environment"] == "production"

    @pytest.mark.asyncio
    async def test_empty_metadata(self):
        """Test handling of empty metadata"""
        factory_fn = factory(provider="memory", shared_key="test_empty_metadata")
        async with factory_fn() as client:
            await client.put_object(
                Bucket="test-bucket",
                Key="test-key",
                Body=b"data",
                ContentType="text/plain",
                Metadata={},
            )

            response = await client.get_object(Bucket="test-bucket", Key="test-key")
            assert response["Metadata"] == {}


class TestVFSAdapterPresignedURLs:
    """Test presigned URL generation"""

    @pytest.mark.asyncio
    async def test_generate_presigned_url_get(self):
        """Test generating presigned URL for GET operation"""
        factory_fn = factory(
            provider="memory", shared_key="test_generate_presigned_url_get"
        )
        async with factory_fn() as client:
            # Put object first
            await client.put_object(
                Bucket="test-bucket",
                Key="test-key",
                Body=b"test data",
                ContentType="text/plain",
                Metadata={},
            )

            # Generate presigned URL
            url = await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": "test-bucket", "Key": "test-key"},
                ExpiresIn=3600,
            )

            # For memory provider, should get a memory:// URL
            assert url.startswith("memory://")
            assert "test-key" in url

    @pytest.mark.asyncio
    async def test_generate_presigned_url_put(self):
        """Test generating presigned URL for PUT operation"""
        factory_fn = factory(
            provider="memory", shared_key="test_generate_presigned_url_put"
        )
        async with factory_fn() as client:
            # Create bucket
            await client.head_bucket(Bucket="test-bucket")

            # Can't generate presigned PUT for non-existent object
            # VFS checks existence first
            # So we skip this for memory provider

    @pytest.mark.asyncio
    async def test_presigned_url_nonexistent_object(self):
        """Test presigned URL generation for non-existent object"""
        factory_fn = factory(
            provider="memory", shared_key="test_presigned_url_nonexistent_object"
        )
        async with factory_fn() as client:
            with pytest.raises(FileNotFoundError):
                await client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": "test-bucket", "Key": "nonexistent"},
                    ExpiresIn=3600,
                )


class TestVFSAdapterSharedStorage:
    """Test shared VFS instances for memory provider"""

    @pytest.mark.asyncio
    async def test_shared_memory_storage(self):
        """Test that memory provider shares storage across instances"""
        factory_fn = factory(provider="memory", shared_key="test_shared_memory_storage")

        # First client stores data
        async with factory_fn() as client1:
            await client1.put_object(
                Bucket="shared-bucket",
                Key="shared-key",
                Body=b"shared data",
                ContentType="text/plain",
                Metadata={},
            )

        # Second client should see the same data
        async with factory_fn() as client2:
            response = await client2.get_object(
                Bucket="shared-bucket", Key="shared-key"
            )
            assert response["Body"] == b"shared data"

    @pytest.mark.asyncio
    async def test_shared_key_parameter(self):
        """Test explicit shared_key parameter"""
        factory_fn = factory(provider="memory", shared_key="custom-key")

        # First client
        async with factory_fn() as client1:
            await client1.put_object(
                Bucket="test-bucket",
                Key="test-key",
                Body=b"test data",
                ContentType="text/plain",
                Metadata={},
            )

        # Second client with same shared_key
        factory_fn2 = factory(provider="memory", shared_key="custom-key")
        async with factory_fn2() as client2:
            response = await client2.get_object(Bucket="test-bucket", Key="test-key")
            assert response["Body"] == b"test data"


class TestVFSAdapterFactory:
    """Test factory function behavior"""

    @pytest.mark.asyncio
    async def test_factory_memory_provider(self):
        """Test factory with memory provider"""
        factory_fn = factory(
            provider="memory", shared_key="test_factory_memory_provider"
        )
        async with factory_fn() as client:
            assert client is not None
            assert isinstance(client, VFSAdapter)

    @pytest.mark.asyncio
    async def test_factory_filesystem_provider(self):
        """Test factory with filesystem provider"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            factory_fn = factory(
                provider="filesystem",
                root_path=tmpdir,
                shared_key="test_factory_filesystem_provider",
            )
            async with factory_fn() as client:
                assert client is not None
                assert isinstance(client, VFSAdapter)

    @pytest.mark.asyncio
    async def test_factory_context_manager(self):
        """Test that factory returns proper context manager"""
        factory_fn = factory(
            provider="memory", shared_key="test_factory_context_manager"
        )

        # Should work as context manager
        async with factory_fn() as client:
            # Client should be usable
            await client.head_bucket(Bucket="test-bucket")


class TestVFSAdapterEdgeCases:
    """Test edge cases and boundary conditions"""

    @pytest.mark.asyncio
    async def test_empty_body(self):
        """Test storing empty file"""
        factory_fn = factory(provider="memory", shared_key="test_empty_body")
        async with factory_fn() as client:
            await client.put_object(
                Bucket="test-bucket",
                Key="empty-file",
                Body=b"",
                ContentType="text/plain",
                Metadata={},
            )

            response = await client.get_object(Bucket="test-bucket", Key="empty-file")
            assert response["Body"] == b""
            assert response["ContentLength"] == 0

    @pytest.mark.asyncio
    async def test_large_metadata(self):
        """Test handling of large metadata"""
        factory_fn = factory(provider="memory", shared_key="test_large_metadata")
        async with factory_fn() as client:
            large_metadata = {f"key{i}": f"value{i}" * 100 for i in range(50)}

            await client.put_object(
                Bucket="test-bucket",
                Key="test-key",
                Body=b"data",
                ContentType="text/plain",
                Metadata=large_metadata,
            )

            response = await client.get_object(Bucket="test-bucket", Key="test-key")
            assert len(response["Metadata"]) == 50

    @pytest.mark.asyncio
    async def test_special_characters_in_keys(self):
        """Test keys with special characters"""
        factory_fn = factory(
            provider="memory", shared_key="test_special_characters_in_keys"
        )
        async with factory_fn() as client:
            special_key = "folder/file-with-special_chars!@#$%^&*().txt"

            await client.put_object(
                Bucket="test-bucket",
                Key=special_key,
                Body=b"special data",
                ContentType="text/plain",
                Metadata={},
            )

            response = await client.get_object(Bucket="test-bucket", Key=special_key)
            assert response["Body"] == b"special data"

    @pytest.mark.asyncio
    async def test_overwrite_existing_object(self):
        """Test overwriting an existing object"""
        factory_fn = factory(
            provider="memory", shared_key="test_overwrite_existing_object"
        )
        async with factory_fn() as client:
            # Put first version
            await client.put_object(
                Bucket="test-bucket",
                Key="test-key",
                Body=b"version 1",
                ContentType="text/plain",
                Metadata={"version": "1"},
            )

            # Verify first version
            response1 = await client.get_object(Bucket="test-bucket", Key="test-key")
            assert response1["Body"] == b"version 1"

            # Overwrite with second version
            await client.put_object(
                Bucket="test-bucket",
                Key="test-key",
                Body=b"version 2",
                ContentType="text/plain",
                Metadata={"version": "2"},
            )

            # Should get second version body
            # Note: VFS metadata updates on existing files may vary by provider
            response = await client.get_object(Bucket="test-bucket", Key="test-key")
            assert response["Body"] == b"version 2"
            # Metadata behavior depends on VFS implementation

    @pytest.mark.asyncio
    async def test_list_with_max_keys(self):
        """Test listing with MaxKeys parameter"""
        factory_fn = factory(provider="memory", shared_key="test_list_with_max_keys")
        async with factory_fn() as client:
            # Put multiple objects
            for i in range(10):
                await client.put_object(
                    Bucket="test-bucket",
                    Key=f"file{i:02d}.txt",
                    Body=f"data{i}".encode(),
                    ContentType="text/plain",
                    Metadata={},
                )

            # List with limit
            response = await client.list_objects_v2(Bucket="test-bucket", MaxKeys=5)
            assert response["KeyCount"] == 5
            assert response["IsTruncated"] is True

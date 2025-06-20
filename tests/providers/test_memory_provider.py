# -*- coding: utf-8 -*-
# tests/test_memory_provider.py
"""
Comprehensive tests for the memory provider.

Tests the memory provider directly to understand its behavior,
limitations, and ensure it works correctly in isolation.
"""

import pytest
import asyncio
import time
from unittest.mock import patch

from chuk_artifacts.providers.memory import (
    _MemoryS3Client, 
    factory, 
    create_shared_memory_factory,
    clear_all_memory_stores
)


class TestMemoryS3Client:
    """Test the _MemoryS3Client directly."""
    
    @pytest.mark.asyncio
    async def test_basic_put_get_operations(self):
        """Test basic put and get operations."""
        client = _MemoryS3Client()
        
        try:
            # Put an object
            response = await client.put_object(
                Bucket="test-bucket",
                Key="test-key",
                Body=b"test content",
                ContentType="text/plain",
                Metadata={"filename": "test.txt", "user": "alice"}
            )
            
            assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
            assert "ETag" in response
            
            # Get the object back
            get_response = await client.get_object(
                Bucket="test-bucket",
                Key="test-key"
            )
            
            assert get_response["Body"] == b"test content"
            assert get_response["ContentType"] == "text/plain"
            assert get_response["Metadata"]["filename"] == "test.txt"
            assert get_response["Metadata"]["user"] == "alice"
            assert get_response["ContentLength"] == len(b"test content")
            
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_head_operations(self):
        """Test head_object and head_bucket operations."""
        client = _MemoryS3Client()
        
        try:
            # head_bucket should always succeed
            bucket_response = await client.head_bucket(Bucket="any-bucket")
            assert bucket_response["ResponseMetadata"]["HTTPStatusCode"] == 200
            
            # Put an object first
            await client.put_object(
                Bucket="test-bucket",
                Key="test-key", 
                Body=b"test content",
                ContentType="application/json",
                Metadata={"type": "test"}
            )
            
            # head_object should return metadata without body
            head_response = await client.head_object(
                Bucket="test-bucket",
                Key="test-key"
            )
            
            assert head_response["ContentType"] == "application/json"
            assert head_response["Metadata"]["type"] == "test"
            assert head_response["ContentLength"] == len(b"test content")
            assert "Body" not in head_response  # Should not include body
            
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_nonexistent_object_errors(self):
        """Test error handling for nonexistent objects."""
        client = _MemoryS3Client()
        
        try:
            # Try to get nonexistent object
            with pytest.raises(Exception) as exc_info:
                await client.get_object(Bucket="test-bucket", Key="nonexistent")
            
            assert "NoSuchKey" in str(exc_info.value)
            
            # Try to head nonexistent object
            with pytest.raises(Exception) as exc_info:
                await client.head_object(Bucket="test-bucket", Key="nonexistent")
            
            assert "NoSuchKey" in str(exc_info.value)
            
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_delete_operations(self):
        """Test delete operations."""
        client = _MemoryS3Client()
        
        try:
            # Put an object
            await client.put_object(
                Bucket="test-bucket",
                Key="test-key",
                Body=b"test content",
                ContentType="text/plain",
                Metadata={}
            )
            
            # Verify it exists
            get_response = await client.get_object(Bucket="test-bucket", Key="test-key")
            assert get_response["Body"] == b"test content"
            
            # Delete it
            delete_response = await client.delete_object(Bucket="test-bucket", Key="test-key")
            assert delete_response["ResponseMetadata"]["HTTPStatusCode"] == 204
            
            # Verify it's gone
            with pytest.raises(Exception) as exc_info:
                await client.get_object(Bucket="test-bucket", Key="test-key")
            assert "NoSuchKey" in str(exc_info.value)
            
            # Deleting nonexistent object should not error
            delete_response2 = await client.delete_object(Bucket="test-bucket", Key="nonexistent")
            assert delete_response2["ResponseMetadata"]["HTTPStatusCode"] == 204
            
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_list_objects(self):
        """Test list_objects_v2 functionality."""
        client = _MemoryS3Client()
        
        try:
            # Put several objects
            test_objects = [
                ("file1.txt", b"content1"),
                ("file2.txt", b"content2"),
                ("docs/readme.md", b"# README"),
                ("docs/guide.md", b"# Guide"),
                ("images/photo.jpg", b"fake image data")
            ]
            
            for key, body in test_objects:
                await client.put_object(
                    Bucket="test-bucket",
                    Key=key,
                    Body=body,
                    ContentType="text/plain",
                    Metadata={"filename": key}
                )
            
            # List all objects
            list_response = await client.list_objects_v2(Bucket="test-bucket")
            
            assert list_response["KeyCount"] == 5
            assert list_response["IsTruncated"] is False
            
            # Check contents
            keys = [obj["Key"] for obj in list_response["Contents"]]
            assert "file1.txt" in keys
            assert "docs/readme.md" in keys
            assert "images/photo.jpg" in keys
            
            # List with prefix
            docs_response = await client.list_objects_v2(
                Bucket="test-bucket",
                Prefix="docs/"
            )
            
            assert docs_response["KeyCount"] == 2
            docs_keys = [obj["Key"] for obj in docs_response["Contents"]]
            assert "docs/readme.md" in docs_keys
            assert "docs/guide.md" in docs_keys
            assert "file1.txt" not in docs_keys
            
            # List with MaxKeys limit
            limited_response = await client.list_objects_v2(
                Bucket="test-bucket",
                MaxKeys=2
            )
            
            assert limited_response["KeyCount"] == 2
            
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_presigned_urls(self):
        """Test presigned URL generation."""
        client = _MemoryS3Client()
        
        try:
            # Put an object first
            await client.put_object(
                Bucket="test-bucket",
                Key="test-file.txt",
                Body=b"presigned test content",
                ContentType="text/plain",
                Metadata={}
            )
            
            # Generate presigned URL
            url = await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": "test-bucket", "Key": "test-file.txt"},
                ExpiresIn=3600
            )
            
            # Verify URL format
            assert url.startswith("memory://test-bucket/test-file.txt")
            assert "operation=get_object" in url
            assert "token=" in url
            assert "expires=" in url
            assert "hash=" in url
            
            # Try to generate URL for nonexistent object
            with pytest.raises(FileNotFoundError):
                await client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": "test-bucket", "Key": "nonexistent.txt"},
                    ExpiresIn=3600
                )
                
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_client_isolation(self):
        """Test that different client instances are isolated."""
        client1 = _MemoryS3Client()
        client2 = _MemoryS3Client()
        
        try:
            # Put object in client1
            await client1.put_object(
                Bucket="test-bucket",
                Key="client1-file",
                Body=b"client1 content",
                ContentType="text/plain",
                Metadata={}
            )
            
            # Put object in client2
            await client2.put_object(
                Bucket="test-bucket", 
                Key="client2-file",
                Body=b"client2 content",
                ContentType="text/plain",
                Metadata={}
            )
            
            # client1 should only see its own object
            response1 = await client1.get_object(Bucket="test-bucket", Key="client1-file")
            assert response1["Body"] == b"client1 content"
            
            with pytest.raises(Exception):
                await client1.get_object(Bucket="test-bucket", Key="client2-file")
            
            # client2 should only see its own object
            response2 = await client2.get_object(Bucket="test-bucket", Key="client2-file")
            assert response2["Body"] == b"client2 content"
            
            with pytest.raises(Exception):
                await client2.get_object(Bucket="test-bucket", Key="client1-file")
                
        finally:
            await client1.close()
            await client2.close()
    
    @pytest.mark.asyncio
    async def test_shared_storage(self):
        """Test shared storage between clients."""
        shared_store = {}
        client1 = _MemoryS3Client(shared_store=shared_store)
        client2 = _MemoryS3Client(shared_store=shared_store)
        
        try:
            # Put object via client1
            await client1.put_object(
                Bucket="shared-bucket",
                Key="shared-file",
                Body=b"shared content",
                ContentType="text/plain",
                Metadata={}
            )
            
            # client2 should see the same object
            response = await client2.get_object(Bucket="shared-bucket", Key="shared-file")
            assert response["Body"] == b"shared content"
            
            # Modify via client2
            await client2.put_object(
                Bucket="shared-bucket",
                Key="shared-file",
                Body=b"modified content",
                ContentType="text/plain",
                Metadata={}
            )
            
            # client1 should see the modification
            response = await client1.get_object(Bucket="shared-bucket", Key="shared-file")
            assert response["Body"] == b"modified content"
            
        finally:
            await client1.close()
            await client2.close()
    
    @pytest.mark.asyncio
    async def test_closed_client_behavior(self):
        """Test behavior after client is closed."""
        client = _MemoryS3Client()
        
        # Put an object
        await client.put_object(
            Bucket="test-bucket",
            Key="test-file",
            Body=b"test content",
            ContentType="text/plain",
            Metadata={}
        )
        
        # Close the client
        await client.close()
        
        # All operations should fail
        with pytest.raises(RuntimeError, match="Client has been closed"):
            await client.put_object(
                Bucket="test-bucket",
                Key="new-file",
                Body=b"new content",
                ContentType="text/plain",
                Metadata={}
            )
        
        with pytest.raises(RuntimeError, match="Client has been closed"):
            await client.get_object(Bucket="test-bucket", Key="test-file")
    
    @pytest.mark.asyncio
    async def test_debug_utilities(self):
        """Test debug utility methods."""
        client = _MemoryS3Client()
        
        try:
            # Initially empty
            keys = await client._debug_list_all_keys()
            assert keys == []
            
            stats = await client._debug_get_stats()
            assert stats["total_objects"] == 0
            assert stats["total_bytes"] == 0
            assert stats["closed"] is False
            
            # Add some objects
            await client.put_object(
                Bucket="bucket1",
                Key="file1",
                Body=b"content1",
                ContentType="text/plain",
                Metadata={}
            )
            
            await client.put_object(
                Bucket="bucket2",
                Key="file2", 
                Body=b"longer content here",
                ContentType="text/plain",
                Metadata={}
            )
            
            # Check debug info
            keys = await client._debug_list_all_keys()
            assert len(keys) == 2
            assert "bucket1/file1" in keys
            assert "bucket2/file2" in keys
            
            stats = await client._debug_get_stats()
            assert stats["total_objects"] == 2
            assert stats["total_bytes"] == len(b"content1") + len(b"longer content here")
            assert stats["closed"] is False
            
        finally:
            await client.close()


class TestMemoryProviderFactory:
    """Test the factory functions."""
    
    @pytest.mark.asyncio
    async def test_basic_factory(self):
        """Test basic factory usage."""
        factory_func = factory()
        
        async with factory_func() as client:
            # Should be a working client
            await client.put_object(
                Bucket="test-bucket",
                Key="test-key",
                Body=b"factory test",
                ContentType="text/plain",
                Metadata={}
            )
            
            response = await client.get_object(Bucket="test-bucket", Key="test-key")
            assert response["Body"] == b"factory test"
    
    @pytest.mark.asyncio
    async def test_shared_factory(self):
        """Test factory with shared storage."""
        factory_func, shared_store = create_shared_memory_factory()
        
        # Create first client
        async with factory_func() as client1:
            await client1.put_object(
                Bucket="shared-bucket",
                Key="shared-file",
                Body=b"shared content",
                ContentType="text/plain", 
                Metadata={}
            )
        
        # Create second client with same shared store
        async with factory_func() as client2:
            # Should see the same data
            response = await client2.get_object(Bucket="shared-bucket", Key="shared-file")
            assert response["Body"] == b"shared content"
        
        # Verify shared_store contains the data
        assert "shared-bucket/shared-file" in shared_store
        assert shared_store["shared-bucket/shared-file"]["data"] == b"shared content"
    
    @pytest.mark.asyncio
    async def test_factory_isolation(self):
        """Test that different factories are isolated."""
        factory1 = factory()
        factory2 = factory()
        
        async with factory1() as client1:
            await client1.put_object(
                Bucket="bucket",
                Key="file1",
                Body=b"content1",
                ContentType="text/plain",
                Metadata={}
            )
        
        async with factory2() as client2:
            # Should not see client1's data
            with pytest.raises(Exception):
                await client2.get_object(Bucket="bucket", Key="file1")
    
    @pytest.mark.asyncio
    async def test_instance_counting(self):
        """Test instance counting for debugging."""
        initial_count = _MemoryS3Client._debug_instance_count()
        
        # Create some clients
        client1 = _MemoryS3Client()
        client2 = _MemoryS3Client()
        
        # Count should increase
        assert _MemoryS3Client._debug_instance_count() >= initial_count + 2
        
        # Close clients
        await client1.close()
        await client2.close()
        
        # Note: WeakSet may not immediately reflect the change due to GC
        # This is more of a smoke test for the functionality


class TestMemoryProviderConcurrency:
    """Test concurrent operations with memory provider."""
    
    @pytest.mark.asyncio
    async def test_concurrent_puts(self):
        """Test concurrent put operations."""
        client = _MemoryS3Client()
        
        try:
            async def put_object(index):
                await client.put_object(
                    Bucket="concurrent-bucket",
                    Key=f"file_{index}",
                    Body=f"content_{index}".encode(),
                    ContentType="text/plain",
                    Metadata={"index": str(index)}
                )
                return index
            
            # Run 10 concurrent puts
            tasks = [put_object(i) for i in range(10)]
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 10
            assert sorted(results) == list(range(10))
            
            # Verify all objects were stored
            for i in range(10):
                response = await client.get_object(
                    Bucket="concurrent-bucket",
                    Key=f"file_{i}"
                )
                assert response["Body"] == f"content_{i}".encode()
                assert response["Metadata"]["index"] == str(i)
                
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_concurrent_gets(self):
        """Test concurrent get operations."""
        client = _MemoryS3Client()
        
        try:
            # Put some objects first
            for i in range(5):
                await client.put_object(
                    Bucket="get-bucket",
                    Key=f"file_{i}",
                    Body=f"content_{i}".encode(),
                    ContentType="text/plain",
                    Metadata={}
                )
            
            async def get_object(index):
                response = await client.get_object(
                    Bucket="get-bucket",
                    Key=f"file_{index}"
                )
                return response["Body"]
            
            # Run concurrent gets
            tasks = [get_object(i) for i in range(5)]
            results = await asyncio.gather(*tasks)
            
            # Verify results
            for i, result in enumerate(results):
                assert result == f"content_{i}".encode()
                
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(self):
        """Test mixed concurrent operations."""
        client = _MemoryS3Client()
        
        try:
            async def put_operation(index):
                await client.put_object(
                    Bucket="mixed-bucket",
                    Key=f"put_{index}",
                    Body=f"put_content_{index}".encode(),
                    ContentType="text/plain",
                    Metadata={}
                )
                return f"put_{index}"
            
            async def get_operation(index):
                try:
                    response = await client.get_object(
                        Bucket="mixed-bucket",
                        Key=f"put_{index}"
                    )
                    return response["Body"]
                except:
                    return None
            
            async def delete_operation(index):
                await client.delete_object(
                    Bucket="mixed-bucket",
                    Key=f"put_{index}"
                )
                return f"deleted_{index}"
            
            # First, put some objects
            put_tasks = [put_operation(i) for i in range(5)]
            await asyncio.gather(*put_tasks)
            
            # Then mix gets and deletes
            mixed_tasks = []
            for i in range(5):
                if i % 2 == 0:
                    mixed_tasks.append(get_operation(i))
                else:
                    mixed_tasks.append(delete_operation(i))
            
            results = await asyncio.gather(*mixed_tasks, return_exceptions=True)
            
            # Should have some successful operations
            non_exception_results = [r for r in results if not isinstance(r, Exception)]
            assert len(non_exception_results) > 0
            
        finally:
            await client.close()


class TestMemoryProviderIntegration:
    """Test memory provider with ArtifactStore integration patterns."""
    
    @pytest.mark.asyncio
    async def test_artifact_store_pattern(self):
        """Test patterns similar to how ArtifactStore would use the provider."""
        shared_store = {}
        factory_func = factory(shared_store)
        
        async with factory_func() as s3:
            # Simulate ArtifactStore operations
            bucket = "mcp-artifacts"
            key = "grid/sandbox-123/sess-456/artifact-789"
            
            # Store an artifact
            await s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=b"artifact content",
                ContentType="application/octet-stream",
                Metadata={
                    "filename": "test.txt",
                    "session_id": "sess-456",
                    "sandbox_id": "sandbox-123"
                }
            )
            
            # Retrieve it
            response = await s3.get_object(Bucket=bucket, Key=key)
            assert response["Body"] == b"artifact content"
            assert response["Metadata"]["filename"] == "test.txt"
            
            # List objects with grid prefix
            list_response = await s3.list_objects_v2(
                Bucket=bucket,
                Prefix="grid/sandbox-123/sess-456/"
            )
            
            assert list_response["KeyCount"] == 1
            assert list_response["Contents"][0]["Key"] == key
            
            # Generate presigned URL
            url = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=3600
            )
            
            assert url.startswith(f"memory://{bucket}/{key}")
    
    @pytest.mark.asyncio
    async def test_session_isolation_pattern(self):
        """Test session isolation pattern."""
        shared_store = {}
        factory_func = factory(shared_store)
        
        async with factory_func() as s3:
            bucket = "mcp-artifacts"
            
            # Store artifacts in different sessions
            await s3.put_object(
                Bucket=bucket,
                Key="grid/sandbox-1/sess-alice/file1",
                Body=b"alice content 1",
                ContentType="text/plain",
                Metadata={"session_id": "sess-alice"}
            )
            
            await s3.put_object(
                Bucket=bucket,
                Key="grid/sandbox-1/sess-alice/file2", 
                Body=b"alice content 2",
                ContentType="text/plain",
                Metadata={"session_id": "sess-alice"}
            )
            
            await s3.put_object(
                Bucket=bucket,
                Key="grid/sandbox-1/sess-bob/file1",
                Body=b"bob content 1",
                ContentType="text/plain",
                Metadata={"session_id": "sess-bob"}
            )
            
            # List Alice's files
            alice_response = await s3.list_objects_v2(
                Bucket=bucket,
                Prefix="grid/sandbox-1/sess-alice/"
            )
            
            assert alice_response["KeyCount"] == 2
            alice_keys = [obj["Key"] for obj in alice_response["Contents"]]
            assert "grid/sandbox-1/sess-alice/file1" in alice_keys
            assert "grid/sandbox-1/sess-alice/file2" in alice_keys
            
            # List Bob's files
            bob_response = await s3.list_objects_v2(
                Bucket=bucket,
                Prefix="grid/sandbox-1/sess-bob/"
            )
            
            assert bob_response["KeyCount"] == 1
            bob_keys = [obj["Key"] for obj in bob_response["Contents"]]
            assert "grid/sandbox-1/sess-bob/file1" in bob_keys
            
            # Verify isolation
            for alice_key in alice_keys:
                assert alice_key not in bob_keys
            
            for bob_key in bob_keys:
                assert bob_key not in alice_keys


class TestMemoryProviderCleanup:
    """Test cleanup functionality."""
    
    @pytest.mark.asyncio 
    async def test_clear_all_memory_stores(self):
        """Test emergency cleanup function."""
        # Create some clients
        client1 = _MemoryS3Client()
        client2 = _MemoryS3Client()
        
        # Add some data
        await client1.put_object(
            Bucket="bucket1",
            Key="file1",
            Body=b"content1",
            ContentType="text/plain",
            Metadata={}
        )
        
        await client2.put_object(
            Bucket="bucket2", 
            Key="file2",
            Body=b"content2",
            ContentType="text/plain",
            Metadata={}
        )
        
        # Verify data exists
        response1 = await client1.get_object(Bucket="bucket1", Key="file1")
        assert response1["Body"] == b"content1"
        
        # Clear all stores
        await clear_all_memory_stores()
        
        # Clients should be closed
        with pytest.raises(RuntimeError):
            await client1.get_object(Bucket="bucket1", Key="file1")
        
        with pytest.raises(RuntimeError):
            await client2.get_object(Bucket="bucket2", Key="file2")
    
    def test_instance_tracking(self):
        """Test that instances are tracked correctly."""
        initial_count = _MemoryS3Client._debug_instance_count()
        
        # Create instances
        clients = [_MemoryS3Client() for _ in range(3)]
        
        # Count should increase
        new_count = _MemoryS3Client._debug_instance_count()
        assert new_count >= initial_count + 3
        
        # Clean up
        for client in clients:
            asyncio.run(client.close())


class TestMemoryProviderEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.mark.asyncio
    async def test_large_objects(self):
        """Test handling of larger objects."""
        client = _MemoryS3Client()
        
        try:
            # Create a larger object (1MB)
            large_data = b"x" * (1024 * 1024)
            
            await client.put_object(
                Bucket="large-bucket",
                Key="large-file",
                Body=large_data,
                ContentType="application/octet-stream",
                Metadata={"size": "1MB"}
            )
            
            response = await client.get_object(Bucket="large-bucket", Key="large-file")
            assert response["Body"] == large_data
            assert response["ContentLength"] == len(large_data)
            
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_special_characters_in_keys(self):
        """Test handling of special characters in keys."""
        client = _MemoryS3Client()
        
        try:
            special_keys = [
                "file with spaces.txt",
                "file-with-dashes.txt", 
                "file_with_underscores.txt",
                "file.with.dots.txt",
                "file/with/slashes.txt",
                "файл.txt",  # Unicode
                "🚀.txt",    # Emoji
            ]
            
            for key in special_keys:
                await client.put_object(
                    Bucket="special-bucket",
                    Key=key,
                    Body=f"content for {key}".encode('utf-8'),
                    ContentType="text/plain",
                    Metadata={"original_key": key}
                )
            
            # Verify all can be retrieved
            for key in special_keys:
                response = await client.get_object(Bucket="special-bucket", Key=key)
                expected_content = f"content for {key}".encode('utf-8')
                assert response["Body"] == expected_content
                assert response["Metadata"]["original_key"] == key
                
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_empty_objects(self):
        """Test handling of empty objects."""
        client = _MemoryS3Client()
        
        try:
            # Put empty object
            await client.put_object(
                Bucket="empty-bucket",
                Key="empty-file",
                Body=b"",
                ContentType="text/plain",
                Metadata={"type": "empty"}
            )
            
            response = await client.get_object(Bucket="empty-bucket", Key="empty-file")
            assert response["Body"] == b""
            assert response["ContentLength"] == 0
            assert response["Metadata"]["type"] == "empty"
            
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_overwrite_objects(self):
        """Test overwriting existing objects."""
        client = _MemoryS3Client()
        
        try:
            # Put initial object
            await client.put_object(
                Bucket="overwrite-bucket",
                Key="file.txt",
                Body=b"original content",
                ContentType="text/plain",
                Metadata={"version": "1"}
            )
            
            # Overwrite with new content
            await client.put_object(
                Bucket="overwrite-bucket",
                Key="file.txt",
                Body=b"updated content",
                ContentType="application/json",
                Metadata={"version": "2"}
            )
            
            # Verify new content
            response = await client.get_object(Bucket="overwrite-bucket", Key="file.txt")
            assert response["Body"] == b"updated content"
            assert response["ContentType"] == "application/json"
            assert response["Metadata"]["version"] == "2"
            
        finally:
            await client.close()
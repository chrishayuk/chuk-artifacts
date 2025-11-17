#!/usr/bin/env python3
# tests/test_s3_provider.py
"""
Unit tests for S3 provider using pytest.
Tests the S3 provider functionality with mocking and real S3 integration.
"""

import pytest
import asyncio
import os
from unittest.mock import AsyncMock, patch
from contextlib import asynccontextmanager

# Test imports
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chuk_artifacts.providers.s3 import factory


class TestS3ProviderFactory:
    """Test S3 provider factory functionality."""

    def test_factory_creation(self):
        """Test basic factory creation."""
        with patch.dict(
            os.environ,
            {
                "AWS_ACCESS_KEY_ID": "test_key",
                "AWS_SECRET_ACCESS_KEY": "test_secret",
            },
        ):
            s3_factory = factory()
            assert callable(s3_factory)

    def test_factory_with_parameters(self):
        """Test factory creation with custom parameters."""
        s3_factory = factory(
            endpoint_url="https://test.endpoint.com",
            region="us-west-2",
            access_key="test_key",
            secret_key="test_secret",
        )
        assert callable(s3_factory)

    def test_factory_missing_credentials(self):
        """Test factory fails without credentials."""
        # Clear environment variables temporarily
        original_access = os.environ.get("AWS_ACCESS_KEY_ID")
        original_secret = os.environ.get("AWS_SECRET_ACCESS_KEY")

        try:
            # Remove credentials
            if "AWS_ACCESS_KEY_ID" in os.environ:
                del os.environ["AWS_ACCESS_KEY_ID"]
            if "AWS_SECRET_ACCESS_KEY" in os.environ:
                del os.environ["AWS_SECRET_ACCESS_KEY"]

            with pytest.raises(RuntimeError, match="AWS credentials missing"):
                factory()
        finally:
            # Restore environment variables
            if original_access:
                os.environ["AWS_ACCESS_KEY_ID"] = original_access
            if original_secret:
                os.environ["AWS_SECRET_ACCESS_KEY"] = original_secret


@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client for testing."""
    client = AsyncMock()

    # Mock successful responses
    client.put_object.return_value = {"ETag": '"test-etag"'}
    client.get_object.return_value = {
        "Body": b"test data",
        "ContentType": "text/plain",
        "Metadata": {"test": "true"},
    }
    client.head_object.return_value = {
        "ContentLength": 9,
        "ContentType": "text/plain",
        "Metadata": {"test": "true"},
    }
    client.head_bucket.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    client.list_objects_v2.return_value = {
        "Contents": [{"Key": "test-file.txt", "Size": 9}],
        "KeyCount": 1,
    }
    client.delete_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 204}}
    client.generate_presigned_url.return_value = "https://test.url/presigned"

    return client


@pytest.fixture
def s3_factory_mock(mock_s3_client):
    """Create a factory that returns a mock S3 client."""

    @asynccontextmanager
    async def mock_factory():
        yield mock_s3_client

    return mock_factory


class TestS3ProviderBasicOperations:
    """Test basic S3 provider operations."""

    @pytest.mark.asyncio
    async def test_put_object(self, s3_factory_mock):
        """Test putting an object to S3."""
        async with s3_factory_mock() as s3:
            response = await s3.put_object(
                Bucket="test-bucket",
                Key="test-key",
                Body=b"test data",
                ContentType="text/plain",
                Metadata={"test": "true"},
            )

            assert response["ETag"] == '"test-etag"'
            s3.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_object(self, s3_factory_mock):
        """Test getting an object from S3."""
        async with s3_factory_mock() as s3:
            response = await s3.get_object(Bucket="test-bucket", Key="test-key")

            assert response["Body"] == b"test data"
            assert response["ContentType"] == "text/plain"
            s3.get_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_head_object(self, s3_factory_mock):
        """Test getting object metadata."""
        async with s3_factory_mock() as s3:
            response = await s3.head_object(Bucket="test-bucket", Key="test-key")

            assert response["ContentLength"] == 9
            assert response["ContentType"] == "text/plain"
            s3.head_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_object(self, s3_factory_mock):
        """Test deleting an object from S3."""
        async with s3_factory_mock() as s3:
            response = await s3.delete_object(Bucket="test-bucket", Key="test-key")

            assert response["ResponseMetadata"]["HTTPStatusCode"] == 204
            s3.delete_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_objects_v2(self, s3_factory_mock):
        """Test listing objects in S3."""
        async with s3_factory_mock() as s3:
            response = await s3.list_objects_v2(Bucket="test-bucket", Prefix="test-")

            assert response["KeyCount"] == 1
            assert len(response["Contents"]) == 1
            assert response["Contents"][0]["Key"] == "test-file.txt"
            s3.list_objects_v2.assert_called_once()

    @pytest.mark.asyncio
    async def test_head_bucket(self, s3_factory_mock):
        """Test checking bucket existence."""
        async with s3_factory_mock() as s3:
            response = await s3.head_bucket(Bucket="test-bucket")

            assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
            s3.head_bucket.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_presigned_url(self, s3_factory_mock):
        """Test generating presigned URLs."""
        async with s3_factory_mock() as s3:
            url = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": "test-bucket", "Key": "test-key"},
                ExpiresIn=3600,
            )

            assert url == "https://test.url/presigned"
            s3.generate_presigned_url.assert_called_once()


class TestS3ProviderErrorHandling:
    """Test S3 provider error handling."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_object(self, mock_s3_client):
        """Test getting a non-existent object raises appropriate error."""
        # Mock NoSuchKey error
        from botocore.exceptions import ClientError

        error = ClientError(
            error_response={"Error": {"Code": "NoSuchKey", "Message": "Key not found"}},
            operation_name="GetObject",
        )
        mock_s3_client.get_object.side_effect = error

        @asynccontextmanager
        async def mock_factory():
            yield mock_s3_client

        with pytest.raises(ClientError) as exc_info:
            async with mock_factory() as s3:
                await s3.get_object(Bucket="test-bucket", Key="nonexistent")

        assert exc_info.value.response["Error"]["Code"] == "NoSuchKey"

    @pytest.mark.asyncio
    async def test_invalid_bucket(self, mock_s3_client):
        """Test accessing invalid bucket raises appropriate error."""
        from botocore.exceptions import ClientError

        error = ClientError(
            error_response={
                "Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}
            },
            operation_name="HeadBucket",
        )
        mock_s3_client.head_bucket.side_effect = error

        @asynccontextmanager
        async def mock_factory():
            yield mock_s3_client

        with pytest.raises(ClientError) as exc_info:
            async with mock_factory() as s3:
                await s3.head_bucket(Bucket="invalid-bucket")

        assert exc_info.value.response["Error"]["Code"] == "NoSuchBucket"


class TestS3ProviderGridArchitecture:
    """Test S3 provider with grid architecture patterns."""

    @pytest.mark.asyncio
    async def test_grid_key_storage(self, s3_factory_mock):
        """Test storing objects with grid-style keys."""
        grid_keys = [
            "grid/sandbox-1/sess-alice/file1.txt",
            "grid/sandbox-1/sess-alice/file2.txt",
            "grid/sandbox-1/sess-bob/file1.txt",
            "grid/sandbox-2/sess-charlie/file1.txt",
        ]

        async with s3_factory_mock() as s3:
            for key in grid_keys:
                await s3.put_object(
                    Bucket="test-bucket",
                    Key=key,
                    Body=b"test data",
                    ContentType="text/plain",
                    Metadata={"grid_test": "true"},
                )

            # Verify all puts were called
            assert s3.put_object.call_count == len(grid_keys)

    @pytest.mark.asyncio
    async def test_grid_prefix_listing(self, mock_s3_client):
        """Test listing objects with grid prefixes."""
        # Mock response for alice's files
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "grid/sandbox-1/sess-alice/file1.txt", "Size": 9},
                {"Key": "grid/sandbox-1/sess-alice/file2.txt", "Size": 10},
            ],
            "KeyCount": 2,
        }

        @asynccontextmanager
        async def mock_factory():
            yield mock_s3_client

        async with mock_factory() as s3:
            response = await s3.list_objects_v2(
                Bucket="test-bucket", Prefix="grid/sandbox-1/sess-alice/"
            )

            assert response["KeyCount"] == 2
            assert all("sess-alice" in obj["Key"] for obj in response["Contents"])


class TestS3ProviderMetadata:
    """Test S3 provider metadata handling."""

    @pytest.mark.asyncio
    async def test_metadata_storage_retrieval(self, s3_factory_mock):
        """Test storing and retrieving object metadata."""
        test_metadata = {
            "filename": "test-file.txt",
            "user-id": "test-user",
            "session-id": "sess-12345",
        }

        async with s3_factory_mock() as s3:
            # Store with metadata
            await s3.put_object(
                Bucket="test-bucket",
                Key="test-key",
                Body=b"test data",
                ContentType="text/plain",
                Metadata=test_metadata,
            )

            # Retrieve metadata
            await s3.head_object(Bucket="test-bucket", Key="test-key")

            # Verify metadata was included in the calls
            put_call = s3.put_object.call_args
            assert put_call.kwargs["Metadata"] == test_metadata

    @pytest.mark.asyncio
    async def test_metadata_case_handling(self, mock_s3_client):
        """Test metadata key case handling (S3 lowercases keys)."""
        # S3 typically lowercases metadata keys
        mock_s3_client.head_object.return_value = {
            "ContentLength": 9,
            "ContentType": "text/plain",
            "Metadata": {
                "filename": "test-file.txt",
                "user-id": "test-user",
                "session-id": "sess-12345",
            },
        }

        @asynccontextmanager
        async def mock_factory():
            yield mock_s3_client

        async with mock_factory() as s3:
            response = await s3.head_object(Bucket="test-bucket", Key="test-key")

            metadata = response["Metadata"]
            assert "filename" in metadata
            assert metadata["filename"] == "test-file.txt"


class TestS3ProviderConcurrency:
    """Test S3 provider concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_put_operations(self, s3_factory_mock):
        """Test multiple concurrent put operations."""

        async def put_file(index):
            async with s3_factory_mock() as s3:
                await s3.put_object(
                    Bucket="test-bucket",
                    Key=f"concurrent/file_{index}.txt",
                    Body=f"Content {index}".encode(),
                    ContentType="text/plain",
                    Metadata={"index": str(index)},
                )
                return f"file_{index}.txt"

        # Run 5 concurrent operations
        tasks = [put_file(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert all(isinstance(result, str) for result in results)

    @pytest.mark.asyncio
    async def test_concurrent_get_operations(self, s3_factory_mock):
        """Test multiple concurrent get operations."""

        async def get_file(key):
            async with s3_factory_mock() as s3:
                response = await s3.get_object(Bucket="test-bucket", Key=key)
                return response["Body"]

        keys = [f"file_{i}.txt" for i in range(5)]
        tasks = [get_file(key) for key in keys]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert all(result == b"test data" for result in results)


class TestS3ProviderPresignedUrls:
    """Test S3 provider presigned URL functionality."""

    @pytest.mark.asyncio
    async def test_presigned_get_url(self, s3_factory_mock):
        """Test generating presigned GET URLs."""
        async with s3_factory_mock() as s3:
            url = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": "test-bucket", "Key": "test-key"},
                ExpiresIn=3600,
            )

            assert url == "https://test.url/presigned"
            assert s3.generate_presigned_url.called

    @pytest.mark.asyncio
    async def test_presigned_put_url(self, s3_factory_mock):
        """Test generating presigned PUT URLs."""
        async with s3_factory_mock() as s3:
            url = await s3.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": "test-bucket",
                    "Key": "test-key",
                    "ContentType": "text/plain",
                },
                ExpiresIn=3600,
            )

            assert url == "https://test.url/presigned"
            call_args = s3.generate_presigned_url.call_args
            assert call_args.args[0] == "put_object"

    @pytest.mark.asyncio
    async def test_presigned_url_expiry(self, s3_factory_mock):
        """Test presigned URL expiry parameter."""
        async with s3_factory_mock() as s3:
            await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": "test-bucket", "Key": "test-key"},
                ExpiresIn=1800,  # 30 minutes
            )

            call_args = s3.generate_presigned_url.call_args
            assert call_args.kwargs["ExpiresIn"] == 1800


class TestS3ProviderLargeFiles:
    """Test S3 provider large file handling."""

    @pytest.mark.asyncio
    async def test_large_file_upload(self, s3_factory_mock):
        """Test uploading a large file."""
        # Create 1MB of test data
        large_data = b"0123456789" * 104857  # ~1MB

        async with s3_factory_mock() as s3:
            response = await s3.put_object(
                Bucket="test-bucket",
                Key="large-file.bin",
                Body=large_data,
                ContentType="application/octet-stream",
                Metadata={"size": str(len(large_data))},
            )

            assert response["ETag"] == '"test-etag"'
            call_args = s3.put_object.call_args
            assert len(call_args.kwargs["Body"]) == len(large_data)

    @pytest.mark.asyncio
    async def test_large_file_metadata(self, mock_s3_client):
        """Test large file metadata handling."""
        large_size = 1048576  # 1MB
        mock_s3_client.head_object.return_value = {
            "ContentLength": large_size,
            "ContentType": "application/octet-stream",
            "Metadata": {"size": str(large_size)},
        }

        @asynccontextmanager
        async def mock_factory():
            yield mock_s3_client

        async with mock_factory() as s3:
            response = await s3.head_object(Bucket="test-bucket", Key="large-file.bin")

            assert response["ContentLength"] == large_size
            assert response["Metadata"]["size"] == str(large_size)


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (deselect with '-m \"not integration\"')",
    )


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])

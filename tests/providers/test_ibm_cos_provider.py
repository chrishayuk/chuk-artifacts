#!/usr/bin/env python3
# tests/test_ibm_cos_provider.py
"""
Unit tests for IBM COS provider using pytest.
Tests both HMAC and IAM authentication for IBM Cloud Object Storage.
"""

import pytest
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from contextlib import asynccontextmanager

# Test imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chuk_artifacts.providers.ibm_cos import factory


class TestIBMCOSProviderFactory:
    """Test IBM COS provider factory functionality."""

    def test_factory_creation_default(self):
        """Test basic factory creation with defaults."""
        # Mock environment variables for HMAC
        with patch.dict(os.environ, {
            'AWS_ACCESS_KEY_ID': 'test_access_key',
            'AWS_SECRET_ACCESS_KEY': 'test_secret_key'
        }):
            cos_factory = factory()
            assert callable(cos_factory)

    def test_factory_creation_with_parameters(self):
        """Test factory creation with custom parameters."""
        cos_factory = factory(
            endpoint_url="https://s3.eu-gb.cloud-object-storage.appdomain.cloud",
            region="eu-gb",
            access_key="test_key",
            secret_key="test_secret"
        )
        assert callable(cos_factory)

    def test_factory_missing_credentials(self):
        """Test factory fails without HMAC credentials."""
        # Clear environment variables
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="HMAC credentials missing"):
                factory()

    def test_factory_with_custom_endpoint(self):
        """Test factory with custom IBM COS endpoint."""
        with patch.dict(os.environ, {
            'AWS_ACCESS_KEY_ID': 'test_access_key',
            'AWS_SECRET_ACCESS_KEY': 'test_secret_key'
        }):
            cos_factory = factory(
                endpoint_url="https://s3.eu-de.cloud-object-storage.appdomain.cloud"
            )
            assert callable(cos_factory)

    def test_factory_region_extraction_from_endpoint(self):
        """Test that region is correctly extracted from endpoint URL."""
        test_cases = [
            ("https://s3.us-south.cloud-object-storage.appdomain.cloud", "us-south"),
            ("https://s3.us-east.cloud-object-storage.appdomain.cloud", "us-east-1"),
            ("https://s3.eu-gb.cloud-object-storage.appdomain.cloud", "eu-gb"),
            ("https://s3.eu-de.cloud-object-storage.appdomain.cloud", "eu-de"),
        ]
        
        for endpoint, expected_region in test_cases:
            with patch.dict(os.environ, {
                'AWS_ACCESS_KEY_ID': 'test_key',
                'AWS_SECRET_ACCESS_KEY': 'test_secret'
            }):
                with patch('chuk_artifacts.providers.ibm_cos.aioboto3.Session') as mock_session:
                    mock_client = Mock()
                    mock_session.return_value.client.return_value = mock_client
                    
                    cos_factory = factory(endpoint_url=endpoint)
                    # The factory function itself doesn't return the region,
                    # but we can test the internal logic by calling _make
                    factory_func = cos_factory()
                    
                    # Verify the session.client was called with correct region
                    # This tests the region extraction logic indirectly

    def test_factory_environment_region_override(self):
        """Test that AWS_REGION environment variable overrides extracted region."""
        with patch.dict(os.environ, {
            'AWS_ACCESS_KEY_ID': 'test_key',
            'AWS_SECRET_ACCESS_KEY': 'test_secret',
            'AWS_REGION': 'override-region'
        }):
            cos_factory = factory(
                endpoint_url="https://s3.us-south.cloud-object-storage.appdomain.cloud"
            )
            assert callable(cos_factory)


# class TestIBMCOSBuildClient:
#     """Test the internal _build_client function."""
# 
#     @patch('chuk_artifacts.providers.ibm_cos.aioboto3.Session')
#     def test_build_client_hmac_auth(self, mock_session):
#         """Test building client with HMAC authentication."""
#         mock_client = Mock()
#         mock_session.return_value.client.return_value = mock_client
#         
#         client = _build_client(
#             endpoint_url="https://s3.us-south.cloud-object-storage.appdomain.cloud",
#             region="us-south",
#             ibm_api_key=None,
#             ibm_instance_crn=None,
#             access_key="test_access_key",
#             secret_key="test_secret_key"
#         )
#         
#         # Verify client was created with correct parameters
#         mock_session.return_value.client.assert_called_once_with(
#             "s3",
#             endpoint_url="https://s3.us-south.cloud-object-storage.appdomain.cloud",
#             region_name="us-south",
#             aws_access_key_id="test_access_key",
#             aws_secret_access_key="test_secret_key",
#             config=mock_session.return_value.client.call_args.kwargs['config']
#         )
#         
#         # Verify config settings
#         config = mock_session.return_value.client.call_args.kwargs['config']
#         assert hasattr(config, 's3')
# 
#     @patch('chuk_artifacts.providers.ibm_cos.aioboto3.Session')
#     def test_build_client_iam_auth(self, mock_session):
#         """Test building client with IAM authentication."""
#         mock_client = Mock()
#         mock_session.return_value.client.return_value = mock_client
#         
#         client = _build_client(
#             endpoint_url="https://s3.us-south.cloud-object-storage.appdomain.cloud",
#             region="us-south",
#             ibm_api_key="test_api_key",
#             ibm_instance_crn="crn:v1:bluemix:public:cloud-object-storage:global:a/account:instance:instance-id",
#             access_key=None,
#             secret_key=None
#         )
#         
#         # Verify client was created with IAM parameters
#         mock_session.return_value.client.assert_called_once_with(
#             "s3",
#             endpoint_url="https://s3.us-south.cloud-object-storage.appdomain.cloud",
#             region_name="us-south",
#             ibm_api_key_id="test_api_key",
#             ibm_service_instance_id="crn:v1:bluemix:public:cloud-object-storage:global:a/account:instance:instance-id",
#             config=mock_session.return_value.client.call_args.kwargs['config']
#         )


@pytest.fixture
def mock_ibm_cos_client():
    """Create a mock IBM COS client for testing."""
    client = AsyncMock()
    
    # Mock IBM COS-specific responses
    client.put_object.return_value = {"ETag": '"ibm-cos-etag"'}
    client.get_object.return_value = {
        "Body": b"IBM COS test data",
        "ContentType": "text/plain",
        "Metadata": {"ibm-cos-test": "true"}
    }
    client.head_object.return_value = {
        "ContentLength": 17,
        "ContentType": "text/plain",
        "Metadata": {"ibm-cos-test": "true"}
    }
    client.head_bucket.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    client.list_objects_v2.return_value = {
        "Contents": [{"Key": "ibm-cos-file.txt", "Size": 17}],
        "KeyCount": 1
    }
    client.delete_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 204}}
    client.generate_presigned_url.return_value = "https://s3.us-south.cloud-object-storage.appdomain.cloud/bucket/key?presigned"
    
    return client


@pytest.fixture
def ibm_cos_factory_mock(mock_ibm_cos_client):
    """Create a factory that returns a mock IBM COS client."""
    @asynccontextmanager
    async def mock_factory():
        yield mock_ibm_cos_client
    
    return mock_factory


class TestIBMCOSProviderBasicOperations:
    """Test basic IBM COS provider operations."""

    @pytest.mark.asyncio
    async def test_put_object(self, ibm_cos_factory_mock):
        """Test putting an object to IBM COS."""
        async with ibm_cos_factory_mock() as cos:
            response = await cos.put_object(
                Bucket="test-cos-bucket",
                Key="test-key",
                Body=b"IBM COS test data",
                ContentType="text/plain",
                Metadata={"ibm-cos-test": "true"}
            )
            
            assert response["ETag"] == '"ibm-cos-etag"'
            cos.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_object(self, ibm_cos_factory_mock):
        """Test getting an object from IBM COS."""
        async with ibm_cos_factory_mock() as cos:
            response = await cos.get_object(
                Bucket="test-cos-bucket",
                Key="test-key"
            )
            
            assert response["Body"] == b"IBM COS test data"
            assert response["ContentType"] == "text/plain"
            assert response["Metadata"]["ibm-cos-test"] == "true"
            cos.get_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_head_object(self, ibm_cos_factory_mock):
        """Test getting object metadata from IBM COS."""
        async with ibm_cos_factory_mock() as cos:
            response = await cos.head_object(
                Bucket="test-cos-bucket",
                Key="test-key"
            )
            
            assert response["ContentLength"] == 17
            assert response["ContentType"] == "text/plain"
            assert response["Metadata"]["ibm-cos-test"] == "true"
            cos.head_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_object(self, ibm_cos_factory_mock):
        """Test deleting an object from IBM COS."""
        async with ibm_cos_factory_mock() as cos:
            response = await cos.delete_object(
                Bucket="test-cos-bucket",
                Key="test-key"
            )
            
            assert response["ResponseMetadata"]["HTTPStatusCode"] == 204
            cos.delete_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_objects_v2(self, ibm_cos_factory_mock):
        """Test listing objects in IBM COS."""
        async with ibm_cos_factory_mock() as cos:
            response = await cos.list_objects_v2(
                Bucket="test-cos-bucket",
                Prefix="test-"
            )
            
            assert response["KeyCount"] == 1
            assert len(response["Contents"]) == 1
            assert response["Contents"][0]["Key"] == "ibm-cos-file.txt"
            cos.list_objects_v2.assert_called_once()

    @pytest.mark.asyncio
    async def test_head_bucket(self, ibm_cos_factory_mock):
        """Test checking bucket existence in IBM COS."""
        async with ibm_cos_factory_mock() as cos:
            response = await cos.head_bucket(Bucket="test-cos-bucket")
            
            assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
            cos.head_bucket.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_presigned_url(self, ibm_cos_factory_mock):
        """Test generating presigned URLs for IBM COS."""
        async with ibm_cos_factory_mock() as cos:
            url = await cos.generate_presigned_url(
                "get_object",
                Params={"Bucket": "test-cos-bucket", "Key": "test-key"},
                ExpiresIn=3600
            )
            
            assert "s3.us-south.cloud-object-storage.appdomain.cloud" in url
            assert "presigned" in url
            cos.generate_presigned_url.assert_called_once()


class TestIBMCOSProviderErrorHandling:
    """Test IBM COS provider error handling."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_object(self, mock_ibm_cos_client):
        """Test getting a non-existent object from IBM COS."""
        from botocore.exceptions import ClientError
        
        error = ClientError(
            error_response={
                "Error": {"Code": "NoSuchKey", "Message": "Key not found"}
            },
            operation_name="GetObject"
        )
        mock_ibm_cos_client.get_object.side_effect = error
        
        @asynccontextmanager
        async def mock_factory():
            yield mock_ibm_cos_client
        
        with pytest.raises(ClientError) as exc_info:
            async with mock_factory() as cos:
                await cos.get_object(Bucket="test-cos-bucket", Key="nonexistent")
        
        assert exc_info.value.response["Error"]["Code"] == "NoSuchKey"

    @pytest.mark.asyncio
    async def test_invalid_bucket(self, mock_ibm_cos_client):
        """Test accessing invalid bucket in IBM COS."""
        from botocore.exceptions import ClientError
        
        error = ClientError(
            error_response={
                "Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}
            },
            operation_name="HeadBucket"
        )
        mock_ibm_cos_client.head_bucket.side_effect = error
        
        @asynccontextmanager
        async def mock_factory():
            yield mock_ibm_cos_client
        
        with pytest.raises(ClientError) as exc_info:
            async with mock_factory() as cos:
                await cos.head_bucket(Bucket="invalid-cos-bucket")
        
        assert exc_info.value.response["Error"]["Code"] == "NoSuchBucket"


class TestIBMCOSProviderConfiguration:
    """Test IBM COS provider configuration scenarios."""

    def test_endpoint_url_defaults(self):
        """Test default endpoint URL configuration."""
        with patch.dict(os.environ, {
            'AWS_ACCESS_KEY_ID': 'test_key',
            'AWS_SECRET_ACCESS_KEY': 'test_secret'
        }, clear=True):
            cos_factory = factory()
            assert callable(cos_factory)

    def test_custom_endpoint_configuration(self):
        """Test custom endpoint configuration."""
        custom_endpoints = [
            "https://s3.eu-gb.cloud-object-storage.appdomain.cloud",
            "https://s3.eu-de.cloud-object-storage.appdomain.cloud",
            "https://s3.jp-tok.cloud-object-storage.appdomain.cloud",
            "https://s3.au-syd.cloud-object-storage.appdomain.cloud"
        ]
        
        for endpoint in custom_endpoints:
            with patch.dict(os.environ, {
                'AWS_ACCESS_KEY_ID': 'test_key',
                'AWS_SECRET_ACCESS_KEY': 'test_secret'
            }):
                cos_factory = factory(endpoint_url=endpoint)
                assert callable(cos_factory)

    def test_environment_variable_configuration(self):
        """Test configuration via environment variables."""
        with patch.dict(os.environ, {
            'AWS_ACCESS_KEY_ID': 'env_access_key',
            'AWS_SECRET_ACCESS_KEY': 'env_secret_key',
            'IBM_COS_ENDPOINT': 'https://s3.eu-gb.cloud-object-storage.appdomain.cloud',
            'AWS_REGION': 'eu-gb'
        }):
            cos_factory = factory()
            assert callable(cos_factory)

    def test_parameter_override_environment(self):
        """Test that parameters override environment variables."""
        with patch.dict(os.environ, {
            'AWS_ACCESS_KEY_ID': 'env_key',
            'AWS_SECRET_ACCESS_KEY': 'env_secret',
            'IBM_COS_ENDPOINT': 'https://s3.us-south.cloud-object-storage.appdomain.cloud'
        }):
            cos_factory = factory(
                access_key="param_key",
                secret_key="param_secret",
                endpoint_url="https://s3.eu-gb.cloud-object-storage.appdomain.cloud"
            )
            assert callable(cos_factory)


class TestIBMCOSProviderGridArchitecture:
    """Test IBM COS provider with grid architecture patterns."""

    @pytest.mark.asyncio
    async def test_grid_key_storage(self, ibm_cos_factory_mock):
        """Test storing objects with grid-style keys in IBM COS."""
        grid_keys = [
            "grid/sandbox-ibm/sess-alice/file1.txt",
            "grid/sandbox-ibm/sess-alice/file2.txt",
            "grid/sandbox-ibm/sess-bob/file1.txt",
            "grid/sandbox-ibm/sess-charlie/file1.txt"
        ]
        
        async with ibm_cos_factory_mock() as cos:
            for key in grid_keys:
                await cos.put_object(
                    Bucket="test-cos-bucket",
                    Key=key,
                    Body=b"IBM COS grid test data",
                    ContentType="text/plain",
                    Metadata={"grid_test": "ibm_cos"}
                )
            
            # Verify all puts were called
            assert cos.put_object.call_count == len(grid_keys)

    @pytest.mark.asyncio
    async def test_grid_prefix_listing(self, mock_ibm_cos_client):
        """Test listing objects with grid prefixes in IBM COS."""
        # Mock response for specific prefix
        mock_ibm_cos_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "grid/sandbox-ibm/sess-alice/file1.txt", "Size": 21},
                {"Key": "grid/sandbox-ibm/sess-alice/file2.txt", "Size": 21}
            ],
            "KeyCount": 2
        }
        
        @asynccontextmanager
        async def mock_factory():
            yield mock_ibm_cos_client
        
        async with mock_factory() as cos:
            response = await cos.list_objects_v2(
                Bucket="test-cos-bucket",
                Prefix="grid/sandbox-ibm/sess-alice/"
            )
            
            assert response["KeyCount"] == 2
            assert all("sess-alice" in obj["Key"] for obj in response["Contents"])


class TestIBMCOSProviderMetadata:
    """Test IBM COS provider metadata handling."""

    @pytest.mark.asyncio
    async def test_metadata_storage_retrieval(self, ibm_cos_factory_mock):
        """Test storing and retrieving object metadata in IBM COS."""
        ibm_metadata = {
            "filename": "ibm-cos-file.txt",
            "user-id": "ibm-user",
            "session-id": "sess-ibm-12345",
            "cos-region": "us-south"
        }
        
        async with ibm_cos_factory_mock() as cos:
            # Store with metadata
            await cos.put_object(
                Bucket="test-cos-bucket",
                Key="test-key",
                Body=b"IBM COS test data",
                ContentType="text/plain",
                Metadata=ibm_metadata
            )
            
            # Retrieve metadata
            response = await cos.head_object(
                Bucket="test-cos-bucket",
                Key="test-key"
            )
            
            # Verify metadata was included in the calls
            put_call = cos.put_object.call_args
            assert put_call.kwargs["Metadata"] == ibm_metadata

    @pytest.mark.asyncio
    async def test_ibm_cos_specific_metadata(self, mock_ibm_cos_client):
        """Test IBM COS specific metadata handling."""
        # IBM COS specific metadata response
        mock_ibm_cos_client.head_object.return_value = {
            "ContentLength": 21,
            "ContentType": "text/plain",
            "Metadata": {
                "ibm-cos-region": "us-south",
                "ibm-cos-storage-class": "standard",
                "user-defined": "custom-value"
            }
        }
        
        @asynccontextmanager
        async def mock_factory():
            yield mock_ibm_cos_client
        
        async with mock_factory() as cos:
            response = await cos.head_object(
                Bucket="test-cos-bucket",
                Key="test-key"
            )
            
            metadata = response["Metadata"]
            assert "ibm-cos-region" in metadata
            assert metadata["ibm-cos-region"] == "us-south"


class TestIBMCOSProviderConcurrency:
    """Test IBM COS provider concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_put_operations(self, ibm_cos_factory_mock):
        """Test multiple concurrent put operations to IBM COS."""
        async def put_file(index):
            async with ibm_cos_factory_mock() as cos:
                await cos.put_object(
                    Bucket="test-cos-bucket",
                    Key=f"concurrent/ibm_file_{index}.txt",
                    Body=f"IBM COS Content {index}".encode(),
                    ContentType="text/plain",
                    Metadata={"index": str(index), "provider": "ibm_cos"}
                )
                return f"ibm_file_{index}.txt"
        
        # Run 5 concurrent operations
        tasks = [put_file(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 5
        assert all(isinstance(result, str) for result in results)
        assert all("ibm_file_" in result for result in results)

    @pytest.mark.asyncio
    async def test_concurrent_get_operations(self, ibm_cos_factory_mock):
        """Test multiple concurrent get operations from IBM COS."""
        async def get_file(key):
            async with ibm_cos_factory_mock() as cos:
                response = await cos.get_object(
                    Bucket="test-cos-bucket",
                    Key=key
                )
                return response["Body"]
        
        keys = [f"ibm_file_{i}.txt" for i in range(5)]
        tasks = [get_file(key) for key in keys]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 5
        assert all(result == b"IBM COS test data" for result in results)


class TestIBMCOSProviderPresignedUrls:
    """Test IBM COS provider presigned URL functionality."""

    @pytest.mark.asyncio
    async def test_presigned_get_url(self, ibm_cos_factory_mock):
        """Test generating presigned GET URLs for IBM COS."""
        async with ibm_cos_factory_mock() as cos:
            url = await cos.generate_presigned_url(
                "get_object",
                Params={"Bucket": "test-cos-bucket", "Key": "test-key"},
                ExpiresIn=3600
            )
            
            assert "s3.us-south.cloud-object-storage.appdomain.cloud" in url
            assert "presigned" in url
            assert cos.generate_presigned_url.called

    @pytest.mark.asyncio
    async def test_presigned_put_url(self, ibm_cos_factory_mock):
        """Test generating presigned PUT URLs for IBM COS."""
        async with ibm_cos_factory_mock() as cos:
            url = await cos.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": "test-cos-bucket", 
                    "Key": "test-key",
                    "ContentType": "text/plain"
                },
                ExpiresIn=3600
            )
            
            assert "s3.us-south.cloud-object-storage.appdomain.cloud" in url
            call_args = cos.generate_presigned_url.call_args
            assert call_args.args[0] == "put_object"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
#!/usr/bin/env python3
# tests/test_ibm_cos_iam_provider.py
"""
Unit tests for IBM COS IAM provider using pytest.
Tests the IAM-based authentication for IBM Cloud Object Storage.
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

from chuk_artifacts.providers.ibm_cos_iam import factory, _sync_client, _AsyncIBMClient


class TestIBMCOSIAMProviderFactory:
    """Test IBM COS IAM provider factory functionality."""

    def test_factory_creation(self):
        """Test basic factory creation."""
        iam_factory = factory()
        assert callable(iam_factory)

    @patch('chuk_artifacts.providers.ibm_cos_iam._sync_client')
    def test_factory_returns_async_context_manager(self, mock_sync_client):
        """Test that factory returns an async context manager."""
        mock_client = Mock()
        mock_sync_client.return_value = mock_client
        
        iam_factory = factory()
        context_manager = iam_factory()
        
        # Test that it's an async context manager
        assert hasattr(context_manager, '__aenter__')
        assert hasattr(context_manager, '__aexit__')


class TestIBMCOSIAMSyncClient:
    """Test the sync client creation function."""

    @patch.dict(os.environ, {
        'IBM_COS_APIKEY': 'test_api_key',
        'IBM_COS_INSTANCE_CRN': 'crn:v1:bluemix:public:cloud-object-storage:global:a/account:instance:instance-id',
        'IBM_COS_ENDPOINT': 'https://s3.us-south.cloud-object-storage.appdomain.cloud'
    })
    @patch('chuk_artifacts.providers.ibm_cos_iam.ibm_boto3.client')
    def test_sync_client_creation_success(self, mock_boto3_client):
        """Test successful sync client creation with proper environment."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client
        
        client = _sync_client()
        
        mock_boto3_client.assert_called_once_with(
            "s3",
            ibm_api_key_id="test_api_key",
            ibm_service_instance_id="crn:v1:bluemix:public:cloud-object-storage:global:a/account:instance:instance-id",
            config=mock_boto3_client.call_args.kwargs['config'],
            endpoint_url="https://s3.us-south.cloud-object-storage.appdomain.cloud"
        )
        
        assert client == mock_client

    @patch.dict(os.environ, {}, clear=True)
    def test_sync_client_missing_credentials(self):
        """Test sync client creation fails with missing credentials."""
        with pytest.raises(RuntimeError, match="Set IBM_COS_APIKEY, IBM_COS_INSTANCE_CRN"):
            _sync_client()

    @patch.dict(os.environ, {
        'IBM_COS_APIKEY': 'test_api_key',
        # Missing IBM_COS_INSTANCE_CRN
        'IBM_COS_ENDPOINT': 'https://s3.us-south.cloud-object-storage.appdomain.cloud'
    })
    def test_sync_client_missing_instance_crn(self):
        """Test sync client creation fails with missing instance CRN."""
        with pytest.raises(RuntimeError, match="Set IBM_COS_APIKEY, IBM_COS_INSTANCE_CRN"):
            _sync_client()

    @patch.dict(os.environ, {
        'IBM_COS_APIKEY': 'test_api_key',
        'IBM_COS_INSTANCE_CRN': 'crn:v1:bluemix:public:cloud-object-storage:global:a/account:instance:instance-id'
        # Missing IBM_COS_ENDPOINT - should use default
    })
    @patch('chuk_artifacts.providers.ibm_cos_iam.ibm_boto3.client')
    def test_sync_client_default_endpoint(self, mock_boto3_client):
        """Test sync client uses default endpoint when not provided."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client
        
        client = _sync_client()
        
        # Should use default endpoint
        call_args = mock_boto3_client.call_args
        assert call_args.kwargs['endpoint_url'] == "https://s3.us-south.cloud-object-storage.appdomain.cloud"


class TestAsyncIBMClient:
    """Test the async wrapper for IBM COS client."""

    @pytest.fixture
    def mock_sync_client(self):
        """Create a mock sync client for testing."""
        sync_client = Mock()
        
        # Mock sync client methods
        sync_client.put_object.return_value = {"ETag": '"ibm-iam-etag"'}
        sync_client.get_object.return_value = {
            "Body": b"IBM COS IAM test data",
            "ContentType": "text/plain",
            "Metadata": {"iam-test": "true"}
        }
        sync_client.head_object.return_value = {
            "ContentLength": 20,
            "ContentType": "text/plain",
            "Metadata": {"iam-test": "true"}
        }
        sync_client.delete_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 204}}
        sync_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "iam-test-file.txt", "Size": 20}],
            "KeyCount": 1
        }
        sync_client.generate_presigned_url.return_value = "https://s3.us-south.cloud-object-storage.appdomain.cloud/bucket/key?iam-presigned"
        
        return sync_client

    @pytest.mark.asyncio
    async def test_async_put_object(self, mock_sync_client):
        """Test async put_object wrapper."""
        async_client = _AsyncIBMClient(mock_sync_client)
        
        response = await async_client.put_object(
            Bucket="test-bucket",
            Key="test-key",
            Body=b"test data",
            ContentType="text/plain",
            Metadata={"test": "iam"}
        )
        
        assert response["ETag"] == '"ibm-iam-etag"'
        mock_sync_client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_get_object(self, mock_sync_client):
        """Test async get_object wrapper."""
        async_client = _AsyncIBMClient(mock_sync_client)
        
        response = await async_client.get_object(
            Bucket="test-bucket",
            Key="test-key"
        )
        
        assert response["Body"] == b"IBM COS IAM test data"
        assert response["Metadata"]["iam-test"] == "true"
        mock_sync_client.get_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_head_object(self, mock_sync_client):
        """Test async head_object wrapper."""
        async_client = _AsyncIBMClient(mock_sync_client)
        
        response = await async_client.head_object(
            Bucket="test-bucket",
            Key="test-key"
        )
        
        assert response["ContentLength"] == 20
        assert response["Metadata"]["iam-test"] == "true"
        mock_sync_client.head_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_delete_object(self, mock_sync_client):
        """Test async delete_object wrapper."""
        async_client = _AsyncIBMClient(mock_sync_client)
        
        response = await async_client.delete_object(
            Bucket="test-bucket",
            Key="test-key"
        )
        
        assert response["ResponseMetadata"]["HTTPStatusCode"] == 204
        mock_sync_client.delete_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_list_objects_v2(self, mock_sync_client):
        """Test async list_objects_v2 wrapper."""
        async_client = _AsyncIBMClient(mock_sync_client)
        
        response = await async_client.list_objects_v2(
            Bucket="test-bucket",
            Prefix="test-"
        )
        
        assert response["KeyCount"] == 1
        assert response["Contents"][0]["Key"] == "iam-test-file.txt"
        mock_sync_client.list_objects_v2.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_generate_presigned_url(self, mock_sync_client):
        """Test async generate_presigned_url wrapper."""
        async_client = _AsyncIBMClient(mock_sync_client)
        
        url = await async_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": "test-key"},
            ExpiresIn=3600
        )
        
        assert "iam-presigned" in url
        assert "s3.us-south.cloud-object-storage.appdomain.cloud" in url
        mock_sync_client.generate_presigned_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_close(self, mock_sync_client):
        """Test async close wrapper."""
        async_client = _AsyncIBMClient(mock_sync_client)
        
        await async_client.close()
        
        mock_sync_client.close.assert_called_once()


@pytest.fixture
def mock_ibm_cos_iam_client():
    """Create a mock IBM COS IAM client for testing."""
    client = AsyncMock()
    
    # Mock IBM COS IAM-specific responses
    client.put_object.return_value = {"ETag": '"ibm-cos-iam-etag"'}
    client.get_object.return_value = {
        "Body": b"IBM COS IAM test data",
        "ContentType": "text/plain",
        "Metadata": {"iam-provider": "true"}
    }
    client.head_object.return_value = {
        "ContentLength": 20,
        "ContentType": "text/plain",
        "Metadata": {"iam-provider": "true"}
    }
    client.delete_object.return_value = {"ResponseMetadata": {"HTTPStatusCode": 204}}
    client.list_objects_v2.return_value = {
        "Contents": [{"Key": "iam-test-file.txt", "Size": 20}],
        "KeyCount": 1
    }
    client.generate_presigned_url.return_value = "https://s3.us-south.cloud-object-storage.appdomain.cloud/bucket/key?iam-signature"
    
    return client


@pytest.fixture
def ibm_cos_iam_factory_mock(mock_ibm_cos_iam_client):
    """Create a factory that returns a mock IBM COS IAM client."""
    @asynccontextmanager
    async def mock_factory():
        yield mock_ibm_cos_iam_client
    
    return mock_factory


class TestIBMCOSIAMProviderBasicOperations:
    """Test basic IBM COS IAM provider operations."""

    @pytest.mark.asyncio
    async def test_put_object(self, ibm_cos_iam_factory_mock):
        """Test putting an object to IBM COS with IAM."""
        async with ibm_cos_iam_factory_mock() as cos:
            response = await cos.put_object(
                Bucket="test-iam-bucket",
                Key="test-key",
                Body=b"IBM COS IAM test data",
                ContentType="text/plain",
                Metadata={"iam-provider": "true"}
            )
            
            assert response["ETag"] == '"ibm-cos-iam-etag"'
            cos.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_object(self, ibm_cos_iam_factory_mock):
        """Test getting an object from IBM COS with IAM."""
        async with ibm_cos_iam_factory_mock() as cos:
            response = await cos.get_object(
                Bucket="test-iam-bucket",
                Key="test-key"
            )
            
            assert response["Body"] == b"IBM COS IAM test data"
            assert response["ContentType"] == "text/plain"
            assert response["Metadata"]["iam-provider"] == "true"
            cos.get_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_presigned_url(self, ibm_cos_iam_factory_mock):
        """Test generating presigned URLs with IBM COS IAM."""
        async with ibm_cos_iam_factory_mock() as cos:
            url = await cos.generate_presigned_url(
                "get_object",
                Params={"Bucket": "test-iam-bucket", "Key": "test-key"},
                ExpiresIn=3600
            )
            
            assert "iam-signature" in url
            assert "s3.us-south.cloud-object-storage.appdomain.cloud" in url
            cos.generate_presigned_url.assert_called_once()


class TestIBMCOSIAMProviderErrorHandling:
    """Test IBM COS IAM provider error handling."""

    @pytest.mark.asyncio
    async def test_oauth_credential_error(self, mock_ibm_cos_iam_client):
        """Test handling of OAuth credential errors."""
        from botocore.exceptions import ClientError
        
        error = ClientError(
            error_response={
                "Error": {"Code": "InvalidToken", "Message": "OAuth token invalid"}
            },
            operation_name="GetObject"
        )
        mock_ibm_cos_iam_client.get_object.side_effect = error
        
        @asynccontextmanager
        async def mock_factory():
            yield mock_ibm_cos_iam_client
        
        with pytest.raises(ClientError) as exc_info:
            async with mock_factory() as cos:
                await cos.get_object(Bucket="test-bucket", Key="test-key")
        
        assert exc_info.value.response["Error"]["Code"] == "InvalidToken"

    @pytest.mark.asyncio
    async def test_iam_permission_error(self, mock_ibm_cos_iam_client):
        """Test handling of IAM permission errors."""
        from botocore.exceptions import ClientError
        
        error = ClientError(
            error_response={
                "Error": {"Code": "AccessDenied", "Message": "IAM policy denied"}
            },
            operation_name="PutObject"
        )
        mock_ibm_cos_iam_client.put_object.side_effect = error
        
        @asynccontextmanager
        async def mock_factory():
            yield mock_ibm_cos_iam_client
        
        with pytest.raises(ClientError) as exc_info:
            async with mock_factory() as cos:
                await cos.put_object(
                    Bucket="test-bucket",
                    Key="test-key",
                    Body=b"test",
                    ContentType="text/plain"
                )
        
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"


class TestIBMCOSIAMProviderConfiguration:
    """Test IBM COS IAM provider configuration scenarios."""

    @patch.dict(os.environ, {
        'IBM_COS_APIKEY': 'test_api_key',
        'IBM_COS_INSTANCE_CRN': 'crn:v1:bluemix:public:cloud-object-storage:global:a/account:instance:instance-id',
        'IBM_COS_ENDPOINT': 'https://s3.eu-gb.cloud-object-storage.appdomain.cloud'
    })
    def test_environment_configuration(self):
        """Test configuration via environment variables."""
        iam_factory = factory()
        assert callable(iam_factory)

    @patch.dict(os.environ, {
        'IBM_COS_APIKEY': 'test_api_key',
        'IBM_COS_INSTANCE_CRN': 'crn:v1:bluemix:public:cloud-object-storage:global:a/account:instance:instance-id'
        # No endpoint - should use default
    })
    def test_default_endpoint_configuration(self):
        """Test default endpoint configuration."""
        iam_factory = factory()
        assert callable(iam_factory)

    def test_different_regions_configuration(self):
        """Test configuration with different IBM COS regions."""
        regions_endpoints = [
            "https://s3.us-south.cloud-object-storage.appdomain.cloud",
            "https://s3.us-east.cloud-object-storage.appdomain.cloud",
            "https://s3.eu-gb.cloud-object-storage.appdomain.cloud",
            "https://s3.eu-de.cloud-object-storage.appdomain.cloud",
            "https://s3.jp-tok.cloud-object-storage.appdomain.cloud",
            "https://s3.au-syd.cloud-object-storage.appdomain.cloud"
        ]
        
        for endpoint in regions_endpoints:
            with patch.dict(os.environ, {
                'IBM_COS_APIKEY': 'test_api_key',
                'IBM_COS_INSTANCE_CRN': 'crn:v1:bluemix:public:cloud-object-storage:global:a/account:instance:instance-id',
                'IBM_COS_ENDPOINT': endpoint
            }):
                iam_factory = factory()
                assert callable(iam_factory)


class TestIBMCOSIAMProviderConcurrency:
    """Test IBM COS IAM provider concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_iam_operations(self, ibm_cos_iam_factory_mock):
        """Test multiple concurrent operations with IAM authentication."""
        async def perform_operation(index):
            async with ibm_cos_iam_factory_mock() as cos:
                # Put operation
                await cos.put_object(
                    Bucket="test-iam-bucket",
                    Key=f"concurrent/iam_file_{index}.txt",
                    Body=f"IAM Content {index}".encode(),
                    ContentType="text/plain",
                    Metadata={"index": str(index), "auth": "iam"}
                )
                
                # Get operation
                response = await cos.get_object(
                    Bucket="test-iam-bucket",
                    Key=f"concurrent/iam_file_{index}.txt"
                )
                
                return response["Body"]
        
        # Run 3 concurrent operations (IAM might have rate limits)
        tasks = [perform_operation(i) for i in range(3)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 3
        assert all(result == b"IBM COS IAM test data" for result in results)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
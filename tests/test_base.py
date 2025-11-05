# -*- coding: utf-8 -*-
# tests/test_base.py
"""
Tests for chuk_artifacts.base module.

Tests the BaseOperations class that provides common functionality
for all operation modules.
"""

import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from chuk_artifacts.base import BaseOperations
from chuk_artifacts.exceptions import (
    ArtifactStoreError,
    ArtifactNotFoundError,
    ArtifactCorruptedError,
    SessionError,
)


@pytest.fixture
def mock_artifact_store():
    """Create a mock ArtifactStore for testing."""
    store = Mock()
    store.bucket = "test-bucket"
    store._s3_factory = Mock()
    store._session_factory = Mock()
    store._storage_provider_name = "memory"
    store._session_provider_name = "memory"
    store.max_retries = 3
    store._session_manager = Mock()
    store._closed = False
    return store


@pytest.fixture
def base_operations(mock_artifact_store):
    """Create BaseOperations instance for testing."""
    return BaseOperations(mock_artifact_store)


class TestBaseOperationsInitialization:
    """Test BaseOperations initialization."""

    def test_initialization(self, mock_artifact_store):
        """Test that BaseOperations initializes correctly."""
        base_ops = BaseOperations(mock_artifact_store)

        assert base_ops._artifact_store is mock_artifact_store

    def test_initialization_with_none_store(self):
        """Test initialization with None store (should work but properties will fail)."""
        base_ops = BaseOperations(None)
        assert base_ops._artifact_store is None


class TestBaseOperationsProperties:
    """Test BaseOperations property accessors."""

    def test_bucket_property(self, base_operations, mock_artifact_store):
        """Test bucket property returns store bucket."""
        assert base_operations.bucket == mock_artifact_store.bucket
        assert base_operations.bucket == "test-bucket"

    def test_s3_factory_property(self, base_operations, mock_artifact_store):
        """Test s3_factory property returns store s3_factory."""
        assert base_operations.s3_factory is mock_artifact_store._s3_factory

    def test_session_factory_property(self, base_operations, mock_artifact_store):
        """Test session_factory property returns store session_factory."""
        assert base_operations.session_factory is mock_artifact_store._session_factory

    def test_storage_provider_name_property(self, base_operations, mock_artifact_store):
        """Test storage_provider_name property."""
        assert (
            base_operations.storage_provider_name
            == mock_artifact_store._storage_provider_name
        )
        assert base_operations.storage_provider_name == "memory"

    def test_session_provider_name_property(self, base_operations, mock_artifact_store):
        """Test session_provider_name property."""
        assert (
            base_operations.session_provider_name
            == mock_artifact_store._session_provider_name
        )
        assert base_operations.session_provider_name == "memory"

    def test_max_retries_property(self, base_operations, mock_artifact_store):
        """Test max_retries property."""
        assert base_operations.max_retries == mock_artifact_store.max_retries
        assert base_operations.max_retries == 3

    def test_session_manager_property(self, base_operations, mock_artifact_store):
        """Test session_manager property."""
        assert base_operations.session_manager is mock_artifact_store._session_manager

    def test_properties_with_different_values(self, mock_artifact_store):
        """Test properties with different store values."""
        mock_artifact_store.bucket = "different-bucket"
        mock_artifact_store._storage_provider_name = "s3"
        mock_artifact_store._session_provider_name = "redis"
        mock_artifact_store.max_retries = 5

        base_ops = BaseOperations(mock_artifact_store)

        assert base_ops.bucket == "different-bucket"
        assert base_ops.storage_provider_name == "s3"
        assert base_ops.session_provider_name == "redis"
        assert base_ops.max_retries == 5


class TestCheckClosed:
    """Test the _check_closed method."""

    def test_check_closed_when_open(self, base_operations, mock_artifact_store):
        """Test _check_closed when store is open."""
        mock_artifact_store._closed = False

        # Should not raise any exception
        base_operations._check_closed()

    def test_check_closed_when_closed(self, base_operations, mock_artifact_store):
        """Test _check_closed when store is closed."""
        mock_artifact_store._closed = True

        with pytest.raises(ArtifactStoreError) as exc_info:
            base_operations._check_closed()

        assert "Store has been closed" in str(exc_info.value)

    def test_check_closed_multiple_calls(self, base_operations, mock_artifact_store):
        """Test multiple calls to _check_closed."""
        mock_artifact_store._closed = False

        # Multiple calls should all succeed
        base_operations._check_closed()
        base_operations._check_closed()
        base_operations._check_closed()

        # Change to closed
        mock_artifact_store._closed = True

        # Now should fail
        with pytest.raises(ArtifactStoreError):
            base_operations._check_closed()


class TestGetRecord:
    """Test the _get_record method."""

    @pytest.mark.asyncio
    async def test_get_record_success(self, base_operations, mock_artifact_store):
        """Test successful _get_record operation."""
        # Mock successful session retrieval with valid ArtifactMetadata structure
        mock_session = AsyncMock()
        test_record = {
            "artifact_id": "test123",
            "session_id": "session456",
            "sandbox_id": "sandbox789",
            "key": "grid/sandbox789/session456/test123",
            "mime": "text/plain",
            "summary": "Test artifact",
            "meta": {},
            "filename": "test.txt",
            "bytes": 100,
            "sha256": "abc123",
            "stored_at": "2025-01-01T00:00:00Z",
            "ttl": 900,
            "storage_provider": "memory",
            "session_provider": "memory",
        }
        mock_session.get.return_value = json.dumps(test_record)

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Test the method
        result = await base_operations._get_record("test123")

        # Result should be an ArtifactMetadata model
        assert result.artifact_id == "test123"
        assert result.session_id == "session456"
        mock_session.get.assert_called_once_with("test123")

    @pytest.mark.asyncio
    async def test_get_record_not_found(self, base_operations, mock_artifact_store):
        """Test _get_record when artifact not found."""
        # Mock session returning None
        mock_session = AsyncMock()
        mock_session.get.return_value = None

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Should raise ArtifactNotFoundError
        with pytest.raises(ArtifactNotFoundError) as exc_info:
            await base_operations._get_record("nonexistent123")

        assert "Artifact nonexistent123 not found or expired" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_record_corrupted_json(
        self, base_operations, mock_artifact_store
    ):
        """Test _get_record with corrupted JSON data."""
        # Mock session returning invalid JSON
        mock_session = AsyncMock()
        mock_session.get.return_value = "invalid json {"

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Should raise ArtifactCorruptedError
        with pytest.raises(ArtifactCorruptedError) as exc_info:
            await base_operations._get_record("corrupted123")

        assert "Corrupted metadata for artifact corrupted123" in str(exc_info.value)
        # With Pydantic, the cause is wrapped differently but still indicates corruption
        assert exc_info.value.__cause__ is not None

    @pytest.mark.asyncio
    async def test_get_record_session_error(self, base_operations, mock_artifact_store):
        """Test _get_record when session provider fails."""
        # Mock session context manager raising exception
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.side_effect = Exception("Session connection failed")

        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Should raise SessionError
        with pytest.raises(SessionError) as exc_info:
            await base_operations._get_record("test123")

        assert "Session provider error retrieving test123" in str(exc_info.value)
        assert "Session connection failed" in str(exc_info.value)
        assert exc_info.value.__cause__ is not None

    @pytest.mark.asyncio
    async def test_get_record_session_get_error(
        self, base_operations, mock_artifact_store
    ):
        """Test _get_record when session.get() fails."""
        # Mock session.get() raising exception
        mock_session = AsyncMock()
        mock_session.get.side_effect = Exception("Redis timeout")

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Should raise SessionError
        with pytest.raises(SessionError) as exc_info:
            await base_operations._get_record("test123")

        assert "Session provider error retrieving test123" in str(exc_info.value)
        assert "Redis timeout" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_record_complex_data(self, base_operations, mock_artifact_store):
        """Test _get_record with complex JSON data and unicode."""
        # Test with complex nested data structure in meta field
        test_record = {
            "artifact_id": "complex123",
            "session_id": "session456",
            "sandbox_id": "sandbox789",
            "key": "grid/sandbox789/session456/complex123",
            "mime": "application/json",
            "summary": "Complex test data",
            "meta": {
                "nested": {"deep": "value"},
                "list": [1, 2, 3],
                "boolean": True,
                "null_value": None,
                "unicode": "测试数据",
            },
            "filename": "complex.json",
            "bytes": 500,
            "sha256": "def456",
            "stored_at": "2025-01-01T00:00:00Z",
            "ttl": 900,
            "storage_provider": "memory",
            "session_provider": "memory",
        }

        mock_session = AsyncMock()
        mock_session.get.return_value = json.dumps(test_record)

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        mock_artifact_store._session_factory.return_value = mock_session_ctx

        result = await base_operations._get_record("complex123")

        # Verify complex data is preserved in the model
        assert result.artifact_id == "complex123"
        assert result.meta["nested"]["deep"] == "value"
        assert result.meta["list"] == [1, 2, 3]
        assert result.meta["unicode"] == "测试数据"


class TestBaseOperationsInheritance:
    """Test that BaseOperations can be properly inherited."""

    def test_inheritance(self, mock_artifact_store):
        """Test that BaseOperations can be inherited."""

        class TestOperations(BaseOperations):
            def custom_method(self):
                return "custom"

        ops = TestOperations(mock_artifact_store)

        # Should have all base properties
        assert ops.bucket == "test-bucket"
        assert ops.max_retries == 3

        # Should have custom method
        assert ops.custom_method() == "custom"

    def test_inheritance_with_async_methods(self, mock_artifact_store):
        """Test inheritance with async methods."""

        class AsyncTestOperations(BaseOperations):
            async def async_custom_method(self):
                # Use inherited _get_record method
                return await self._get_record("test")

        ops = AsyncTestOperations(mock_artifact_store)

        # Should be able to create instance
        assert isinstance(ops, BaseOperations)
        assert hasattr(ops, "async_custom_method")


class TestLogging:
    """Test logging behavior in BaseOperations."""

    @pytest.mark.asyncio
    async def test_get_record_logs_corruption_error(
        self, base_operations, mock_artifact_store
    ):
        """Test that _get_record logs corruption errors."""
        mock_session = AsyncMock()
        mock_session.get.return_value = "invalid json"

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        mock_artifact_store._session_factory.return_value = mock_session_ctx

        with patch("chuk_artifacts.base.logger") as mock_logger:
            with pytest.raises(ArtifactCorruptedError):
                await base_operations._get_record("test123")

            # Should have logged the error
            mock_logger.error.assert_called_once()
            args = mock_logger.error.call_args[0]
            assert "Corrupted metadata for artifact test123" in args[0]


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_get_record_empty_string(self, base_operations, mock_artifact_store):
        """Test _get_record with empty string response."""
        mock_session = AsyncMock()
        mock_session.get.return_value = ""

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Empty string should be treated as corrupted JSON
        with pytest.raises(ArtifactCorruptedError):
            await base_operations._get_record("test123")

    @pytest.mark.asyncio
    async def test_get_record_whitespace_only(
        self, base_operations, mock_artifact_store
    ):
        """Test _get_record with whitespace-only response."""
        mock_session = AsyncMock()
        mock_session.get.return_value = "   \n\t  "

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Whitespace should be treated as corrupted JSON
        with pytest.raises(ArtifactCorruptedError):
            await base_operations._get_record("test123")

    @pytest.mark.asyncio
    async def test_get_record_valid_empty_dict(
        self, base_operations, mock_artifact_store
    ):
        """Test _get_record with empty dict - should fail validation."""
        mock_session = AsyncMock()
        mock_session.get.return_value = "{}"

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Empty dict should fail Pydantic validation
        with pytest.raises(ArtifactCorruptedError):
            await base_operations._get_record("test123")

    def test_properties_with_none_artifact_store(self):
        """Test that properties raise appropriate errors with None store."""
        base_ops = BaseOperations(None)

        with pytest.raises(AttributeError):
            _ = base_ops.bucket

        with pytest.raises(AttributeError):
            _ = base_ops.max_retries


class TestIntegration:
    """Integration tests with mock stores."""

    def test_full_workflow_simulation(self, mock_artifact_store):
        """Test a complete workflow using BaseOperations."""
        base_ops = BaseOperations(mock_artifact_store)

        # Simulate store being open
        mock_artifact_store._closed = False

        # Check that store is open (should not raise)
        base_ops._check_closed()

        # Access properties
        assert base_ops.bucket == "test-bucket"
        assert base_ops.storage_provider_name == "memory"

        # Simulate store being closed
        mock_artifact_store._closed = True

        # Now check_closed should raise
        with pytest.raises(ArtifactStoreError):
            base_ops._check_closed()

    @pytest.mark.asyncio
    async def test_record_retrieval_workflow(self, mock_artifact_store):
        """Test record retrieval workflow."""
        base_ops = BaseOperations(mock_artifact_store)

        test_record = {
            "artifact_id": "workflow123",
            "session_id": "session456",
            "sandbox_id": "sandbox789",
            "key": "grid/sandbox789/session456/workflow123",
            "mime": "text/plain",
            "summary": "Test workflow",
            "meta": {},
            "filename": "test.txt",
            "bytes": 100,
            "sha256": "abc123",
            "stored_at": "2025-01-01T00:00:00Z",
            "ttl": 900,
            "storage_provider": "memory",
            "session_provider": "memory",
            "data": "test_data",
        }

        mock_session = AsyncMock()
        mock_session.get.return_value = json.dumps(test_record)

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Test successful retrieval
        result = await base_ops._get_record("workflow123")

        assert result.artifact_id == "workflow123"
        assert result.session_id == "session456"
        # Custom field allowed by extra="allow" config
        assert result.data == "test_data"

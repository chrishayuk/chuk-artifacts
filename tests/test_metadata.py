# -*- coding: utf-8 -*-
"""
Comprehensive tests for chuk_artifacts.metadata module.

Tests cover:
- MetadataOperations class functionality
- Metadata retrieval and storage
- Artifact existence checking
- Artifact deletion
- Session-based listing
- Prefix-based filtering
- Metadata updates and TTL extensions
- Error handling and edge cases
- Grid architecture integration
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock

from chuk_artifacts.metadata import MetadataOperations
from chuk_artifacts.exceptions import ProviderError, SessionError, ArtifactNotFoundError
from chuk_artifacts.models import ArtifactMetadata, GridKeyComponents


class TestMetadataOperationsBasics:
    """Test basic MetadataOperations functionality."""

    @pytest.fixture
    def mock_artifact_store(self):
        """Create a mock ArtifactStore."""
        store = Mock()
        store.bucket = "test-bucket"
        store._s3_factory = Mock()
        store._session_factory = Mock()
        store.get_canonical_prefix = Mock()
        store.parse_grid_key = Mock()
        return store

    @pytest.fixture
    def metadata_ops(self, mock_artifact_store):
        """Create MetadataOperations instance with mocked store."""
        return MetadataOperations(mock_artifact_store)

    def test_init(self, mock_artifact_store):
        """Test MetadataOperations initialization."""
        ops = MetadataOperations(mock_artifact_store)
        assert ops.artifact_store is mock_artifact_store

    @pytest.mark.asyncio
    async def test_get_metadata_success(self, metadata_ops, mock_artifact_store):
        """Test successful metadata retrieval."""
        # Setup mock session
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Mock metadata record
        test_record = ArtifactMetadata(
            artifact_id="test123",
            key="test/key",
            session_id="session123",
            sandbox_id="sandbox123",
            mime="text/plain",
            summary="Test artifact",
            meta={},
            bytes=1024,
            sha256="abc123",
            stored_at="2025-01-01T00:00:00Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
        )
        mock_session.get.return_value = test_record.model_dump_json()

        # Test get_metadata
        result = await metadata_ops.get_metadata("test123")

        # Verify
        assert result == test_record
        mock_session.get.assert_called_once_with("test123")

    @pytest.mark.asyncio
    async def test_get_metadata_not_found(self, metadata_ops, mock_artifact_store):
        """Test metadata retrieval when artifact not found."""
        # Setup mock session to return None
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_artifact_store._session_factory.return_value = mock_session_ctx
        mock_session.get.return_value = None

        # Test get_metadata
        with pytest.raises(ArtifactNotFoundError, match="Artifact test123 not found"):
            await metadata_ops.get_metadata("test123")

    @pytest.mark.asyncio
    async def test_get_metadata_corrupted(self, metadata_ops, mock_artifact_store):
        """Test metadata retrieval with corrupted JSON."""
        # Setup mock session to return invalid JSON
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_artifact_store._session_factory.return_value = mock_session_ctx
        mock_session.get.return_value = "invalid json {"

        # Test get_metadata
        with pytest.raises(ProviderError, match="Corrupted metadata for test123"):
            await metadata_ops.get_metadata("test123")

    @pytest.mark.asyncio
    async def test_get_metadata_session_error(self, metadata_ops, mock_artifact_store):
        """Test metadata retrieval with session error."""
        # Setup mock session to raise an error
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_artifact_store._session_factory.return_value = mock_session_ctx
        mock_session.get.side_effect = Exception("Connection failed")

        # Test get_metadata
        with pytest.raises(SessionError, match="Session error for test123"):
            await metadata_ops.get_metadata("test123")


class TestMetadataOperationsExists:
    """Test artifact existence checking."""

    @pytest.fixture
    def metadata_ops(self):
        """Create MetadataOperations with mocked dependencies."""
        store = Mock()
        ops = MetadataOperations(store)
        return ops

    @pytest.mark.asyncio
    async def test_exists_true(self, metadata_ops):
        """Test exists returns True when artifact found."""
        # Mock _get_record to return successfully
        metadata_ops._get_record = AsyncMock()
        metadata_ops._get_record.return_value = {"artifact_id": "test123"}

        result = await metadata_ops.exists("test123")
        assert result is True
        metadata_ops._get_record.assert_called_once_with("test123")

    @pytest.mark.asyncio
    async def test_exists_false(self, metadata_ops):
        """Test exists returns False when artifact not found."""
        # Mock _get_record to raise exception
        metadata_ops._get_record = AsyncMock()
        metadata_ops._get_record.side_effect = ArtifactNotFoundError("Not found")

        result = await metadata_ops.exists("test123")
        assert result is False
        metadata_ops._get_record.assert_called_once_with("test123")

    @pytest.mark.asyncio
    async def test_exists_false_on_any_error(self, metadata_ops):
        """Test exists returns False on any error."""
        # Mock _get_record to raise any exception
        metadata_ops._get_record = AsyncMock()
        metadata_ops._get_record.side_effect = ProviderError("Provider error")

        result = await metadata_ops.exists("test123")
        assert result is False


class TestMetadataOperationsDelete:
    """Test artifact deletion."""

    @pytest.fixture
    def mock_artifact_store(self):
        """Create a mock ArtifactStore for deletion tests."""
        store = Mock()
        store.bucket = "test-bucket"
        store._s3_factory = Mock()
        store._session_factory = Mock()
        return store

    @pytest.fixture
    def metadata_ops(self, mock_artifact_store):
        """Create MetadataOperations instance."""
        return MetadataOperations(mock_artifact_store)

    @pytest.mark.asyncio
    async def test_delete_failure(self, metadata_ops, mock_artifact_store):
        """Test deletion failure."""
        # Mock record retrieval to fail
        metadata_ops._get_record = AsyncMock()
        metadata_ops._get_record.side_effect = ArtifactNotFoundError("Not found")

        # Test deletion
        result = await metadata_ops.delete("test123")

        # Should return False on failure (as expected based on the exception handling)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_session_without_delete_method(
        self, metadata_ops, mock_artifact_store
    ):
        """Test deletion when session provider doesn't have delete method."""
        # Mock successful record retrieval
        metadata_ops._get_record = AsyncMock()
        metadata_ops._get_record.return_value = ArtifactMetadata(
            artifact_id="test123",
            key="test/path/test123",
            session_id="session123",
            sandbox_id="sandbox123",
            mime="text/plain",
            summary="Test",
            meta={},
            bytes=100,
            sha256="abc123",
            stored_at="2025-01-01T00:00:00Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
        )

        # Mock storage deletion (successful)
        mock_s3 = AsyncMock()
        mock_s3.delete_object = AsyncMock()
        mock_storage_ctx = AsyncMock()
        mock_storage_ctx.__aenter__.return_value = mock_s3
        mock_storage_ctx.__aexit__.return_value = None
        mock_artifact_store._s3_factory.return_value = mock_storage_ctx

        # Create a custom object that truly doesn't have a delete method
        class SessionWithoutDelete:
            pass

        mock_session = SessionWithoutDelete()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None
        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Test deletion
        result = await metadata_ops.delete("test123")

        # Should return True even without session delete method
        # (storage deletion succeeded, session deletion skipped due to no delete method)
        assert result is True

        # Verify storage delete was called
        mock_s3.delete_object.assert_called_once_with(
            Bucket=mock_artifact_store.bucket, Key="test/path/test123"
        )

    @pytest.mark.asyncio
    async def test_delete_session_with_delete_method_success(
        self, metadata_ops, mock_artifact_store
    ):
        """Test successful deletion when session provider has delete method."""
        # Mock successful record retrieval
        metadata_ops._get_record = AsyncMock()
        metadata_ops._get_record.return_value = ArtifactMetadata(
            artifact_id="test123",
            key="test/path/test123",
            session_id="session123",
            sandbox_id="sandbox123",
            mime="text/plain",
            summary="Test",
            meta={},
            bytes=100,
            sha256="abc123",
            stored_at="2025-01-01T00:00:00Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
        )

        # Mock storage deletion (successful)
        mock_s3 = AsyncMock()
        mock_s3.delete_object = AsyncMock()
        mock_storage_ctx = AsyncMock()
        mock_storage_ctx.__aenter__.return_value = mock_s3
        mock_storage_ctx.__aexit__.return_value = None
        mock_artifact_store._s3_factory.return_value = mock_storage_ctx

        # Mock session provider WITH async delete method
        mock_session = AsyncMock()
        mock_session.delete = AsyncMock()  # Proper async delete method
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None
        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Test deletion
        result = await metadata_ops.delete("test123")

        # Should return True
        assert result is True

        # Verify both storage and session delete were called
        mock_s3.delete_object.assert_called_once_with(
            Bucket=mock_artifact_store.bucket, Key="test/path/test123"
        )
        mock_session.delete.assert_called_once_with("test123")

    @pytest.mark.asyncio
    async def test_delete_session_delete_method_failure(
        self, metadata_ops, mock_artifact_store
    ):
        """Test deletion when session delete method fails."""
        # Mock successful record retrieval
        metadata_ops._get_record = AsyncMock()
        metadata_ops._get_record.return_value = ArtifactMetadata(
            artifact_id="test123",
            key="test/path/test123",
            session_id="session123",
            sandbox_id="sandbox123",
            mime="text/plain",
            summary="Test",
            meta={},
            bytes=100,
            sha256="abc123",
            stored_at="2025-01-01T00:00:00Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
        )

        # Mock storage deletion (successful)
        mock_s3 = AsyncMock()
        mock_s3.delete_object = AsyncMock()
        mock_storage_ctx = AsyncMock()
        mock_storage_ctx.__aenter__.return_value = mock_s3
        mock_storage_ctx.__aexit__.return_value = None
        mock_artifact_store._s3_factory.return_value = mock_storage_ctx

        # Mock session provider with failing delete method
        mock_session = AsyncMock()
        mock_session.delete = AsyncMock()
        mock_session.delete.side_effect = Exception("Session delete failed")
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None
        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Test deletion
        result = await metadata_ops.delete("test123")

        # Should return False due to session delete failure
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_storage_error(self, metadata_ops, mock_artifact_store):
        """Test deletion with storage error."""
        # Mock record retrieval
        test_record = ArtifactMetadata(
            artifact_id="test123",
            key="test/key",
            session_id="session123",
            sandbox_id="sandbox123",
            mime="text/plain",
            summary="Test",
            meta={},
            bytes=100,
            sha256="abc123",
            stored_at="2025-01-01T00:00:00Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
        )
        metadata_ops._get_record = AsyncMock(return_value=test_record)

        # Mock storage deletion to fail
        mock_s3 = AsyncMock()
        mock_s3_ctx = AsyncMock()
        mock_s3_ctx.__aenter__.return_value = mock_s3
        mock_s3.delete_object.side_effect = Exception("Storage error")
        mock_artifact_store._s3_factory.return_value = mock_s3_ctx

        # Test deletion
        result = await metadata_ops.delete("test123")

        # Should return False on storage error
        assert result is False


class TestMetadataOperationsListing:
    """Test artifact listing operations."""

    @pytest.fixture
    def mock_artifact_store(self):
        """Create a mock ArtifactStore for listing tests."""
        store = Mock()
        store.bucket = "test-bucket"
        store._s3_factory = Mock()
        store._session_factory = Mock()
        store.get_canonical_prefix = Mock()
        store.parse_grid_key = Mock()
        return store

    @pytest.fixture
    def metadata_ops(self, mock_artifact_store):
        """Create MetadataOperations instance."""
        return MetadataOperations(mock_artifact_store)

    @pytest.mark.asyncio
    async def test_list_by_session_success(self, metadata_ops, mock_artifact_store):
        """Test successful session listing."""
        # Mock canonical prefix
        mock_artifact_store.get_canonical_prefix.return_value = (
            "grid/sandbox/session123/"
        )

        # Mock S3 listing
        mock_s3 = AsyncMock()
        mock_s3_ctx = AsyncMock()
        mock_s3_ctx.__aenter__.return_value = mock_s3
        mock_artifact_store._s3_factory.return_value = mock_s3_ctx

        # Mock S3 response
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "grid/sandbox/session123/artifact1"},
                {"Key": "grid/sandbox/session123/artifact2"},
                {"Key": "grid/sandbox/session123/artifact3"},
            ]
        }

        # Mock grid key parsing
        mock_artifact_store.parse_grid_key.side_effect = [
            GridKeyComponents(
                sandbox_id="sandbox",
                session_id="session123",
                artifact_id="artifact1",
            ),
            GridKeyComponents(
                sandbox_id="sandbox",
                session_id="session123",
                artifact_id="artifact2",
            ),
            GridKeyComponents(
                sandbox_id="sandbox",
                session_id="session123",
                artifact_id="artifact3",
            ),
        ]

        # Mock metadata records
        test_records = [
            ArtifactMetadata(
                artifact_id="artifact1",
                key="grid/sandbox/session123/artifact1",
                session_id="session123",
                sandbox_id="sandbox",
                mime="text/plain",
                summary="First artifact",
                meta={},
                bytes=100,
                sha256="abc123",
                stored_at="2025-01-01T00:00:00Z",
                ttl=900,
                storage_provider="memory",
                session_provider="memory",
            ),
            ArtifactMetadata(
                artifact_id="artifact2",
                key="grid/sandbox/session123/artifact2",
                session_id="session123",
                sandbox_id="sandbox",
                mime="text/plain",
                summary="Second artifact",
                meta={},
                bytes=100,
                sha256="def456",
                stored_at="2025-01-01T00:00:00Z",
                ttl=900,
                storage_provider="memory",
                session_provider="memory",
            ),
            ArtifactMetadata(
                artifact_id="artifact3",
                key="grid/sandbox/session123/artifact3",
                session_id="session123",
                sandbox_id="sandbox",
                mime="text/plain",
                summary="Third artifact",
                meta={},
                bytes=100,
                sha256="ghi789",
                stored_at="2025-01-01T00:00:00Z",
                ttl=900,
                storage_provider="memory",
                session_provider="memory",
            ),
        ]
        metadata_ops._get_record = AsyncMock()
        metadata_ops._get_record.side_effect = test_records

        # Test listing
        result = await metadata_ops.list_by_session("session123", limit=10)

        # Verify
        assert len(result) == 3
        assert result[0].artifact_id == "artifact1"
        assert result[1].artifact_id == "artifact2"
        assert result[2].artifact_id == "artifact3"

        mock_artifact_store.get_canonical_prefix.assert_called_once_with("session123")
        mock_s3.list_objects_v2.assert_called_once_with(
            Bucket="test-bucket", Prefix="grid/sandbox/session123/", MaxKeys=10
        )

    @pytest.mark.asyncio
    async def test_list_by_session_no_list_support(
        self, metadata_ops, mock_artifact_store
    ):
        """Test listing when storage doesn't support list_objects_v2."""
        # Mock S3 without list_objects_v2
        mock_s3 = Mock()  # Regular mock without list_objects_v2
        mock_s3_ctx = AsyncMock()
        mock_s3_ctx.__aenter__.return_value = mock_s3
        mock_artifact_store._s3_factory.return_value = mock_s3_ctx

        # Test listing
        result = await metadata_ops.list_by_session("session123")

        # Should return empty list
        assert result == []

    @pytest.mark.asyncio
    async def test_list_by_session_with_metadata_errors(
        self, metadata_ops, mock_artifact_store
    ):
        """Test listing with some metadata retrieval errors."""
        # Mock S3 setup
        mock_artifact_store.get_canonical_prefix.return_value = (
            "grid/sandbox/session123/"
        )
        mock_s3 = AsyncMock()
        mock_s3_ctx = AsyncMock()
        mock_s3_ctx.__aenter__.return_value = mock_s3
        mock_artifact_store._s3_factory.return_value = mock_s3_ctx

        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "grid/sandbox/session123/artifact1"},
                {"Key": "grid/sandbox/session123/artifact2"},
                {"Key": "grid/sandbox/session123/artifact3"},
            ]
        }

        mock_artifact_store.parse_grid_key.side_effect = [
            GridKeyComponents(
                sandbox_id="sandbox",
                session_id="session123",
                artifact_id="artifact1",
            ),
            GridKeyComponents(
                sandbox_id="sandbox",
                session_id="session123",
                artifact_id="artifact2",
            ),
            GridKeyComponents(
                sandbox_id="sandbox",
                session_id="session123",
                artifact_id="artifact3",
            ),
        ]

        # Mock metadata records with one failure
        def mock_get_record(artifact_id):
            if artifact_id == "artifact2":
                raise ArtifactNotFoundError("Metadata missing")
            return ArtifactMetadata(
                artifact_id=artifact_id,
                key=f"grid/sandbox/session123/{artifact_id}",
                session_id="session123",
                sandbox_id="sandbox",
                mime="text/plain",
                summary=f"Artifact {artifact_id}",
                meta={},
                bytes=100,
                sha256="abc123",
                stored_at="2025-01-01T00:00:00Z",
                ttl=900,
                storage_provider="memory",
                session_provider="memory",
            )

        metadata_ops._get_record = AsyncMock(side_effect=mock_get_record)

        # Test listing
        result = await metadata_ops.list_by_session("session123")

        # Should skip artifact2 and return only artifact1 and artifact3
        assert len(result) == 2
        assert result[0].artifact_id == "artifact1"
        assert result[1].artifact_id == "artifact3"

    @pytest.mark.asyncio
    async def test_list_by_session_error(self, metadata_ops, mock_artifact_store):
        """Test listing with general error."""
        # Mock error in get_canonical_prefix
        mock_artifact_store.get_canonical_prefix.side_effect = Exception(
            "General error"
        )

        # Test listing
        result = await metadata_ops.list_by_session("session123")

        # Should return empty list on error
        assert result == []

    @pytest.mark.asyncio
    async def test_list_by_prefix_no_prefix(self, metadata_ops):
        """Test prefix listing with no prefix (returns all)."""
        # Mock list_by_session
        test_artifacts = [
            {"artifact_id": "artifact1", "filename": "file1.txt"},
            {"artifact_id": "artifact2", "filename": "file2.txt"},
            {"artifact_id": "artifact3", "filename": "doc1.pdf"},
        ]
        metadata_ops.list_by_session = AsyncMock(return_value=test_artifacts)

        # Test with no prefix
        result = await metadata_ops.list_by_prefix("session123", prefix="", limit=5)

        # Should return all artifacts
        assert len(result) == 3
        metadata_ops.list_by_session.assert_called_once_with(
            "session123", 10
        )  # limit * 2

    @pytest.mark.asyncio
    async def test_list_by_prefix_with_filter(self, metadata_ops):
        """Test prefix listing with filename filtering."""
        # Mock list_by_session
        test_artifacts = [
            {"artifact_id": "artifact1", "filename": "doc1.txt"},
            {"artifact_id": "artifact2", "filename": "image1.png"},
            {"artifact_id": "artifact3", "filename": "doc2.pdf"},
            {"artifact_id": "artifact4", "filename": "doc3.docx"},
        ]
        metadata_ops.list_by_session = AsyncMock(return_value=test_artifacts)

        # Test with "doc" prefix
        result = await metadata_ops.list_by_prefix("session123", prefix="doc", limit=5)

        # Should return only files starting with "doc"
        assert len(result) == 3
        assert all(artifact["filename"].startswith("doc") for artifact in result)

    @pytest.mark.asyncio
    async def test_list_by_prefix_with_limit(self, metadata_ops):
        """Test prefix listing respects limit."""
        # Mock list_by_session
        test_artifacts = [
            {"artifact_id": f"artifact{i}", "filename": f"file{i}.txt"}
            for i in range(10)
        ]
        metadata_ops.list_by_session = AsyncMock(return_value=test_artifacts)

        # Test with limit
        result = await metadata_ops.list_by_prefix("session123", prefix="file", limit=3)

        # Should return only 3 results
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_list_by_prefix_missing_filename(self, metadata_ops):
        """Test prefix listing with missing filename fields."""
        # Mock list_by_session with some missing filenames
        test_artifacts = [
            {"artifact_id": "artifact1", "filename": "file1.txt"},
            {"artifact_id": "artifact2"},  # No filename
            {"artifact_id": "artifact3", "filename": "file3.txt"},
            {"artifact_id": "artifact4", "filename": ""},  # Empty filename
        ]
        metadata_ops.list_by_session = AsyncMock(return_value=test_artifacts)

        # Test with prefix
        result = await metadata_ops.list_by_prefix("session123", prefix="file", limit=5)

        # Should only return artifacts with matching filenames
        assert len(result) == 2
        assert result[0]["filename"] == "file1.txt"
        assert result[1]["filename"] == "file3.txt"

    @pytest.mark.asyncio
    async def test_list_by_prefix_error(self, metadata_ops):
        """Test prefix listing with error."""
        # Mock list_by_session to raise error
        metadata_ops.list_by_session = AsyncMock(side_effect=Exception("Listing error"))

        # Test listing
        result = await metadata_ops.list_by_prefix("session123", prefix="test")

        # Should return empty list on error
        assert result == []


class TestMetadataOperationsUpdate:
    """Test metadata update operations."""

    @pytest.fixture
    def mock_artifact_store(self):
        """Create a mock ArtifactStore."""
        store = Mock()
        store._session_factory = Mock()
        return store

    @pytest.fixture
    def metadata_ops(self, mock_artifact_store):
        """Create MetadataOperations instance."""
        return MetadataOperations(mock_artifact_store)

    @pytest.mark.asyncio
    async def test_update_metadata_summary(self, metadata_ops, mock_artifact_store):
        """Test updating metadata summary."""
        # Mock existing record
        existing_record = ArtifactMetadata(
            artifact_id="test123",
            key="test/key",
            session_id="session123",
            sandbox_id="sandbox123",
            mime="text/plain",
            summary="Old summary",
            meta={"key": "value"},
            bytes=100,
            sha256="abc123",
            stored_at="2025-01-01T00:00:00Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
        )
        metadata_ops._get_record = AsyncMock(return_value=existing_record)

        # Mock session
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Test update
        result = await metadata_ops.update_metadata("test123", summary="New summary")

        # Verify
        assert result.summary == "New summary"
        assert result.meta == {"key": "value"}  # Unchanged
        mock_session.setex.assert_called_once()

        # Check the stored data
        call_args = mock_session.setex.call_args
        assert call_args[0][0] == "test123"  # artifact_id
        assert call_args[0][1] == 900  # ttl
        stored_data = json.loads(call_args[0][2])
        assert stored_data["summary"] == "New summary"

    @pytest.mark.asyncio
    async def test_update_metadata_merge_meta(self, metadata_ops, mock_artifact_store):
        """Test updating metadata with merge."""
        # Mock existing record
        existing_record = ArtifactMetadata(
            artifact_id="test123",
            key="test/key",
            session_id="session123",
            sandbox_id="sandbox123",
            mime="text/plain",
            summary="Test",
            meta={"existing_key": "existing_value", "keep": "this"},
            bytes=100,
            sha256="abc123",
            stored_at="2025-01-01T00:00:00Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
        )
        metadata_ops._get_record = AsyncMock(return_value=existing_record)

        # Mock session
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Test update with merge
        result = await metadata_ops.update_metadata(
            "test123",
            meta={"new_key": "new_value", "existing_key": "updated_value"},
            merge=True,
        )

        # Verify merge behavior
        expected_meta = {
            "existing_key": "updated_value",  # Updated
            "keep": "this",  # Kept
            "new_key": "new_value",  # Added
        }
        assert result.meta == expected_meta

    @pytest.mark.asyncio
    async def test_update_metadata_replace_meta(
        self, metadata_ops, mock_artifact_store
    ):
        """Test updating metadata without merge."""
        # Mock existing record
        existing_record = ArtifactMetadata(
            artifact_id="test123",
            key="test/key",
            session_id="session123",
            sandbox_id="sandbox123",
            mime="text/plain",
            summary="Test",
            meta={"existing_key": "existing_value", "keep": "this"},
            bytes=100,
            sha256="abc123",
            stored_at="2025-01-01T00:00:00Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
        )
        metadata_ops._get_record = AsyncMock(return_value=existing_record)

        # Mock session
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Test update without merge
        result = await metadata_ops.update_metadata(
            "test123", meta={"new_key": "new_value"}, merge=False
        )

        # Verify replace behavior
        assert result.meta == {"new_key": "new_value"}

    @pytest.mark.asyncio
    async def test_update_metadata_kwargs(self, metadata_ops, mock_artifact_store):
        """Test updating metadata with additional kwargs."""
        # Mock existing record
        existing_record = ArtifactMetadata(
            artifact_id="test123",
            key="test/key",
            session_id="session123",
            sandbox_id="sandbox123",
            mime="text/plain",
            summary="Test",
            meta={},
            bytes=100,
            sha256="abc123",
            stored_at="2025-01-01T00:00:00Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
        )
        metadata_ops._get_record = AsyncMock(return_value=existing_record)

        # Mock session
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Test update with kwargs
        result = await metadata_ops.update_metadata(
            "test123", mime="application/json", custom_field="custom_value"
        )

        # Verify kwargs were applied
        assert result.mime == "application/json"
        assert result.custom_field == "custom_value"

    @pytest.mark.asyncio
    async def test_update_metadata_error(self, metadata_ops, mock_artifact_store):
        """Test update metadata with error."""
        # Mock _get_record to fail
        metadata_ops._get_record = AsyncMock()
        metadata_ops._get_record.side_effect = ArtifactNotFoundError("Not found")

        # Test update
        with pytest.raises(ProviderError, match="Metadata update failed"):
            await metadata_ops.update_metadata("test123", summary="New summary")

    @pytest.mark.asyncio
    async def test_extend_ttl(self, metadata_ops, mock_artifact_store):
        """Test extending TTL."""
        # Mock existing record
        existing_record = ArtifactMetadata(
            artifact_id="test123",
            key="test/key",
            session_id="session123",
            sandbox_id="sandbox123",
            mime="text/plain",
            summary="Test",
            meta={},
            bytes=100,
            sha256="abc123",
            stored_at="2025-01-01T00:00:00Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
        )
        metadata_ops._get_record = AsyncMock(return_value=existing_record)

        # Mock session
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Test TTL extension
        result = await metadata_ops.extend_ttl("test123", 600)

        # Verify
        assert result.ttl == 1500  # 900 + 600

        # Check storage call
        mock_session.setex.assert_called_once()
        call_args = mock_session.setex.call_args
        assert call_args[0][1] == 1500  # new TTL used for setex

    @pytest.mark.asyncio
    async def test_extend_ttl_default_ttl(self, metadata_ops, mock_artifact_store):
        """Test extending TTL when using default TTL."""
        # Mock existing record
        existing_record = ArtifactMetadata(
            artifact_id="test123",
            key="test/key",
            session_id="session123",
            sandbox_id="sandbox123",
            mime="text/plain",
            summary="Test",
            meta={},
            bytes=100,
            sha256="abc123",
            stored_at="2025-01-01T00:00:00Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
        )
        metadata_ops._get_record = AsyncMock(return_value=existing_record)

        # Mock session
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_artifact_store._session_factory.return_value = mock_session_ctx

        # Test TTL extension
        result = await metadata_ops.extend_ttl("test123", 300)

        # Verify default TTL (900) + extension
        assert result.ttl == 1200  # 900 + 300

    @pytest.mark.asyncio
    async def test_extend_ttl_error(self, metadata_ops, mock_artifact_store):
        """Test TTL extension with error."""
        # Mock _get_record to fail
        metadata_ops._get_record = AsyncMock()
        metadata_ops._get_record.side_effect = Exception("Database error")

        # Test TTL extension
        with pytest.raises(ProviderError, match="TTL extension failed"):
            await metadata_ops.extend_ttl("test123", 600)


class TestMetadataOperationsEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def metadata_ops(self):
        """Create MetadataOperations with basic mock."""
        store = Mock()
        return MetadataOperations(store)

    @pytest.mark.asyncio
    async def test_large_metadata_record(self, metadata_ops):
        """Test handling of very large metadata records."""
        # Create a large metadata record
        large_meta = {f"key_{i}": f"value_{i}" * 1000 for i in range(100)}
        large_record = ArtifactMetadata(
            artifact_id="large_test",
            key="test/key",
            session_id="session123",
            sandbox_id="sandbox123",
            mime="application/octet-stream",
            summary="Large metadata test",
            meta=large_meta,
            bytes=1024000,
            sha256="abc123",
            stored_at="2025-01-01T00:00:00Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
        )

        # Mock session to return large record
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        metadata_ops.artifact_store._session_factory.return_value = mock_session_ctx
        mock_session.get.return_value = large_record.model_dump_json()

        # Test retrieval
        result = await metadata_ops.get_metadata("large_test")

        # Should handle large records
        assert result.artifact_id == "large_test"
        assert len(result.meta) == 100

    @pytest.mark.asyncio
    async def test_unicode_metadata(self, metadata_ops):
        """Test handling of Unicode in metadata."""
        unicode_record = ArtifactMetadata(
            artifact_id="unicode_test_🎉",
            key="test/key",
            session_id="session123",
            sandbox_id="sandbox123",
            mime="text/plain",
            summary="Unicode test: 世界 🌍 café résumé",
            meta={
                "description": "Contains émojis 🚀 and spéciâl chàractérs",
                "tags": ["tëst", "üñïcodé", "🏷️"],
                "chinese": "中文测试",
            },
            bytes=100,
            sha256="abc123",
            stored_at="2025-01-01T00:00:00Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
        )

        # Mock session
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        metadata_ops.artifact_store._session_factory.return_value = mock_session_ctx
        mock_session.get.return_value = unicode_record.model_dump_json()

        # Test retrieval
        result = await metadata_ops.get_metadata("unicode_test_🎉")

        # Should handle Unicode correctly
        assert result.artifact_id == "unicode_test_🎉"
        assert "🚀" in result.meta["description"]
        assert "🏷️" in result.meta["tags"]
        assert result.meta["chinese"] == "中文测试"

    @pytest.mark.asyncio
    async def test_empty_metadata_values(self, metadata_ops):
        """Test handling of empty/null metadata values."""
        empty_record = ArtifactMetadata(
            artifact_id="empty_test",
            key="test/key",
            session_id="session123",
            sandbox_id="sandbox123",
            mime="application/octet-stream",
            summary="",
            meta={},
            filename=None,
            bytes=0,
            sha256=None,
            stored_at="2025-01-01T00:00:00Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
            tags=[],  # Extra field allowed by extra="allow"
        )

        # Mock session
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        metadata_ops.artifact_store._session_factory.return_value = mock_session_ctx
        mock_session.get.return_value = empty_record.model_dump_json()

        # Test retrieval
        result = await metadata_ops.get_metadata("empty_test")

        # Should handle empty values
        assert result.artifact_id == "empty_test"
        assert result.summary == ""
        assert result.meta == {}
        assert result.filename is None
        assert result.tags == []
        assert result.bytes == 0

    @pytest.mark.asyncio
    async def test_concurrent_metadata_operations(self, metadata_ops):
        """Test concurrent metadata operations."""
        # Mock session for concurrent access
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        metadata_ops.artifact_store._session_factory.return_value = mock_session_ctx

        # Mock different records for different artifact IDs
        def mock_get_side_effect(artifact_id):
            return ArtifactMetadata(
                artifact_id=artifact_id,
                key=f"test/key/{artifact_id}",
                session_id="session123",
                sandbox_id="sandbox123",
                mime="text/plain",
                summary=f"Concurrent test {artifact_id}",
                meta={"index": artifact_id[-1]},
                bytes=100,
                sha256="abc123",
                stored_at="2025-01-01T00:00:00Z",
                ttl=900,
                storage_provider="memory",
                session_provider="memory",
            ).model_dump_json()

        mock_session.get.side_effect = mock_get_side_effect

        # Test concurrent retrieval
        tasks = [metadata_ops.get_metadata(f"concurrent_test_{i}") for i in range(5)]
        results = await asyncio.gather(*tasks)

        # Verify all completed successfully
        assert len(results) == 5
        for i, result in enumerate(results):
            assert result.artifact_id == f"concurrent_test_{i}"
            assert result.meta["index"] == str(i)


if __name__ == "__main__":
    # Run the tests
    pytest.main(
        [
            __file__,
            "-v",
            "--tb=short",
            "--durations=10",
        ]
    )

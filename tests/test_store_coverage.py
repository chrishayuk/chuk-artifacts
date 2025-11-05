"""
Additional tests for ArtifactStore to increase coverage to 90%+.
"""

import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock
from chuk_artifacts.store import ArtifactStore
from chuk_artifacts.config import configure_memory


class TestStoreUpdateFileValidation:
    """Test update_file validation."""

    def setup_method(self):
        """Ensure memory provider is configured before each test."""
        os.environ.pop("ARTIFACT_PROVIDER", None)
        os.environ.pop("SESSION_PROVIDER", None)
        configure_memory()

    @pytest.mark.asyncio
    async def test_update_file_no_parameters_raises_error(self):
        """Test that update_file raises ValueError when no parameters provided."""
        store = ArtifactStore(storage_provider="memory", session_provider="memory")

        try:
            session_id = await store.create_session(user_id="test_user")

            # Store an initial file
            artifact_id = await store.write_file(
                content="initial content", filename="test.txt", session_id=session_id
            )

            # Try to update without providing any parameters
            with pytest.raises(
                ValueError, match="At least one update parameter must be provided"
            ):
                await store.update_file(artifact_id)
        finally:
            await store.close()


class TestStorePresignedOperations:
    """Test presigned URL operations to cover delegation methods."""

    def setup_method(self):
        """Ensure memory provider is configured before each test."""
        os.environ.pop("ARTIFACT_PROVIDER", None)
        os.environ.pop("SESSION_PROVIDER", None)
        configure_memory()

    @pytest.mark.asyncio
    async def test_presign_medium(self):
        """Test presign_medium method."""
        store = ArtifactStore(storage_provider="memory", session_provider="memory")

        try:
            session_id = await store.create_session(user_id="test_user")

            # Store an artifact
            artifact_id = await store.store(
                data=b"test data",
                mime="text/plain",
                summary="Test",
                session_id=session_id,
            )

            # Generate medium presigned URL
            url = await store.presign_medium(artifact_id)
            assert url.startswith("memory://")
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_presign_long(self):
        """Test presign_long method."""
        store = ArtifactStore(storage_provider="memory", session_provider="memory")

        try:
            session_id = await store.create_session(user_id="test_user")

            # Store an artifact
            artifact_id = await store.store(
                data=b"test data",
                mime="text/plain",
                summary="Test",
                session_id=session_id,
            )

            # Generate long presigned URL
            url = await store.presign_long(artifact_id)
            assert url.startswith("memory://")
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_register_uploaded_artifact(self):
        """Test register_uploaded_artifact method."""
        store = ArtifactStore(storage_provider="memory", session_provider="memory")

        try:
            session_id = await store.create_session(user_id="test_user")

            # First store an artifact (simulating an upload)
            artifact_id = await store.store(
                data=b"uploaded data",
                mime="application/octet-stream",
                summary="Uploaded",
                session_id=session_id,
            )

            # Register metadata for it
            result = await store.register_uploaded_artifact(
                artifact_id,
                mime="text/plain",
                summary="Registered after upload",
                session_id=session_id,
            )
            assert result is True
        finally:
            await store.close()

    # Note: presign_upload_and_register is not suitable for testing with memory provider
    # as it tries to create a presigned URL for an object that doesn't exist yet,
    # which the memory provider doesn't support. This is covered by integration tests.


class TestStoreSandboxInfo:
    """Test get_sandbox_info with error handling."""

    def setup_method(self):
        """Ensure memory provider is configured before each test."""
        os.environ.pop("ARTIFACT_PROVIDER", None)
        os.environ.pop("SESSION_PROVIDER", None)
        configure_memory()

    @pytest.mark.asyncio
    async def test_get_sandbox_info_basic(self):
        """Test basic get_sandbox_info functionality."""
        store = ArtifactStore(storage_provider="memory", session_provider="memory")

        try:
            info = await store.get_sandbox_info()

            assert "sandbox_id" in info
            assert "bucket" in info
            assert "storage_provider" in info
            assert "session_provider" in info
            assert "session_ttl_hours" in info
            assert "grid_prefix_pattern" in info
            assert "created_at" in info
            assert "closed" in info
            assert info["closed"] is False
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_get_sandbox_info_with_session_stats_error(self):
        """Test get_sandbox_info when session stats raise exception."""
        store = ArtifactStore(storage_provider="memory", session_provider="memory")

        try:
            # Mock session_manager.get_cache_stats to raise exception
            original_method = store._session_manager.get_cache_stats
            store._session_manager.get_cache_stats = MagicMock(
                side_effect=Exception("Stats error")
            )

            # Should still return info, just without session stats
            info = await store.get_sandbox_info()
            assert "sandbox_id" in info
            assert "session_stats" in info
            assert info["session_stats"] == {}  # Empty dict due to exception

            # Restore
            store._session_manager.get_cache_stats = original_method
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_get_sandbox_info_with_storage_stats_error(self):
        """Test get_sandbox_info when storage stats raise exception."""
        store = ArtifactStore(storage_provider="memory", session_provider="memory")

        try:
            # Mock _admin.get_stats to raise exception
            store._admin.get_stats = AsyncMock(
                side_effect=Exception("Storage stats error")
            )

            # Should still return info, just without storage stats
            info = await store.get_sandbox_info()
            assert "sandbox_id" in info
            assert "storage_stats" in info
            assert info["storage_stats"] == {}  # Empty dict due to exception
        finally:
            await store.close()


class TestStoreDefaultFactories:
    """Test that default factory functions are called."""

    @pytest.mark.asyncio
    async def test_default_storage_factory_used(self):
        """Test that default storage factory is used when provider not specified."""
        # Don't specify storage_provider, should use default
        with patch.dict(
            os.environ, {"ARTIFACT_PROVIDER": "memory", "SESSION_PROVIDER": "memory"}
        ):
            store = ArtifactStore(session_provider="memory")

            try:
                # Verify store works
                session_id = await store.create_session(user_id="test")
                artifact_id = await store.store(
                    data=b"test",
                    mime="text/plain",
                    summary="Test",
                    session_id=session_id,
                )
                assert artifact_id is not None
            finally:
                await store.close()

    @pytest.mark.asyncio
    async def test_default_session_factory_used(self):
        """Test that default session factory is used when provider not specified."""
        # Don't specify session_provider, should use default
        with patch.dict(
            os.environ, {"SESSION_PROVIDER": "memory", "ARTIFACT_PROVIDER": "memory"}
        ):
            store = ArtifactStore(storage_provider="memory")

            try:
                # Verify session creation works
                session_id = await store.create_session(user_id="test")
                assert session_id is not None

                # Verify session validation works
                is_valid = await store.validate_session(session_id)
                assert is_valid is True
            finally:
                await store.close()


class TestStoreEnvironmentDetection:
    """Test environment-based provider detection."""

    @pytest.mark.asyncio
    async def test_storage_provider_from_env(self):
        """Test that storage provider is detected from environment."""
        with patch.dict(
            os.environ, {"ARTIFACT_PROVIDER": "memory", "SESSION_PROVIDER": "memory"}
        ):
            # Don't pass storage_provider parameter
            store = ArtifactStore()

            try:
                assert store._storage_provider_name == "memory"

                # Verify it works
                session_id = await store.create_session(user_id="test")
                artifact_id = await store.store(
                    data=b"test",
                    mime="text/plain",
                    summary="Test",
                    session_id=session_id,
                )
                assert artifact_id is not None
            finally:
                await store.close()

    @pytest.mark.asyncio
    async def test_session_provider_from_env(self):
        """Test that session provider is detected from environment."""
        with patch.dict(
            os.environ, {"ARTIFACT_PROVIDER": "memory", "SESSION_PROVIDER": "memory"}
        ):
            # Don't pass session_provider parameter
            store = ArtifactStore()

            try:
                assert store._session_provider_name == "memory"

                # Verify session operations work
                session_id = await store.create_session(user_id="test")
                is_valid = await store.validate_session(session_id)
                assert is_valid is True
            finally:
                await store.close()


class TestStoreEdgeCaseCoverage:
    """Test edge cases to maximize coverage."""

    def setup_method(self):
        """Ensure memory provider is configured before each test."""
        os.environ.pop("ARTIFACT_PROVIDER", None)
        os.environ.pop("SESSION_PROVIDER", None)
        configure_memory()

    @pytest.mark.asyncio
    async def test_store_with_all_optional_params(self):
        """Test store method with all optional parameters to cover all code paths."""
        store = ArtifactStore(storage_provider="memory", session_provider="memory")

        try:
            session_id = await store.create_session(user_id="test_user")

            # Store with all parameters
            artifact_id = await store.store(
                data=b"test data",
                mime="application/json",
                summary="Test artifact",
                filename="test.json",
                session_id=session_id,
                user_id="explicit_user",
                meta={"key": "value"},
            )

            assert artifact_id is not None

            # Verify metadata
            metadata = await store.metadata(artifact_id)
            assert metadata.mime == "application/json"
            assert metadata.filename == "test.json"
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_update_file_with_single_parameter(self):
        """Test update_file with just one parameter to ensure it doesn't raise ValueError."""
        store = ArtifactStore(storage_provider="memory", session_provider="memory")

        try:
            session_id = await store.create_session(user_id="test_user")

            # Store initial file
            artifact_id = await store.write_file(
                content="initial", filename="test.txt", session_id=session_id
            )

            # Update with just data
            await store.update_file(artifact_id, data=b"updated")

            # Verify
            content = await store.read_file(artifact_id, as_text=True)
            assert content == "updated"
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_update_file_with_mime_only(self):
        """Test update_file with just mime parameter."""
        store = ArtifactStore(storage_provider="memory", session_provider="memory")

        try:
            session_id = await store.create_session(user_id="test_user")

            # Store initial file
            artifact_id = await store.write_file(
                content="test", filename="test.txt", session_id=session_id
            )

            # Update with just mime
            await store.update_file(artifact_id, mime="application/json")

            # Verify
            metadata = await store.metadata(artifact_id)
            assert metadata.mime == "application/json"
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_update_file_with_summary_only(self):
        """Test update_file with just summary parameter."""
        store = ArtifactStore(storage_provider="memory", session_provider="memory")

        try:
            session_id = await store.create_session(user_id="test_user")

            # Store initial file
            artifact_id = await store.write_file(
                content="test", filename="test.txt", session_id=session_id
            )

            # Update with just summary
            await store.update_file(artifact_id, summary="Updated summary")

            # Verify
            metadata = await store.metadata(artifact_id)
            assert metadata.summary == "Updated summary"
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_update_file_with_meta_only(self):
        """Test update_file with just meta parameter."""
        store = ArtifactStore(storage_provider="memory", session_provider="memory")

        try:
            session_id = await store.create_session(user_id="test_user")

            # Store initial file
            artifact_id = await store.write_file(
                content="test", filename="test.txt", session_id=session_id
            )

            # Update with just meta
            await store.update_file(artifact_id, meta={"updated": "true"})

            # Verify
            metadata = await store.metadata(artifact_id)
            assert "updated" in metadata.meta
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_update_file_with_filename_only(self):
        """Test update_file with just filename parameter."""
        store = ArtifactStore(storage_provider="memory", session_provider="memory")

        try:
            session_id = await store.create_session(user_id="test_user")

            # Store initial file
            artifact_id = await store.write_file(
                content="test", filename="test.txt", session_id=session_id
            )

            # Update with just filename
            await store.update_file(artifact_id, filename="updated.txt")

            # Verify
            metadata = await store.metadata(artifact_id)
            assert metadata.filename == "updated.txt"
        finally:
            await store.close()

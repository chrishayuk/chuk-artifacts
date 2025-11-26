"""
Comprehensive tests for namespace.py to achieve >90% coverage.
"""

import pytest

from chuk_artifacts import ArtifactStore, NamespaceType, StorageScope
from chuk_artifacts.namespace import NamespaceOperations
from chuk_artifacts.exceptions import SessionError


class TestNamespaceCreation:
    """Test namespace creation with various configurations."""

    @pytest.mark.asyncio
    async def test_create_blob_namespace_session_scope(self):
        """Test creating a BLOB namespace with SESSION scope."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB,
            scope=StorageScope.SESSION,
            user_id="test-user",
        )

        assert info.type == NamespaceType.BLOB
        assert info.scope == StorageScope.SESSION
        assert info.namespace_id.startswith("ns-")
        assert info.session_id is not None
        assert info.user_id == "test-user"
        assert "sess-" in info.grid_path

    @pytest.mark.asyncio
    async def test_create_workspace_namespace_user_scope(self):
        """Test creating a WORKSPACE namespace with USER scope."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.WORKSPACE,
            name="test-workspace",
            scope=StorageScope.USER,
            user_id="alice",
        )

        assert info.type == NamespaceType.WORKSPACE
        assert info.scope == StorageScope.USER
        assert info.name == "test-workspace"
        assert info.user_id == "alice"
        assert "user-alice" in info.grid_path

    @pytest.mark.asyncio
    async def test_create_namespace_sandbox_scope(self):
        """Test creating a namespace with SANDBOX scope."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB,
            scope=StorageScope.SANDBOX,
        )

        assert info.scope == StorageScope.SANDBOX
        assert "shared" in info.grid_path
        # SANDBOX scope still gets a session_id for tracking, but uses 'shared' in grid path
        assert info.user_id is None

    @pytest.mark.asyncio
    async def test_create_namespace_with_custom_ttl(self):
        """Test creating namespace with custom TTL."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB,
            scope=StorageScope.SESSION,
            user_id="test-user",
            ttl_hours=2,
        )

        assert info.ttl_seconds == 7200
        assert info.expires_at is not None

    @pytest.mark.asyncio
    async def test_create_namespace_with_metadata(self):
        """Test creating namespace with custom metadata."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        metadata = {"project": "test", "version": "1.0"}
        info = await namespace_ops.create_namespace(
            type=NamespaceType.WORKSPACE,
            scope=StorageScope.SESSION,
            user_id="test-user",
            metadata=metadata,
        )

        assert info.metadata == metadata

    @pytest.mark.asyncio
    async def test_create_namespace_user_scope_without_user_id_fails(self):
        """Test that USER scope requires user_id."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        with pytest.raises(ValueError, match="user_id required for USER scope"):
            await namespace_ops.create_namespace(
                type=NamespaceType.BLOB, scope=StorageScope.USER
            )

    @pytest.mark.asyncio
    async def test_create_namespace_with_existing_session(self):
        """Test creating namespace with existing session."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        # Create first namespace to get session
        info1 = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB,
            scope=StorageScope.SESSION,
            user_id="test-user",
        )

        # Create second namespace with same session
        info2 = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB,
            scope=StorageScope.SESSION,
            session_id=info1.session_id,
            user_id="test-user",
        )

        assert info2.session_id == info1.session_id

    @pytest.mark.asyncio
    async def test_create_namespace_with_invalid_session_fails(self):
        """Test that invalid session ID fails."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        with pytest.raises(SessionError, match="Invalid session"):
            await namespace_ops.create_namespace(
                type=NamespaceType.BLOB,
                scope=StorageScope.SESSION,
                session_id="invalid-session-id",
                user_id="test-user",
            )

    @pytest.mark.asyncio
    async def test_create_namespace_with_filesystem_provider(self):
        """Test creating namespace with filesystem provider."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.WORKSPACE,
            scope=StorageScope.SESSION,
            user_id="test-user",
            provider_type="vfs-filesystem",
        )

        assert info.provider_type == "vfs-filesystem"

    @pytest.mark.asyncio
    async def test_create_namespace_with_sqlite_provider(self):
        """Test creating namespace with sqlite provider."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB,
            scope=StorageScope.SESSION,
            user_id="test-user",
            provider_type="vfs-sqlite",
        )

        assert info.provider_type == "vfs-sqlite"


class TestNamespaceReadWrite:
    """Test reading and writing to namespaces."""

    @pytest.mark.asyncio
    async def test_write_and_read_blob(self):
        """Test writing and reading blob data."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB,
            scope=StorageScope.SESSION,
            user_id="test-user",
        )

        # Write data
        await namespace_ops.write_namespace(info.namespace_id, data=b"test data")

        # Read data
        data = await namespace_ops.read_namespace(info.namespace_id)
        assert data == b"test data"

    @pytest.mark.asyncio
    async def test_write_blob_with_mime_type(self):
        """Test writing blob with MIME type metadata."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB,
            scope=StorageScope.SESSION,
            user_id="test-user",
        )

        # Write with MIME type
        await namespace_ops.write_namespace(
            info.namespace_id, data=b"test data", mime="text/plain"
        )

        # Read back
        data = await namespace_ops.read_namespace(info.namespace_id)
        assert data == b"test data"

    @pytest.mark.asyncio
    async def test_write_and_read_workspace_file(self):
        """Test writing and reading workspace files."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.WORKSPACE,
            scope=StorageScope.SESSION,
            user_id="test-user",
        )

        # Write file
        await namespace_ops.write_namespace(
            info.namespace_id, path="/test.txt", data=b"file content"
        )

        # Read file
        data = await namespace_ops.read_namespace(info.namespace_id, path="/test.txt")
        assert data == b"file content"

    @pytest.mark.asyncio
    async def test_write_workspace_without_path_fails(self):
        """Test that writing to workspace without path fails."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.WORKSPACE,
            scope=StorageScope.SESSION,
            user_id="test-user",
        )

        with pytest.raises(ValueError, match="path required for workspace"):
            await namespace_ops.write_namespace(info.namespace_id, data=b"data")

    @pytest.mark.asyncio
    async def test_read_workspace_without_path_fails(self):
        """Test that reading workspace without path fails."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.WORKSPACE,
            scope=StorageScope.SESSION,
            user_id="test-user",
        )

        with pytest.raises(ValueError, match="path required for workspace"):
            await namespace_ops.read_namespace(info.namespace_id)


class TestNamespaceVFS:
    """Test VFS access to namespaces."""

    @pytest.mark.asyncio
    async def test_get_namespace_vfs(self):
        """Test getting VFS for a namespace."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.WORKSPACE,
            scope=StorageScope.SESSION,
            user_id="test-user",
        )

        vfs = namespace_ops.get_namespace_vfs(info.namespace_id)
        assert vfs is not None

        # Test VFS operations
        await vfs.write_file("/test.txt", b"vfs test")
        data = await vfs.read_file("/test.txt")
        assert data == b"vfs test"

    @pytest.mark.asyncio
    async def test_get_vfs_for_nonexistent_namespace_fails(self):
        """Test that getting VFS for non-existent namespace fails."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        with pytest.raises(ValueError, match="Namespace not found"):
            namespace_ops.get_namespace_vfs("nonexistent-id")


class TestNamespaceList:
    """Test listing namespaces."""

    @pytest.mark.asyncio
    async def test_list_namespaces_by_session(self):
        """Test listing namespaces by session."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        # Create namespaces
        info1 = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB,
            scope=StorageScope.SESSION,
            user_id="test-user",
        )

        _info2 = await namespace_ops.create_namespace(
            type=NamespaceType.WORKSPACE,
            scope=StorageScope.SESSION,
            session_id=info1.session_id,
            user_id="test-user",
        )

        # List by session
        namespaces = namespace_ops.list_namespaces(session_id=info1.session_id)
        assert len(namespaces) == 2

    @pytest.mark.asyncio
    async def test_list_namespaces_by_user(self):
        """Test listing namespaces by user."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        # Create user namespaces
        await namespace_ops.create_namespace(
            type=NamespaceType.BLOB, scope=StorageScope.USER, user_id="alice"
        )

        await namespace_ops.create_namespace(
            type=NamespaceType.WORKSPACE, scope=StorageScope.USER, user_id="alice"
        )

        await namespace_ops.create_namespace(
            type=NamespaceType.BLOB, scope=StorageScope.USER, user_id="bob"
        )

        # List alice's namespaces
        alice_namespaces = namespace_ops.list_namespaces(user_id="alice")
        assert len(alice_namespaces) == 2

    @pytest.mark.asyncio
    async def test_list_namespaces_by_type(self):
        """Test filtering namespaces by type."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        # Create mixed types in USER scope (so they're all listable)
        await namespace_ops.create_namespace(
            type=NamespaceType.BLOB,
            scope=StorageScope.USER,
            user_id="test-user",
        )

        await namespace_ops.create_namespace(
            type=NamespaceType.WORKSPACE,
            scope=StorageScope.USER,
            user_id="test-user",
        )

        # List blobs only for this user
        blobs = namespace_ops.list_namespaces(
            user_id="test-user", type=NamespaceType.BLOB
        )
        assert len(blobs) >= 1
        assert all(ns.type == NamespaceType.BLOB for ns in blobs)


class TestNamespaceCheckpoints:
    """Test namespace checkpoint operations."""

    @pytest.mark.asyncio
    async def test_checkpoint_namespace(self):
        """Test creating a checkpoint."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.WORKSPACE,
            scope=StorageScope.SESSION,
            user_id="test-user",
        )

        # Write some data
        await namespace_ops.write_namespace(
            info.namespace_id, path="/test.txt", data=b"original"
        )

        # Create checkpoint
        cp = await namespace_ops.checkpoint_namespace(
            info.namespace_id, name="v1", description="First version"
        )

        assert cp.checkpoint_id == "v1"  # VFS uses name as checkpoint_id
        assert cp.name == "v1"
        assert cp.description == "First version"

    @pytest.mark.asyncio
    async def test_list_checkpoints(self):
        """Test listing checkpoints."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.WORKSPACE,
            scope=StorageScope.SESSION,
            user_id="test-user",
        )

        # Create multiple checkpoints
        await namespace_ops.checkpoint_namespace(info.namespace_id, name="v1")
        await namespace_ops.checkpoint_namespace(info.namespace_id, name="v2")

        # List checkpoints
        checkpoints = await namespace_ops.list_checkpoints(info.namespace_id)
        assert len(checkpoints) == 2

    @pytest.mark.asyncio
    async def test_restore_namespace(self):
        """Test restoring from checkpoint."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.WORKSPACE,
            scope=StorageScope.SESSION,
            user_id="test-user",
        )

        # Write original data
        await namespace_ops.write_namespace(
            info.namespace_id, path="/test.txt", data=b"original"
        )

        # Create checkpoint
        cp = await namespace_ops.checkpoint_namespace(info.namespace_id, name="v1")

        # Modify data
        await namespace_ops.write_namespace(
            info.namespace_id, path="/test.txt", data=b"modified"
        )

        # Restore checkpoint
        await namespace_ops.restore_namespace(info.namespace_id, cp.checkpoint_id)

        # Verify restoration
        data = await namespace_ops.read_namespace(info.namespace_id, path="/test.txt")
        assert data == b"original"

    @pytest.mark.asyncio
    async def test_delete_checkpoint(self):
        """Test deleting a checkpoint."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.WORKSPACE,
            scope=StorageScope.SESSION,
            user_id="test-user",
        )

        # Create checkpoint
        cp = await namespace_ops.checkpoint_namespace(info.namespace_id, name="v1")

        # Delete checkpoint
        await namespace_ops.delete_checkpoint(info.namespace_id, cp.checkpoint_id)

        # Verify deletion
        checkpoints = await namespace_ops.list_checkpoints(info.namespace_id)
        assert len(checkpoints) == 0


class TestNamespaceDestroy:
    """Test destroying namespaces."""

    @pytest.mark.asyncio
    async def test_destroy_namespace(self):
        """Test destroying a namespace."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB,
            scope=StorageScope.SESSION,
            user_id="test-user",
        )

        # Destroy namespace
        await namespace_ops.destroy_namespace(info.namespace_id)

        # Verify it's gone
        with pytest.raises(ValueError, match="Namespace not found"):
            namespace_ops.get_namespace_vfs(info.namespace_id)

    @pytest.mark.asyncio
    async def test_destroy_nonexistent_namespace_fails(self):
        """Test that destroying non-existent namespace fails."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        with pytest.raises(ValueError, match="Namespace not found"):
            await namespace_ops.destroy_namespace("nonexistent-id")


class TestNamespaceGetInfo:
    """Test getting namespace info."""

    @pytest.mark.asyncio
    async def test_get_namespace_info(self):
        """Test getting namespace info."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        created_info = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB,
            scope=StorageScope.SESSION,
            user_id="test-user",
        )

        # Get info
        info = namespace_ops.get_namespace_info(created_info.namespace_id)

        assert info.namespace_id == created_info.namespace_id
        assert info.type == created_info.type
        assert info.scope == created_info.scope

    @pytest.mark.asyncio
    async def test_get_info_for_nonexistent_namespace_fails(self):
        """Test that getting info for non-existent namespace fails."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        with pytest.raises(ValueError, match="Namespace not found"):
            namespace_ops.get_namespace_info("nonexistent-id")


class TestNamespaceProviderConfig:
    """Test namespace creation with provider configuration."""

    @pytest.mark.asyncio
    async def test_create_filesystem_with_custom_root(self):
        """Test creating filesystem namespace with custom root path."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        config = {"root_path": "/tmp/custom-test-path"}
        info = await namespace_ops.create_namespace(
            type=NamespaceType.WORKSPACE,
            scope=StorageScope.SESSION,
            user_id="test-user",
            provider_type="vfs-filesystem",
            provider_config=config,
        )

        assert info.provider_type == "vfs-filesystem"

    @pytest.mark.asyncio
    async def test_create_sqlite_with_custom_db_path(self):
        """Test creating SQLite namespace with custom DB path."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        config = {"db_path": "/tmp/custom-test.db"}
        info = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB,
            scope=StorageScope.SESSION,
            user_id="test-user",
            provider_type="vfs-sqlite",
            provider_config=config,
        )

        assert info.provider_type == "vfs-sqlite"


class TestNamespaceExpiration:
    """Test namespace expiration handling."""

    @pytest.mark.asyncio
    async def test_session_namespace_has_expiration(self):
        """Test that session namespaces have expiration."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB,
            scope=StorageScope.SESSION,
            user_id="test-user",
            ttl_hours=1,
        )

        assert info.expires_at is not None
        assert info.ttl_seconds == 3600

    @pytest.mark.asyncio
    async def test_user_namespace_no_expiration(self):
        """Test that user namespaces don't have expiration."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB, scope=StorageScope.USER, user_id="test-user"
        )

        assert info.expires_at is None
        assert info.ttl_seconds == 0

    @pytest.mark.asyncio
    async def test_sandbox_namespace_no_expiration(self):
        """Test that sandbox namespaces don't have expiration."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB, scope=StorageScope.SANDBOX
        )

        assert info.expires_at is None
        assert info.ttl_seconds == 0


class TestNamespaceGridPaths:
    """Test grid path generation."""

    @pytest.mark.asyncio
    async def test_session_grid_path_format(self):
        """Test session scope grid path format."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB,
            scope=StorageScope.SESSION,
            user_id="test-user",
        )

        assert "sess-" in info.grid_path
        assert info.namespace_id in info.grid_path

    @pytest.mark.asyncio
    async def test_user_grid_path_format(self):
        """Test user scope grid path format."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB, scope=StorageScope.USER, user_id="alice"
        )

        assert "user-alice" in info.grid_path
        assert info.namespace_id in info.grid_path

    @pytest.mark.asyncio
    async def test_sandbox_grid_path_format(self):
        """Test sandbox scope grid path format."""
        store = ArtifactStore()
        namespace_ops = NamespaceOperations(store)

        info = await namespace_ops.create_namespace(
            type=NamespaceType.BLOB, scope=StorageScope.SANDBOX
        )

        assert "shared" in info.grid_path
        assert info.namespace_id in info.grid_path

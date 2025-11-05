# -*- coding: utf-8 -*-
# tests/test_access_control.py
"""
Tests for access control module.
"""

import pytest
from chuk_artifacts.access_control import check_access, can_modify, build_context
from chuk_artifacts.models import ArtifactMetadata, AccessContext
from chuk_artifacts.exceptions import AccessDeniedError
from datetime import datetime


class TestBuildContext:
    """Tests for build_context helper function."""

    def test_build_context_full(self):
        """Test building context with all parameters."""
        context = build_context(
            user_id="user123", session_id="session456", sandbox_id="sandbox789"
        )
        assert context.user_id == "user123"
        assert context.session_id == "session456"
        assert context.sandbox_id == "sandbox789"

    def test_build_context_no_user(self):
        """Test building context without user_id."""
        context = build_context(session_id="session456", sandbox_id="sandbox789")
        assert context.user_id is None
        assert context.session_id == "session456"
        assert context.sandbox_id == "sandbox789"

    def test_build_context_no_session(self):
        """Test building context without session_id."""
        context = build_context(user_id="user123", sandbox_id="sandbox789")
        assert context.user_id == "user123"
        assert context.session_id is None
        assert context.sandbox_id == "sandbox789"

    def test_build_context_only_sandbox(self):
        """Test building context with only sandbox_id."""
        context = build_context(sandbox_id="sandbox789")
        assert context.user_id is None
        assert context.session_id is None
        assert context.sandbox_id == "sandbox789"


class TestCheckAccessSessionScope:
    """Tests for check_access with session-scoped artifacts."""

    def test_session_scope_same_session_allowed(self):
        """Session-scoped artifact accessed by same session should succeed."""
        artifact = ArtifactMetadata(
            artifact_id="art1",
            session_id="session1",
            sandbox_id="sandbox1",
            key="grid/sandbox1/session1/art1",
            mime="text/plain",
            summary="test",
            bytes=100,
            stored_at=datetime.utcnow().isoformat() + "Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
            scope="session",
            owner_id=None,
        )
        context = AccessContext(
            user_id="user1", session_id="session1", sandbox_id="sandbox1"
        )

        # Should not raise
        check_access(artifact, context)

    def test_session_scope_different_session_denied(self):
        """Session-scoped artifact accessed by different session should fail."""
        artifact = ArtifactMetadata(
            artifact_id="art1",
            session_id="session1",
            sandbox_id="sandbox1",
            key="grid/sandbox1/session1/art1",
            mime="text/plain",
            summary="test",
            bytes=100,
            stored_at=datetime.utcnow().isoformat() + "Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
            scope="session",
            owner_id=None,
        )
        context = AccessContext(
            user_id="user1", session_id="session2", sandbox_id="sandbox1"
        )

        with pytest.raises(AccessDeniedError) as exc_info:
            check_access(artifact, context)
        assert "session1" in str(exc_info.value)
        assert "session2" in str(exc_info.value)


class TestCheckAccessUserScope:
    """Tests for check_access with user-scoped artifacts."""

    def test_user_scope_same_user_allowed(self):
        """User-scoped artifact accessed by same user should succeed."""
        artifact = ArtifactMetadata(
            artifact_id="art1",
            session_id="session1",
            sandbox_id="sandbox1",
            key="grid/sandbox1/session1/art1",
            mime="text/plain",
            summary="test",
            bytes=100,
            stored_at=datetime.utcnow().isoformat() + "Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
            scope="user",
            owner_id="user1",
        )
        context = AccessContext(
            user_id="user1", session_id="session1", sandbox_id="sandbox1"
        )

        # Should not raise
        check_access(artifact, context)

    def test_user_scope_different_user_denied(self):
        """User-scoped artifact accessed by different user should fail."""
        artifact = ArtifactMetadata(
            artifact_id="art1",
            session_id="session1",
            sandbox_id="sandbox1",
            key="grid/sandbox1/session1/art1",
            mime="text/plain",
            summary="test",
            bytes=100,
            stored_at=datetime.utcnow().isoformat() + "Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
            scope="user",
            owner_id="user1",
        )
        context = AccessContext(
            user_id="user2", session_id="session1", sandbox_id="sandbox1"
        )

        with pytest.raises(AccessDeniedError) as exc_info:
            check_access(artifact, context)
        assert "user1" in str(exc_info.value)
        assert "user2" in str(exc_info.value)

    def test_user_scope_no_user_id_denied(self):
        """User-scoped artifact accessed without user_id should fail."""
        artifact = ArtifactMetadata(
            artifact_id="art1",
            session_id="session1",
            sandbox_id="sandbox1",
            key="grid/sandbox1/session1/art1",
            mime="text/plain",
            summary="test",
            bytes=100,
            stored_at=datetime.utcnow().isoformat() + "Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
            scope="user",
            owner_id="user1",
        )
        context = AccessContext(
            user_id=None, session_id="session1", sandbox_id="sandbox1"
        )

        with pytest.raises(AccessDeniedError) as exc_info:
            check_access(artifact, context)
        assert "user_id required" in str(exc_info.value)


class TestCheckAccessSandboxScope:
    """Tests for check_access with sandbox-scoped artifacts."""

    def test_sandbox_scope_same_sandbox_allowed(self):
        """Sandbox-scoped artifact accessed within same sandbox should succeed."""
        artifact = ArtifactMetadata(
            artifact_id="art1",
            session_id="session1",
            sandbox_id="sandbox1",
            key="grid/sandbox1/session1/art1",
            mime="text/plain",
            summary="test",
            bytes=100,
            stored_at=datetime.utcnow().isoformat() + "Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
            scope="sandbox",
            owner_id=None,
        )
        context = AccessContext(
            user_id="user1", session_id="session1", sandbox_id="sandbox1"
        )

        # Should not raise
        check_access(artifact, context)

    def test_sandbox_scope_different_user_same_sandbox_allowed(self):
        """Sandbox-scoped artifacts are accessible to any user in the sandbox."""
        artifact = ArtifactMetadata(
            artifact_id="art1",
            session_id="session1",
            sandbox_id="sandbox1",
            key="grid/sandbox1/session1/art1",
            mime="text/plain",
            summary="test",
            bytes=100,
            stored_at=datetime.utcnow().isoformat() + "Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
            scope="sandbox",
            owner_id=None,
        )
        context = AccessContext(
            user_id="user2", session_id="session2", sandbox_id="sandbox1"
        )

        # Should not raise
        check_access(artifact, context)


class TestCheckAccessSandboxMismatch:
    """Tests for sandbox mismatch validation."""

    def test_sandbox_mismatch_denied(self):
        """Access should be denied if sandbox_id doesn't match."""
        artifact = ArtifactMetadata(
            artifact_id="art1",
            session_id="session1",
            sandbox_id="sandbox1",
            key="grid/sandbox1/session1/art1",
            mime="text/plain",
            summary="test",
            bytes=100,
            stored_at=datetime.utcnow().isoformat() + "Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
            scope="session",
            owner_id=None,
        )
        context = AccessContext(
            user_id="user1", session_id="session1", sandbox_id="sandbox2"
        )

        with pytest.raises(AccessDeniedError) as exc_info:
            check_access(artifact, context)
        assert "Sandbox mismatch" in str(exc_info.value)
        assert "sandbox1" in str(exc_info.value)
        assert "sandbox2" in str(exc_info.value)


class TestCanModifySessionScope:
    """Tests for can_modify with session-scoped artifacts."""

    def test_session_scope_same_session_can_modify(self):
        """Session owner can modify session-scoped artifacts."""
        artifact = ArtifactMetadata(
            artifact_id="art1",
            session_id="session1",
            sandbox_id="sandbox1",
            key="grid/sandbox1/session1/art1",
            mime="text/plain",
            summary="test",
            bytes=100,
            stored_at=datetime.utcnow().isoformat() + "Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
            scope="session",
            owner_id=None,
        )
        context = AccessContext(
            user_id="user1", session_id="session1", sandbox_id="sandbox1"
        )

        assert can_modify(artifact, context) is True

    def test_session_scope_different_session_cannot_modify(self):
        """Different session cannot modify session-scoped artifacts."""
        artifact = ArtifactMetadata(
            artifact_id="art1",
            session_id="session1",
            sandbox_id="sandbox1",
            key="grid/sandbox1/session1/art1",
            mime="text/plain",
            summary="test",
            bytes=100,
            stored_at=datetime.utcnow().isoformat() + "Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
            scope="session",
            owner_id=None,
        )
        context = AccessContext(
            user_id="user1", session_id="session2", sandbox_id="sandbox1"
        )

        assert can_modify(artifact, context) is False


class TestCanModifyUserScope:
    """Tests for can_modify with user-scoped artifacts."""

    def test_user_scope_same_user_can_modify(self):
        """User owner can modify user-scoped artifacts."""
        artifact = ArtifactMetadata(
            artifact_id="art1",
            session_id="session1",
            sandbox_id="sandbox1",
            key="grid/sandbox1/session1/art1",
            mime="text/plain",
            summary="test",
            bytes=100,
            stored_at=datetime.utcnow().isoformat() + "Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
            scope="user",
            owner_id="user1",
        )
        context = AccessContext(
            user_id="user1", session_id="session1", sandbox_id="sandbox1"
        )

        assert can_modify(artifact, context) is True

    def test_user_scope_different_user_cannot_modify(self):
        """Different user cannot modify user-scoped artifacts."""
        artifact = ArtifactMetadata(
            artifact_id="art1",
            session_id="session1",
            sandbox_id="sandbox1",
            key="grid/sandbox1/session1/art1",
            mime="text/plain",
            summary="test",
            bytes=100,
            stored_at=datetime.utcnow().isoformat() + "Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
            scope="user",
            owner_id="user1",
        )
        context = AccessContext(
            user_id="user2", session_id="session1", sandbox_id="sandbox1"
        )

        assert can_modify(artifact, context) is False

    def test_user_scope_no_user_id_cannot_modify(self):
        """Cannot modify user-scoped artifacts without user_id."""
        artifact = ArtifactMetadata(
            artifact_id="art1",
            session_id="session1",
            sandbox_id="sandbox1",
            key="grid/sandbox1/session1/art1",
            mime="text/plain",
            summary="test",
            bytes=100,
            stored_at=datetime.utcnow().isoformat() + "Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
            scope="user",
            owner_id="user1",
        )
        context = AccessContext(
            user_id=None, session_id="session1", sandbox_id="sandbox1"
        )

        assert can_modify(artifact, context) is False


class TestCanModifySandboxScope:
    """Tests for can_modify with sandbox-scoped artifacts."""

    def test_sandbox_scope_cannot_modify(self):
        """Sandbox-scoped artifacts cannot be modified via regular operations."""
        artifact = ArtifactMetadata(
            artifact_id="art1",
            session_id="session1",
            sandbox_id="sandbox1",
            key="grid/sandbox1/session1/art1",
            mime="text/plain",
            summary="test",
            bytes=100,
            stored_at=datetime.utcnow().isoformat() + "Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
            scope="sandbox",
            owner_id=None,
        )
        context = AccessContext(
            user_id="user1", session_id="session1", sandbox_id="sandbox1"
        )

        assert can_modify(artifact, context) is False


class TestCanModifySandboxMismatch:
    """Tests for sandbox mismatch in can_modify."""

    def test_sandbox_mismatch_cannot_modify(self):
        """Cannot modify if sandbox doesn't match."""
        artifact = ArtifactMetadata(
            artifact_id="art1",
            session_id="session1",
            sandbox_id="sandbox1",
            key="grid/sandbox1/session1/art1",
            mime="text/plain",
            summary="test",
            bytes=100,
            stored_at=datetime.utcnow().isoformat() + "Z",
            ttl=900,
            storage_provider="memory",
            session_provider="memory",
            scope="session",
            owner_id=None,
        )
        context = AccessContext(
            user_id="user1", session_id="session1", sandbox_id="sandbox2"
        )

        assert can_modify(artifact, context) is False

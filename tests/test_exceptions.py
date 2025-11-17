# -*- coding: utf-8 -*-
# tests/test_exceptions.py
"""
Tests for exception classes in chuk_artifacts.exceptions.

Validates exception hierarchy, instantiation, inheritance, and behavior.
"""

import pytest
from chuk_artifacts.exceptions import (
    ArtifactStoreError,
    ArtifactNotFoundError,
    ArtifactExpiredError,
    ArtifactCorruptedError,
    ProviderError,
    SessionError,
)


class TestExceptionHierarchy:
    """Test exception inheritance and hierarchy."""

    def test_base_exception_inheritance(self):
        """Test that ArtifactStoreError inherits from Exception."""
        assert issubclass(ArtifactStoreError, Exception)

        # Create instance
        exc = ArtifactStoreError("test error")
        assert isinstance(exc, Exception)
        assert isinstance(exc, ArtifactStoreError)

    def test_artifact_not_found_error_inheritance(self):
        """Test ArtifactNotFoundError inheritance."""
        assert issubclass(ArtifactNotFoundError, ArtifactStoreError)
        assert issubclass(ArtifactNotFoundError, Exception)

        exc = ArtifactNotFoundError("artifact not found")
        assert isinstance(exc, ArtifactStoreError)
        assert isinstance(exc, ArtifactNotFoundError)
        assert isinstance(exc, Exception)

    def test_artifact_expired_error_inheritance(self):
        """Test ArtifactExpiredError inheritance."""
        assert issubclass(ArtifactExpiredError, ArtifactStoreError)
        assert issubclass(ArtifactExpiredError, Exception)

        exc = ArtifactExpiredError("artifact expired")
        assert isinstance(exc, ArtifactStoreError)
        assert isinstance(exc, ArtifactExpiredError)
        assert isinstance(exc, Exception)

    def test_artifact_corrupted_error_inheritance(self):
        """Test ArtifactCorruptedError inheritance."""
        assert issubclass(ArtifactCorruptedError, ArtifactStoreError)
        assert issubclass(ArtifactCorruptedError, Exception)

        exc = ArtifactCorruptedError("artifact corrupted")
        assert isinstance(exc, ArtifactStoreError)
        assert isinstance(exc, ArtifactCorruptedError)
        assert isinstance(exc, Exception)

    def test_provider_error_inheritance(self):
        """Test ProviderError inheritance."""
        assert issubclass(ProviderError, ArtifactStoreError)
        assert issubclass(ProviderError, Exception)

        exc = ProviderError("provider error")
        assert isinstance(exc, ArtifactStoreError)
        assert isinstance(exc, ProviderError)
        assert isinstance(exc, Exception)

    def test_session_error_inheritance(self):
        """Test SessionError inheritance."""
        assert issubclass(SessionError, ArtifactStoreError)
        assert issubclass(SessionError, Exception)

        exc = SessionError("session error")
        assert isinstance(exc, ArtifactStoreError)
        assert isinstance(exc, SessionError)
        assert isinstance(exc, Exception)


class TestExceptionInstantiation:
    """Test exception instantiation with various parameters."""

    def test_artifact_store_error_instantiation(self):
        """Test ArtifactStoreError instantiation."""
        # No message
        exc = ArtifactStoreError()
        assert str(exc) == ""
        assert exc.args == ()

        # With message
        exc = ArtifactStoreError("test message")
        assert str(exc) == "test message"
        assert exc.args == ("test message",)

        # With multiple args
        exc = ArtifactStoreError("message", 123, {"key": "value"})
        assert exc.args == ("message", 123, {"key": "value"})

    def test_artifact_not_found_error_instantiation(self):
        """Test ArtifactNotFoundError instantiation."""
        exc = ArtifactNotFoundError("Artifact abc123 not found")
        assert str(exc) == "Artifact abc123 not found"
        assert exc.args == ("Artifact abc123 not found",)

    def test_artifact_expired_error_instantiation(self):
        """Test ArtifactExpiredError instantiation."""
        exc = ArtifactExpiredError("Artifact abc123 has expired")
        assert str(exc) == "Artifact abc123 has expired"
        assert exc.args == ("Artifact abc123 has expired",)

    def test_artifact_corrupted_error_instantiation(self):
        """Test ArtifactCorruptedError instantiation."""
        exc = ArtifactCorruptedError("Metadata corrupted for artifact abc123")
        assert str(exc) == "Metadata corrupted for artifact abc123"
        assert exc.args == ("Metadata corrupted for artifact abc123",)

    def test_provider_error_instantiation(self):
        """Test ProviderError instantiation."""
        exc = ProviderError("S3 connection failed")
        assert str(exc) == "S3 connection failed"
        assert exc.args == ("S3 connection failed",)

    def test_session_error_instantiation(self):
        """Test SessionError instantiation."""
        exc = SessionError("Redis connection timeout")
        assert str(exc) == "Redis connection timeout"
        assert exc.args == ("Redis connection timeout",)


class TestExceptionCatching:
    """Test exception catching behavior."""

    def test_catch_specific_exceptions(self):
        """Test catching specific exception types."""
        # ArtifactNotFoundError
        with pytest.raises(ArtifactNotFoundError):
            raise ArtifactNotFoundError("not found")

        # ArtifactExpiredError
        with pytest.raises(ArtifactExpiredError):
            raise ArtifactExpiredError("expired")

        # ArtifactCorruptedError
        with pytest.raises(ArtifactCorruptedError):
            raise ArtifactCorruptedError("corrupted")

        # ProviderError
        with pytest.raises(ProviderError):
            raise ProviderError("provider failed")

        # SessionError
        with pytest.raises(SessionError):
            raise SessionError("session failed")

    def test_catch_base_exception(self):
        """Test catching all artifact store exceptions via base class."""
        exceptions_to_test = [
            ArtifactNotFoundError("not found"),
            ArtifactExpiredError("expired"),
            ArtifactCorruptedError("corrupted"),
            ProviderError("provider failed"),
            SessionError("session failed"),
            ArtifactStoreError("generic error"),
        ]

        for exc in exceptions_to_test:
            with pytest.raises(ArtifactStoreError):
                raise exc

    def test_exception_hierarchy_catching(self):
        """Test that child exceptions can be caught by parent exception handlers."""

        def raise_not_found():
            raise ArtifactNotFoundError("test artifact not found")

        # Can catch as specific type
        with pytest.raises(ArtifactNotFoundError) as exc_info:
            raise_not_found()
        assert "test artifact not found" in str(exc_info.value)

        # Can catch as base type
        with pytest.raises(ArtifactStoreError) as exc_info:
            raise_not_found()
        assert "test artifact not found" in str(exc_info.value)

        # Can catch as Exception
        with pytest.raises(Exception) as exc_info:
            raise_not_found()
        assert "test artifact not found" in str(exc_info.value)


class TestExceptionChaining:
    """Test exception chaining behavior."""

    def test_exception_chaining_from_clause(self):
        """Test chaining exceptions using 'raise ... from ...' syntax."""
        original_error = ValueError("Original error")

        try:
            try:
                raise original_error
            except ValueError as e:
                raise ProviderError("Provider failed") from e
        except ProviderError as pe:
            assert pe.__cause__ is original_error
            assert str(pe) == "Provider failed"
            assert str(pe.__cause__) == "Original error"

    def test_exception_chaining_implicit(self):
        """Test implicit exception chaining."""
        try:
            try:
                raise ValueError("Original error")
            except ValueError:
                raise SessionError("Session failed")
        except SessionError as se:
            assert se.__context__ is not None
            assert isinstance(se.__context__, ValueError)
            assert str(se.__context__) == "Original error"


class TestExceptionDocstrings:
    """Test that exceptions have proper docstrings."""

    def test_all_exceptions_have_docstrings(self):
        """Test that all exception classes have docstrings."""
        exceptions = [
            ArtifactStoreError,
            ArtifactNotFoundError,
            ArtifactExpiredError,
            ArtifactCorruptedError,
            ProviderError,
            SessionError,
        ]

        for exc_class in exceptions:
            assert exc_class.__doc__ is not None
            assert exc_class.__doc__.strip() != ""
            assert "." in exc_class.__doc__  # Should be a proper sentence

    def test_docstring_content(self):
        """Test that docstrings contain appropriate content."""
        assert "Base exception" in ArtifactStoreError.__doc__
        assert "cannot be found" in ArtifactNotFoundError.__doc__
        assert "expired" in ArtifactExpiredError.__doc__
        assert "corrupted" in ArtifactCorruptedError.__doc__
        assert "storage provider" in ProviderError.__doc__
        assert "session provider" in SessionError.__doc__


class TestExceptionEquality:
    """Test exception equality and comparison."""

    def test_exception_equality(self):
        """Test exception equality comparison."""
        # Same message, same type
        exc1 = ArtifactNotFoundError("not found")
        exc2 = ArtifactNotFoundError("not found")

        # Exceptions with same message are equal (standard Python behavior)
        assert exc1.args == exc2.args
        assert str(exc1) == str(exc2)

        # Different messages
        exc3 = ArtifactNotFoundError("different message")
        assert exc1.args != exc3.args
        assert str(exc1) != str(exc3)

    def test_exception_type_differences(self):
        """Test that different exception types are distinguishable."""
        exc1 = ArtifactNotFoundError("test")
        exc2 = ArtifactExpiredError("test")

        assert type(exc1) is not type(exc2)
        assert isinstance(exc1, ArtifactNotFoundError)
        assert not isinstance(exc1, ArtifactExpiredError)
        assert isinstance(exc2, ArtifactExpiredError)
        assert not isinstance(exc2, ArtifactNotFoundError)


class TestRealWorldUsage:
    """Test realistic usage patterns for exceptions."""

    def test_typical_artifact_not_found_usage(self):
        """Test typical usage of ArtifactNotFoundError."""
        artifact_id = "abc123"

        def find_artifact(aid):
            if aid != "exists":
                raise ArtifactNotFoundError(f"Artifact {aid} not found")
            return {"id": aid, "data": "test"}

        # Should raise for non-existent artifact
        with pytest.raises(ArtifactNotFoundError) as exc_info:
            find_artifact(artifact_id)

        assert artifact_id in str(exc_info.value)
        assert "not found" in str(exc_info.value)

        # Should work for existing artifact
        result = find_artifact("exists")
        assert result["id"] == "exists"

    def test_typical_provider_error_usage(self):
        """Test typical usage of ProviderError."""

        def connect_to_storage():
            # Simulate connection failure
            raise ProviderError("Failed to connect to S3: Connection timeout")

        with pytest.raises(ProviderError) as exc_info:
            connect_to_storage()

        assert "Failed to connect" in str(exc_info.value)
        assert "S3" in str(exc_info.value)
        assert "timeout" in str(exc_info.value)

    def test_exception_handling_patterns(self):
        """Test common exception handling patterns."""

        def operation_that_might_fail(fail_type=None):
            if fail_type == "not_found":
                raise ArtifactNotFoundError("Artifact not found")
            elif fail_type == "expired":
                raise ArtifactExpiredError("Artifact expired")
            elif fail_type == "provider":
                raise ProviderError("Provider failed")
            elif fail_type == "session":
                raise SessionError("Session failed")
            return "success"

        # Test specific exception handling
        try:
            operation_that_might_fail("not_found")
            assert False, "Should have raised exception"
        except ArtifactNotFoundError:
            pass  # Expected
        except ArtifactStoreError:
            assert False, "Should have caught specific exception"

        # Test generic exception handling
        error_types = ["not_found", "expired", "provider", "session"]

        for error_type in error_types:
            try:
                operation_that_might_fail(error_type)
                assert False, f"Should have raised exception for {error_type}"
            except ArtifactStoreError:
                pass  # Expected - all our exceptions inherit from this
            except Exception:
                assert False, "Should have caught ArtifactStoreError"

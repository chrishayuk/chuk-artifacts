# -*- coding: utf-8 -*-
# tests/test_provider_factory.py
"""
Tests for provider_factory.py - ensuring proper provider resolution and error handling.
"""

import os
import pytest
from unittest.mock import patch, Mock
from importlib import import_module

from chuk_artifacts.provider_factory import factory_for_env


# Helper functions
def _can_import_s3_provider():
    """Check if S3 provider dependencies are available."""
    try:
        import_module("chuk_artifacts.providers.s3")
        return True
    except ImportError:
        return False


class TestProviderFactoryBuiltins:
    """Test built-in provider resolution."""

    def test_memory_provider_default(self):
        """Test memory provider is default when no env var set."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear ARTIFACT_PROVIDER if it exists
            if "ARTIFACT_PROVIDER" in os.environ:
                del os.environ["ARTIFACT_PROVIDER"]

            factory = factory_for_env()
            assert callable(factory)

            # The factory should be callable and return an async context manager
            assert factory is not None

    @pytest.mark.parametrize(
        "provider_name", ["memory", "mem", "inmemory", "MEMORY", "  Memory  "]
    )
    def test_memory_provider_variants(self, provider_name):
        """Test various memory provider name variants."""
        with patch.dict(os.environ, {"ARTIFACT_PROVIDER": provider_name}):
            factory = factory_for_env()
            assert callable(factory)

    @pytest.mark.parametrize(
        "provider_name", ["fs", "filesystem", "FS", "FILESYSTEM", "  filesystem  "]
    )
    def test_filesystem_provider_variants(self, provider_name):
        """Test various filesystem provider name variants."""
        with patch.dict(os.environ, {"ARTIFACT_PROVIDER": provider_name}):
            factory = factory_for_env()
            assert callable(factory)

    def test_s3_provider(self):
        """Test S3 provider resolution."""
        with patch.dict(
            os.environ,
            {
                "ARTIFACT_PROVIDER": "s3",
                "AWS_ACCESS_KEY_ID": "test_key",
                "AWS_SECRET_ACCESS_KEY": "test_secret",
            },
        ):
            factory = factory_for_env()
            assert callable(factory)

    def test_ibm_cos_provider(self):
        """Test IBM COS provider resolution."""
        with patch.dict(
            os.environ,
            {
                "ARTIFACT_PROVIDER": "ibm_cos",
                "AWS_ACCESS_KEY_ID": "test_key",
                "AWS_SECRET_ACCESS_KEY": "test_secret",
            },
        ):
            factory = factory_for_env()
            assert callable(factory)


class TestProviderFactoryVFSProviders:
    """Test VFS-backed provider resolution."""

    @pytest.mark.parametrize("provider_name", ["vfs", "vfs-memory", "vfs_memory"])
    def test_vfs_memory_provider_variants(self, provider_name):
        """Test VFS memory provider name variants."""
        with patch.dict(os.environ, {"ARTIFACT_PROVIDER": provider_name}):
            factory = factory_for_env()
            assert callable(factory)

    @pytest.mark.parametrize(
        "provider_name", ["vfs-filesystem", "vfs_filesystem", "vfs-fs", "vfs_fs"]
    )
    def test_vfs_filesystem_provider_variants(self, provider_name):
        """Test VFS filesystem provider name variants."""
        with patch.dict(os.environ, {"ARTIFACT_PROVIDER": provider_name}):
            factory = factory_for_env()
            assert callable(factory)

    @pytest.mark.parametrize("provider_name", ["vfs-s3", "vfs_s3"])
    def test_vfs_s3_provider_variants(self, provider_name):
        """Test VFS S3 provider name variants."""
        with patch.dict(os.environ, {"ARTIFACT_PROVIDER": provider_name}):
            factory = factory_for_env()
            assert callable(factory)

    @pytest.mark.parametrize("provider_name", ["vfs-sqlite", "vfs_sqlite"])
    def test_vfs_sqlite_provider_variants(self, provider_name):
        """Test VFS SQLite provider name variants."""
        with patch.dict(os.environ, {"ARTIFACT_PROVIDER": provider_name}):
            factory = factory_for_env()
            assert callable(factory)

    def test_vfs_filesystem_with_custom_root(self):
        """Test VFS filesystem provider respects ARTIFACT_FS_ROOT."""
        with patch.dict(
            os.environ,
            {"ARTIFACT_PROVIDER": "vfs-filesystem", "ARTIFACT_FS_ROOT": "/custom/path"},
        ):
            factory = factory_for_env()
            assert callable(factory)

    def test_vfs_s3_with_custom_bucket(self):
        """Test VFS S3 provider respects ARTIFACT_BUCKET."""
        with patch.dict(
            os.environ,
            {"ARTIFACT_PROVIDER": "vfs-s3", "ARTIFACT_BUCKET": "my-custom-bucket"},
        ):
            factory = factory_for_env()
            assert callable(factory)

    def test_vfs_sqlite_with_custom_db_path(self):
        """Test VFS SQLite provider respects ARTIFACT_SQLITE_PATH."""
        with patch.dict(
            os.environ,
            {
                "ARTIFACT_PROVIDER": "vfs-sqlite",
                "ARTIFACT_SQLITE_PATH": "/custom/db.sqlite",
            },
        ):
            factory = factory_for_env()
            assert callable(factory)


class TestProviderFactoryDynamicLookup:
    """Test dynamic provider lookup and error handling."""

    def test_unknown_provider_error(self):
        """Test error when provider doesn't exist."""
        with patch.dict(os.environ, {"ARTIFACT_PROVIDER": "nonexistent_provider"}):
            with pytest.raises(ValueError) as exc_info:
                factory_for_env()

            assert "Unknown storage provider 'nonexistent_provider'" in str(
                exc_info.value
            )
            # Should list both legacy and VFS providers
            assert "Available providers:" in str(exc_info.value)
            assert "memory" in str(exc_info.value)
            assert "vfs" in str(exc_info.value)

    @patch("chuk_artifacts.provider_factory.import_module")
    def test_dynamic_provider_without_factory_function(self, mock_import):
        """Test error when dynamic provider lacks factory() function."""
        # Mock a module without factory function
        mock_module = Mock()
        del mock_module.factory  # Ensure no factory attribute
        mock_import.return_value = mock_module

        with patch.dict(os.environ, {"ARTIFACT_PROVIDER": "custom_provider"}):
            with pytest.raises(AttributeError) as exc_info:
                factory_for_env()

            assert "Provider 'custom_provider' lacks a factory() function" in str(
                exc_info.value
            )
            mock_import.assert_called_once_with(
                "chuk_artifacts.providers.custom_provider"
            )

    @patch("chuk_artifacts.provider_factory.import_module")
    def test_dynamic_provider_with_callable_factory(self, mock_import):
        """Test dynamic provider with callable factory that returns a factory."""
        # Mock a module with factory function that returns another function
        mock_factory_result = Mock()
        mock_factory_func = Mock(return_value=mock_factory_result)
        mock_module = Mock()
        mock_module.factory = mock_factory_func
        mock_import.return_value = mock_module

        with patch.dict(os.environ, {"ARTIFACT_PROVIDER": "custom_provider"}):
            result = factory_for_env()

            assert result == mock_factory_result
            mock_factory_func.assert_called_once()
            mock_import.assert_called_once_with(
                "chuk_artifacts.providers.custom_provider"
            )

    @patch("chuk_artifacts.provider_factory.import_module")
    def test_dynamic_provider_factory_already_factory(self, mock_import):
        """Test dynamic provider where factory is already the factory function."""
        # Mock a module where factory is the actual factory function (not a function that returns one)
        mock_factory_func = Mock()
        mock_factory_func.side_effect = TypeError("Direct factory function")
        mock_module = Mock()
        mock_module.factory = mock_factory_func
        mock_import.return_value = mock_module

        with patch.dict(os.environ, {"ARTIFACT_PROVIDER": "custom_provider"}):
            result = factory_for_env()

            assert result == mock_factory_func
            mock_factory_func.assert_called_once()

    @patch("chuk_artifacts.provider_factory.import_module")
    def test_dynamic_provider_non_callable_factory(self, mock_import):
        """Test dynamic provider with non-callable factory attribute."""
        # Mock a module with non-callable factory
        mock_factory = "not_callable"
        mock_module = Mock()
        mock_module.factory = mock_factory
        mock_import.return_value = mock_module

        with patch.dict(os.environ, {"ARTIFACT_PROVIDER": "custom_provider"}):
            result = factory_for_env()

            assert result == mock_factory


class TestProviderFactoryEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_provider_name(self):
        """Test empty provider name raises ValueError."""
        with patch.dict(os.environ, {"ARTIFACT_PROVIDER": ""}):
            with pytest.raises(ValueError) as exc_info:
                factory_for_env()

            assert "Unknown storage provider ''" in str(exc_info.value)
            assert "Available providers:" in str(exc_info.value)

    def test_whitespace_only_provider_name(self):
        """Test whitespace-only provider name raises ValueError."""
        with patch.dict(os.environ, {"ARTIFACT_PROVIDER": "   "}):
            with pytest.raises(ValueError) as exc_info:
                factory_for_env()

            assert "Unknown storage provider ''" in str(exc_info.value)
            assert "Available providers:" in str(exc_info.value)

    def test_case_insensitive_provider_names(self):
        """Test that provider names are case insensitive."""
        test_cases = [
            ("S3", "s3"),
            ("IBM_COS", "ibm_cos"),
            ("Memory", "memory"),
            ("FileSystem", "filesystem"),
        ]

        for input_name, expected_provider in test_cases:
            env_vars = {"ARTIFACT_PROVIDER": input_name}
            # Add AWS credentials for S3 and IBM COS
            if expected_provider in ["s3", "ibm_cos"]:
                env_vars["AWS_ACCESS_KEY_ID"] = "test_key"
                env_vars["AWS_SECRET_ACCESS_KEY"] = "test_secret"

            with patch.dict(os.environ, env_vars):
                # Should not raise an error
                factory = factory_for_env()
                assert callable(factory)

    @patch("chuk_artifacts.provider_factory.import_module")
    def test_import_error_propagation(self, mock_import):
        """Test that import errors are properly wrapped."""
        mock_import.side_effect = ModuleNotFoundError("Module not found")

        with patch.dict(os.environ, {"ARTIFACT_PROVIDER": "missing_provider"}):
            with pytest.raises(ValueError) as exc_info:
                factory_for_env()

            assert "Unknown storage provider 'missing_provider'" in str(exc_info.value)
            assert "Available providers:" in str(exc_info.value)
            assert exc_info.value.__cause__ is not None
            assert isinstance(exc_info.value.__cause__, ModuleNotFoundError)


class TestProviderFactoryIntegration:
    """Integration tests with actual provider modules."""

    def test_memory_provider_integration(self):
        """Test that memory provider actually works."""
        with patch.dict(os.environ, {"ARTIFACT_PROVIDER": "memory"}):
            factory = factory_for_env()

            # Should be able to call the factory
            ctx_manager = factory()
            assert hasattr(ctx_manager, "__aenter__")
            assert hasattr(ctx_manager, "__aexit__")

    def test_filesystem_provider_integration(self):
        """Test that filesystem provider actually works."""
        with patch.dict(os.environ, {"ARTIFACT_PROVIDER": "filesystem"}):
            factory = factory_for_env()

            # Should be able to call the factory
            ctx_manager = factory()
            assert hasattr(ctx_manager, "__aenter__")
            assert hasattr(ctx_manager, "__aexit__")

    @pytest.mark.skipif(
        not _can_import_s3_provider(), reason="S3 provider dependencies not available"
    )
    def test_s3_provider_integration(self):
        """Test that S3 provider actually works."""
        with patch.dict(
            os.environ,
            {
                "ARTIFACT_PROVIDER": "s3",
                "AWS_ACCESS_KEY_ID": "test_key",
                "AWS_SECRET_ACCESS_KEY": "test_secret",
            },
        ):
            factory = factory_for_env()

            # Should be able to call the factory
            ctx_manager = factory()
            assert hasattr(ctx_manager, "__aenter__")
            assert hasattr(ctx_manager, "__aexit__")


class TestProviderFactoryDocumentation:
    """Test that the factory behavior matches documentation."""

    def test_all_documented_providers_available(self):
        """Test all providers mentioned in docstring are available."""
        documented_providers = [
            "memory",
            "filesystem",
            "s3",
            "ibm_cos",
            "vfs",
            "vfs-memory",
            "vfs-filesystem",
            "vfs-s3",
            "vfs-sqlite",
        ]

        for provider in documented_providers:
            env_vars = {"ARTIFACT_PROVIDER": provider}
            # Add AWS credentials for providers that need them
            if provider in ["s3", "ibm_cos", "vfs-s3"]:
                env_vars["AWS_ACCESS_KEY_ID"] = "test_key"
                env_vars["AWS_SECRET_ACCESS_KEY"] = "test_secret"

            with patch.dict(os.environ, env_vars):
                # Should not raise an error
                factory = factory_for_env()
                assert callable(factory)

    def test_provider_aliases_work(self):
        """Test that documented aliases work."""
        aliases = {
            "mem": "memory",
            "inmemory": "memory",
            "fs": "filesystem",
            "vfs_memory": "vfs",
            "vfs_filesystem": "vfs-filesystem",
            "vfs_s3": "vfs-s3",
            "vfs_sqlite": "vfs-sqlite",
        }

        for alias in aliases.keys():
            with patch.dict(os.environ, {"ARTIFACT_PROVIDER": alias}):
                factory = factory_for_env()
                assert callable(factory)


# Helper functions (moved to end)
# def _can_import_s3_provider():
#     """Check if S3 provider dependencies are available."""
#     try:
#         import_module("chuk_artifacts.providers.s3")
#         return True
#     except ImportError:
#         return False


# Fixtures for testing with temporary environment
@pytest.fixture
def clean_env():
    """Provide a clean environment for testing."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_provider_module():
    """Create a mock provider module for testing."""
    mock_module = Mock()
    mock_factory = Mock()
    mock_module.factory = mock_factory
    return mock_module, mock_factory

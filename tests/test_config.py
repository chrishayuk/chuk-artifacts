# -*- coding: utf-8 -*-
# tests/test_config.py
"""
Tests for chuk_artifacts.config module.

Tests configuration helpers, environment variable setting, and store creation.
"""

import os
import pytest
from unittest.mock import patch, Mock
from chuk_artifacts.config import (
    configure_memory,
    configure_filesystem,
    configure_s3,
    configure_redis_session,
    configure_ibm_cos,
    create_store,
    development_setup,
    testing_setup,
    production_setup,
)
from chuk_artifacts.store import ArtifactStore


@pytest.fixture
def clean_env():
    """Provide a clean environment for testing."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


class TestConfigureMemory:
    """Test memory configuration."""

    def test_configure_memory_basic(self, clean_env):
        """Test basic memory configuration."""
        result = configure_memory()

        expected_vars = {
            "ARTIFACT_PROVIDER": "memory",
            "SESSION_PROVIDER": "memory",
            "ARTIFACT_BUCKET": "mcp-artifacts",
        }

        assert result == expected_vars

        # Check environment variables were set
        for key, value in expected_vars.items():
            assert os.environ[key] == value

    def test_configure_memory_return_type(self, clean_env):
        """Test that configure_memory returns correct type."""
        result = configure_memory()
        assert isinstance(result, dict)
        assert len(result) == 3


class TestConfigureFilesystem:
    """Test filesystem configuration."""

    def test_configure_filesystem_default_root(self, clean_env):
        """Test filesystem configuration with default root."""
        result = configure_filesystem()

        expected_vars = {
            "ARTIFACT_PROVIDER": "filesystem",
            "SESSION_PROVIDER": "memory",
            "ARTIFACT_FS_ROOT": "./artifacts",
            "ARTIFACT_BUCKET": "mcp-artifacts",
        }

        assert result == expected_vars

        for key, value in expected_vars.items():
            assert os.environ[key] == value

    def test_configure_filesystem_custom_root(self, clean_env):
        """Test filesystem configuration with custom root."""
        custom_root = "/custom/path/artifacts"
        result = configure_filesystem(custom_root)

        expected_vars = {
            "ARTIFACT_PROVIDER": "filesystem",
            "SESSION_PROVIDER": "memory",
            "ARTIFACT_FS_ROOT": custom_root,
            "ARTIFACT_BUCKET": "mcp-artifacts",
        }

        assert result == expected_vars
        assert os.environ["ARTIFACT_FS_ROOT"] == custom_root


class TestConfigureS3:
    """Test S3 configuration."""

    def test_configure_s3_basic(self, clean_env):
        """Test basic S3 configuration."""
        result = configure_s3(
            access_key="AKIA12345", secret_key="secret123", bucket="test-bucket"
        )

        expected_vars = {
            "ARTIFACT_PROVIDER": "s3",
            "SESSION_PROVIDER": "memory",
            "AWS_ACCESS_KEY_ID": "AKIA12345",
            "AWS_SECRET_ACCESS_KEY": "secret123",
            "AWS_REGION": "us-east-1",
            "ARTIFACT_BUCKET": "test-bucket",
        }

        assert result == expected_vars

        for key, value in expected_vars.items():
            assert os.environ[key] == value

    def test_configure_s3_with_endpoint_url(self, clean_env):
        """Test S3 configuration with custom endpoint URL."""
        endpoint_url = "https://nyc3.digitaloceanspaces.com"
        result = configure_s3(
            access_key="AKIA12345",
            secret_key="secret123",
            bucket="test-bucket",
            endpoint_url=endpoint_url,
        )

        assert result["S3_ENDPOINT_URL"] == endpoint_url
        assert os.environ["S3_ENDPOINT_URL"] == endpoint_url

    def test_configure_s3_custom_region(self, clean_env):
        """Test S3 configuration with custom region."""
        result = configure_s3(
            access_key="AKIA12345",
            secret_key="secret123",
            bucket="test-bucket",
            region="eu-west-1",
        )

        assert result["AWS_REGION"] == "eu-west-1"
        assert os.environ["AWS_REGION"] == "eu-west-1"

    def test_configure_s3_custom_session_provider(self, clean_env):
        """Test S3 configuration with custom session provider."""
        result = configure_s3(
            access_key="AKIA12345",
            secret_key="secret123",
            bucket="test-bucket",
            session_provider="redis",
        )

        assert result["SESSION_PROVIDER"] == "redis"
        assert os.environ["SESSION_PROVIDER"] == "redis"


class TestConfigureRedisSession:
    """Test Redis session configuration."""

    def test_configure_redis_session_default(self, clean_env):
        """Test Redis session configuration with default URL."""
        result = configure_redis_session()

        expected_vars = {
            "SESSION_PROVIDER": "redis",
            "SESSION_REDIS_URL": "redis://localhost:6379/0",
        }

        assert result == expected_vars

        for key, value in expected_vars.items():
            assert os.environ[key] == value

    def test_configure_redis_session_custom_url(self, clean_env):
        """Test Redis session configuration with custom URL."""
        custom_url = "redis://redis.example.com:6379/1"
        result = configure_redis_session(custom_url)

        expected_vars = {"SESSION_PROVIDER": "redis", "SESSION_REDIS_URL": custom_url}

        assert result == expected_vars
        assert os.environ["SESSION_REDIS_URL"] == custom_url


class TestConfigureIBMCOS:
    """Test IBM COS configuration."""

    def test_configure_ibm_cos_basic(self, clean_env):
        """Test basic IBM COS configuration."""
        result = configure_ibm_cos(
            access_key="hmac_access", secret_key="hmac_secret", bucket="cos-bucket"
        )

        expected_vars = {
            "ARTIFACT_PROVIDER": "ibm_cos",
            "SESSION_PROVIDER": "memory",
            "AWS_ACCESS_KEY_ID": "hmac_access",
            "AWS_SECRET_ACCESS_KEY": "hmac_secret",
            "AWS_REGION": "us-south",
            "IBM_COS_ENDPOINT": "https://s3.us-south.cloud-object-storage.appdomain.cloud",
            "ARTIFACT_BUCKET": "cos-bucket",
        }

        assert result == expected_vars

        for key, value in expected_vars.items():
            assert os.environ[key] == value

    def test_configure_ibm_cos_custom_endpoint(self, clean_env):
        """Test IBM COS configuration with custom endpoint."""
        custom_endpoint = "https://s3.eu-gb.cloud-object-storage.appdomain.cloud"
        result = configure_ibm_cos(
            access_key="hmac_access",
            secret_key="hmac_secret",
            bucket="cos-bucket",
            endpoint=custom_endpoint,
        )

        assert result["IBM_COS_ENDPOINT"] == custom_endpoint
        assert os.environ["IBM_COS_ENDPOINT"] == custom_endpoint

    def test_configure_ibm_cos_custom_region(self, clean_env):
        """Test IBM COS configuration with custom region."""
        result = configure_ibm_cos(
            access_key="hmac_access",
            secret_key="hmac_secret",
            bucket="cos-bucket",
            region="eu-gb",
        )

        assert result["AWS_REGION"] == "eu-gb"
        assert os.environ["AWS_REGION"] == "eu-gb"


class TestCreateStore:
    """Test store creation."""

    @patch("chuk_artifacts.config.ArtifactStore")
    def test_create_store(self, mock_artifact_store):
        """Test create_store function."""
        mock_instance = Mock()
        mock_artifact_store.return_value = mock_instance

        result = create_store()

        mock_artifact_store.assert_called_once()
        assert result == mock_instance

    def test_create_store_returns_artifact_store(self):
        """Test that create_store returns an ArtifactStore instance."""
        # This test might fail if dependencies aren't available, but tests the actual function
        with patch.dict(os.environ, {"ARTIFACT_PROVIDER": "memory"}):
            store = create_store()
            assert isinstance(store, ArtifactStore)


class TestConvenienceFunctions:
    """Test convenience setup functions."""

    @patch("chuk_artifacts.config.configure_memory")
    @patch("chuk_artifacts.config.create_store")
    def test_development_setup(self, mock_create_store, mock_configure_memory):
        """Test development_setup function."""
        mock_store = Mock()
        mock_create_store.return_value = mock_store

        result = development_setup()

        mock_configure_memory.assert_called_once()
        mock_create_store.assert_called_once()
        assert result == mock_store

    @patch("chuk_artifacts.config.configure_filesystem")
    @patch("chuk_artifacts.config.create_store")
    def test_testing_setup_default(self, mock_create_store, mock_configure_filesystem):
        """Test testing_setup function with default directory."""
        mock_store = Mock()
        mock_create_store.return_value = mock_store

        result = testing_setup()

        mock_configure_filesystem.assert_called_once_with("./test-artifacts")
        mock_create_store.assert_called_once()
        assert result == mock_store

    @patch("chuk_artifacts.config.configure_filesystem")
    @patch("chuk_artifacts.config.create_store")
    def test_testing_setup_custom_dir(
        self, mock_create_store, mock_configure_filesystem
    ):
        """Test testing_setup function with custom directory."""
        custom_dir = "/custom/test/dir"
        mock_store = Mock()
        mock_create_store.return_value = mock_store

        result = testing_setup(custom_dir)

        mock_configure_filesystem.assert_called_once_with(custom_dir)
        mock_create_store.assert_called_once()
        assert result == mock_store


class TestProductionSetup:
    """Test production setup function."""

    @patch("chuk_artifacts.config.configure_s3")
    @patch("chuk_artifacts.config.create_store")
    def test_production_setup_s3(self, mock_create_store, mock_configure_s3):
        """Test production_setup with S3 storage type."""
        mock_store = Mock()
        mock_create_store.return_value = mock_store

        kwargs = {
            "access_key": "AKIA123",
            "secret_key": "secret",
            "bucket": "prod-bucket",
        }

        result = production_setup(storage_type="s3", **kwargs)

        mock_configure_s3.assert_called_once_with(**kwargs)
        mock_create_store.assert_called_once()
        assert result == mock_store

    @patch("chuk_artifacts.config.configure_ibm_cos")
    @patch("chuk_artifacts.config.create_store")
    def test_production_setup_ibm_cos(self, mock_create_store, mock_configure_ibm_cos):
        """Test production_setup with IBM COS storage type."""
        mock_store = Mock()
        mock_create_store.return_value = mock_store

        kwargs = {
            "access_key": "hmac_key",
            "secret_key": "hmac_secret",
            "bucket": "cos-bucket",
        }

        result = production_setup(storage_type="ibm_cos", **kwargs)

        mock_configure_ibm_cos.assert_called_once_with(**kwargs)
        mock_create_store.assert_called_once()
        assert result == mock_store

    def test_production_setup_unknown_storage_type(self):
        """Test production_setup with unknown storage type."""
        with pytest.raises(ValueError) as exc_info:
            production_setup(storage_type="unknown_storage")

        assert "Unknown storage type: unknown_storage" in str(exc_info.value)


class TestEnvironmentVariableManagement:
    """Test environment variable setting and isolation."""

    def test_multiple_configurations_dont_interfere(self, clean_env):
        """Test that multiple configuration calls don't interfere."""
        # Configure memory first
        memory_result = configure_memory()
        assert os.environ["ARTIFACT_PROVIDER"] == "memory"

        # Configure S3 - should override
        s3_result = configure_s3(
            access_key="AKIA123", secret_key="secret", bucket="test-bucket"
        )
        assert os.environ["ARTIFACT_PROVIDER"] == "s3"
        assert os.environ["AWS_ACCESS_KEY_ID"] == "AKIA123"

        # Configure filesystem - should override again
        fs_result = configure_filesystem("/tmp/artifacts")
        assert os.environ["ARTIFACT_PROVIDER"] == "filesystem"
        assert os.environ["ARTIFACT_FS_ROOT"] == "/tmp/artifacts"

        # Memory config shouldn't affect new configurations
        assert memory_result != s3_result
        assert s3_result != fs_result

    def test_environment_variables_are_strings(self, clean_env):
        """Test that all environment variables are set as strings."""
        configure_s3(access_key="AKIA123", secret_key="secret", bucket="test-bucket")

        # All env vars should be strings
        for key, value in os.environ.items():
            assert isinstance(value, str)


class TestConfigurationIntegration:
    """Integration tests for configuration functions."""

    def test_memory_configuration_integration(self, clean_env):
        """Test memory configuration creates working store."""
        configure_memory()
        store = create_store()

        assert isinstance(store, ArtifactStore)
        assert store._storage_provider_name == "memory"
        assert store._session_provider_name == "memory"

    def test_filesystem_configuration_integration(self, clean_env):
        """Test filesystem configuration creates working store."""
        configure_filesystem("./test-artifacts")
        store = create_store()

        assert isinstance(store, ArtifactStore)
        assert store._storage_provider_name == "filesystem"

    def test_development_setup_integration(self, clean_env):
        """Test development_setup creates working store."""
        store = development_setup()

        assert isinstance(store, ArtifactStore)
        assert store._storage_provider_name == "memory"
        assert store._session_provider_name == "memory"

    def test_testing_setup_integration(self, clean_env):
        """Test testing_setup creates working store."""
        store = testing_setup("./test-integration")

        assert isinstance(store, ArtifactStore)
        assert store._storage_provider_name == "filesystem"


class TestParameterValidation:
    """Test parameter validation and type checking."""

    def test_configure_s3_required_parameters(self):
        """Test that configure_s3 requires necessary parameters."""
        with pytest.raises(TypeError):
            configure_s3()  # Missing required parameters

        with pytest.raises(TypeError):
            configure_s3(access_key="AKIA123")  # Missing secret_key and bucket

    def test_configure_ibm_cos_required_parameters(self):
        """Test that configure_ibm_cos requires necessary parameters."""
        with pytest.raises(TypeError):
            configure_ibm_cos()  # Missing required parameters

        with pytest.raises(TypeError):
            configure_ibm_cos(access_key="key")  # Missing secret_key and bucket


class TestReturnValues:
    """Test return value consistency and content."""

    def test_all_configure_functions_return_dict(self, clean_env):
        """Test that all configure functions return dictionaries."""
        functions_and_args = [
            (configure_memory, {}),
            (configure_filesystem, {}),
            (configure_redis_session, {}),
            (
                configure_s3,
                {"access_key": "key", "secret_key": "secret", "bucket": "bucket"},
            ),
            (
                configure_ibm_cos,
                {"access_key": "key", "secret_key": "secret", "bucket": "bucket"},
            ),
        ]

        for func, args in functions_and_args:
            result = func(**args)
            assert isinstance(result, dict)
            assert len(result) > 0

            # All values should be strings (for environment variables)
            for key, value in result.items():
                assert isinstance(key, str)
                assert isinstance(value, str)

    def test_returned_variables_match_environment(self, clean_env):
        """Test that returned variables match what's set in environment."""
        result = configure_s3(
            access_key="AKIA123", secret_key="secret", bucket="test-bucket"
        )

        for key, value in result.items():
            assert os.environ[key] == value

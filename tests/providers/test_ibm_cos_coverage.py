"""
Additional tests for IBM COS provider to increase coverage to 90%+.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from chuk_artifacts.providers.ibm_cos import factory, client


class TestIBMCOSClientFunction:
    """Test the client() convenience function."""

    def test_client_function_with_default_endpoint(self):
        """Test client() function uses default IBM COS endpoint."""
        with patch.dict(
            os.environ,
            {"AWS_ACCESS_KEY_ID": "test_key", "AWS_SECRET_ACCESS_KEY": "test_secret"},
            clear=True,
        ):
            with patch(
                "chuk_artifacts.providers.ibm_cos.aioboto3.Session"
            ) as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session

                client()

                mock_session.client.assert_called_once()
                call_kwargs = mock_session.client.call_args.kwargs
                assert (
                    call_kwargs["endpoint_url"]
                    == "https://s3.us-south.cloud-object-storage.appdomain.cloud"
                )
                assert call_kwargs["region_name"] == "us-south"

    def test_client_function_with_env_endpoint(self):
        """Test client() function reads endpoint from environment."""
        with patch.dict(
            os.environ,
            {
                "IBM_COS_ENDPOINT": "https://s3.eu-gb.cloud-object-storage.appdomain.cloud",
                "AWS_ACCESS_KEY_ID": "test_key",
                "AWS_SECRET_ACCESS_KEY": "test_secret",
            },
            clear=True,
        ):
            with patch(
                "chuk_artifacts.providers.ibm_cos.aioboto3.Session"
            ) as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session

                client()

                call_kwargs = mock_session.client.call_args.kwargs
                assert (
                    call_kwargs["endpoint_url"]
                    == "https://s3.eu-gb.cloud-object-storage.appdomain.cloud"
                )
                assert call_kwargs["region_name"] == "eu-gb"

    def test_client_function_region_extraction_us_south(self):
        """Test region extraction from us-south endpoint."""
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "chuk_artifacts.providers.ibm_cos.aioboto3.Session"
            ) as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session

                client(
                    endpoint_url="https://s3.us-south.cloud-object-storage.appdomain.cloud"
                )

                call_kwargs = mock_session.client.call_args.kwargs
                assert call_kwargs["region_name"] == "us-south"

    def test_client_function_region_extraction_us_east(self):
        """Test region extraction from us-east endpoint."""
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "chuk_artifacts.providers.ibm_cos.aioboto3.Session"
            ) as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session

                client(
                    endpoint_url="https://s3.us-east.cloud-object-storage.appdomain.cloud"
                )

                call_kwargs = mock_session.client.call_args.kwargs
                assert call_kwargs["region_name"] == "us-east"

    def test_client_function_region_extraction_eu_gb(self):
        """Test region extraction from eu-gb endpoint."""
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "chuk_artifacts.providers.ibm_cos.aioboto3.Session"
            ) as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session

                client(
                    endpoint_url="https://s3.eu-gb.cloud-object-storage.appdomain.cloud"
                )

                call_kwargs = mock_session.client.call_args.kwargs
                assert call_kwargs["region_name"] == "eu-gb"

    def test_client_function_region_extraction_unknown(self):
        """Test region extraction defaults to us-south for unknown endpoints."""
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "chuk_artifacts.providers.ibm_cos.aioboto3.Session"
            ) as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session

                client(endpoint_url="https://s3.unknown-region.example.com")

                call_kwargs = mock_session.client.call_args.kwargs
                assert call_kwargs["region_name"] == "us-south"

    def test_client_function_explicit_region_overrides_extraction(self):
        """Test explicit region parameter overrides extraction."""
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "chuk_artifacts.providers.ibm_cos.aioboto3.Session"
            ) as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session

                client(
                    endpoint_url="https://s3.us-south.cloud-object-storage.appdomain.cloud",
                    region="custom-region",
                )

                call_kwargs = mock_session.client.call_args.kwargs
                assert call_kwargs["region_name"] == "custom-region"

    def test_client_function_with_credentials(self):
        """Test client() function with explicit credentials."""
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "chuk_artifacts.providers.ibm_cos.aioboto3.Session"
            ) as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session

                client(access_key="explicit_key", secret_key="explicit_secret")

                call_kwargs = mock_session.client.call_args.kwargs
                assert call_kwargs["aws_access_key_id"] == "explicit_key"
                assert call_kwargs["aws_secret_access_key"] == "explicit_secret"

    def test_client_function_config_parameters(self):
        """Test client() function sets correct config parameters."""
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "chuk_artifacts.providers.ibm_cos.aioboto3.Session"
            ) as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session

                client()

                call_kwargs = mock_session.client.call_args.kwargs
                config = call_kwargs["config"]

                # Verify AioConfig settings
                assert config.signature_version == "s3"
                assert config.s3 == {"addressing_style": "virtual"}
                assert config.read_timeout == 60
                assert config.connect_timeout == 30


class TestIBMCOSFactoryIntegration:
    """Test factory function with client function integration."""

    @pytest.mark.asyncio
    async def test_factory_uses_correct_defaults(self):
        """Test that factory creates client with correct defaults."""
        with patch.dict(
            os.environ,
            {"AWS_ACCESS_KEY_ID": "test_key", "AWS_SECRET_ACCESS_KEY": "test_secret"},
            clear=True,
        ):
            factory_func = factory()

            with patch(
                "chuk_artifacts.providers.ibm_cos.aioboto3.Session"
            ) as mock_session_class:
                mock_session = MagicMock()
                from unittest.mock import AsyncMock

                mock_client = AsyncMock()
                mock_session.client.return_value.__aenter__ = AsyncMock(
                    return_value=mock_client
                )
                mock_session.client.return_value.__aexit__ = AsyncMock(
                    return_value=None
                )
                mock_session_class.return_value = mock_session

                async with factory_func() as cos_client:
                    assert cos_client is mock_client

                # Verify default IBM COS endpoint was used
                call_kwargs = mock_session.client.call_args.kwargs
                assert (
                    "cloud-object-storage.appdomain.cloud"
                    in call_kwargs["endpoint_url"]
                )


class TestIBMCOSRegionDetection:
    """Test region detection logic comprehensively."""

    def test_region_detection_with_partial_match(self):
        """Test region detection works with partial string matches."""
        test_cases = [
            ("https://prefix.us-south.suffix.com", "us-south"),
            ("https://test-us-east-endpoint.com", "us-east"),
            ("https://eu-gb-test.example.com", "eu-gb"),
            ("https://no-known-region.com", "us-south"),  # Default
        ]

        for endpoint, expected_region in test_cases:
            with patch.dict(os.environ, {}, clear=True):
                with patch(
                    "chuk_artifacts.providers.ibm_cos.aioboto3.Session"
                ) as mock_session_class:
                    mock_session = MagicMock()
                    mock_session_class.return_value = mock_session

                    client(endpoint_url=endpoint)

                    call_kwargs = mock_session.client.call_args.kwargs
                    assert (
                        call_kwargs["region_name"] == expected_region
                    ), f"Failed for endpoint: {endpoint}, expected: {expected_region}, got: {call_kwargs['region_name']}"

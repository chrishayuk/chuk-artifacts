# -*- coding: utf-8 -*-
"""
Tests for multipart upload functionality.

Covers:
- Multipart upload initiation
- Part URL generation
- Upload completion
- Upload abortion
- Error handling
- Pydantic model usage
- Different scopes (session, user, sandbox)
"""

import os
import pytest

# IMPORTANT: Set environment variables first to use memory providers
os.environ["SESSION_PROVIDER"] = "memory"
os.environ["ARTIFACT_PROVIDER"] = "vfs-memory"

from chuk_artifacts import (  # noqa: E402
    ArtifactStore,
    MultipartUploadInitRequest,
    MultipartUploadCompleteRequest,
    MultipartUploadPart,
    ArtifactNotFoundError,
)


class TestMultipartUploadInitiation:
    """Test multipart upload initiation."""

    @pytest.mark.asyncio
    async def test_initiate_multipart_upload_basic(self):
        """Test basic multipart upload initiation."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            request = MultipartUploadInitRequest(
                filename="test_video.mp4",
                mime_type="video/mp4",
            )

            result = await store.initiate_multipart_upload(request)

            assert "upload_id" in result
            assert "artifact_id" in result
            assert "key" in result
            assert "session_id" in result
            assert result["upload_id"].startswith("upload-")

    @pytest.mark.asyncio
    async def test_initiate_multipart_upload_with_user_scope(self):
        """Test multipart upload with user scope."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            request = MultipartUploadInitRequest(
                filename="user_video.mp4",
                mime_type="video/mp4",
                user_id="alice",
                scope="user",
                ttl=86400,
            )

            result = await store.initiate_multipart_upload(request)

            assert "upload_id" in result
            assert "artifact_id" in result
            # Verify user-scoped path
            assert "/users/" in result["key"]

    @pytest.mark.asyncio
    async def test_initiate_multipart_upload_with_sandbox_scope(self):
        """Test multipart upload with sandbox scope."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            request = MultipartUploadInitRequest(
                filename="shared_assets.zip",
                mime_type="application/zip",
                scope="sandbox",
            )

            result = await store.initiate_multipart_upload(request)

            assert "upload_id" in result
            # Verify sandbox-scoped path
            assert "/shared/" in result["key"]

    @pytest.mark.asyncio
    async def test_initiate_multipart_upload_with_metadata(self):
        """Test multipart upload with custom metadata."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            request = MultipartUploadInitRequest(
                filename="dataset.tar.gz",
                mime_type="application/gzip",
                user_id="data-scientist",
                meta={"project": "ml-training", "version": "v2.0"},
            )

            result = await store.initiate_multipart_upload(request)

            assert "upload_id" in result
            assert result["upload_id"] is not None

    @pytest.mark.asyncio
    async def test_initiate_multipart_upload_user_scope_requires_user_id(self):
        """Test that user scope requires user_id."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            request = MultipartUploadInitRequest(
                filename="test.mp4",
                mime_type="video/mp4",
                scope="user",
                # Missing user_id
            )

            with pytest.raises(ValueError, match="user_id is required"):
                await store.initiate_multipart_upload(request)


class TestMultipartPartUpload:
    """Test multipart part upload URL generation."""

    @pytest.mark.asyncio
    async def test_get_part_upload_url_basic(self):
        """Test getting presigned URL for part upload."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Initiate upload
            init_request = MultipartUploadInitRequest(
                filename="large_file.bin",
                mime_type="application/octet-stream",
            )
            result = await store.initiate_multipart_upload(init_request)
            upload_id = result["upload_id"]

            # Get part URL
            url = await store.get_part_upload_url(upload_id, part_number=1)

            assert url is not None
            assert "memory://" in url or "http" in url

    @pytest.mark.asyncio
    async def test_get_part_upload_url_multiple_parts(self):
        """Test getting URLs for multiple parts."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Initiate upload
            init_request = MultipartUploadInitRequest(
                filename="large_file.bin",
                mime_type="application/octet-stream",
            )
            result = await store.initiate_multipart_upload(init_request)
            upload_id = result["upload_id"]

            # Get URLs for 3 parts
            urls = []
            for part_num in range(1, 4):
                url = await store.get_part_upload_url(upload_id, part_number=part_num)
                urls.append(url)

            assert len(urls) == 3
            assert all(url is not None for url in urls)

    @pytest.mark.asyncio
    async def test_get_part_upload_url_custom_expiry(self):
        """Test getting part URL with custom expiry."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Initiate upload
            init_request = MultipartUploadInitRequest(
                filename="large_file.bin",
                mime_type="application/octet-stream",
            )
            result = await store.initiate_multipart_upload(init_request)
            upload_id = result["upload_id"]

            # Get part URL with 7200 second expiry
            url = await store.get_part_upload_url(
                upload_id, part_number=1, expires=7200
            )

            assert url is not None

    @pytest.mark.asyncio
    async def test_get_part_upload_url_invalid_upload_id(self):
        """Test getting part URL with invalid upload ID."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            with pytest.raises(ArtifactNotFoundError):
                await store.get_part_upload_url("invalid-upload-id", part_number=1)

    @pytest.mark.asyncio
    async def test_get_part_upload_url_invalid_part_number(self):
        """Test getting part URL with invalid part number."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Initiate upload
            init_request = MultipartUploadInitRequest(
                filename="large_file.bin",
                mime_type="application/octet-stream",
            )
            result = await store.initiate_multipart_upload(init_request)
            upload_id = result["upload_id"]

            # Part number too low
            with pytest.raises(ValueError, match="between 1 and 10,000"):
                await store.get_part_upload_url(upload_id, part_number=0)

            # Part number too high
            with pytest.raises(ValueError, match="between 1 and 10,000"):
                await store.get_part_upload_url(upload_id, part_number=10001)


class TestMultipartUploadCompletion:
    """Test multipart upload completion."""

    @pytest.mark.asyncio
    async def test_complete_multipart_upload_basic(self):
        """Test completing a multipart upload."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Initiate upload
            init_request = MultipartUploadInitRequest(
                filename="complete_test.mp4",
                mime_type="video/mp4",
                user_id="alice",
            )
            result = await store.initiate_multipart_upload(init_request)
            upload_id = result["upload_id"]

            # Get part URLs (simulate uploading 2 parts)
            await store.get_part_upload_url(upload_id, part_number=1)
            await store.get_part_upload_url(upload_id, part_number=2)

            # Complete upload
            parts = [
                MultipartUploadPart(PartNumber=1, ETag="etag1"),
                MultipartUploadPart(PartNumber=2, ETag="etag2"),
            ]
            complete_request = MultipartUploadCompleteRequest(
                upload_id=upload_id,
                parts=parts,
                summary="Test multipart upload",
            )

            artifact_id = await store.complete_multipart_upload(complete_request)

            assert artifact_id is not None
            assert len(artifact_id) > 0

            # Verify artifact exists
            metadata = await store.metadata(artifact_id)
            assert metadata.mime == "video/mp4"
            assert metadata.filename == "complete_test.mp4"
            assert metadata.summary == "Test multipart upload"
            assert metadata.uploaded_via_presigned is True

    @pytest.mark.asyncio
    async def test_complete_multipart_upload_with_many_parts(self):
        """Test completing upload with many parts."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Initiate upload
            init_request = MultipartUploadInitRequest(
                filename="large_dataset.tar.gz",
                mime_type="application/gzip",
            )
            result = await store.initiate_multipart_upload(init_request)
            upload_id = result["upload_id"]

            # Simulate 10 parts
            num_parts = 10
            parts = []
            for part_num in range(1, num_parts + 1):
                await store.get_part_upload_url(upload_id, part_number=part_num)
                parts.append(
                    MultipartUploadPart(PartNumber=part_num, ETag=f"etag-{part_num}")
                )

            # Complete upload
            complete_request = MultipartUploadCompleteRequest(
                upload_id=upload_id,
                parts=parts,
                summary="Large dataset upload",
            )

            artifact_id = await store.complete_multipart_upload(complete_request)

            assert artifact_id is not None

            # Verify metadata
            metadata = await store.metadata(artifact_id)
            assert metadata.filename == "large_dataset.tar.gz"

    @pytest.mark.asyncio
    async def test_complete_multipart_upload_preserves_metadata(self):
        """Test that completion preserves metadata from initiation."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Initiate with metadata
            init_request = MultipartUploadInitRequest(
                filename="video_with_meta.mp4",
                mime_type="video/mp4",
                user_id="bob",
                scope="user",
                meta={"resolution": "4K", "fps": 60},
            )
            result = await store.initiate_multipart_upload(init_request)
            upload_id = result["upload_id"]

            # Get part URL
            await store.get_part_upload_url(upload_id, part_number=1)

            # Complete
            parts = [MultipartUploadPart(PartNumber=1, ETag="etag1")]
            complete_request = MultipartUploadCompleteRequest(
                upload_id=upload_id, parts=parts, summary="4K video"
            )

            artifact_id = await store.complete_multipart_upload(complete_request)

            # Verify metadata was preserved
            metadata = await store.metadata(artifact_id)
            assert metadata.scope == "user"
            assert metadata.owner_id == "bob"
            assert metadata.meta["resolution"] == "4K"
            assert metadata.meta["fps"] == 60

    @pytest.mark.asyncio
    async def test_complete_multipart_upload_invalid_upload_id(self):
        """Test completing with invalid upload ID."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            parts = [MultipartUploadPart(PartNumber=1, ETag="etag1")]
            complete_request = MultipartUploadCompleteRequest(
                upload_id="invalid-upload-id", parts=parts
            )

            with pytest.raises(ArtifactNotFoundError):
                await store.complete_multipart_upload(complete_request)

    @pytest.mark.asyncio
    async def test_complete_multipart_upload_empty_parts(self):
        """Test completing with empty parts list."""
        from pydantic import ValidationError

        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Initiate upload
            init_request = MultipartUploadInitRequest(
                filename="test.mp4",
                mime_type="video/mp4",
            )
            result = await store.initiate_multipart_upload(init_request)
            upload_id = result["upload_id"]

            # Try to complete with empty parts (Pydantic will reject this)
            with pytest.raises(ValidationError):
                _ = MultipartUploadCompleteRequest(upload_id=upload_id, parts=[])


class TestMultipartUploadAbortion:
    """Test multipart upload abortion."""

    @pytest.mark.asyncio
    async def test_abort_multipart_upload_basic(self):
        """Test aborting a multipart upload."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Initiate upload
            init_request = MultipartUploadInitRequest(
                filename="abort_test.mp4",
                mime_type="video/mp4",
            )
            result = await store.initiate_multipart_upload(init_request)
            upload_id = result["upload_id"]

            # Abort upload
            success = await store.abort_multipart_upload(upload_id)

            assert success is True

    @pytest.mark.asyncio
    async def test_abort_multipart_upload_after_parts(self):
        """Test aborting after uploading some parts."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Initiate upload
            init_request = MultipartUploadInitRequest(
                filename="partial_upload.mp4",
                mime_type="video/mp4",
            )
            result = await store.initiate_multipart_upload(init_request)
            upload_id = result["upload_id"]

            # Upload some parts
            await store.get_part_upload_url(upload_id, part_number=1)
            await store.get_part_upload_url(upload_id, part_number=2)

            # Abort
            success = await store.abort_multipart_upload(upload_id)

            assert success is True

            # Verify we can't get parts after abort
            with pytest.raises(ArtifactNotFoundError):
                await store.get_part_upload_url(upload_id, part_number=3)

    @pytest.mark.asyncio
    async def test_abort_multipart_upload_nonexistent(self):
        """Test aborting nonexistent upload (should succeed)."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Abort nonexistent upload (should return True)
            success = await store.abort_multipart_upload("nonexistent-upload-id")

            assert success is True

    @pytest.mark.asyncio
    async def test_abort_multipart_upload_cleans_metadata(self):
        """Test that abort cleans up metadata."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Initiate upload
            init_request = MultipartUploadInitRequest(
                filename="cleanup_test.mp4",
                mime_type="video/mp4",
            )
            result = await store.initiate_multipart_upload(init_request)
            upload_id = result["upload_id"]

            # Abort
            await store.abort_multipart_upload(upload_id)

            # Verify metadata is gone (trying to get part URL should fail)
            with pytest.raises(ArtifactNotFoundError):
                await store.get_part_upload_url(upload_id, part_number=1)


class TestMultipartPydanticModels:
    """Test Pydantic model validation."""

    def test_multipart_upload_init_request_validation(self):
        """Test MultipartUploadInitRequest validation."""
        # Valid request
        request = MultipartUploadInitRequest(
            filename="test.mp4",
            mime_type="video/mp4",
        )
        assert request.filename == "test.mp4"
        assert request.mime_type == "video/mp4"
        assert request.scope == "session"  # Default
        assert request.ttl == 900  # Default

        # Custom values
        request = MultipartUploadInitRequest(
            filename="custom.mp4",
            mime_type="video/mp4",
            user_id="alice",
            scope="user",
            ttl=3600,
            meta={"key": "value"},
        )
        assert request.user_id == "alice"
        assert request.scope == "user"
        assert request.ttl == 3600
        assert request.meta == {"key": "value"}

    def test_multipart_upload_part_validation(self):
        """Test MultipartUploadPart validation."""
        # Valid part
        part = MultipartUploadPart(PartNumber=1, ETag="abc123")
        assert part.PartNumber == 1
        assert part.ETag == "abc123"

        # Part number validation (too low)
        with pytest.raises(ValueError):
            MultipartUploadPart(PartNumber=0, ETag="abc123")

        # Part number validation (too high)
        with pytest.raises(ValueError):
            MultipartUploadPart(PartNumber=10001, ETag="abc123")

        # ETag required
        with pytest.raises(ValueError):
            MultipartUploadPart(PartNumber=1, ETag="")

    def test_multipart_upload_complete_request_validation(self):
        """Test MultipartUploadCompleteRequest validation."""
        parts = [
            MultipartUploadPart(PartNumber=1, ETag="etag1"),
            MultipartUploadPart(PartNumber=2, ETag="etag2"),
        ]

        # Valid request
        request = MultipartUploadCompleteRequest(
            upload_id="upload-abc123", parts=parts, summary="Test upload"
        )
        assert request.upload_id == "upload-abc123"
        assert len(request.parts) == 2
        assert request.summary == "Test upload"

        # Default summary
        request = MultipartUploadCompleteRequest(upload_id="upload-abc123", parts=parts)
        assert request.summary == "Multipart upload"

        # Upload ID required
        with pytest.raises(ValueError):
            MultipartUploadCompleteRequest(upload_id="", parts=parts)

        # Parts required
        with pytest.raises(ValueError):
            MultipartUploadCompleteRequest(upload_id="upload-abc123", parts=[])

    def test_multipart_upload_part_immutability(self):
        """Test that MultipartUploadPart is immutable."""
        part = MultipartUploadPart(PartNumber=1, ETag="abc123")

        # Should not be able to modify
        with pytest.raises(Exception):  # Pydantic raises ValidationError
            part.PartNumber = 2


class TestMultipartEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_multipart_workflow_complete_cycle(self):
        """Test complete multipart upload workflow."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # 1. Initiate
            init_request = MultipartUploadInitRequest(
                filename="complete_workflow.mp4",
                mime_type="video/mp4",
                user_id="test-user",
                scope="user",
                meta={"test": "data"},
            )
            init_result = await store.initiate_multipart_upload(init_request)
            upload_id = init_result["upload_id"]
            artifact_id = init_result["artifact_id"]

            # 2. Get part URLs
            url1 = await store.get_part_upload_url(upload_id, 1)
            url2 = await store.get_part_upload_url(upload_id, 2)
            url3 = await store.get_part_upload_url(upload_id, 3)

            assert all([url1, url2, url3])

            # 3. Complete
            parts = [
                MultipartUploadPart(PartNumber=1, ETag="etag1"),
                MultipartUploadPart(PartNumber=2, ETag="etag2"),
                MultipartUploadPart(PartNumber=3, ETag="etag3"),
            ]
            complete_request = MultipartUploadCompleteRequest(
                upload_id=upload_id, parts=parts, summary="Complete workflow test"
            )
            final_artifact_id = await store.complete_multipart_upload(complete_request)

            # 4. Verify
            assert final_artifact_id == artifact_id

            metadata = await store.metadata(final_artifact_id)
            assert metadata.filename == "complete_workflow.mp4"
            assert metadata.mime == "video/mp4"
            assert metadata.scope == "user"
            assert metadata.owner_id == "test-user"
            assert metadata.meta["test"] == "data"

    @pytest.mark.asyncio
    async def test_multipart_concurrent_uploads(self):
        """Test multiple concurrent multipart uploads."""
        import asyncio

        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:

            async def upload_file(filename: str):
                init_request = MultipartUploadInitRequest(
                    filename=filename, mime_type="application/octet-stream"
                )
                result = await store.initiate_multipart_upload(init_request)
                upload_id = result["upload_id"]

                # Get part URL
                await store.get_part_upload_url(upload_id, 1)

                # Complete
                parts = [MultipartUploadPart(PartNumber=1, ETag="etag1")]
                complete_request = MultipartUploadCompleteRequest(
                    upload_id=upload_id, parts=parts
                )
                return await store.complete_multipart_upload(complete_request)

            # Upload 5 files concurrently
            tasks = [upload_file(f"file_{i}.bin") for i in range(5)]
            artifact_ids = await asyncio.gather(*tasks)

            assert len(artifact_ids) == 5
            assert len(set(artifact_ids)) == 5  # All unique

    @pytest.mark.asyncio
    async def test_multipart_session_scope_default(self):
        """Test that session scope is the default."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            init_request = MultipartUploadInitRequest(
                filename="session_default.mp4", mime_type="video/mp4"
            )
            result = await store.initiate_multipart_upload(init_request)
            upload_id = result["upload_id"]

            # Complete minimal upload
            await store.get_part_upload_url(upload_id, 1)
            parts = [MultipartUploadPart(PartNumber=1, ETag="etag1")]
            complete_request = MultipartUploadCompleteRequest(
                upload_id=upload_id, parts=parts
            )
            artifact_id = await store.complete_multipart_upload(complete_request)

            # Verify scope is session
            metadata = await store.metadata(artifact_id)
            assert metadata.scope == "session"

    @pytest.mark.asyncio
    async def test_multipart_large_metadata(self):
        """Test multipart upload with large metadata."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Create large metadata
            large_meta = {f"key_{i}": f"value_{i}" for i in range(100)}

            init_request = MultipartUploadInitRequest(
                filename="large_meta.mp4",
                mime_type="video/mp4",
                meta=large_meta,
            )
            result = await store.initiate_multipart_upload(init_request)
            upload_id = result["upload_id"]

            # Complete
            await store.get_part_upload_url(upload_id, 1)
            parts = [MultipartUploadPart(PartNumber=1, ETag="etag1")]
            complete_request = MultipartUploadCompleteRequest(
                upload_id=upload_id, parts=parts
            )
            artifact_id = await store.complete_multipart_upload(complete_request)

            # Verify metadata preserved
            metadata = await store.metadata(artifact_id)
            assert len(metadata.meta) == 100
            assert metadata.meta["key_0"] == "value_0"


class TestMultipartErrorHandling:
    """Test error handling and edge cases in multipart uploads."""

    @pytest.mark.asyncio
    async def test_initiate_multipart_with_closed_store(self):
        """Test initiating multipart upload with closed store."""
        from chuk_artifacts import ArtifactStoreError

        store = ArtifactStore(storage_provider="vfs-memory", session_provider="memory")
        await store.close()

        init_request = MultipartUploadInitRequest(
            filename="test.mp4", mime_type="video/mp4"
        )

        with pytest.raises(ArtifactStoreError, match="closed"):
            await store.initiate_multipart_upload(init_request)

    @pytest.mark.asyncio
    async def test_get_part_upload_url_with_closed_store(self):
        """Test getting part URL with closed store."""
        from chuk_artifacts import ArtifactStoreError

        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            init_request = MultipartUploadInitRequest(
                filename="test.mp4", mime_type="video/mp4"
            )
            result = await store.initiate_multipart_upload(init_request)
            upload_id = result["upload_id"]

        # Store is now closed
        with pytest.raises(ArtifactStoreError, match="closed"):
            await store.get_part_upload_url(upload_id, 1)

    @pytest.mark.asyncio
    async def test_complete_multipart_with_closed_store(self):
        """Test completing multipart upload with closed store."""
        from chuk_artifacts import ArtifactStoreError

        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            init_request = MultipartUploadInitRequest(
                filename="test.mp4", mime_type="video/mp4"
            )
            result = await store.initiate_multipart_upload(init_request)
            upload_id = result["upload_id"]
            await store.get_part_upload_url(upload_id, 1)

        # Store is now closed
        parts = [MultipartUploadPart(PartNumber=1, ETag="etag1")]
        complete_request = MultipartUploadCompleteRequest(
            upload_id=upload_id, parts=parts
        )

        with pytest.raises(ArtifactStoreError, match="closed"):
            await store.complete_multipart_upload(complete_request)

    @pytest.mark.asyncio
    async def test_abort_multipart_with_closed_store(self):
        """Test aborting multipart upload with closed store."""
        from chuk_artifacts import ArtifactStoreError

        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            init_request = MultipartUploadInitRequest(
                filename="test.mp4", mime_type="video/mp4"
            )
            result = await store.initiate_multipart_upload(init_request)
            upload_id = result["upload_id"]

        # Store is now closed
        with pytest.raises(ArtifactStoreError, match="closed"):
            await store.abort_multipart_upload(upload_id)

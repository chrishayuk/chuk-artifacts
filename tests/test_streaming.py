# -*- coding: utf-8 -*-
"""
Tests for streaming upload/download functionality.

This test suite ensures streaming operations work correctly with:
- Progress callbacks
- Large files
- Access control
- Error handling
"""

import pytest
import asyncio
from chuk_artifacts import (
    ArtifactStore,
    StreamUploadRequest,
    StreamDownloadRequest,
)


class TestStreamingUpload:
    """Test streaming upload functionality."""

    @pytest.mark.asyncio
    async def test_basic_stream_upload(self):
        """Test basic streaming upload."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Generate test data stream
            async def data_generator():
                for i in range(10):
                    yield f"Chunk {i}\n".encode()

            request = StreamUploadRequest(
                data_stream=data_generator(),
                mime="text/plain",
                summary="Test streaming upload",
                filename="stream_test.txt",
                user_id="alice",
            )

            artifact_id = await store.stream_upload(request)
            assert artifact_id is not None

            # Verify stored data
            metadata = await store.metadata(artifact_id)
            assert metadata.mime == "text/plain"
            assert metadata.filename == "stream_test.txt"

    @pytest.mark.asyncio
    async def test_stream_upload_with_content_length(self):
        """Test streaming upload with known content length."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            test_data = b"Test data for streaming"

            async def data_generator():
                yield test_data

            request = StreamUploadRequest(
                data_stream=data_generator(),
                mime="application/octet-stream",
                summary="Test with content length",
                user_id="bob",
                content_length=len(test_data),
            )

            artifact_id = await store.stream_upload(request)
            metadata = await store.metadata(artifact_id)
            assert metadata.bytes == len(test_data)

    @pytest.mark.asyncio
    async def test_stream_upload_with_progress_callback(self):
        """Test streaming upload with progress tracking."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            progress_calls = []

            def progress_callback(bytes_sent, total_bytes):
                progress_calls.append((bytes_sent, total_bytes))

            chunk_size = 1024
            num_chunks = 10
            total_size = chunk_size * num_chunks

            async def data_generator():
                for _ in range(num_chunks):
                    yield b"X" * chunk_size

            request = StreamUploadRequest(
                data_stream=data_generator(),
                mime="application/octet-stream",
                summary="Test with progress",
                user_id="charlie",
                content_length=total_size,
                progress_callback=progress_callback,
            )

            await store.stream_upload(request)

            # Progress should have been called
            assert len(progress_calls) > 0

    @pytest.mark.asyncio
    async def test_stream_upload_user_scope(self):
        """Test streaming upload with user scope."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:

            async def data_generator():
                yield b"User scoped data"

            request = StreamUploadRequest(
                data_stream=data_generator(),
                mime="text/plain",
                summary="User scoped stream",
                user_id="dave",
                scope="user",
                ttl=3600,
            )

            artifact_id = await store.stream_upload(request)
            metadata = await store.metadata(artifact_id)
            assert metadata.scope == "user"
            assert metadata.owner_id == "dave"

    @pytest.mark.asyncio
    async def test_stream_upload_with_metadata(self):
        """Test streaming upload with custom metadata."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:

            async def data_generator():
                yield b"Data with metadata"

            custom_meta = {"source": "test", "version": "1.0"}

            request = StreamUploadRequest(
                data_stream=data_generator(),
                mime="application/json",
                summary="With custom metadata",
                user_id="eve",
                meta=custom_meta,
            )

            artifact_id = await store.stream_upload(request)
            metadata = await store.metadata(artifact_id)
            assert metadata.meta["source"] == "test"
            assert metadata.meta["version"] == "1.0"

    @pytest.mark.asyncio
    async def test_stream_upload_large_file(self):
        """Test streaming upload of large file."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            chunk_size = 65536  # 64KB
            num_chunks = 100  # ~6.4MB
            total_size = chunk_size * num_chunks

            async def data_generator():
                for _ in range(num_chunks):
                    yield b"X" * chunk_size

            request = StreamUploadRequest(
                data_stream=data_generator(),
                mime="application/octet-stream",
                summary="Large file stream",
                filename="large_file.bin",
                user_id="frank",
                content_length=total_size,
            )

            artifact_id = await store.stream_upload(request)
            metadata = await store.metadata(artifact_id)
            assert metadata.bytes == total_size

    @pytest.mark.asyncio
    async def test_stream_upload_requires_user_id_for_user_scope(self):
        """Test that user scope requires user_id."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:

            async def data_generator():
                yield b"Test data"

            request = StreamUploadRequest(
                data_stream=data_generator(),
                mime="text/plain",
                summary="User scope without user_id",
                scope="user",  # Requires user_id
            )

            with pytest.raises(ValueError, match="user_id is required"):
                await store.stream_upload(request)


class TestStreamingDownload:
    """Test streaming download functionality."""

    @pytest.mark.asyncio
    async def test_basic_stream_download(self):
        """Test basic streaming download."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Upload test data first
            test_data = b"Test data for download streaming"
            artifact_id = await store.store(
                data=test_data,
                mime="text/plain",
                summary="Test download",
                user_id="alice",
            )

            # Stream download
            request = StreamDownloadRequest(
                artifact_id=artifact_id,
                chunk_size=10,  # Small chunks to test streaming
            )

            chunks = []
            async for chunk in store.stream_download(request):
                chunks.append(chunk)

            # Verify data
            downloaded = b"".join(chunks)
            assert downloaded == test_data
            assert len(chunks) > 1  # Should be multiple chunks

    @pytest.mark.asyncio
    async def test_stream_download_with_progress_callback(self):
        """Test streaming download with progress tracking."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Upload test data
            test_data = b"X" * 10000
            artifact_id = await store.store(
                data=test_data,
                mime="application/octet-stream",
                summary="Test progress download",
                user_id="bob",
            )

            progress_calls = []

            def progress_callback(bytes_received, total_bytes):
                progress_calls.append((bytes_received, total_bytes))

            request = StreamDownloadRequest(
                artifact_id=artifact_id,
                chunk_size=1000,
                progress_callback=progress_callback,
            )

            chunks = []
            async for chunk in store.stream_download(request):
                chunks.append(chunk)

            # Progress should have been called
            assert len(progress_calls) > 0
            # Last call should have all bytes
            last_call = progress_calls[-1]
            assert last_call[0] == len(test_data)

    @pytest.mark.asyncio
    async def test_stream_download_with_access_control(self):
        """Test streaming download with access control."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Upload user-scoped data
            test_data = b"Private user data"
            artifact_id = await store.store(
                data=test_data,
                mime="text/plain",
                summary="Private data",
                user_id="charlie",
                scope="user",
            )

            # Download with correct user_id
            request = StreamDownloadRequest(
                artifact_id=artifact_id,
                user_id="charlie",
            )

            chunks = []
            async for chunk in store.stream_download(request):
                chunks.append(chunk)

            downloaded = b"".join(chunks)
            assert downloaded == test_data

    @pytest.mark.asyncio
    async def test_stream_download_access_denied(self):
        """Test streaming download access denied."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Upload user-scoped data
            artifact_id = await store.store(
                data=b"Private data",
                mime="text/plain",
                summary="Private",
                user_id="dave",
                scope="user",
            )

            # Try to download with wrong user_id
            request = StreamDownloadRequest(
                artifact_id=artifact_id,
                user_id="eve",  # Wrong user
            )

            from chuk_artifacts import AccessDeniedError

            with pytest.raises(AccessDeniedError):
                async for _ in store.stream_download(request):
                    pass

    @pytest.mark.asyncio
    async def test_stream_download_nonexistent_artifact(self):
        """Test streaming download of non-existent artifact."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            request = StreamDownloadRequest(
                artifact_id="nonexistent123",
            )

            from chuk_artifacts import ArtifactNotFoundError

            with pytest.raises(ArtifactNotFoundError):
                async for _ in store.stream_download(request):
                    pass

    @pytest.mark.asyncio
    async def test_stream_download_custom_chunk_size(self):
        """Test streaming download with custom chunk size."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Upload test data
            test_data = b"X" * 10000
            artifact_id = await store.store(
                data=test_data,
                mime="application/octet-stream",
                summary="Test chunk size",
                user_id="frank",
            )

            # Download with specific chunk size
            chunk_size = 500
            request = StreamDownloadRequest(
                artifact_id=artifact_id,
                chunk_size=chunk_size,
            )

            chunks = []
            async for chunk in store.stream_download(request):
                chunks.append(chunk)
                # Each chunk (except last) should be exactly chunk_size
                if len(chunks) < len(test_data) // chunk_size:
                    assert len(chunk) == chunk_size

            # Verify total data
            downloaded = b"".join(chunks)
            assert downloaded == test_data

    @pytest.mark.asyncio
    async def test_stream_download_large_file(self):
        """Test streaming download of large file."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Upload large file
            large_data = b"X" * (1024 * 1024)  # 1MB
            artifact_id = await store.store(
                data=large_data,
                mime="application/octet-stream",
                summary="Large file",
                user_id="grace",
            )

            # Stream download
            request = StreamDownloadRequest(
                artifact_id=artifact_id,
                chunk_size=65536,  # 64KB chunks
            )

            chunks = []
            async for chunk in store.stream_download(request):
                chunks.append(chunk)

            downloaded = b"".join(chunks)
            assert downloaded == large_data
            assert len(chunks) > 1  # Should be multiple chunks


class TestStreamingEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_stream_upload_empty_stream(self):
        """Test streaming upload with empty stream."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:

            async def empty_generator():
                # Empty generator
                return
                yield  # Never reached

            request = StreamUploadRequest(
                data_stream=empty_generator(),
                mime="text/plain",
                summary="Empty stream",
                user_id="alice",
            )

            artifact_id = await store.stream_upload(request)
            metadata = await store.metadata(artifact_id)
            assert metadata.bytes == 0

    @pytest.mark.asyncio
    async def test_stream_upload_single_chunk(self):
        """Test streaming upload with single chunk."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:

            async def single_chunk():
                yield b"Single chunk of data"

            request = StreamUploadRequest(
                data_stream=single_chunk(),
                mime="text/plain",
                summary="Single chunk",
                user_id="bob",
            )

            artifact_id = await store.stream_upload(request)
            metadata = await store.metadata(artifact_id)
            assert metadata.bytes == len(b"Single chunk of data")

    @pytest.mark.asyncio
    async def test_concurrent_streaming_operations(self):
        """Test concurrent streaming uploads and downloads."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            num_operations = 5

            async def upload_task(task_num):
                async def data_gen():
                    for i in range(10):
                        yield f"Task {task_num}, chunk {i}\n".encode()

                request = StreamUploadRequest(
                    data_stream=data_gen(),
                    mime="text/plain",
                    summary=f"Concurrent upload {task_num}",
                    user_id=f"user{task_num}",
                )
                return await store.stream_upload(request)

            # Upload concurrently
            artifact_ids = await asyncio.gather(
                *[upload_task(i) for i in range(num_operations)]
            )

            assert len(artifact_ids) == num_operations
            assert len(set(artifact_ids)) == num_operations  # All unique

            # Download concurrently
            async def download_task(artifact_id):
                request = StreamDownloadRequest(artifact_id=artifact_id)
                chunks = []
                async for chunk in store.stream_download(request):
                    chunks.append(chunk)
                return b"".join(chunks)

            downloaded_data = await asyncio.gather(
                *[download_task(aid) for aid in artifact_ids]
            )

            assert len(downloaded_data) == num_operations
            # All downloads should have data
            assert all(len(data) > 0 for data in downloaded_data)

    @pytest.mark.asyncio
    async def test_stream_upload_zero_chunks(self):
        """Test streaming upload with zero content."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:

            async def zero_gen():
                # Generator that yields nothing
                if False:
                    yield b""

            request = StreamUploadRequest(
                data_stream=zero_gen(),
                mime="text/plain",
                summary="Zero size",
                user_id="alice",
                content_length=0,
            )

            artifact_id = await store.stream_upload(request)
            metadata = await store.metadata(artifact_id)
            assert metadata.bytes == 0

    @pytest.mark.asyncio
    async def test_stream_operations_after_store_close(self):
        """Test that streaming operations fail after store is closed."""
        store = ArtifactStore(storage_provider="vfs-memory", session_provider="memory")

        # Store some data
        async def data_gen():
            yield b"test data"

        await store.__aenter__()

        request = StreamUploadRequest(
            data_stream=data_gen(),
            mime="text/plain",
            summary="Test",
            user_id="alice",
        )

        await store.stream_upload(request)

        # Close the store
        await store.__aexit__(None, None, None)

        # Try to stream upload after close

        async def another_gen():
            yield b"more data"

        request2 = StreamUploadRequest(
            data_stream=another_gen(),
            mime="text/plain",
            summary="After close",
            user_id="alice",
        )

        # This should raise an error about closed store
        from chuk_artifacts import ArtifactStoreError

        with pytest.raises(ArtifactStoreError, match="Store is closed"):
            await store.stream_upload(request2)


class TestStreamingFallbackPaths:
    """Test streaming with providers that don't support native streaming."""

    @pytest.mark.asyncio
    async def test_stream_upload_fallback_without_native_support(self):
        """Test streaming upload with provider that doesn't have put_object_stream."""
        async with ArtifactStore(
            storage_provider="memory", session_provider="memory"
        ) as store:
            # Generate test data
            test_chunks = [b"chunk1", b"chunk2", b"chunk3"]

            async def data_gen():
                for chunk in test_chunks:
                    yield chunk

            request = StreamUploadRequest(
                data_stream=data_gen(),
                mime="text/plain",
                summary="Fallback upload test",
                user_id="alice",
                content_length=sum(len(c) for c in test_chunks),
            )

            artifact_id = await store.stream_upload(request)
            assert artifact_id is not None

            # Verify data was stored correctly
            metadata = await store.metadata(artifact_id)
            assert metadata.bytes == sum(len(c) for c in test_chunks)

            # Verify can retrieve
            data = await store.retrieve(artifact_id)
            assert data == b"".join(test_chunks)

    @pytest.mark.asyncio
    async def test_stream_download_fallback_without_native_support(self):
        """Test streaming download with provider that doesn't have get_object_stream."""
        async with ArtifactStore(
            storage_provider="memory", session_provider="memory"
        ) as store:
            # Upload test data
            test_data = b"Test data for fallback download"
            artifact_id = await store.store(
                data=test_data,
                mime="text/plain",
                summary="Fallback download test",
                user_id="bob",
            )

            # Stream download using fallback path
            request = StreamDownloadRequest(
                artifact_id=artifact_id,
                chunk_size=10,  # Small chunks to test chunking
            )

            chunks = []
            async for chunk in store.stream_download(request):
                chunks.append(chunk)

            # Verify data
            downloaded = b"".join(chunks)
            assert downloaded == test_data
            assert len(chunks) > 1  # Should be multiple chunks

    @pytest.mark.asyncio
    async def test_stream_upload_fallback_with_progress(self):
        """Test streaming upload fallback with progress callbacks."""
        async with ArtifactStore(
            storage_provider="memory", session_provider="memory"
        ) as store:
            progress_calls = []

            def progress_callback(bytes_sent, total_bytes):
                progress_calls.append((bytes_sent, total_bytes))

            test_data = b"X" * 1000

            async def data_gen():
                # Yield in chunks
                for i in range(0, len(test_data), 100):
                    yield test_data[i : i + 100]

            request = StreamUploadRequest(
                data_stream=data_gen(),
                mime="application/octet-stream",
                summary="Fallback with progress",
                user_id="charlie",
                content_length=len(test_data),
                progress_callback=progress_callback,
            )

            await store.stream_upload(request)

            # Progress should have been called
            assert len(progress_calls) > 0
            # Last call should have total bytes
            final_bytes, final_total = progress_calls[-1]
            assert final_bytes == len(test_data)


class TestUpdateFileEdgeCases:
    """Test update_file edge cases for coverage."""

    @pytest.mark.asyncio
    async def test_update_with_ttl_parameter(self):
        """Test updating artifact with TTL parameter."""
        async with ArtifactStore(
            storage_provider="memory", session_provider="memory"
        ) as store:
            # Store initial artifact
            artifact_id = await store.store(
                data=b"original data",
                mime="text/plain",
                summary="Original",
                user_id="alice",
            )

            # Update with new TTL
            await store.update_file(
                artifact_id=artifact_id,
                data=b"updated data",
                ttl=1800,  # Different TTL
            )

            # Verify update
            metadata = await store.metadata(artifact_id)
            assert metadata.ttl == 1800

    @pytest.mark.asyncio
    async def test_update_with_no_parameters_raises_error(self):
        """Test that update with no parameters raises ValueError."""
        async with ArtifactStore(
            storage_provider="memory", session_provider="memory"
        ) as store:
            # Store initial artifact
            artifact_id = await store.store(
                data=b"original data",
                mime="text/plain",
                summary="Original",
                user_id="alice",
            )

            # Try to update with no parameters
            with pytest.raises(ValueError, match="At least one update parameter"):
                await store.update_file(artifact_id=artifact_id)


class TestStreamingIntegration:
    """Integration tests for streaming functionality."""

    @pytest.mark.asyncio
    async def test_stream_upload_and_regular_download(self):
        """Test streaming upload with regular (non-streaming) download."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            test_data = b"Test streaming upload, regular download"

            async def data_gen():
                yield test_data

            request = StreamUploadRequest(
                data_stream=data_gen(),
                mime="text/plain",
                summary="Stream up, regular down",
                user_id="alice",
            )

            artifact_id = await store.stream_upload(request)

            # Regular download
            downloaded = await store.retrieve(artifact_id)
            assert downloaded == test_data

    @pytest.mark.asyncio
    async def test_regular_upload_and_stream_download(self):
        """Test regular upload with streaming download."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            test_data = b"Test regular upload, streaming download"

            # Regular upload
            artifact_id = await store.store(
                data=test_data,
                mime="text/plain",
                summary="Regular up, stream down",
                user_id="bob",
            )

            # Streaming download
            request = StreamDownloadRequest(artifact_id=artifact_id)
            chunks = []
            async for chunk in store.stream_download(request):
                chunks.append(chunk)

            downloaded = b"".join(chunks)
            assert downloaded == test_data

    @pytest.mark.asyncio
    async def test_stream_roundtrip_preserves_data_integrity(self):
        """Test that streaming roundtrip preserves data integrity."""
        async with ArtifactStore(
            storage_provider="vfs-memory", session_provider="memory"
        ) as store:
            # Create test data with specific pattern
            test_data = b""
            for i in range(100):
                test_data += f"Line {i}: ".encode() + b"X" * 100 + b"\n"

            async def data_gen():
                # Upload in chunks
                chunk_size = 1024
                for i in range(0, len(test_data), chunk_size):
                    yield test_data[i : i + chunk_size]

            # Streaming upload
            request = StreamUploadRequest(
                data_stream=data_gen(),
                mime="text/plain",
                summary="Integrity test",
                user_id="charlie",
                content_length=len(test_data),
            )

            artifact_id = await store.stream_upload(request)

            # Streaming download
            download_request = StreamDownloadRequest(
                artifact_id=artifact_id, chunk_size=512
            )

            chunks = []
            async for chunk in store.stream_download(download_request):
                chunks.append(chunk)

            downloaded = b"".join(chunks)

            # Verify integrity
            assert len(downloaded) == len(test_data)
            assert downloaded == test_data

            # Verify metadata
            metadata = await store.metadata(artifact_id)
            assert metadata.bytes == len(test_data)
            assert metadata.sha256 is not None

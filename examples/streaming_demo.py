#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streaming Upload/Download Demo with Progress Tracking

This example demonstrates:
1. Streaming uploads for large files
2. Streaming downloads with progress callbacks
3. Memory-efficient processing of large artifacts
4. Real-time progress reporting
"""

# IMPORTANT: Set environment BEFORE importing chuk_artifacts
import os

os.environ.setdefault("SESSION_PROVIDER", "memory")
os.environ.setdefault("ARTIFACT_PROVIDER", "vfs-memory")

import asyncio  # noqa: E402
import time  # noqa: E402
from chuk_artifacts import (  # noqa: E402
    ArtifactStore,
    StreamUploadRequest,
    StreamDownloadRequest,
)


async def demo_basic_streaming():
    """Demo basic streaming upload and download."""
    print("\n" + "=" * 60)
    print("Basic Streaming Demo")
    print("=" * 60)

    async with ArtifactStore(
        storage_provider="vfs-memory", session_provider="memory"
    ) as store:
        # Create a large file in memory (10MB)
        chunk_size = 65536  # 64KB chunks
        num_chunks = 160  # 10MB total
        total_size = chunk_size * num_chunks

        print(f"\n✓ Creating {total_size / 1024 / 1024:.1f} MB test file")

        # Upload with streaming
        async def generate_chunks():
            """Generate chunks of test data."""
            for i in range(num_chunks):
                # Generate unique data for each chunk
                data = f"Chunk {i}: " + ("x" * (chunk_size - 20))
                yield data.encode()

        # Create upload request
        request = StreamUploadRequest(
            data_stream=generate_chunks(),
            mime="application/octet-stream",
            summary="Large test file (streaming upload)",
            filename="large_test_file.bin",
            user_id="alice",
            content_length=total_size,
        )

        print("Uploading...")
        start_time = time.time()
        artifact_id = await store.stream_upload(request)
        upload_time = time.time() - start_time
        print(
            f"✓ Uploaded in {upload_time:.2f}s "
            f"({total_size / upload_time / 1024 / 1024:.1f} MB/s)"
        )

        # Download with streaming
        download_request = StreamDownloadRequest(
            artifact_id=artifact_id,
            chunk_size=chunk_size,
        )

        print("\nDownloading...")
        start_time = time.time()
        bytes_received = 0
        async for chunk in store.stream_download(download_request):
            bytes_received += len(chunk)
            # In real app, you'd write to file or process

        download_time = time.time() - start_time
        print(
            f"✓ Downloaded {bytes_received / 1024 / 1024:.1f} MB in {download_time:.2f}s "
            f"({bytes_received / download_time / 1024 / 1024:.1f} MB/s)"
        )


async def demo_progress_tracking():
    """Demo streaming with detailed progress tracking."""
    print("\n" + "=" * 60)
    print("Progress Tracking Demo")
    print("=" * 60)

    async with ArtifactStore(
        storage_provider="vfs-memory", session_provider="memory"
    ) as store:
        # Create test data
        chunk_size = 65536  # 64KB
        num_chunks = 100  # ~6.4MB
        total_size = chunk_size * num_chunks

        print(f"\n✓ Preparing {total_size / 1024 / 1024:.1f} MB file")

        # Progress callback for upload
        def upload_progress(bytes_sent, total_bytes):
            if total_bytes:
                pct = (bytes_sent / total_bytes) * 100
                mb_sent = bytes_sent / 1024 / 1024
                mb_total = total_bytes / 1024 / 1024
                print(
                    f"  Upload: {pct:5.1f}% ({mb_sent:6.2f} / {mb_total:.2f} MB)",
                    end="\r",
                )

        # Upload with progress
        async def generate_test_data():
            for i in range(num_chunks):
                await asyncio.sleep(0.001)  # Simulate slow data source
                yield b"X" * chunk_size

        upload_request = StreamUploadRequest(
            data_stream=generate_test_data(),
            mime="application/octet-stream",
            summary="File with upload progress tracking",
            filename="progress_test.bin",
            user_id="bob",
            content_length=total_size,
            progress_callback=upload_progress,
        )

        print("\nUploading with progress tracking...")
        artifact_id = await store.stream_upload(upload_request)
        print("\n✓ Upload complete")

        # Progress callback for download
        def download_progress(bytes_received, total_bytes):
            if total_bytes:
                pct = (bytes_received / total_bytes) * 100
                mb_received = bytes_received / 1024 / 1024
                mb_total = total_bytes / 1024 / 1024
                print(
                    f"  Download: {pct:5.1f}% ({mb_received:6.2f} / {mb_total:.2f} MB)",
                    end="\r",
                )

        # Download with progress
        download_request = StreamDownloadRequest(
            artifact_id=artifact_id,
            user_id="bob",
            chunk_size=chunk_size,
            progress_callback=download_progress,
        )

        print("\nDownloading with progress tracking...")
        bytes_downloaded = 0
        async for chunk in store.stream_download(download_request):
            bytes_downloaded += len(chunk)
            await asyncio.sleep(0.001)  # Simulate slow processing

        print(f"\n✓ Download complete ({bytes_downloaded / 1024 / 1024:.1f} MB)")


async def demo_file_streaming():
    """Demo streaming from/to actual files."""
    print("\n" + "=" * 60)
    print("File Streaming Demo")
    print("=" * 60)

    import tempfile

    async with ArtifactStore(
        storage_provider="vfs-memory", session_provider="memory"
    ) as store:
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".dat") as tf:
            test_file = tf.name
            # Write 5MB test file
            test_data = b"Test data for streaming\n" * (1024 * 200)
            tf.write(test_data)
            file_size = len(test_data)

        print(f"\n✓ Created test file: {file_size / 1024 / 1024:.1f} MB")

        # Stream upload from file
        async def file_chunks():
            """Read file in chunks."""
            with open(test_file, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    yield chunk

        # Progress tracking
        upload_start = None

        def upload_progress(bytes_sent, total_bytes):
            nonlocal upload_start
            if upload_start is None:
                upload_start = time.time()

            if total_bytes:
                elapsed = time.time() - upload_start
                pct = (bytes_sent / total_bytes) * 100
                rate = bytes_sent / elapsed / 1024 / 1024 if elapsed > 0 else 0
                print(
                    f"  Upload: {pct:5.1f}% ({rate:.1f} MB/s)",
                    end="\r",
                )

        upload_request = StreamUploadRequest(
            data_stream=file_chunks(),
            mime="application/octet-stream",
            summary="Streamed from file",
            filename="streamed_file.dat",
            user_id="charlie",
            content_length=file_size,
            progress_callback=upload_progress,
        )

        print("\nStreaming upload from file...")
        artifact_id = await store.stream_upload(upload_request)
        print("\n✓ Upload complete")

        # Stream download to file
        output_file = test_file + ".downloaded"

        download_start = None

        def download_progress(bytes_received, total_bytes):
            nonlocal download_start
            if download_start is None:
                download_start = time.time()

            if total_bytes:
                elapsed = time.time() - download_start
                pct = (bytes_received / total_bytes) * 100
                rate = bytes_received / elapsed / 1024 / 1024 if elapsed > 0 else 0
                print(
                    f"  Download: {pct:5.1f}% ({rate:.1f} MB/s)",
                    end="\r",
                )

        download_request = StreamDownloadRequest(
            artifact_id=artifact_id,
            user_id="charlie",
            chunk_size=65536,
            progress_callback=download_progress,
        )

        print("\nStreaming download to file...")
        with open(output_file, "wb") as f:
            async for chunk in store.stream_download(download_request):
                f.write(chunk)

        print(f"\n✓ Download complete: {output_file}")

        # Verify file integrity
        with open(test_file, "rb") as f1, open(output_file, "rb") as f2:
            original = f1.read()
            downloaded = f2.read()
            if original == downloaded:
                print("✓ File integrity verified - data matches!")
            else:
                print("❌ File integrity check failed")

        # Cleanup
        os.unlink(test_file)
        os.unlink(output_file)


async def demo_concurrent_streaming():
    """Demo concurrent streaming operations."""
    print("\n" + "=" * 60)
    print("Concurrent Streaming Demo")
    print("=" * 60)

    async with ArtifactStore(
        storage_provider="vfs-memory", session_provider="memory"
    ) as store:
        # Upload multiple files concurrently
        num_files = 5
        file_size = 1024 * 1024  # 1MB each

        print(f"\n✓ Uploading {num_files} files concurrently...")

        async def upload_file(file_num):
            """Upload a single file."""

            async def generate_data():
                # Generate 1MB in 16 chunks (64KB each)
                for i in range(16):
                    yield f"File {file_num}, Chunk {i}: ".encode() + (
                        b"X" * (65536 - 30)
                    )

            request = StreamUploadRequest(
                data_stream=generate_data(),
                mime="application/octet-stream",
                summary=f"Concurrent test file {file_num}",
                filename=f"concurrent_{file_num}.bin",
                user_id=f"user{file_num}",
                content_length=file_size,
            )

            artifact_id = await store.stream_upload(request)
            print(f"  ✓ File {file_num} uploaded: {artifact_id}")
            return artifact_id

        # Upload all files concurrently
        start_time = time.time()
        artifact_ids = await asyncio.gather(*[upload_file(i) for i in range(num_files)])
        upload_time = time.time() - start_time

        total_mb = num_files * file_size / 1024 / 1024
        print(
            f"\n✓ Uploaded {total_mb:.1f} MB in {upload_time:.2f}s "
            f"({total_mb / upload_time:.1f} MB/s)"
        )

        # Download all files concurrently
        print(f"\nDownloading {num_files} files concurrently...")

        async def download_file(artifact_id, file_num):
            """Download a single file."""
            request = StreamDownloadRequest(
                artifact_id=artifact_id,
                user_id=f"user{file_num}",
                chunk_size=65536,
            )

            bytes_received = 0
            async for chunk in store.stream_download(request):
                bytes_received += len(chunk)

            print(f"  ✓ File {file_num} downloaded: {bytes_received / 1024:.0f} KB")
            return bytes_received

        start_time = time.time()
        sizes = await asyncio.gather(
            *[download_file(aid, i) for i, aid in enumerate(artifact_ids)]
        )
        download_time = time.time() - start_time

        total_downloaded = sum(sizes) / 1024 / 1024
        print(
            f"\n✓ Downloaded {total_downloaded:.1f} MB in {download_time:.2f}s "
            f"({total_downloaded / download_time:.1f} MB/s)"
        )


async def main():
    """Run all streaming demos."""
    print("\n" + "=" * 70)
    print(" CHUK-ARTIFACTS STREAMING DEMO")
    print(" Memory-Efficient Large File Operations")
    print("=" * 70)

    try:
        await demo_basic_streaming()
        await demo_progress_tracking()
        await demo_file_streaming()
        await demo_concurrent_streaming()

        print("\n" + "=" * 70)
        print(" All streaming demos completed successfully!")
        print("=" * 70)

        print("\n📊 Key Features Demonstrated:")
        print("  ✓ Streaming uploads - memory-efficient for large files")
        print("  ✓ Streaming downloads - chunked retrieval")
        print("  ✓ Progress callbacks - real-time status tracking")
        print("  ✓ File I/O streaming - direct file-to-storage")
        print("  ✓ Concurrent operations - parallel streaming")
        print("\n💡 Use Cases:")
        print("  • Video file uploads (GB+ files)")
        print("  • Dataset processing (large CSV/JSON)")
        print("  • Backup operations with progress tracking")
        print("  • Media transcoding pipelines")
        print("  • Real-time data ingestion")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

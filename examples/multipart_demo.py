#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multipart Upload Demo for Large Files

This example demonstrates:
1. Initiating multipart uploads for large files
2. Uploading parts with presigned URLs
3. Completing multipart uploads
4. Error handling and abort operations
5. Real-world use cases (video, datasets, media)
"""

# IMPORTANT: Set environment BEFORE importing chuk_artifacts
import os

os.environ.setdefault("SESSION_PROVIDER", "memory")
os.environ.setdefault("ARTIFACT_PROVIDER", "vfs-memory")

import asyncio  # noqa: E402
import time  # noqa: E402
from typing import List  # noqa: E402
from chuk_artifacts import (  # noqa: E402
    ArtifactStore,
    MultipartUploadInitRequest,
    MultipartUploadCompleteRequest,
    MultipartUploadPart,
)


async def demo_basic_multipart():
    """Demo basic multipart upload workflow."""
    print("\n" + "=" * 60)
    print("Basic Multipart Upload Demo")
    print("=" * 60)

    async with ArtifactStore(
        storage_provider="vfs-memory", session_provider="memory"
    ) as store:
        # Step 1: Initiate multipart upload
        print("\n📤 Step 1: Initiating multipart upload...")
        init_request = MultipartUploadInitRequest(
            filename="large_video.mp4",
            mime_type="video/mp4",
            user_id="alice",
            scope="user",
            ttl=3600,  # 1 hour
            meta={"project": "Q4-demo", "resolution": "4K"},
        )

        result = await store.initiate_multipart_upload(init_request)
        upload_id = result["upload_id"]
        artifact_id = result["artifact_id"]
        session_id = result["session_id"]

        print("✓ Upload initiated")
        print(f"  Upload ID: {upload_id}")
        print(f"  Artifact ID: {artifact_id}")
        print(f"  Session ID: {session_id}")

        # Step 2: Upload parts
        print("\n📦 Step 2: Getting presigned URLs and uploading parts...")

        # Simulate 3 parts of a large file
        num_parts = 3
        part_size = 5 * 1024 * 1024  # 5MB (minimum part size)
        parts: List[MultipartUploadPart] = []

        for part_num in range(1, num_parts + 1):
            # Get presigned URL for this part
            presigned_url = await store.get_part_upload_url(
                upload_id=upload_id, part_number=part_num, expires=3600
            )

            print(f"\n  Part {part_num}/{num_parts}:")
            print(f"    URL: {presigned_url[:80]}...")

            # Simulate uploading part data
            # In real scenario, client would PUT to this URL
            part_data = f"Part {part_num} data: " + ("x" * (part_size - 20))

            # Simulate ETag response from upload
            # In real scenario, this comes from the PUT response headers
            etag = f"etag-part-{part_num}-{hash(part_data) % 10000}"

            parts.append(MultipartUploadPart(PartNumber=part_num, ETag=etag))
            print(f"    ✓ Uploaded ({part_size / 1024 / 1024:.1f} MB)")
            print(f"    ETag: {etag}")

        # Step 3: Complete upload
        print("\n✅ Step 3: Completing multipart upload...")
        complete_request = MultipartUploadCompleteRequest(
            upload_id=upload_id,
            parts=parts,
            summary="Large 4K video upload (multipart)",
        )

        final_artifact_id = await store.complete_multipart_upload(complete_request)

        print("✓ Upload completed!")
        print(f"  Final Artifact ID: {final_artifact_id}")
        print(f"  Total size: {num_parts * part_size / 1024 / 1024:.1f} MB")

        # Verify artifact exists
        metadata = await store.metadata(final_artifact_id)
        print("\n📊 Artifact metadata:")
        print(f"  MIME: {metadata.mime}")
        print(f"  Filename: {metadata.filename}")
        print(f"  Size: {metadata.bytes / 1024 / 1024:.1f} MB")
        print(f"  Scope: {metadata.scope}")
        print(f"  Owner: {metadata.owner_id}")
        print(f"  Meta: {metadata.meta}")


async def demo_abort_multipart():
    """Demo aborting a multipart upload."""
    print("\n" + "=" * 60)
    print("Abort Multipart Upload Demo")
    print("=" * 60)

    async with ArtifactStore(
        storage_provider="vfs-memory", session_provider="memory"
    ) as store:
        # Initiate upload
        print("\n📤 Initiating upload...")
        init_request = MultipartUploadInitRequest(
            filename="incomplete_upload.mp4",
            mime_type="video/mp4",
            user_id="bob",
        )

        result = await store.initiate_multipart_upload(init_request)
        upload_id = result["upload_id"]
        print(f"✓ Upload ID: {upload_id}")

        # Upload one part
        print("\n📦 Uploading part 1...")
        _url = await store.get_part_upload_url(upload_id, part_number=1)
        print("✓ Got URL for part 1")

        # Simulate error - abort the upload
        print("\n❌ Error occurred! Aborting upload...")
        success = await store.abort_multipart_upload(upload_id)

        if success:
            print("✓ Upload aborted successfully")
            print("  All resources cleaned up")
        else:
            print("✗ Abort failed")


async def demo_large_file_workflow():
    """Demo realistic large file upload workflow."""
    print("\n" + "=" * 60)
    print("Large File Upload Workflow (Realistic)")
    print("=" * 60)

    async with ArtifactStore(
        storage_provider="vfs-memory", session_provider="memory"
    ) as store:
        # Simulate uploading a 100MB file
        file_size = 100 * 1024 * 1024  # 100MB
        part_size = 10 * 1024 * 1024  # 10MB per part
        num_parts = (file_size + part_size - 1) // part_size  # Ceiling division

        print("\n📁 File details:")
        print(f"  Total size: {file_size / 1024 / 1024:.1f} MB")
        print(f"  Part size: {part_size / 1024 / 1024:.1f} MB")
        print(f"  Number of parts: {num_parts}")

        # Step 1: Initiate
        print("\n📤 Initiating multipart upload...")
        start_time = time.time()

        init_request = MultipartUploadInitRequest(
            filename="large_dataset.tar.gz",
            mime_type="application/gzip",
            user_id="data-scientist",
            scope="user",
            ttl=86400,  # 24 hours
            meta={
                "dataset": "ml-training-data",
                "version": "v2.1",
                "compressed": True,
            },
        )

        result = await store.initiate_multipart_upload(init_request)
        upload_id = result["upload_id"]
        print(f"✓ Upload ID: {upload_id}")

        # Step 2: Upload parts with progress
        print(f"\n📦 Uploading {num_parts} parts...")
        parts: List[MultipartUploadPart] = []

        for part_num in range(1, num_parts + 1):
            # Get presigned URL
            _url = await store.get_part_upload_url(upload_id, part_num)

            # Simulate upload (in real scenario, client PUTs to URL)
            # Show progress
            progress = (part_num / num_parts) * 100
            print(
                f"  [{part_num}/{num_parts}] Progress: {progress:.1f}% ",
                end="",
                flush=True,
            )

            # Simulate upload time
            await asyncio.sleep(0.1)

            # Mock ETag from response
            etag = f"etag-{upload_id}-part-{part_num}"
            parts.append(MultipartUploadPart(PartNumber=part_num, ETag=etag))
            print("✓")

        # Step 3: Complete
        print("\n✅ Completing upload...")
        complete_request = MultipartUploadCompleteRequest(
            upload_id=upload_id,
            parts=parts,
            summary="ML training dataset (multipart upload)",
        )

        artifact_id = await store.complete_multipart_upload(complete_request)
        elapsed = time.time() - start_time

        print(f"\n✓ Upload completed in {elapsed:.2f}s")
        print(f"  Artifact ID: {artifact_id}")
        print(
            f"  Average speed: {file_size / elapsed / 1024 / 1024:.1f} MB/s (simulated)"
        )

        # Get final metadata
        metadata = await store.metadata(artifact_id)
        print("\n📊 Final artifact:")
        print(f"  Filename: {metadata.filename}")
        print(f"  Size: {metadata.bytes / 1024 / 1024:.1f} MB")
        print(f"  MIME: {metadata.mime}")
        print("  Uploaded via: presigned URLs")


async def demo_scope_examples():
    """Demo different scope types for multipart uploads."""
    print("\n" + "=" * 60)
    print("Multipart Upload Scopes Demo")
    print("=" * 60)

    async with ArtifactStore(
        storage_provider="vfs-memory", session_provider="memory"
    ) as store:
        # 1. Session-scoped (ephemeral)
        print("\n1️⃣ Session-scoped upload (ephemeral):")
        init_request = MultipartUploadInitRequest(
            filename="temp_render.mp4",
            mime_type="video/mp4",
            scope="session",  # Default
            ttl=900,  # 15 minutes
        )
        result = await store.initiate_multipart_upload(init_request)
        print(f"   ✓ Upload ID: {result['upload_id']}")
        print("   Scope: session (ephemeral)")
        print("   TTL: 15 minutes")

        # Clean up
        await store.abort_multipart_upload(result["upload_id"])

        # 2. User-scoped (persistent)
        print("\n2️⃣ User-scoped upload (persistent):")
        init_request = MultipartUploadInitRequest(
            filename="user_profile_video.mp4",
            mime_type="video/mp4",
            user_id="alice",
            scope="user",
            ttl=86400 * 30,  # 30 days
        )
        result = await store.initiate_multipart_upload(init_request)
        print(f"   ✓ Upload ID: {result['upload_id']}")
        print("   Scope: user (persistent)")
        print("   Owner: alice")
        print("   TTL: 30 days")

        # Clean up
        await store.abort_multipart_upload(result["upload_id"])

        # 3. Sandbox-scoped (shared)
        print("\n3️⃣ Sandbox-scoped upload (shared):")
        init_request = MultipartUploadInitRequest(
            filename="shared_assets.zip",
            mime_type="application/zip",
            scope="sandbox",
            ttl=86400 * 90,  # 90 days
        )
        result = await store.initiate_multipart_upload(init_request)
        print(f"   ✓ Upload ID: {result['upload_id']}")
        print("   Scope: sandbox (shared)")
        print("   TTL: 90 days")

        # Clean up
        await store.abort_multipart_upload(result["upload_id"])


async def demo_use_cases():
    """Demo real-world use cases."""
    print("\n" + "=" * 60)
    print("Real-World Use Cases")
    print("=" * 60)

    async with ArtifactStore(
        storage_provider="vfs-memory", session_provider="memory"
    ) as store:
        use_cases = [
            {
                "name": "Video Upload (Remotion)",
                "filename": "rendered_video_4k.mp4",
                "mime": "video/mp4",
                "size_mb": 250,
                "meta": {"renderer": "remotion", "fps": 60, "resolution": "3840x2160"},
            },
            {
                "name": "Audio Dataset",
                "filename": "speech_training_data.tar.gz",
                "mime": "application/gzip",
                "size_mb": 500,
                "meta": {"format": "wav", "sample_rate": 48000, "duration_hours": 100},
            },
            {
                "name": "PPTX Generation",
                "filename": "generated_presentation.pptx",
                "mime": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "size_mb": 50,
                "meta": {
                    "slides": 150,
                    "template": "corporate",
                    "with_animations": True,
                },
            },
            {
                "name": "Image Pipeline Output",
                "filename": "batch_processed_images.zip",
                "mime": "application/zip",
                "size_mb": 300,
                "meta": {"count": 1000, "format": "png", "dimensions": "4096x4096"},
            },
        ]

        for i, use_case in enumerate(use_cases, 1):
            print(f"\n{i}. {use_case['name']}:")
            print(f"   File: {use_case['filename']}")
            print(f"   Size: {use_case['size_mb']} MB")
            print(f"   Type: {use_case['mime']}")
            print(f"   Metadata: {use_case['meta']}")

            # Initiate
            init_request = MultipartUploadInitRequest(
                filename=use_case["filename"],
                mime_type=use_case["mime"],
                user_id=f"user-{i}",
                scope="user",
                meta=use_case["meta"],
            )
            result = await store.initiate_multipart_upload(init_request)
            print(f"   ✓ Upload ID: {result['upload_id'][:16]}...")

            # Clean up (in real scenario, would upload parts and complete)
            await store.abort_multipart_upload(result["upload_id"])


async def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("🎬 MULTIPART UPLOAD DEMO")
    print("=" * 60)
    print("\nDemonstrating multipart uploads for large files:")
    print("- Large videos (Remotion, media pipelines)")
    print("- Audio datasets")
    print("- Generated documents (PPTX)")
    print("- Batch processed images")
    print("\nMinimum part size: 5MB (except last part)")
    print("Maximum parts: 10,000 per upload")

    # Run demos
    await demo_basic_multipart()
    await demo_abort_multipart()
    await demo_large_file_workflow()
    await demo_scope_examples()
    await demo_use_cases()

    print("\n" + "=" * 60)
    print("✅ All demos completed!")
    print("=" * 60)
    print("\n💡 Key takeaways:")
    print("  1. Use MultipartUploadInitRequest to start uploads")
    print("  2. Get presigned URLs for each part")
    print("  3. Client uploads parts to presigned URLs")
    print("  4. Complete with MultipartUploadCompleteRequest")
    print("  5. Abort if upload fails or is cancelled")
    print("\n📚 See README for full documentation")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VFS Provider Demo - Showcasing chuk-virtual-fs integration

This demo shows how to use the new VFS-backed storage providers in chuk-artifacts.
VFS (Virtual File System) provides a unified interface to multiple storage backends.
"""

# IMPORTANT: Set environment BEFORE importing chuk_artifacts
# This ensures SessionManager picks up the correct provider
import os

os.environ.setdefault("SESSION_PROVIDER", "memory")
os.environ.setdefault("ARTIFACT_PROVIDER", "vfs-memory")

import asyncio  # noqa: E402
from chuk_artifacts import ArtifactStore  # noqa: E402


async def demo_vfs_memory():
    """Demo VFS memory provider - fast, ephemeral storage"""
    print("\n" + "=" * 60)
    print("VFS Memory Provider Demo")
    print("=" * 60)

    # Use VFS memory provider (backed by chuk-virtual-fs)
    # Also use memory session provider for no external dependencies
    async with ArtifactStore(
        storage_provider="vfs-memory", session_provider="memory"
    ) as store:
        print("✓ Initialized VFS memory provider")

        # Store an artifact
        artifact_id = await store.store(
            data=b"Hello from VFS!",
            mime="text/plain",
            summary="Test artifact using VFS memory backend",
            filename="test.txt",
        )
        print(f"✓ Stored artifact: {artifact_id}")

        # Retrieve it
        data = await store.retrieve(artifact_id)
        print(f"✓ Retrieved: {data.decode()}")

        # Get metadata
        metadata = await store.metadata(artifact_id)
        print(f"✓ Storage provider: {metadata.storage_provider}")
        print(f"✓ Session ID: {metadata.session_id}")


async def demo_vfs_filesystem():
    """Demo VFS filesystem provider - local disk storage"""
    print("\n" + "=" * 60)
    print("VFS Filesystem Provider Demo")
    print("=" * 60)

    # Use VFS filesystem provider (backed by chuk-virtual-fs)
    # Files are stored in /tmp/artifacts by default
    async with ArtifactStore(
        storage_provider="vfs-filesystem", session_provider="memory"
    ) as store:
        print("✓ Initialized VFS filesystem provider")

        # Store a larger file
        data = b"This is a test file stored via VFS filesystem backend.\n" * 10
        artifact_id = await store.store(
            data=data,
            mime="text/plain",
            summary="Test file using VFS filesystem backend",
            filename="filesystem_test.txt",
            meta={"vfs_backend": "filesystem"},
        )
        print(f"✓ Stored artifact: {artifact_id}")

        # Retrieve and verify
        retrieved = await store.retrieve(artifact_id)
        assert retrieved == data
        print(f"✓ Retrieved and verified {len(retrieved)} bytes")

        # Check metadata
        metadata = await store.metadata(artifact_id)
        print(f"✓ Grid path: {metadata.key}")
        print(f"✓ Custom meta: {metadata.meta}")


async def demo_vfs_comparison():
    """Compare legacy vs VFS providers"""
    print("\n" + "=" * 60)
    print("Legacy vs VFS Provider Comparison")
    print("=" * 60)

    test_data = b"Comparison test data"

    # Legacy memory provider
    async with ArtifactStore(
        storage_provider="memory", session_provider="memory"
    ) as store_legacy:
        artifact_id_legacy = await store_legacy.store(
            data=test_data,
            mime="text/plain",
            summary="Legacy memory provider",
        )
        print(f"✓ Legacy memory: {artifact_id_legacy}")

    # VFS memory provider
    async with ArtifactStore(
        storage_provider="vfs-memory", session_provider="memory"
    ) as store_vfs:
        artifact_id_vfs = await store_vfs.store(
            data=test_data,
            mime="text/plain",
            summary="VFS memory provider",
        )
        print(f"✓ VFS memory: {artifact_id_vfs}")

    print("\nBoth providers work identically from user perspective!")
    print("VFS provides unified interface + future streaming/mount features")


async def demo_scoped_storage():
    """Demo scope-based storage with VFS"""
    print("\n" + "=" * 60)
    print("Scoped Storage with VFS")
    print("=" * 60)

    async with ArtifactStore(
        storage_provider="vfs-memory", session_provider="memory"
    ) as store:
        # Session-scoped (default, ephemeral)
        session_id = await store.store(
            data=b"Temporary session data",
            mime="text/plain",
            summary="Session-scoped artifact",
            scope="session",
            ttl=900,  # 15 minutes
        )
        print(f"✓ Session-scoped: {session_id}")

        # User-scoped (persistent)
        user_id = await store.store(
            data=b"User persistent data",
            mime="application/json",
            summary="User's personal artifact",
            scope="user",
            user_id="alice",
            ttl=86400 * 365,  # 1 year (very long-lived)
        )
        print(f"✓ User-scoped: {user_id}")

        # Sandbox-scoped (shared resources)
        sandbox_id = await store.store(
            data=b"Shared template",
            mime="text/html",
            summary="Shared sandbox resource",
            scope="sandbox",
        )
        print(f"✓ Sandbox-scoped: {sandbox_id}")

        # Search user artifacts
        user_artifacts = await store.search(
            user_id="alice",
            scope="user",
        )
        print(f"✓ Found {len(user_artifacts)} user artifacts")


async def demo_vfs_features():
    """Showcase VFS-specific features"""
    print("\n" + "=" * 60)
    print("VFS-Specific Features")
    print("=" * 60)

    async with ArtifactStore(
        storage_provider="vfs-memory", session_provider="memory"
    ) as store:
        print("✓ VFS provider initialized")

        # Store nested path (VFS auto-creates directories)
        artifact_id = await store.store(
            data=b"Nested data",
            mime="text/plain",
            summary="Artifact with nested path",
            filename="folder/subfolder/nested.txt",
        )
        print(f"✓ Stored nested artifact: {artifact_id}")

        # List all artifacts
        session_info = await store.get_session_info(
            (await store.metadata(artifact_id)).session_id
        )
        print(f"✓ Session info available: {session_info is not None}")

        # Get storage stats
        stats = await store.get_stats()
        print("✓ Storage stats:")
        print(f"  - Provider: {stats.get('provider', 'N/A')}")
        print(
            f"  - Operations: {stats.get('session_manager', {}).get('cache_hits', 0)} cache hits"
        )


async def main():
    """Run all VFS demos"""
    print("\n" + "=" * 70)
    print(" CHUK-ARTIFACTS VFS PROVIDER DEMO")
    print(" Powered by chuk-virtual-fs")
    print("=" * 70)

    try:
        # Run demos
        await demo_vfs_memory()
        await demo_vfs_filesystem()
        await demo_vfs_comparison()
        await demo_scoped_storage()
        await demo_vfs_features()

        print("\n" + "=" * 70)
        print(" All VFS demos completed successfully!")
        print("=" * 70)
        print("\nAvailable VFS Providers:")
        print("  - vfs-memory      : In-memory storage (fast, ephemeral)")
        print("  - vfs-filesystem  : Local filesystem storage")
        print("  - vfs-s3          : AWS S3 or S3-compatible storage")
        print("  - vfs-sqlite      : SQLite database storage")
        print("\nFuture VFS Features (Phase 2+):")
        print("  - Streaming for large files (video/audio)")
        print("  - Progress callbacks for uploads/downloads")
        print("  - Virtual mounts (mix providers per scope)")
        print("  - Advanced security profiles")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

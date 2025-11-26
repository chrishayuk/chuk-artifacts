#!/usr/bin/env python3
"""
Quick Start: Unified Namespace API

The simplest example showing the unified "everything is VFS" architecture.
"""

import asyncio

from chuk_artifacts import ArtifactStore, NamespaceType, StorageScope


async def main():
    store = ArtifactStore()

    print("🚀 chuk-artifacts Unified Namespace API - Quick Start\n")

    # =================================================================
    # BLOB NAMESPACE (Single file storage)
    # =================================================================
    print("📦 BLOB Namespace:")

    # Create blob namespace
    blob = await store.create_namespace(
        type=NamespaceType.BLOB,
        scope=StorageScope.SESSION,
    )
    print(f"  ✓ Created: {blob.namespace_id}")

    # Write data
    await store.write_namespace(blob.namespace_id, data=b"Hello, World!")

    # Read data
    data = await store.read_namespace(blob.namespace_id)
    print(f"  ✓ Data: {data.decode()}\n")

    # =================================================================
    # WORKSPACE NAMESPACE (Multi-file storage)
    # =================================================================
    print("📁 WORKSPACE Namespace:")

    # Create workspace namespace
    workspace = await store.create_namespace(
        type=NamespaceType.WORKSPACE,
        name="my-project",
        scope=StorageScope.SESSION,
    )
    print(f"  ✓ Created: {workspace.name} ({workspace.namespace_id})")

    # Write files
    await store.write_namespace(
        workspace.namespace_id, path="/main.py", data=b"print('hello')"
    )
    await store.write_namespace(
        workspace.namespace_id, path="/config.json", data=b'{"version": "1.0"}'
    )

    # Get VFS for advanced operations
    vfs = store.get_namespace_vfs(workspace.namespace_id)
    files = await vfs.ls("/")
    print(f"  ✓ Files: {files}\n")

    # =================================================================
    # CHECKPOINTS (Work for both types!)
    # =================================================================
    print("💾 Checkpoints:")

    # Checkpoint blob
    blob_cp = await store.checkpoint_namespace(blob.namespace_id, name="blob-v1")
    print(f"  ✓ Blob checkpoint: {blob_cp.name}")

    # Checkpoint workspace
    ws_cp = await store.checkpoint_namespace(workspace.namespace_id, name="ws-v1")
    print(f"  ✓ Workspace checkpoint: {ws_cp.name}\n")

    # =================================================================
    # SUMMARY
    # =================================================================
    print("✨ Everything is VFS:")
    print("  • Same API for blobs and workspaces")
    print("  • Same checkpoints, scoping, session management")
    print("  • Only difference: BLOB=single file, WORKSPACE=file tree")
    print("\n✅ Quick start complete!")

    # Cleanup
    await store.destroy_namespace(blob.namespace_id)
    await store.destroy_namespace(workspace.namespace_id)


if __name__ == "__main__":
    asyncio.run(main())

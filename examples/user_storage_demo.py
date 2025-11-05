#!/usr/bin/env python3
"""
User Storage Demo - Phase 1 Scope-Based Storage

Demonstrates the new scope-based storage capabilities:
- Session scope (ephemeral, default)
- User scope (persistent across sessions)
- Sandbox scope (shared by all users)
"""

import asyncio
import os
from chuk_artifacts import ArtifactStore


async def demo_session_scope():
    """Demonstrate session-scoped storage (default, ephemeral)."""
    print("=" * 70)
    print("SESSION-SCOPED STORAGE (Ephemeral)")
    print("=" * 70)

    os.environ["ARTIFACT_PROVIDER"] = "memory"
    os.environ["SESSION_PROVIDER"] = "memory"

    async with ArtifactStore(sandbox_id="demo") as store:
        # Session-scoped (default behavior - unchanged from before)
        artifact_id = await store.store(
            data=b"Temporary session data",
            mime="text/plain",
            summary="Session work file",
            user_id="alice",
            # scope="session" is the default
        )

        print(f"✓ Stored session-scoped artifact: {artifact_id}")

        # Retrieve requires the same session
        metadata = await store.metadata(artifact_id)
        print(f"  Metadata type: {type(metadata)}")
        print(f"  Session ID: {metadata.session_id}")
        print(f"  Scope: {metadata.scope}")
        print(f"  Key: {metadata.key}")

        # Can retrieve with session_id
        data = await store.retrieve(artifact_id, session_id=metadata.session_id)
        print(f"  ✓ Retrieved: {data.decode()}")

        # Cannot retrieve from different session
        try:
            await store.retrieve(artifact_id, session_id="different-session")
            print("  ❌ Should have denied access!")
        except Exception as e:
            print(f"  ✓ Access denied (expected): {e.__class__.__name__}")


async def demo_user_scope():
    """Demonstrate user-scoped storage (persistent)."""
    print("\n" + "=" * 70)
    print("USER-SCOPED STORAGE (Persistent)")
    print("=" * 70)

    os.environ["ARTIFACT_PROVIDER"] = "memory"
    os.environ["SESSION_PROVIDER"] = "memory"

    async with ArtifactStore(sandbox_id="demo") as store:
        # User-scoped: Persistent across sessions
        artifact_id = await store.store(
            data=b"User's persistent document",
            mime="text/plain",
            summary="User's saved file",
            filename="my_document.txt",
            user_id="alice",
            scope="user",  # USER SCOPE - persists!
            ttl=86400 * 365,  # 1 year
        )

        print(f"✓ Stored user-scoped artifact: {artifact_id}")

        metadata = await store.metadata(artifact_id)
        print(f"  Scope: {metadata.scope}")
        print(f"  Owner: {metadata.owner_id}")
        print(f"  Key: {metadata.key}")
        print("  Note: Can be accessed from ANY of Alice's sessions!")

        # Can retrieve with user_id (any session)
        data = await store.retrieve(artifact_id, user_id="alice")
        print(f"  ✓ Retrieved: {data.decode()}")

        # Cannot retrieve as different user
        try:
            await store.retrieve(artifact_id, user_id="bob")
            print("  ❌ Should have denied access!")
        except Exception as e:
            print(f"  ✓ Cross-user access denied (expected): {e.__class__.__name__}")


async def demo_sandbox_scope():
    """Demonstrate sandbox-scoped storage (shared)."""
    print("\n" + "=" * 70)
    print("SANDBOX-SCOPED STORAGE (Shared)")
    print("=" * 70)

    os.environ["ARTIFACT_PROVIDER"] = "memory"
    os.environ["SESSION_PROVIDER"] = "memory"

    async with ArtifactStore(sandbox_id="demo") as store:
        # Sandbox-scoped: Shared by everyone in the sandbox
        artifact_id = await store.store(
            data=b"Shared template for all users",
            mime="text/plain",
            summary="Company template",
            filename="template.txt",
            scope="sandbox",  # SANDBOX SCOPE - shared!
            ttl=86400 * 365,  # Long-lived
        )

        print(f"✓ Stored sandbox-scoped artifact: {artifact_id}")

        metadata = await store.metadata(artifact_id)
        print(f"  Scope: {metadata.scope}")
        print(f"  Key: {metadata.key}")
        print("  Note: Any user in sandbox can read this!")

        # Anyone in the sandbox can read
        data = await store.retrieve(artifact_id, user_id="alice")
        print(f"  ✓ Alice retrieved: {data.decode()}")

        data = await store.retrieve(artifact_id, user_id="bob")
        print(f"  ✓ Bob retrieved: {data.decode()}")

        # But sandbox artifacts cannot be deleted via regular API
        try:
            await store.delete(artifact_id, user_id="alice")
            print("  ❌ Should have denied deletion!")
        except Exception as e:
            print(f"  ✓ Deletion denied (expected): {e.__class__.__name__}")
            print("     Note: Use admin endpoints to manage sandbox artifacts")


async def demo_search():
    """Demonstrate searching user artifacts."""
    print("\n" + "=" * 70)
    print("SEARCH USER ARTIFACTS")
    print("=" * 70)

    os.environ["ARTIFACT_PROVIDER"] = "memory"
    os.environ["SESSION_PROVIDER"] = "memory"

    async with ArtifactStore(sandbox_id="demo") as store:
        # Create multiple user artifacts
        print("Creating test artifacts...")

        await store.store(
            data=b"Document 1",
            mime="text/plain",
            summary="Project doc",
            user_id="alice",
            scope="user",
            meta={"project": "Q4", "type": "doc"},
        )

        await store.store(
            data=b"Image data",
            mime="image/png",
            summary="Project image",
            user_id="alice",
            scope="user",
            meta={"project": "Q4", "type": "image"},
        )

        await store.store(
            data=b"Document 2",
            mime="text/plain",
            summary="Different project",
            user_id="alice",
            scope="user",
            meta={"project": "Q3", "type": "doc"},
        )

        print("✓ Created 3 user artifacts\n")

        # Search all Alice's artifacts
        results = await store.search(user_id="alice", scope="user")
        print(f"All Alice's user artifacts: {len(results)}")
        for r in results:
            print(f"  - {r.summary} ({r.mime})")

        # Search by MIME type
        images = await store.search(user_id="alice", scope="user", mime_prefix="image/")
        print(f"\nAlice's images: {len(images)}")
        for r in images:
            print(f"  - {r.summary}")

        # Search by metadata
        q4_artifacts = await store.search(
            user_id="alice", scope="user", meta_filter={"project": "Q4"}
        )
        print(f"\nAlice's Q4 project artifacts: {len(q4_artifacts)}")
        for r in q4_artifacts:
            print(f"  - {r.summary} (type: {r.meta.get('type')})")


async def demo_mcp_workflow():
    """Demonstrate MCP server workflow with persistent storage."""
    print("\n" + "=" * 70)
    print("MCP WORKFLOW: Persistent User Storage")
    print("=" * 70)

    os.environ["ARTIFACT_PROVIDER"] = "memory"
    os.environ["SESSION_PROVIDER"] = "memory"

    async with ArtifactStore(sandbox_id="demo") as store:
        # Simulate: User creates a deck in one session
        print("📝 Session 1: User creates presentation")
        deck_id = await store.store(
            data=b"Presentation content...",
            mime="application/vnd.ms-powerpoint",
            summary="Q4 Sales Deck",
            filename="sales_deck.pptx",
            user_id="alice",
            scope="user",  # Persistent!
            meta={"status": "draft", "version": 1},
        )
        print(f"   ✓ Created deck: {deck_id}")

        # Later: User wants to process it in a different session
        print("\n🎬 Session 2: User requests video rendering")

        # Find user's decks
        decks = await store.search(
            user_id="alice",
            scope="user",
            mime_prefix="application/vnd.ms-powerpoint",
        )
        print(f"   Found {len(decks)} deck(s)")

        # Get the deck from persistent storage
        deck_data = await store.retrieve(deck_id, user_id="alice")
        print(f"   ✓ Retrieved deck: {len(deck_data)} bytes")

        # Process and store result as user artifact
        video_id = await store.store(
            data=b"Rendered video content...",
            mime="video/mp4",
            summary="Q4 Sales Deck Video",
            filename="sales_deck.mp4",
            user_id="alice",
            scope="user",  # Also persistent!
            meta={"source_deck": deck_id, "status": "completed"},
        )
        print(f"   ✓ Rendered video: {video_id}")

        # User can find all their artifacts later
        print("\n📋 Session 3: List all user's work")
        user_artifacts = await store.search(user_id="alice", scope="user")
        print(f"   Alice has {len(user_artifacts)} persistent artifacts:")
        for artifact in user_artifacts:
            print(f"     - {artifact.filename}: {artifact.summary}")


async def main():
    """Run all demonstrations."""
    print("🎯 CHUK ARTIFACTS - Phase 1: Scope-Based Storage")
    print("Demonstrating session, user, and sandbox scopes\n")

    try:
        await demo_session_scope()
        await demo_user_scope()
        await demo_sandbox_scope()
        await demo_search()
        await demo_mcp_workflow()

        print("\n" + "=" * 70)
        print("✅ ALL DEMONSTRATIONS COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print("\n📚 Key Features Demonstrated:")
        print("  ✓ Session scope: Ephemeral, isolated to session")
        print("  ✓ User scope: Persistent across sessions, user-owned")
        print("  ✓ Sandbox scope: Shared by all users in sandbox")
        print("  ✓ Access control: Enforced at retrieve/delete")
        print("  ✓ Search: Find user artifacts by filters")
        print("  ✓ MCP workflow: Persistent state between operations")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

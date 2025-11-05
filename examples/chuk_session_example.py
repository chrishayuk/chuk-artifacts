#!/usr/bin/env python3
"""
CHUK Sessions + Artifacts Integration Example

This script demonstrates the PROPER usage of chuk_sessions with its clean API,
showing session management and grid architecture working together.
"""

import asyncio
import json
import os
import time

# Import using the CLEAN API from chuk_sessions
from chuk_sessions import get_session, session, SessionManager

# Import artifact management
from chuk_artifacts import ArtifactStore


async def demonstrate_simple_session_api():
    """Demonstrate the simple session API (best developer experience)."""
    print("=" * 70)
    print("SIMPLE SESSION API DEMONSTRATION")
    print("=" * 70)

    # Set environment to use memory provider
    os.environ["SESSION_PROVIDER"] = "memory"

    # CLEAN API - much better than the confusing factory pattern!
    async with get_session() as session_store:
        print("✓ Created session store using get_session()")

        # Store some basic session data
        print("\n📝 Storing basic session data...")
        await session_store.setex(
            "user:123",
            60,
            json.dumps(
                {
                    "user_id": "123",
                    "username": "alice",
                    "role": "admin",
                    "login_time": "2024-01-01T10:00:00Z",
                }
            ),
        )

        await session_store.setex("temp_token", 5, "abc123def456")

        print("   • User session (60s TTL)")
        print("   • Temp token (5s TTL)")

        # Retrieve data
        print("\n📖 Retrieving stored data...")
        user_data = await session_store.get("user:123")
        token = await session_store.get("temp_token")

        print(f"   • User data: {json.loads(user_data)['username']}")
        print(f"   • Temp token: {token}")

        # Test TTL expiration
        print("\n⏰ Testing TTL expiration...")
        print("   Waiting 6 seconds for temp token to expire...")
        await asyncio.sleep(6)

        expired_token = await session_store.get("temp_token")
        user_still_valid = await session_store.get("user:123")

        print(f"   • Temp token after 6s: {expired_token}")
        print(f"   • User session still valid: {user_still_valid is not None}")


async def demonstrate_session_context_manager():
    """Demonstrate the session context manager API."""
    print("\n" + "=" * 70)
    print("SESSION CONTEXT MANAGER API")
    print("=" * 70)

    os.environ["SESSION_PROVIDER"] = "memory"

    # Even cleaner - context manager style
    async with session() as s:
        print("✓ Created session using session() context manager")

        # Store some application data
        print("\n📝 Storing application data...")

        app_data = {
            "app_name": "MyApp",
            "version": "1.0.0",
            "features": ["auth", "uploads", "sharing"],
            "config": {"max_upload_size": "100MB", "session_timeout": 3600},
        }

        await s.setex("app:config", 3600, json.dumps(app_data))

        # Store user preferences
        preferences = {
            "theme": "dark",
            "language": "en",
            "notifications": True,
            "auto_save": True,
        }

        await s.setex("user:alice:preferences", 1800, json.dumps(preferences))

        print("   • App configuration stored")
        print("   • User preferences stored")

        # Retrieve and display
        print("\n📖 Retrieving stored data...")

        app_config = json.loads(await s.get("app:config"))
        user_prefs = json.loads(await s.get("user:alice:preferences"))

        print(f"   • App: {app_config['app_name']} v{app_config['version']}")
        print(f"   • Features: {', '.join(app_config['features'])}")
        print(f"   • User theme: {user_prefs['theme']}")
        print(f"   • Notifications: {user_prefs['notifications']}")


async def demonstrate_session_manager():
    """Demonstrate the high-level SessionManager API."""
    print("\n" + "=" * 70)
    print("SESSION MANAGER API (High-Level)")
    print("=" * 70)

    os.environ["SESSION_PROVIDER"] = "memory"

    # High-level session management
    session_mgr = SessionManager(sandbox_id="demo-app", default_ttl_hours=24)

    print("✓ Created SessionManager for sandbox: demo-app")

    # Session Lifecycle Management
    print("\n📝 Session Lifecycle Management...")

    # Create sessions for different users
    alice_session = await session_mgr.allocate_session(
        user_id="alice",
        ttl_hours=2,
        custom_metadata={"role": "admin", "department": "engineering"},
    )
    print(f"   • Alice's session: {alice_session}")

    bob_session = await session_mgr.allocate_session(
        user_id="bob", custom_metadata={"role": "user", "department": "marketing"}
    )
    print(f"   • Bob's session: {bob_session}")

    # Auto-allocated session (no user_id)
    anon_session = await session_mgr.allocate_session()
    print(f"   • Anonymous session: {anon_session}")

    # Session Validation and Info
    print("\n🔍 Session Validation and Information...")

    # Validate sessions
    alice_valid = await session_mgr.validate_session(alice_session)
    bob_valid = await session_mgr.validate_session(bob_session)
    invalid_valid = await session_mgr.validate_session("invalid_session_id")

    print(f"   • Alice session valid: {alice_valid}")
    print(f"   • Bob session valid: {bob_valid}")
    print(f"   • Invalid session valid: {invalid_valid}")

    # Get session information
    alice_info = await session_mgr.get_session_info(alice_session)
    print("\n   • Alice's session info:")
    print(f"     - User ID: {alice_info['user_id']}")
    print(f"     - Created: {alice_info['created_at']}")
    print(f"     - Expires: {alice_info['expires_at']}")
    print(f"     - Status: {alice_info['status']}")
    print(f"     - Custom data: {alice_info['custom_metadata']}")

    # Advanced Session Operations
    print("\n🔧 Advanced Session Operations...")

    # Update custom metadata
    await session_mgr.update_session_metadata(
        alice_session,
        {"last_login": time.time(), "login_count": 5, "preferred_theme": "dark"},
    )
    print("   • Updated Alice's custom metadata")

    # Extend session TTL
    extended = await session_mgr.extend_session_ttl(bob_session, additional_hours=12)
    print(f"   • Extended Bob's session TTL: {extended}")

    # Get updated session info
    alice_updated = await session_mgr.get_session_info(alice_session)
    print(f"   • Alice's updated custom metadata: {alice_updated['custom_metadata']}")

    return alice_session, bob_session, anon_session


async def demonstrate_artifact_store_integration():
    """Demonstrate ArtifactStore with session integration."""
    print("\n" + "=" * 70)
    print("ARTIFACT STORE + SESSION INTEGRATION")
    print("=" * 70)

    # Set environment for both providers
    os.environ["ARTIFACT_PROVIDER"] = "memory"
    os.environ["SESSION_PROVIDER"] = "memory"

    # Create artifact store (this will use chuk_sessions internally)
    async with ArtifactStore(sandbox_id="demo-app") as store:
        print("✓ Created ArtifactStore with session integration")

        # The artifact store automatically manages sessions using chuk_sessions
        print("\n📝 Storing artifacts with automatic session management...")

        # Store some artifacts (sessions are auto-allocated via chuk_sessions)
        artifact1_id = await store.store(
            data=b"Hello, world! This is a test document.",
            mime="text/plain",
            summary="Test document",
            filename="hello.txt",
            user_id="alice",
        )
        print(f"   • Stored artifact 1: {artifact1_id}")

        artifact2_id = await store.store(
            data=b"{'data': 'some json content'}",
            mime="application/json",
            summary="JSON data file",
            filename="data.json",
            user_id="alice",  # Same user, should reuse session
        )
        print(f"   • Stored artifact 2: {artifact2_id}")

        artifact3_id = await store.store(
            data=b"Bob's private document",
            mime="text/plain",
            summary="Bob's document",
            filename="bob_doc.txt",
            user_id="bob",  # Different user, different session
        )
        print(f"   • Stored artifact 3: {artifact3_id}")

        # Grid Architecture Demonstration
        print("\n🏗️  Grid Architecture Support...")

        # Get metadata to see grid paths (generated automatically by chuk_sessions integration)
        meta1 = await store.metadata(artifact1_id)
        meta2 = await store.metadata(artifact2_id)
        meta3 = await store.metadata(artifact3_id)

        print("   • Alice's artifacts (same session via chuk_sessions):")
        print(f"     - Artifact 1 key: {meta1['key']}")
        print(f"     - Artifact 2 key: {meta2['key']}")
        print(f"     - Session ID: {meta1['session_id']}")

        print("\n   • Bob's artifacts (different session via chuk_sessions):")
        print(f"     - Artifact 3 key: {meta3['key']}")
        print(f"     - Session ID: {meta3['session_id']}")

        # Demonstrate grid key parsing (ArtifactStore functionality)
        parsed1 = store.parse_grid_key(meta1["key"])
        parsed3 = store.parse_grid_key(meta3["key"])

        print("\n   • Parsed Alice's key:")
        print(f"     - Sandbox: {parsed1['sandbox_id']}")
        print(f"     - Session: {parsed1['session_id']}")
        print(f"     - Artifact: {parsed1['artifact_id']}")

        print("\n   • Parsed Bob's key:")
        print(f"     - Sandbox: {parsed3['sandbox_id']}")
        print(f"     - Session: {parsed3['session_id']}")
        print(f"     - Artifact: {parsed3['artifact_id']}")

        # List artifacts by session
        print("\n📋 Listing artifacts by session...")

        alice_session_id = meta1["session_id"]
        bob_session_id = meta3["session_id"]

        alice_artifacts = await store.list_by_session(alice_session_id)
        bob_artifacts = await store.list_by_session(bob_session_id)

        print(f"   • Alice's session has {len(alice_artifacts)} artifacts")
        for artifact in alice_artifacts:
            print(f"     - {artifact['filename']}: {artifact['summary']}")

        print(f"   • Bob's session has {len(bob_artifacts)} artifacts")
        for artifact in bob_artifacts:
            print(f"     - {artifact['filename']}: {artifact['summary']}")

        return store, {
            "alice_artifacts": [artifact1_id, artifact2_id],
            "bob_artifacts": [artifact3_id],
            "alice_session": alice_session_id,
            "bob_session": bob_session_id,
        }


async def demonstrate_real_world_usage():
    """Demonstrate real-world usage patterns."""
    print("\n" + "=" * 70)
    print("REAL-WORLD USAGE PATTERNS")
    print("=" * 70)

    # Scenario: Web application with user sessions and file uploads
    print("🌐 Scenario: Web Application with File Uploads")

    os.environ["ARTIFACT_PROVIDER"] = "memory"
    os.environ["SESSION_PROVIDER"] = "memory"

    # Method 1: Direct session management with chuk_sessions
    print("\n   📝 Method 1: Direct session management")

    async with get_session() as session_store:
        # Store user authentication data
        user_auth = {
            "user_id": "alice123",
            "email": "alice@company.com",
            "role": "editor",
            "login_time": time.time(),
            "permissions": ["read", "write", "upload"],
        }

        await session_store.setex("auth:alice123", 3600, json.dumps(user_auth))
        print("   • Stored user authentication in session")

        # Store temporary upload metadata
        upload_meta = {
            "upload_id": "upload_789",
            "filename": "presentation.pdf",
            "size": 2048576,
            "status": "processing",
        }

        await session_store.setex("upload:upload_789", 300, json.dumps(upload_meta))
        print("   • Stored temporary upload metadata")

        # Retrieve and verify
        auth_data = json.loads(await session_store.get("auth:alice123"))
        upload_data = json.loads(await session_store.get("upload:upload_789"))

        print(f"   • User {auth_data['email']} has role: {auth_data['role']}")
        print(f"   • Upload {upload_data['filename']} status: {upload_data['status']}")

    # Method 2: Integrated artifact + session management
    print("\n   📁 Method 2: Integrated artifact + session management")

    async with ArtifactStore(sandbox_id="webapp") as store:
        # Upload files with automatic session management
        pdf_id = await store.store(
            data=b"[PDF content would be here]",
            mime="application/pdf",
            summary="Company presentation",
            filename="presentation.pdf",
            user_id="alice123",
            meta={"department": "marketing", "confidential": False},
        )

        image_id = await store.store(
            data=b"[Image content would be here]",
            mime="image/png",
            summary="Chart for presentation",
            filename="sales_chart.png",
            user_id="alice123",
            meta={"department": "marketing", "confidential": False},
        )

        print(f"   • Uploaded PDF: {pdf_id}")
        print(f"   • Uploaded image: {image_id}")

        # Show how sessions are automatically managed
        pdf_meta = await store.metadata(pdf_id)
        image_meta = await store.metadata(image_id)

        print(
            f"   • Both files in same session: {pdf_meta['session_id'] == image_meta['session_id']}"
        )
        print(f"   • Grid organization: {pdf_meta['key']}")


async def demonstrate_api_comparison():
    """Show the API progression from simple to advanced."""
    print("\n" + "=" * 70)
    print("API PROGRESSION: Simple → Advanced")
    print("=" * 70)

    os.environ["SESSION_PROVIDER"] = "memory"
    os.environ["ARTIFACT_PROVIDER"] = "memory"

    # Level 1: Simple session storage
    print("📍 Level 1: Simple session storage")
    async with get_session() as s:
        await s.setex("simple_key", 60, "simple_value")
        value = await s.get("simple_key")
        print(f"   • Stored and retrieved: {value}")

    # Level 2: Session management with metadata
    print("\n📍 Level 2: Session management with metadata")
    session_mgr = SessionManager(sandbox_id="api-demo")
    user_session = await session_mgr.allocate_session(
        user_id="demo_user", custom_metadata={"api_level": "intermediate"}
    )
    print(f"   • Allocated managed session: {user_session}")

    # Level 3: Full artifact + session integration
    print("\n📍 Level 3: Full artifact + session integration")
    async with ArtifactStore(sandbox_id="api-demo") as store:
        artifact_id = await store.store(
            data=b"Advanced usage example",
            mime="text/plain",
            summary="API demo file",
            user_id="demo_user",
        )
        print(f"   • Stored artifact with auto session: {artifact_id}")

        # Show the full integration
        meta = await store.metadata(artifact_id)
        print(f"   • Artifact stored in grid path: {meta['key']}")
        print("   • Session automatically managed by chuk_sessions")


async def main():
    """Run all demonstrations using proper chuk_sessions API."""
    print("🎯 CHUK Sessions + Artifacts Integration (PROPER API)")
    print("📦 Using clean chuk_sessions API: get_session(), session(), SessionManager")
    print("🔧 No confusing factory patterns - just clean, intuitive functions!")

    try:
        await demonstrate_simple_session_api()
        await demonstrate_session_context_manager()
        await demonstrate_session_manager()
        await demonstrate_artifact_store_integration()
        await demonstrate_real_world_usage()
        await demonstrate_api_comparison()

        print("\n" + "=" * 70)
        print("✅ ALL DEMONSTRATIONS COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print("\n📚 Clean API Features Demonstrated:")
        print("   • get_session() - Simple session store access")
        print("   • session() - Context manager for session operations")
        print("   • SessionManager - High-level session lifecycle management")
        print("   • ArtifactStore integration - Automatic session handling")
        print("   • Grid architecture - Organized storage paths")
        print("   • Multi-level API - From simple to advanced usage")
        print("\n🎉 Much better developer experience!")
        print("   • No confusing factory patterns")
        print("   • Intuitive function names")
        print("   • Clean import statements")
        print("   • Progressive complexity")

    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Clean up environment variables at start
    for var in ["SESSION_PROVIDER", "ARTIFACT_PROVIDER", "SESSION_REDIS_URL"]:
        if var in os.environ:
            del os.environ[var]

    # Run the demonstration
    asyncio.run(main())

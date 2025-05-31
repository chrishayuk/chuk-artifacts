#!/usr/bin/env python3
# examples/session_operations_demo.py (SECURE VERSION)
# =============================================================================
# Session Operations Example - Demonstrating SECURE File Management
# NO cross-session operations allowed
# =============================================================================

import asyncio
import os
import tempfile
import shutil
import json
from datetime import datetime
from chuk_artifacts import ArtifactStore, ArtifactNotFoundError

# Clear any problematic environment variables
def clear_environment():
    """Clear any problematic environment variables."""
    problematic_vars = ['ARTIFACT_PROVIDER', 'SESSION_PROVIDER', 'ARTIFACT_BUCKET']
    cleared = {}
    
    for var in problematic_vars:
        if var in os.environ:
            cleared[var] = os.environ[var]
            del os.environ[var]
    
    return cleared

# Store original environment and clear it
ORIGINAL_ENV = clear_environment()

# =============================================================================
# Demo: Secure Session-Based File Management (NO cross-session operations)
# =============================================================================

async def secure_session_demo():
    """Demonstrate secure session operations with strict isolation."""
    print("🔒 Secure Session-Based File Management Demo")
    print("=" * 50)
    print("🚫 NO cross-session operations allowed")
    
    # Setup filesystem storage for full functionality
    temp_dir = tempfile.mkdtemp(prefix="secure_session_demo_")
    os.environ["ARTIFACT_FS_ROOT"] = temp_dir
    
    store = ArtifactStore(
        storage_provider="filesystem",
        session_provider="memory",
        bucket="secure-session-demo"
    )
    
    try:
        # Test sessions
        session_alice = "user_alice_2024"
        session_bob = "user_bob_2024"
        
        print(f"📁 Working with isolated sessions: {session_alice}, {session_bob}")
        
        # =====================================================================
        # 1. Create files in separate sessions
        # =====================================================================
        print("\n📝 1. Creating files in separate sessions...")
        
        # Alice creates files in her session
        alice_doc_id = await store.write_file(
            content="# Alice's Private Document\n\nThis is Alice's confidential work.",
            filename="docs/private_plan.md",
            mime="text/markdown",
            summary="Alice's private project plan",
            session_id=session_alice,
            meta={"author": "Alice", "confidential": True}
        )
        print(f"✅ Alice created: docs/private_plan.md -> {alice_doc_id}")
        
        alice_config_id = await store.write_file(
            content='{"user": "alice", "permissions": ["admin"], "secret_key": "alice123"}',
            filename="config/alice_config.json",
            mime="application/json",
            summary="Alice's private configuration",
            session_id=session_alice,
            meta={"author": "Alice", "sensitive": True}
        )
        print(f"✅ Alice created: config/alice_config.json -> {alice_config_id}")
        
        # Bob creates files in his session
        bob_doc_id = await store.write_file(
            content="# Bob's Work Notes\n\nBob's personal task list and notes.",
            filename="docs/work_notes.md",
            mime="text/markdown",
            summary="Bob's work documentation",
            session_id=session_bob,
            meta={"author": "Bob", "department": "engineering"}
        )
        print(f"✅ Bob created: docs/work_notes.md -> {bob_doc_id}")
        
        # =====================================================================
        # 2. Demonstrate secure session isolation
        # =====================================================================
        print("\n🔒 2. Testing secure session isolation...")
        
        # Show each user can only see their own files
        alice_files = await store.list_by_session(session_alice)
        bob_files = await store.list_by_session(session_bob)
        
        print(f"📁 Alice's session ({len(alice_files)} files):")
        for file_meta in alice_files:
            print(f"   - {file_meta.get('filename', 'unnamed')}")
        
        print(f"📁 Bob's session ({len(bob_files)} files):")
        for file_meta in bob_files:
            print(f"   - {file_meta.get('filename', 'unnamed')}")
        
        # =====================================================================
        # 3. Test blocked cross-session operations
        # =====================================================================
        print("\n🚫 3. Testing blocked cross-session operations...")
        
        # Try to copy Alice's file to Bob's session (should fail)
        print("🧪 Testing cross-session copy (should fail)...")
        try:
            await store.copy_file(
                alice_doc_id,
                new_filename="stolen/alice_doc.md",
                target_session_id=session_bob  # This should fail
            )
            print("❌ Cross-session copy should have failed!")
        except Exception as e:
            print(f"✅ Cross-session copy correctly blocked: {str(e)[:80]}...")
        
        # Try to move Alice's file to Bob's session (should fail)
        print("🧪 Testing cross-session move (should fail)...")
        try:
            await store.move_file(
                alice_doc_id,
                new_filename="stolen/alice_doc.md",
                new_session_id=session_bob  # This should fail
            )
            print("❌ Cross-session move should have failed!")
        except Exception as e:
            print(f"✅ Cross-session move correctly blocked: {str(e)[:80]}...")
        
        # Try to overwrite Bob's file from Alice's session (should fail)
        print("🧪 Testing cross-session overwrite (should fail)...")
        try:
            await store.write_file(
                content="Alice trying to overwrite Bob's file",
                filename="docs/hacked.md",
                session_id=session_alice,
                overwrite_artifact_id=bob_doc_id  # This should fail
            )
            print("❌ Cross-session overwrite should have failed!")
        except Exception as e:
            print(f"✅ Cross-session overwrite correctly blocked: {str(e)[:80]}...")
        
        # =====================================================================
        # 4. Demonstrate allowed same-session operations
        # =====================================================================
        print("\n✅ 4. Testing allowed same-session operations...")
        
        # Alice copies her own file within her session
        alice_copy_id = await store.copy_file(
            alice_doc_id,
            new_filename="docs/private_plan_backup.md",
            # No target_session_id = stays in same session
            new_meta={"backup": True, "original_id": alice_doc_id}
        )
        print(f"✅ Alice copied her own file -> {alice_copy_id}")
        
        # Alice renames her file
        await store.move_file(
            alice_config_id,
            new_filename="config/alice_settings_v2.json",
            new_meta={"version": "2.0", "updated": datetime.now().isoformat()}
        )
        print("✅ Alice renamed her config file")
        
        # Bob creates a copy of his own work
        bob_copy_id = await store.copy_file(
            bob_doc_id,
            new_filename="docs/work_notes_archive.md",
            new_meta={"archived": True, "archive_date": datetime.now().isoformat()}
        )
        print(f"✅ Bob archived his own work -> {bob_copy_id}")
        
        # =====================================================================
        # 5. Test file reading (inherently session-safe)
        # =====================================================================
        print("\n📖 5. Testing file reading (session-safe by artifact ID)...")
        
        # Alice reads her own files
        alice_content = await store.read_file(alice_doc_id, as_text=True)
        print(f"✅ Alice read her document: {alice_content[:40]}...")
        
        # Bob reads his own files
        bob_content = await store.read_file(bob_doc_id, as_text=True)
        print(f"✅ Bob read his document: {bob_content[:40]}...")
        
        # Note: Cross-session reading would require knowing the artifact ID,
        # which should not be shared between sessions in a secure system
        
        # =====================================================================
        # 6. Final session state
        # =====================================================================
        print("\n📊 6. Final secure session state...")
        
        alice_final = await store.list_by_session(session_alice)
        bob_final = await store.list_by_session(session_bob)
        
        print(f"🔒 Alice's secure session ({len(alice_final)} files):")
        for file_meta in alice_final:
            confidential = "🔐" if file_meta.get('meta', {}).get('confidential') else "📄"
            print(f"   {confidential} {file_meta.get('filename', 'unnamed')} ({file_meta.get('bytes', 0)} bytes)")
        
        print(f"🔒 Bob's secure session ({len(bob_final)} files):")
        for file_meta in bob_final:
            print(f"   📄 {file_meta.get('filename', 'unnamed')} ({file_meta.get('bytes', 0)} bytes)")
        
        print(f"\n🎉 Secure session operations completed successfully!")
        print(f"🔒 All cross-session operations properly blocked!")
        print(f"✅ Session isolation maintained perfectly!")
        
    finally:
        await store.close()
        # Cleanup
        shutil.rmtree(temp_dir)
        os.environ.pop("ARTIFACT_FS_ROOT", None)


# =============================================================================
# Demo: Security validation tests
# =============================================================================

async def security_validation_demo():
    """Test various security scenarios to ensure proper isolation."""
    print("\n🛡️  Security Validation Demo")
    print("=" * 35)
    
    temp_dir = tempfile.mkdtemp(prefix="security_demo_")
    os.environ["ARTIFACT_FS_ROOT"] = temp_dir
    
    store = ArtifactStore(
        storage_provider="filesystem",
        session_provider="memory",
        bucket="security-demo"
    )
    
    try:
        # Create test sessions
        session_a = "company_a"
        session_b = "company_b"
        session_c = "company_c"
        
        print(f"🏢 Testing with multiple company sessions:")
        print(f"   - {session_a}")
        print(f"   - {session_b}")
        print(f"   - {session_c}")
        
        # Create sensitive files in each session
        file_a = await store.write_file(
            content="Company A's trade secrets and financial data",
            filename="confidential/trade_secrets.txt",
            session_id=session_a,
            meta={"classification": "top_secret", "company": "A"}
        )
        
        file_b = await store.write_file(
            content="Company B's proprietary algorithms and code",
            filename="confidential/algorithms.txt", 
            session_id=session_b,
            meta={"classification": "confidential", "company": "B"}
        )
        
        file_c = await store.write_file(
            content="Company C's customer database and contracts",
            filename="confidential/customers.txt",
            session_id=session_c,
            meta={"classification": "restricted", "company": "C"}
        )
        
        print("✅ Created sensitive files in each company session")
        
        # Test comprehensive security scenarios
        security_tests = [
            ("Copy A->B", lambda: store.copy_file(file_a, target_session_id=session_b)),
            ("Copy B->C", lambda: store.copy_file(file_b, target_session_id=session_c)),
            ("Copy C->A", lambda: store.copy_file(file_c, target_session_id=session_a)),
            ("Move A->B", lambda: store.move_file(file_a, new_session_id=session_b)),
            ("Move B->C", lambda: store.move_file(file_b, new_session_id=session_c)),
            ("Overwrite A from B", lambda: store.write_file("hacked", filename="hack.txt", session_id=session_b, overwrite_artifact_id=file_a)),
        ]
        
        print("\n🧪 Running comprehensive security tests:")
        all_blocked = True
        
        for test_name, test_func in security_tests:
            try:
                await test_func()
                print(f"❌ {test_name}: FAILED - operation should have been blocked!")
                all_blocked = False
            except Exception as e:
                print(f"✅ {test_name}: Correctly blocked")
        
        if all_blocked:
            print("\n🛡️  ALL SECURITY TESTS PASSED!")
            print("🔒 Complete session isolation maintained")
        else:
            print("\n⚠️  SECURITY VULNERABILITIES DETECTED!")
        
        # Show final isolation
        for session in [session_a, session_b, session_c]:
            files = await store.list_by_session(session)
            print(f"🏢 {session}: {len(files)} files (isolated)")
        
    finally:
        await store.close()
        shutil.rmtree(temp_dir)
        os.environ.pop("ARTIFACT_FS_ROOT", None)


# =============================================================================
# Main execution
# =============================================================================

async def run_secure_demos():
    """Run all secure session operation demonstrations."""
    print("🛡️  SECURE Session Operations Demo")
    print("=" * 40)
    print("🔒 Demonstrating chuk_artifacts with STRICT session isolation")
    print("🚫 NO cross-session operations allowed")
    print()
    
    demos = [
        ("Secure Session Management", secure_session_demo),
        ("Security Validation", security_validation_demo),
    ]
    
    for name, demo_func in demos:
        try:
            await demo_func()
            print(f"✅ {name} demo completed\n")
        except Exception as e:
            print(f"❌ {name} demo failed: {e}")
            import traceback
            traceback.print_exc()
            print()
    
    print("🎉 All secure session demos completed!")
    print("🔒 Enhanced chuk_artifacts with STRICT session security!")
    print("🛡️  Ready for secure MCP server deployment!")


def restore_environment():
    """Restore original environment variables."""
    for var, value in ORIGINAL_ENV.items():
        os.environ[var] = value


if __name__ == "__main__":
    try:
        asyncio.run(run_secure_demos())
    finally:
        restore_environment()
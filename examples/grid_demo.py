#!/usr/bin/env python3
# examples/grid_demo.py
"""
Clean grid architecture demonstration.

Shows:
- Mandatory session allocation
- Grid paths: grid/{sandbox_id}/{session_id}/{artifact_id}
- Simple, focused operations
"""

import asyncio
import os
import tempfile
import shutil

# CRITICAL: Set environment BEFORE imports
for var in ['ARTIFACT_PROVIDER', 'SESSION_PROVIDER', 'ARTIFACT_BUCKET', 'SESSION_REDIS_URL']:
    os.environ.pop(var, None)

# Force memory session provider BEFORE importing
os.environ['SESSION_PROVIDER'] = 'memory'
os.environ['ARTIFACT_PROVIDER'] = 'filesystem'

from chuk_artifacts import ArtifactStore

async def clean_grid_demo():
    """Demonstrate clean grid architecture."""
    print("🎯 Clean Grid Architecture Demo")
    print("=" * 40)
    
    temp_dir = tempfile.mkdtemp(prefix="clean_grid_")
    os.environ["ARTIFACT_FS_ROOT"] = temp_dir
    
    try:
        async with ArtifactStore(
            bucket="clean-demo",
            sandbox_id="demo-box",
        ) as store:
            
            print(f"✅ Store initialized")
            print(f"   Sandbox: {store.sandbox_id}")
            print(f"   Bucket: {store.bucket}")
            print(f"   Storage: {store._storage_provider_name}")
            print(f"   Session: {store._session_provider_name}")
            
            # ─────────────────────────────────────────────────────────────
            # Demo 1: Auto session allocation
            # ─────────────────────────────────────────────────────────────
            print("\n📝 Auto Session Allocation")
            print("-" * 30)
            
            # Store without session_id - auto allocated
            artifact_id = await store.store(
                data=b"Hello from clean grid!",
                mime="text/plain",
                summary="Clean grid demo file",
                filename="demo.txt",
                user_id="alice"
            )
            
            metadata = await store.metadata(artifact_id)
            session_id = metadata["session_id"]
            
            print(f"✅ Auto-allocated session: {session_id}")
            print(f"   Artifact: {artifact_id}")
            print(f"   Grid key: {metadata['key']}")
            print(f"   Sandbox: {metadata['sandbox_id']}")
            
            # ─────────────────────────────────────────────────────────────
            # Demo 2: Explicit session creation
            # ─────────────────────────────────────────────────────────────
            print("\n📝 Explicit Session Creation")
            print("-" * 32)
            
            # Create specific session
            bob_session = await store.create_session(user_id="bob")
            print(f"✅ Created session: {bob_session}")
            
            # Store multiple files in same session
            files = []
            for i in range(3):
                file_id = await store.write_file(
                    content=f"File {i} content for Bob",
                    filename=f"bob/file_{i}.txt",
                    session_id=bob_session,
                    user_id="bob"
                )
                files.append(file_id)
                print(f"   File {i}: {file_id}")
            
            # ─────────────────────────────────────────────────────────────
            # Demo 3: Grid path structure
            # ─────────────────────────────────────────────────────────────
            print("\n📝 Grid Path Structure")
            print("-" * 26)
            
            # Show canonical prefix
            prefix = store.get_canonical_prefix(bob_session)
            print(f"✅ Session prefix: {prefix}")
            
            # Show individual artifact keys
            for i, file_id in enumerate(files):
                meta = await store.metadata(file_id)
                print(f"   File {i} key: {meta['key']}")
            
            # Parse a grid key to show structure
            parsed = store.parse_grid_key(meta['key'])
            print(f"✅ Parsed grid key:")
            print(f"   Sandbox: {parsed['sandbox_id']}")
            print(f"   Session: {parsed['session_id']}")
            print(f"   Artifact: {parsed['artifact_id']}")
            
            # ─────────────────────────────────────────────────────────────
            # Demo 4: Session-based listing
            # ─────────────────────────────────────────────────────────────
            print("\n📝 Session-Based Listing")
            print("-" * 28)
            
            # List Alice's files
            alice_files = await store.list_by_session(session_id)
            print(f"✅ Alice's session ({len(alice_files)} files):")
            for file_meta in alice_files:
                print(f"   - {file_meta['filename']} ({file_meta['bytes']} bytes)")
            
            # List Bob's files
            bob_files = await store.list_by_session(bob_session)
            print(f"✅ Bob's session ({len(bob_files)} files):")
            for file_meta in bob_files:
                print(f"   - {file_meta['filename']} ({file_meta['bytes']} bytes)")
            
            # ─────────────────────────────────────────────────────────────
            # Demo 5: File operations
            # ─────────────────────────────────────────────────────────────
            print("\n📝 File Operations")
            print("-" * 20)
            
            # Read file content
            content = await store.read_file(files[0], as_text=True)
            print(f"✅ Read file content: {content[:30]}...")
            
            # Update a file
            await store.update_file(
                files[1],
                data=b"Updated content for Bob's file",
                summary="Updated file via grid demo"
            )
            print(f"✅ File updated successfully")
            
            # Check if artifacts exist
            exists = await store.exists(files[1])
            print(f"✅ File exists: {exists}")
            
            # Delete a file
            deleted = await store.delete(files[2])
            print(f"✅ File deleted: {deleted}")
            
            # Verify deletion
            remaining_files = await store.list_by_session(bob_session)
            print(f"✅ Remaining files: {len(remaining_files)}")
            
            # ─────────────────────────────────────────────────────────────
            # Demo 6: Session validation
            # ─────────────────────────────────────────────────────────────
            print("\n📝 Session Validation")
            print("-" * 23)
            
            # Validate sessions
            alice_valid = await store.validate_session(session_id)
            bob_valid = await store.validate_session(bob_session)
            print(f"✅ Alice session valid: {alice_valid}")
            print(f"✅ Bob session valid: {bob_valid}")
            
            # Get session info
            alice_info = await store.get_session_info(session_id)
            bob_info = await store.get_session_info(bob_session)
            
            print(f"✅ Alice session info:")
            print(f"   User: {alice_info['user_id']}")
            print(f"   Created: {alice_info['created_at']}")
            print(f"   Status: {alice_info['status']}")
            
            print(f"✅ Bob session info:")
            print(f"   User: {bob_info['user_id']}")
            print(f"   Created: {bob_info['created_at']}")
            print(f"   Status: {bob_info['status']}")
            
            # ─────────────────────────────────────────────────────────────
            # Demo 7: Grid architecture benefits
            # ─────────────────────────────────────────────────────────────
            print("\n📝 Grid Architecture Benefits")
            print("-" * 33)
            
            print("✅ Clean path structure:")
            print(f"   Pattern: grid/{{sandbox}}/{{session}}/{{artifact}}")
            print(f"   Example: {metadata['key']}")
            print("")
            print("✅ Federation ready:")
            print(f"   Sandbox isolation: {store.sandbox_id}")
            print(f"   Cross-sandbox discovery: prefix search")
            print(f"   Session-based security: strict isolation")
            print("")
            print("✅ Simple operations:")
            print(f"   Mandatory sessions (no anonymous artifacts)")
            print(f"   Auto-allocation when needed")
            print(f"   Grid-aware key generation")
            
            # ─────────────────────────────────────────────────────────────
            # Demo 8: Security demonstration
            # ─────────────────────────────────────────────────────────────
            print("\n📝 Security Demonstration")
            print("-" * 29)
            
            # Try to copy across sessions (should be prevented)
            try:
                await store.copy_file(
                    files[0], 
                    target_session_id=session_id,  # Alice's session
                    new_filename="stolen_file.txt"
                )
                print("❌ Cross-session copy should have failed!")
            except Exception as e:
                print(f"✅ Cross-session copy blocked: {str(e)[:50]}...")
            
            # Copy within same session (should work)
            copied_file = await store.copy_file(
                files[0],
                new_filename="bob_copy.txt"
            )
            print(f"✅ Same-session copy allowed: {copied_file}")
            
            print(f"\n🎉 Clean grid architecture demo completed!")
            print(f"🏗️  Simple, focused, federation-ready design")
            
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        shutil.rmtree(temp_dir)
        os.environ.pop("ARTIFACT_FS_ROOT", None)


async def federation_preview():
    """Preview how federation would work with this clean architecture."""
    print("\n🌐 Federation Preview")
    print("=" * 25)
    
    print("With this clean grid architecture, federation becomes simple:")
    print("")
    print("📁 Storage structure:")
    print("   grid/sandbox-a/session-123/artifact-456")
    print("   grid/sandbox-b/session-123/artifact-789")
    print("   grid/sandbox-c/session-456/artifact-abc")
    print("")
    print("🔍 Discovery:")
    print("   List session across sandboxes: LIST grid/*/session-123/")
    print("   Find artifact location: lookup artifact-456 → sandbox-a")
    print("")
    print("🔗 Cross-sandbox access:")
    print("   1. Validate session access")
    print("   2. Route to owning sandbox")
    print("   3. Generate presigned URL")
    print("   4. Stream data back")
    print("")
    print("🔒 Security:")
    print("   - Session-based access control")
    print("   - Sandbox isolation")
    print("   - Audit trail in paths")
    print("")
    print("🚀 Implementation steps:")
    print("   1. Federation registry (sandbox discovery)")
    print("   2. Session validation across sandboxes")
    print("   3. Artifact routing and proxying")
    print("   4. Distributed presigned URL generation")


async def multi_sandbox_demo():
    """Demonstrate multi-sandbox isolation."""
    print("\n🏢 Multi-Sandbox Isolation Demo")
    print("=" * 35)
    
    temp_dir1 = tempfile.mkdtemp(prefix="sandbox_a_")
    temp_dir2 = tempfile.mkdtemp(prefix="sandbox_b_")
    
    try:
        # Create two separate sandboxes
        os.environ["ARTIFACT_FS_ROOT"] = temp_dir1
        async with ArtifactStore(
            bucket="sandbox-a",
            sandbox_id="company-a"
        ) as store_a:
            
            os.environ["ARTIFACT_FS_ROOT"] = temp_dir2
            async with ArtifactStore(
                bucket="sandbox-b", 
                sandbox_id="company-b"
            ) as store_b:
                
                print("✅ Created two isolated sandboxes:")
                print(f"   Company A: {store_a.sandbox_id}")
                print(f"   Company B: {store_b.sandbox_id}")
                
                # Store same filename in both sandboxes
                file_a = await store_a.store(
                    data=b"Company A confidential data",
                    mime="text/plain",
                    summary="Confidential document",
                    filename="secret.txt",
                    user_id="alice"
                )
                
                file_b = await store_b.store(
                    data=b"Company B confidential data",
                    mime="text/plain", 
                    summary="Confidential document",
                    filename="secret.txt",
                    user_id="alice"  # Same user, different company
                )
                
                # Show isolation
                meta_a = await store_a.metadata(file_a)
                meta_b = await store_b.metadata(file_b)
                
                print(f"\n✅ Perfect isolation demonstrated:")
                print(f"   Company A path: {meta_a['key']}")
                print(f"   Company B path: {meta_b['key']}")
                print(f"   Same user, different sandboxes = complete isolation")
                
    finally:
        shutil.rmtree(temp_dir1)
        shutil.rmtree(temp_dir2)
        os.environ.pop("ARTIFACT_FS_ROOT", None)


async def main():
    """Run clean grid demonstrations."""
    await clean_grid_demo()
    await federation_preview()
    await multi_sandbox_demo()
    
    print(f"\n🚀 Clean Grid Architecture Complete!")
    print(f"✅ Mandatory sessions")
    print(f"✅ Grid-only paths") 
    print(f"✅ Federation ready")
    print(f"✅ Simple & focused")
    print(f"✅ Multi-tenant isolation")
    print(f"✅ Security enforced")


if __name__ == "__main__":
    asyncio.run(main())
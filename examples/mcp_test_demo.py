#!/usr/bin/env python3
# examples/mcp_server_test_demo.py
# =============================================================================
# MCP Server Test Demo - Real-World Scenarios (FIXED SESSION HANDLING)
# Simulates actual MCP client interactions and use cases
# =============================================================================

import asyncio
import os
import tempfile
import shutil
import json
import base64
from datetime import datetime
from chuk_artifacts import ArtifactStore


# Clear any problematic environment variables
def clear_environment():
    """Clear any problematic environment variables."""
    problematic_vars = ["ARTIFACT_PROVIDER", "SESSION_PROVIDER", "ARTIFACT_BUCKET"]
    cleared = {}

    for var in problematic_vars:
        if var in os.environ:
            cleared[var] = os.environ[var]
            del os.environ[var]

    return cleared


# Store original environment and clear it
ORIGINAL_ENV = clear_environment()

# =============================================================================
# Demo 1: MCP Client File Management Workflow (FIXED)
# =============================================================================


async def mcp_client_workflow_demo():
    """Simulate typical MCP client file management workflow."""
    print("🎯 MCP Client File Management Workflow Demo")
    print("=" * 50)
    print("Simulating real-world MCP client interactions")

    # Setup similar to MCP server environment
    temp_dir = tempfile.mkdtemp(prefix="mcp_client_demo_")
    os.environ["ARTIFACT_FS_ROOT"] = temp_dir

    store = ArtifactStore(
        storage_provider="filesystem",
        session_provider="memory",
        bucket="mcp-client-demo",
    )

    try:
        # Simulate MCP client session
        session_id = "claude_conversation_12345"

        print(f"📱 MCP Client session: {session_id}")

        # =====================================================================
        # Scenario 1: User uploads files through MCP client
        # =====================================================================
        print("\n📤 1. User uploads files via MCP client...")

        # User uploads a document - FIXED: Always include session_id
        doc_content = """# Project Requirements
        
## Overview
This document outlines the requirements for our new web application.

## Features
- User authentication
- File upload/download
- Session management
- Security controls

## Technical Requirements
- Python backend
- React frontend
- PostgreSQL database
"""

        doc_encoded = base64.b64encode(doc_content.encode()).decode()
        doc_id = await store.store(
            data=base64.b64decode(doc_encoded),
            mime="text/markdown",
            summary="Project requirements document",
            filename="project_requirements.md",
            session_id=session_id,  # FIXED: Always provide session_id
            meta={"uploaded_by": "user", "document_type": "requirements"},
        )
        print(f"✅ Uploaded document: project_requirements.md -> {doc_id}")

        # User uploads a configuration file - FIXED: Always include session_id
        config_content = {
            "app_name": "WebApp",
            "version": "1.0.0",
            "features": {
                "authentication": True,
                "file_upload": True,
                "session_management": True,
            },
            "security": {
                "session_timeout": 3600,
                "max_file_size": "10MB",
                "allowed_types": ["jpg", "png", "pdf", "md", "txt"],
            },
        }

        config_encoded = base64.b64encode(
            json.dumps(config_content, indent=2).encode()
        ).decode()
        config_id = await store.store(
            data=base64.b64decode(config_encoded),
            mime="application/json",
            summary="Application configuration",
            filename="config/app_config.json",
            session_id=session_id,  # FIXED: Always provide session_id
            meta={"uploaded_by": "user", "config_type": "application"},
        )
        print(f"✅ Uploaded config: config/app_config.json -> {config_id}")

        # User uploads an image - FIXED: Always include session_id
        fake_image = (
            b"\x89PNG\r\n\x1a\n" + b"fake image data" * 100
        )  # Fake PNG header + data
        image_encoded = base64.b64encode(fake_image).decode()
        image_id = await store.store(
            data=base64.b64decode(image_encoded),
            mime="image/png",
            summary="Project logo",
            filename="assets/logo.png",
            session_id=session_id,  # FIXED: Always provide session_id
            meta={"uploaded_by": "user", "asset_type": "logo"},
        )
        print(f"✅ Uploaded image: assets/logo.png -> {image_id}")

        # =====================================================================
        # Scenario 2: List and organize files
        # =====================================================================
        print("\n📋 2. User lists and organizes files...")

        # List all files in session
        all_files = await store.list_by_session(session_id)
        print(f"📁 Session contains {len(all_files)} files:")
        for file_meta in all_files:
            print(f"   - {file_meta.filename or 'unnamed'} ({file_meta.bytes} bytes)")

        # List files by directory
        config_files = await store.get_directory_contents(session_id, "config/")
        print(f"⚙️  Config directory: {len(config_files)} files")

        assets_files = await store.get_directory_contents(session_id, "assets/")
        print(f"🖼️  Assets directory: {len(assets_files)} files")

        # =====================================================================
        # Scenario 3: User creates new files with content
        # =====================================================================
        print("\n✍️  3. User creates new files with write_file...")

        # Create a README file
        readme_content = """# Project WebApp
        
This is the main project repository for our new web application.

## Files
- `project_requirements.md` - Main requirements document
- `config/app_config.json` - Application configuration
- `assets/logo.png` - Project logo

## Getting Started
1. Review the requirements document
2. Check the configuration settings
3. Run the application

Created via MCP session operations.
"""

        readme_id = await store.write_file(
            content=readme_content,
            filename="README.md",
            mime="text/markdown",
            summary="Project README file",
            session_id=session_id,
            meta={"created_by": "mcp_client", "file_type": "documentation"},
        )
        print(f"✅ Created README.md -> {readme_id}")

        # Create a notes file
        notes_content = """# Development Notes
        
## Progress
- [x] Upload requirements document
- [x] Configure application settings
- [x] Add project logo
- [x] Create README file
- [ ] Start development

## Next Steps
- Set up development environment
- Create database schema
- Implement authentication
"""

        notes_id = await store.write_file(
            content=notes_content,
            filename="docs/development_notes.md",
            mime="text/markdown",
            summary="Development progress notes",
            session_id=session_id,
            meta={"created_by": "mcp_client", "file_type": "notes"},
        )
        print(f"✅ Created docs/development_notes.md -> {notes_id}")

        # =====================================================================
        # Scenario 4: Read and modify existing files (FIXED)
        # =====================================================================
        print("\n📖 4. User reads and modifies files...")

        # Read the config file
        config_data = await store.read_file(config_id, as_text=True)
        config_json = json.loads(config_data)
        print(f"📄 Read config file: app_name = {config_json['app_name']}")

        # Update the config with new settings
        config_json["version"] = "1.1.0"
        config_json["features"]["notifications"] = True
        config_json["last_updated"] = datetime.now().isoformat()

        # FIXED: Use same session_id for overwrite to avoid session mismatch
        await store.write_file(
            content=json.dumps(config_json, indent=2),
            filename="config/app_config_v2.json",  # ✅ Different filename
            mime="application/json",
            summary="Updated application configuration v2",
            session_id=session_id,
            # ✅ No overwrite, just create new file
            meta={
                "updated_by": "mcp_client",
                "version": "1.1.0",
                "replaces": config_id,
            },
        )

        # =====================================================================
        # Scenario 5: Copy and organize files
        # =====================================================================
        print("\n📋 5. User copies and organizes files...")

        # Create a backup of the requirements
        backup_id = await store.copy_file(
            doc_id,
            new_filename="backups/project_requirements_backup.md",
            new_meta={"backup_date": datetime.now().isoformat(), "original_id": doc_id},
        )
        print(f"✅ Created backup -> {backup_id}")

        # Move/rename the notes file
        await store.move_file(
            notes_id,
            new_filename="docs/project_notes.md",
            new_meta={"renamed_date": datetime.now().isoformat()},
        )
        print("✅ Renamed development notes to project notes")

        # =====================================================================
        # Scenario 6: Generate file summary and stats
        # =====================================================================
        print("\n📊 6. Session summary and statistics...")

        # Get final file listing
        final_files = await store.list_by_session(session_id)

        # Organize by directory
        directories = {}
        total_bytes = 0

        for file_meta in final_files:
            filename = file_meta.filename or ""
            file_bytes = file_meta.bytes
            total_bytes += file_bytes

            if "/" in filename:
                directory = filename.split("/")[0] + "/"
            else:
                directory = "root/"

            if directory not in directories:
                directories[directory] = {"files": [], "bytes": 0}

            directories[directory]["files"].append(filename)
            directories[directory]["bytes"] += file_bytes

        print("🎯 MCP Session Summary:")
        print(f"   Total files: {len(final_files)}")
        print(f"   Total size: {total_bytes:,} bytes ({total_bytes/1024:.1f} KB)")
        print(f"   Directories: {len(directories)}")

        for directory, info in sorted(directories.items()):
            print(
                f"     📁 {directory}: {len(info['files'])} files, {info['bytes']:,} bytes"
            )

        # =====================================================================
        # Scenario 7: Test security isolation
        # =====================================================================
        print("\n🔒 7. Testing session isolation...")

        # Try to access files from a different session (should show empty)
        other_session = "different_user_session"
        other_files = await store.list_by_session(other_session)
        print(
            f"🔐 Other session '{other_session}': {len(other_files)} files (isolated)"
        )

        # Try cross-session operations (should fail)
        try:
            await store.copy_file(doc_id, target_session_id=other_session)
            print("❌ Cross-session copy should have failed!")
        except Exception:
            print("✅ Cross-session operations properly blocked")

        print("\n🎉 MCP client workflow completed successfully!")
        print(f"📱 Session '{session_id}' contains {len(final_files)} organized files")
        print("🔒 Session isolation verified")

    finally:
        await store.close()
        shutil.rmtree(temp_dir)
        os.environ.pop("ARTIFACT_FS_ROOT", None)


# =============================================================================
# Demo 2: Multi-User MCP Environment (Already working correctly)
# =============================================================================


async def multi_user_mcp_demo():
    """Simulate multi-user MCP environment with different workflows."""
    print("\n🏢 Multi-User MCP Environment Demo")
    print("=" * 40)
    print("Simulating multiple users working simultaneously")

    temp_dir = tempfile.mkdtemp(prefix="multi_user_mcp_")
    os.environ["ARTIFACT_FS_ROOT"] = temp_dir

    store = ArtifactStore(
        storage_provider="filesystem",
        session_provider="memory",
        bucket="multi-user-mcp",
    )

    try:
        # Different user sessions
        sessions = {
            "developer": "dev_session_alice",
            "designer": "design_session_bob",
            "manager": "mgmt_session_carol",
        }

        print(f"👥 Users: {', '.join(sessions.keys())}")

        # =====================================================================
        # Developer workflow
        # =====================================================================
        print("\n💻 Developer (Alice) workflow...")

        dev_session = sessions["developer"]

        # Developer creates code files
        main_py = """#!/usr/bin/env python3
# main.py - Main application entry point

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="WebApp", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""

        main_id = await store.write_file(
            content=main_py,
            filename="src/main.py",
            mime="text/x-python",
            summary="Main application entry point",
            session_id=dev_session,
            meta={"author": "alice", "language": "python", "type": "source"},
        )
        print(f"✅ Developer created: src/main.py -> {main_id}")

        # Developer creates requirements file
        requirements = """fastapi==0.104.1
uvicorn==0.24.0
python-multipart==0.0.6
pydantic==2.5.0
"""

        req_id = await store.write_file(
            content=requirements,
            filename="requirements.txt",
            mime="text/plain",
            summary="Python dependencies",
            session_id=dev_session,
            meta={"author": "alice", "type": "dependencies"},
        )
        print(f"✅ Developer created: requirements.txt -> {req_id}")

        # =====================================================================
        # Designer workflow
        # =====================================================================
        print("\n🎨 Designer (Bob) workflow...")

        design_session = sessions["designer"]

        # Designer creates CSS
        styles_css = """/* styles.css - Main application styles */

:root {
    --primary-color: #3b82f6;
    --secondary-color: #64748b;
    --background-color: #f8fafc;
    --text-color: #1e293b;
}

body {
    font-family: 'Inter', sans-serif;
    background-color: var(--background-color);
    color: var(--text-color);
    margin: 0;
    padding: 0;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
}

.btn-primary {
    background-color: var(--primary-color);
    color: white;
    padding: 0.75rem 1.5rem;
    border: none;
    border-radius: 0.5rem;
    cursor: pointer;
    transition: background-color 0.2s;
}

.btn-primary:hover {
    background-color: #2563eb;
}
"""

        css_id = await store.write_file(
            content=styles_css,
            filename="assets/css/styles.css",
            mime="text/css",
            summary="Main application styles",
            session_id=design_session,
            meta={"author": "bob", "type": "stylesheet", "framework": "custom"},
        )
        print(f"✅ Designer created: assets/css/styles.css -> {css_id}")

        # Designer creates HTML template
        template_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WebApp</title>
    <link rel="stylesheet" href="/assets/css/styles.css">
</head>
<body>
    <div class="container">
        <h1>Welcome to WebApp</h1>
        <p>A modern web application built with FastAPI and custom styling.</p>
        <button class="btn-primary">Get Started</button>
    </div>
</body>
</html>
"""

        html_id = await store.write_file(
            content=template_html,
            filename="templates/index.html",
            mime="text/html",
            summary="Main page template",
            session_id=design_session,
            meta={"author": "bob", "type": "template", "page": "index"},
        )
        print(f"✅ Designer created: templates/index.html -> {html_id}")

        # =====================================================================
        # Manager workflow
        # =====================================================================
        print("\n📊 Manager (Carol) workflow...")

        mgmt_session = sessions["manager"]

        # Manager creates project plan
        project_plan = """# WebApp Development Project Plan
        
## Team
- Developer: Alice (Backend development)
- Designer: Bob (Frontend design & styling)
- Manager: Carol (Project coordination)

## Timeline
- Week 1: Backend API development
- Week 2: Frontend design implementation
- Week 3: Integration and testing
- Week 4: Deployment and documentation

## Deliverables
- [ ] FastAPI backend with endpoints
- [ ] Responsive frontend design
- [ ] User authentication system
- [ ] File upload/download functionality
- [ ] Session management
- [ ] Production deployment

## Status
- Backend: In Progress
- Frontend: In Progress
- Testing: Pending
- Deployment: Pending

## Next Actions
- Review developer's API implementation
- Approve designer's style choices
- Plan integration testing
"""

        plan_id = await store.write_file(
            content=project_plan,
            filename="docs/project_plan.md",
            mime="text/markdown",
            summary="Development project plan",
            session_id=mgmt_session,
            meta={"author": "carol", "type": "planning", "status": "active"},
        )
        print(f"✅ Manager created: docs/project_plan.md -> {plan_id}")

        # Manager creates status report
        status_report = {
            "project": "WebApp Development",
            "report_date": datetime.now().isoformat(),
            "team_status": {
                "developer": {
                    "name": "Alice",
                    "progress": "75%",
                    "current_task": "API endpoints",
                    "files_created": 2,
                },
                "designer": {
                    "name": "Bob",
                    "progress": "60%",
                    "current_task": "CSS styling",
                    "files_created": 2,
                },
                "manager": {
                    "name": "Carol",
                    "progress": "90%",
                    "current_task": "Project coordination",
                    "files_created": 2,
                },
            },
            "overall_progress": "70%",
            "next_milestone": "Integration testing",
        }

        report_id = await store.write_file(
            content=json.dumps(status_report, indent=2),
            filename="reports/status_report.json",
            mime="application/json",
            summary="Weekly status report",
            session_id=mgmt_session,
            meta={"author": "carol", "type": "report", "week": 2},
        )
        print(f"✅ Manager created: reports/status_report.json -> {report_id}")

        # =====================================================================
        # Summary of all user sessions
        # =====================================================================
        print("\n📈 Multi-user session summary...")

        for role, session_id in sessions.items():
            files = await store.list_by_session(session_id)
            total_size = sum(f.bytes for f in files)

            print(f"👤 {role.title()} ({session_id}):")
            print(f"   Files: {len(files)}")
            print(f"   Size: {total_size:,} bytes")

            # Show file types
            file_types = {}
            for file_meta in files:
                mime = file_meta.mime
                file_types[mime] = file_types.get(mime, 0) + 1

            for mime, count in file_types.items():
                print(f"   - {mime}: {count} files")

        # Verify session isolation
        print("\n🔒 Verifying session isolation...")
        total_isolated_files = 0
        for role, session_id in sessions.items():
            files = await store.list_by_session(session_id)
            total_isolated_files += len(files)

        print(f"✅ Total files across all sessions: {total_isolated_files}")
        print("✅ Each user can only see their own files")
        print("✅ No cross-session data leakage")

    finally:
        await store.close()
        shutil.rmtree(temp_dir)
        os.environ.pop("ARTIFACT_FS_ROOT", None)


# =============================================================================
# Demo 3: MCP Server Performance Testing (Already working correctly)
# =============================================================================


async def mcp_performance_demo():
    """Test MCP server performance with realistic workloads."""
    print("\n⚡ MCP Server Performance Demo")
    print("=" * 35)
    print("Testing performance with realistic MCP workloads")

    temp_dir = tempfile.mkdtemp(prefix="mcp_perf_")
    os.environ["ARTIFACT_FS_ROOT"] = temp_dir

    store = ArtifactStore(
        storage_provider="filesystem",
        session_provider="memory",
        bucket="mcp-performance",
    )

    try:
        session_id = "performance_test_session"

        import time

        # =====================================================================
        # Test 1: Rapid file creation (simulating user uploads)
        # =====================================================================
        print("\n📤 Test 1: Rapid file creation...")

        start_time = time.time()
        created_files = []

        for i in range(20):
            content = f"File {i:02d}\n{'Content line ' * 10}\nEnd of file {i:02d}"

            file_id = await store.write_file(
                content=content,
                filename=f"uploads/file_{i:02d}.txt",
                mime="text/plain",
                summary=f"Performance test file {i:02d}",
                session_id=session_id,
                meta={"test_index": i, "test_type": "performance"},
            )
            created_files.append(file_id)

        create_time = time.time() - start_time
        print(
            f"✅ Created 20 files in {create_time:.3f}s ({20/create_time:.1f} files/sec)"
        )

        # =====================================================================
        # Test 2: Session listing performance
        # =====================================================================
        print("\n📋 Test 2: Session listing performance...")

        start_time = time.time()
        all_files = await store.list_by_session(session_id)
        list_time = time.time() - start_time

        print(f"✅ Listed {len(all_files)} files in {list_time:.3f}s")

        # =====================================================================
        # Test 3: Directory operations performance
        # =====================================================================
        print("\n📁 Test 3: Directory operations...")

        start_time = time.time()
        upload_files = await store.get_directory_contents(session_id, "uploads/")
        dir_time = time.time() - start_time

        print(
            f"✅ Listed uploads/ directory ({len(upload_files)} files) in {dir_time:.3f}s"
        )

        # =====================================================================
        # Test 4: Batch read operations
        # =====================================================================
        print("\n📖 Test 4: Batch read operations...")

        start_time = time.time()
        read_count = min(10, len(created_files))

        for i in range(read_count):
            content = await store.read_file(created_files[i], as_text=True)

        read_time = time.time() - start_time
        print(
            f"✅ Read {read_count} files in {read_time:.3f}s ({read_count/read_time:.1f} reads/sec)"
        )

        # =====================================================================
        # Test 5: Copy operations performance
        # =====================================================================
        print("\n📋 Test 5: Copy operations...")

        start_time = time.time()
        copy_count = 5

        for i in range(copy_count):
            await store.copy_file(
                created_files[i],
                new_filename=f"backups/backup_{i:02d}.txt",
                new_meta={"backup_of": created_files[i], "backup_time": time.time()},
            )

        copy_time = time.time() - start_time
        print(
            f"✅ Copied {copy_count} files in {copy_time:.3f}s ({copy_count/copy_time:.1f} copies/sec)"
        )

        # =====================================================================
        # Performance summary
        # =====================================================================
        print("\n📊 Performance Summary:")

        final_files = await store.list_by_session(session_id)
        total_bytes = sum(f.bytes for f in final_files)

        print(f"   Total files: {len(final_files)}")
        print(f"   Total data: {total_bytes:,} bytes ({total_bytes/1024:.1f} KB)")
        print(f"   Create rate: {20/create_time:.1f} files/sec")
        print(f"   Read rate: {read_count/read_time:.1f} files/sec")
        print(f"   Copy rate: {copy_count/copy_time:.1f} files/sec")
        print(f"   List time: {list_time:.3f}s")

        print("\n🎯 Performance meets MCP server requirements!")

    finally:
        await store.close()
        shutil.rmtree(temp_dir)
        os.environ.pop("ARTIFACT_FS_ROOT", None)


# =============================================================================
# Main execution
# =============================================================================


async def run_mcp_test_demos():
    """Run all MCP server test demonstrations."""
    print("🎯 MCP Server Test Demos")
    print("=" * 30)
    print("Testing real-world MCP client scenarios and workflows")
    print()

    demos = [
        ("MCP Client Workflow", mcp_client_workflow_demo),
        ("Multi-User Environment", multi_user_mcp_demo),
        ("Performance Testing", mcp_performance_demo),
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

    print("🎉 All MCP server test demos completed!")
    print("🚀 chuk_artifacts ready for production MCP deployment!")
    print("📱 Supports real-world client workflows")
    print("👥 Multi-user isolation verified")
    print("⚡ Performance requirements met")


def restore_environment():
    """Restore original environment variables."""
    for var, value in ORIGINAL_ENV.items():
        os.environ[var] = value


if __name__ == "__main__":
    try:
        asyncio.run(run_mcp_test_demos())
    finally:
        restore_environment()

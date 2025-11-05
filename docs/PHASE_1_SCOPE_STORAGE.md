# Phase 1: Scope-Based Storage

## Overview

Phase 1 extends `chuk-artifacts` from session-only storage to support three distinct storage scopes:

| Scope | Lifecycle | Use Case | Access Control |
|-------|-----------|----------|----------------|
| **session** | Ephemeral (15min-24h) | Temporary work files | Session-isolated |
| **user** | Persistent (long/unlimited) | User's saved files | User-owned |
| **sandbox** | Shared (long/unlimited) | Templates, shared resources | Sandbox-wide read, admin-only write |

This enables **persistent user storage** while maintaining the security of session isolation for ephemeral data.

## Architecture Changes

### 1. Grid Path Hierarchy

**Before (session-only):**
```
grid/{sandbox_id}/{session_id}/{artifact_id}
```

**After (scope-based):**
```
Session:  grid/{sandbox_id}/sessions/{session_id}/{artifact_id}
User:     grid/{sandbox_id}/users/{user_id}/{artifact_id}
Sandbox:  grid/{sandbox_id}/shared/{artifact_id}
```

### 2. Metadata Model Extensions

Added to `ArtifactMetadata`:
- `scope`: `"session" | "user" | "sandbox"` (default: `"session"`)
- `owner_id`: User ID for user-scoped artifacts (optional)

### 3. Access Control

New `AccessContext` model and access control rules:
- **Session scope**: Only owning session can read/write
- **User scope**: Only owning user can read/write (across all sessions)
- **Sandbox scope**: Any user can read, write/delete via admin operations only

## API Changes

### Store Artifacts with Scope

```python
# Session-scoped (default, unchanged behavior)
artifact_id = await store.store(
    data=b"...",
    mime="text/plain",
    summary="Temporary file",
    user_id="alice"
    # scope="session" is default
)

# User-scoped (NEW: persistent across sessions)
artifact_id = await store.store(
    data=b"...",
    mime="application/pdf",
    summary="User's document",
    user_id="alice",
    scope="user",  # Persistent!
    ttl=86400 * 365  # 1 year
)

# Sandbox-scoped (NEW: shared by all users)
artifact_id = await store.store(
    data=b"...",
    mime="image/png",
    summary="Company logo",
    scope="sandbox",  # Shared!
    ttl=None  # No expiry
)
```

### Retrieve with Access Control

```python
# Session-scoped: requires session_id
data = await store.retrieve(artifact_id, session_id="sess123")

# User-scoped: requires user_id
data = await store.retrieve(artifact_id, user_id="alice")

# Sandbox-scoped: anyone in sandbox can read
data = await store.retrieve(artifact_id)
```

### Search User Artifacts

```python
# Find all user's artifacts
artifacts = await store.search(user_id="alice", scope="user")

# Find by MIME type
images = await store.search(
    user_id="alice",
    scope="user",
    mime_prefix="image/"
)

# Find by custom metadata
docs = await store.search(
    user_id="alice",
    scope="user",
    meta_filter={"project": "Q4"}
)
```

### Delete with Access Control

```python
# Only owner can delete their artifacts
await store.delete(artifact_id, user_id="alice")

# Sandbox artifacts cannot be deleted via regular API
# Use admin endpoints for sandbox artifact management
```

## MCP Workflow Example

```python
# Session 1: User creates presentation
deck_id = await store.store(
    data=pptx_bytes,
    mime="application/vnd.ms-powerpoint",
    summary="Q4 Sales Deck",
    user_id="alice",
    scope="user",  # Persists beyond session!
)

# Session 2: Different MCP server retrieves and processes
deck_data = await store.retrieve(deck_id, user_id="alice")
video_id = await remotion_server.render(deck_data)

# Session 3: User finds all their work
artifacts = await store.search(user_id="alice", scope="user")
```

## Migration Guide

### Backward Compatibility

✅ **All existing code works without changes**

- Default `scope="session"` maintains current behavior
- Grid paths now use `/sessions/` segment but parse() handles both formats
- No breaking changes to existing APIs

### Opt-In to User Storage

To enable persistent user storage:

```python
# 1. Add scope parameter
await store.store(..., scope="user", user_id="alice")

# 2. Retrieve with user_id instead of session_id
data = await store.retrieve(artifact_id, user_id="alice")

# 3. Search across sessions
artifacts = await store.search(user_id="alice", scope="user")
```

## Security Model

### Access Rules

| Operation | Session Scope | User Scope | Sandbox Scope |
|-----------|---------------|------------|---------------|
| **Read** | Same session only | Same user only | Anyone in sandbox |
| **Write** | Same session only | Same user only | Not allowed* |
| **Delete** | Same session only | Same user only | Not allowed* |

*Use admin operations for sandbox artifacts

### Cross-Scope Protection

❌ **Blocked by design:**
- Cross-session access (session scope)
- Cross-user access (user scope)
- Non-admin writes (sandbox scope)

✅ **Allowed:**
- User accessing own artifacts across sessions (user scope)
- Anyone reading sandbox artifacts (sandbox scope)

## Implementation Files

### Modified Files
- `src/chuk_artifacts/models.py` - Added `scope`, `owner_id`, `AccessContext`
- `src/chuk_artifacts/grid.py` - Updated path generation for scopes
- `src/chuk_artifacts/core.py` - Store operations with scope support
- `src/chuk_artifacts/store.py` - API methods with access control
- `src/chuk_artifacts/exceptions.py` - Added `AccessDeniedError`

### New Files
- `src/chuk_artifacts/access_control.py` - Access control logic
- `examples/user_storage_demo.py` - Comprehensive demo
- `docs/PHASE_1_SCOPE_STORAGE.md` - This document

## Testing

Run the demo:
```bash
python examples/user_storage_demo.py
```

## Next Steps (Phase 2+)

Potential future enhancements:
1. **Streaming uploads/downloads** for large files
2. **Metadata search index** (Elasticsearch/Typesense)
3. **Share links** with expiry and permissions
4. **Webhooks** for artifact events
5. **User quotas** and usage limits

## Notes

- Search is currently brute-force (S3 ListObjects). For production with large datasets, consider a proper search index.
- TTL still applies to user-scoped artifacts. Set `ttl=None` or very long TTL for persistent storage.
- Sandbox-scoped artifacts are read-only for non-admins by design.

---

**Status**: ✅ Phase 1 Complete
**Version**: 1.1.0 (proposed)
**Date**: 2025-11-05

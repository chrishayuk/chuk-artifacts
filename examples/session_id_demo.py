# -*- coding: utf-8 -*-
"""
End-to-end demonstration showcasing **sandbox-ID** propagation through
`ArtifactStore` ⟶ `chuk_sessions.SessionManager` ⟶ grid paths.

Run directly from the project root:

    python examples/session_id_demo.py

The script walks through three distinct scenarios and prints the resulting
canonical prefix and artifact key so you can visually confirm they start with
the expected sandbox namespace.

Scenarios
─────────
1. **Explicit** `sandbox_id` passed to `ArtifactStore` at construction time
2. `ARTIFACT_SANDBOX_ID` **environment variable** supplies the namespace
3. **Auto-generated** sandbox ID when nothing is provided (looks like
   `sandbox-xxxxxxxx`)

Each step:
• Allocates a fresh session  
• Stores a tiny in-memory artifact  
• Prints out the sandbox ID, session ID, canonical prefix, generated key, and
  the key recorded in metadata.
"""

from __future__ import annotations

import os
import asyncio
import textwrap

from chuk_artifacts import ArtifactStore
from chuk_artifacts.config import configure_memory

# ─────────────────────────────────────────────────────────────────────────────
# Helper for a single scenario
# ─────────────────────────────────────────────────────────────────────────────

async def demo_case(title: str, *, sandbox_id: str | None = None, env_var: str | None = None):
    """Run one sandbox-ID demo scenario and pretty-print the results."""
    print(f"\n{title}\n" + "-" * len(title))

    # Ensure memory providers so the demo is self-contained
    configure_memory()

    # Manage environment var influence
    if env_var is not None:
        os.environ["ARTIFACT_SANDBOX_ID"] = env_var
    else:
        os.environ.pop("ARTIFACT_SANDBOX_ID", None)

    # Instantiate store (optionally with explicit sandbox_id)
    store = ArtifactStore(sandbox_id=sandbox_id)

    try:
        # Allocate session + store artifact
        session_id = await store.create_session(user_id="demo-user")
        artifact_id = await store.store(
            b"hello-sandbox", mime="text/plain", summary="demo-artifact", session_id=session_id
        )

        # Gather details
        canonical_prefix = store.get_canonical_prefix(session_id)
        artifact_key = store.generate_artifact_key(session_id, artifact_id)
        metadata = await store.metadata(artifact_id)

        # Print nicely-formatted block
        print(textwrap.dedent(f"""
            Sandbox ID       : {store.sandbox_id}
            Session ID       : {session_id}
            Canonical prefix : {canonical_prefix}
            Generated key    : {artifact_key}
            Metadata['key']  : {metadata['key']}
        """))

    finally:
        await store.close()


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point running all scenarios sequentially
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print("🧪  Sandbox-ID End-to-End Demonstration  🧪")

    await demo_case(
        "1️⃣  Explicit sandbox_id parameter",
        sandbox_id="explicit-sandbox",
        env_var=None,
    )

    await demo_case(
        "2️⃣  ARTIFACT_SANDBOX_ID environment variable",
        sandbox_id=None,
        env_var="env-sandbox",
    )

    await demo_case(
        "3️⃣  Auto-generated sandbox_id (fallback)",
        sandbox_id=None,
        env_var=None,
    )

    print("\n✅  Demo completed – sandbox namespaces propagate correctly!\n")


if __name__ == "__main__":
    asyncio.run(main())

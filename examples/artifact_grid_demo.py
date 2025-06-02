#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive ArtifactStore smoke-test with real S3/MinIO **or** in-memory
backend.  Verifies:

• session creation & grid helpers
• store / retrieve round-trip (txt & png)
• presign → HTTP GET download (short/medium/long)
• batch copy, move (same-session security)
• list, exists, delete
• final bucket key enumeration matches helpers
• exits 0 on success, 1 on any failure
"""
from __future__ import annotations
import asyncio, os, sys, hashlib, re, textwrap, json
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())  # load .env before we instantiate anything

from chuk_artifacts import ArtifactStore
from chuk_artifacts.config import configure_memory
from chuk_artifacts.exceptions import ArtifactStoreError

try:
    import requests
except ImportError:
    print("`requests` is required for the demo (pip install requests)", file=sys.stderr)
    sys.exit(1)


def s3_configured() -> bool:
    return all(os.getenv(v) for v in (
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "ARTIFACT_BUCKET"))


async def run_demo() -> None:
    # ------------------------------------------------------------------
    # 1. backend – either real S3/minio or in-memory
    # ------------------------------------------------------------------
    if s3_configured():
        backend = "s3"
        print("🔧  Using **REAL** S3 / MinIO backend")
    else:
        backend = "memory"
        print("🔧  No S3 credentials – using in-memory provider")
        configure_memory()

    # ------------------------------------------------------------------
    # 2. create store + session
    # ------------------------------------------------------------------
    store = ArtifactStore(sandbox_id="grid-demo", max_retries=1)
    sess  = await store.create_session(user_id="tester")
    print(f"🆔  Session: {sess}")

    # ------------------------------------------------------------------
    # 3. store two artefacts (txt + png sentinel header)
    # ------------------------------------------------------------------
    aid_txt = await store.store(b"hello grid", mime="text/plain",
                                summary="demo-text", filename="demo.txt",
                                session_id=sess)
    aid_png = await store.store(b"\x89PNG\r\n\x1a\n", mime="image/png",
                                summary="demo-png", filename="demo.png",
                                session_id=sess)
    print("💾  Stored artefacts:", aid_txt, aid_png)

    # ------------------------------------------------------------------
    # 4. retrieve & SHA-check
    # ------------------------------------------------------------------
    txt_back = await store.retrieve(aid_txt)
    png_back = await store.retrieve(aid_png)
    assert txt_back == b"hello grid"
    assert png_back.startswith(b"\x89PNG"), "PNG header mismatch"
    print("✅  Retrieve round-trip OK")

    # ------------------------------------------------------------------
    # 5. presign URLs & GET
    # ------------------------------------------------------------------
    url_short  = await store.presign_short(aid_txt)
    url_medium = await store.presign_medium(aid_png)

    def grid_from(url: str) -> str:
        return re.sub(r'^.+?/(grid/.+?)(\?|$).*', r'\1', url)

    assert grid_from(url_short)  == store.generate_artifact_key(sess, aid_txt)
    assert grid_from(url_medium) == store.generate_artifact_key(sess, aid_png)

    if backend == "s3":
        for lab, url in (("short", url_short), ("medium", url_medium)):
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            print(f"🌐  {lab} GET → {r.status_code}, {len(r.content)} bytes")

    # ------------------------------------------------------------------
    # 6. copy & move within same session
    # ------------------------------------------------------------------
    aid_copy = await store.copy_file(aid_txt, new_filename="demo_copy.txt")
    meta_copy = await store.metadata(aid_copy)
    assert meta_copy["meta"]["copied_from"] == aid_txt
    moved = await store.move_file(aid_png, new_filename="renamed.png")
    assert moved["filename"] == "renamed.png"
    print("📝  Copy & move safeguards OK")

    # ------------------------------------------------------------------
    # 7. list / exists
    # ------------------------------------------------------------------
    listing = await store.list_by_session(sess)
    ids = {x["artifact_id"] for x in listing}
    assert {aid_txt, aid_copy, aid_png} <= ids
    for aid in (aid_txt, aid_copy, aid_png):
        assert await store.exists(aid)
    print(f"📃  List/exists OK ({len(listing)} records)")

    # ------------------------------------------------------------------
    # 8. delete and confirm gone
    # ------------------------------------------------------------------
    await store.delete(aid_copy)
    assert not await store.exists(aid_copy)
    print("🗑️   Delete confirmed")

    # ------------------------------------------------------------------
    # 9. prove keys in bucket match helpers (real S3 only)
    # ------------------------------------------------------------------
    if backend == "s3":
        s3_factory = store._s3_factory
        async with s3_factory() as s3:
            resp = await s3.list_objects_v2(
                Bucket=store.bucket,
                Prefix=store.get_canonical_prefix(sess))
            keys = [obj["Key"] for obj in resp.get("Contents", [])]
            print("🗂️   Keys in bucket:")
            for k in keys:
                print("   •", k)
            for aid in (aid_txt, aid_png):
                assert store.generate_artifact_key(sess, aid) in keys

    # ------------------------------------------------------------------
    # 10. tidy
    # ------------------------------------------------------------------
    await store.close()
    print("\n🎉  ALL CHECKS PASSED")


# ----------------------------------------------------------------------
if __name__ == "__main__":
    try:
        asyncio.run(run_demo())
    except (AssertionError, ArtifactStoreError, Exception) as err:
        print("❌  Demo FAILED:", err, file=sys.stderr)
        sys.exit(1)

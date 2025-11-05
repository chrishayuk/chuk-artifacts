# -*- coding: utf-8 -*-
# chuk_artifacts/providers/__init__.py
"""
Convenience re-exports so caller code can do:

    from chuk_artifacts.providers import s3, ibm_cos, memory, filesystem, vfs_adapter
"""

from . import s3, ibm_cos, memory, filesystem, vfs_adapter

__all__ = ["s3", "ibm_cos", "memory", "filesystem", "vfs_adapter"]

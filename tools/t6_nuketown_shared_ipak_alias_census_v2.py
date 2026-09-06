#!/usr/bin/env python3
"""Shared-IPAK packed-image alias census v2.

Runs the retained v1 census/proof logic unchanged while substituting the exact
0xCF skip-aware T6 IPAK range reader v2.  This isolates the transport/container
fix from the alias proof logic so the earlier proof boundary cannot drift.
"""
from __future__ import annotations

import t6_nuketown_shared_ipak_alias_census_v1 as v1
from t6_ipak_http_range_v2 import open_ipak

# v1 resolves open_ipak as a module global; replace only that dependency.
v1.open_ipak = open_ipak

if __name__ == "__main__":
    raise SystemExit(v1.main())

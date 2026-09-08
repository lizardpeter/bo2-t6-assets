#!/usr/bin/env python3
"""Extend the exact T6 PC dedicated-server XAsset override proof to code_post_gfx_mp.

This adapter reuses the fail-closed v1 EXE/MAP/function-byte gates, then closes
one additional startup row end to end:

    "code_post_gfx" + "_mp" -> CODE_FAST_FILE_NAME -> allocFlags 0x08
    -> DB_GetZonePriority(0x08) -> 52.

Authority remains restricted to the exact SHA-pinned PC dedicated-server build.
It must not select a retail t6mp.exe client winner.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import t6_pc_server_xasset_override_proof_v1 as v1

FORMAT = "t6-pc-server-xasset-override-proof-v2"
CODE_POST_GFX_MP_ALLOC_FLAG = 0x00000008
CODE_POST_GFX_MP_PRIORITY = 52
VA_CODE_FAST_FILE_NAME = 0x017F6404
VA_STR_CODE_POST_GFX = 0x00BD435C


def build(exe: Path, map_path: Path) -> dict:
    result = v1.build(exe, map_path)
    pe = v1.PE(exe)

    if pe.cstr(VA_STR_CODE_POST_GFX) != "code_post_gfx":
        raise v1.ProofError("unexpected code_post_gfx base string")

    evidence = result["instructionEvidence"]
    evidence.append(v1._expect_bytes(
        pe,
        0x00551A51,
        "6a18685c43bd006804647f01e86ec52300",
        "CODE_FAST_FILE_NAME <- 'code_post_gfx' base",
    ))
    evidence.append(v1._expect_bytes(
        pe,
        0x00551BF9,
        "685c4035016a186804647f01e806c92300",
        "append mode-selected _mp/_zm suffix to CODE_FAST_FILE_NAME",
    ))
    evidence.append(v1._expect_bytes(
        pe,
        0x0055024E,
        "4883f81f0f87440100000fb680f0035500ff",
        "DB_GetZonePriority low-flag indexed dispatch",
    ))
    evidence.append(v1._expect_bytes(
        pe,
        0x005503D4,
        "74025500890255006d0255007b02550066025500820255009c035500",
        "DB_GetZonePriority low-flag jump table",
    ))
    evidence.append(v1._expect_bytes(
        pe,
        0x005503F0,
        "0001060206060603060606060606060406060606060606060606060606060605",
        "DB_GetZonePriority low-flag index table",
    ))
    evidence.append(v1._expect_bytes(
        pe,
        0x0055027B,
        "b8340000005dc3",
        "DB_GetZonePriority selected return -> 52",
    ))

    priority = v1._decode_low_priority(pe, CODE_POST_GFX_MP_ALLOC_FLAG)
    if priority != CODE_POST_GFX_MP_PRIORITY:
        raise v1.ProofError(
            f"code_post_gfx_mp flag priority mismatch {priority} != {CODE_POST_GFX_MP_PRIORITY}"
        )

    naming = result["fastFileNaming"]
    naming["codePostGfxBase"] = "code_post_gfx"
    naming["codeFastFileGlobalVaHex"] = f"0x{VA_CODE_FAST_FILE_NAME:08x}"
    naming["mpResolvedNames"]["codePostGfx"] = "code_post_gfx_mp"

    result["mpFlags"]["code_post_gfx_mp"] = {
        "allocFlagsHex": f"0x{CODE_POST_GFX_MP_ALLOC_FLAG:08x}",
        "priority": priority,
    }

    patch_priority = result["mpFlags"]["patch_mp"]["priority"]
    common_priority = result["mpFlags"]["common_mp"]["priority"]
    map_priority = result["mpFlags"]["ordinaryBuiltInMpMap"]["priority"]
    if not patch_priority > map_priority > common_priority > priority:
        raise v1.ProofError(
            "unexpected exact server MP priority ordering; expected "
            "patch > built-in map > common > code_post_gfx_mp"
        )

    result["overrideRule"]["codePostGfxVsPatchServerPrediction"] = "patch_mp"
    result["overrideRule"]["codePostGfxVsPatchReason"] = (
        f"patch priority {patch_priority} > code_post_gfx_mp priority {priority}; "
        "load order cannot change this pair's winner"
    )
    result["format"] = FORMAT
    result["authority"]["state"] = (
        "exact-pc-dedicated-server-proof-including-code-post-gfx-mp-client-promotion-blocked"
    )
    result["proofBoundary"] = (
        "Authoritative for the ordinary duplicate-XAsset precedence path and the exact "
        "common_mp, patch_mp, code_post_gfx_mp, and ordinary built-in MP-map load flags/" 
        "priorities in the SHA-pinned CoDMPServer_PC.exe + linker MAP pair only. It proves "
        "code_post_gfx is suffixed to code_post_gfx_mp, loaded with allocFlags 0x08, and "
        "routes through the exact low-flag DB_GetZonePriority dispatch to priority 52. "
        "It does not prove that the retail t6mp.exe client uses identical function bytes, "
        "priority values, flag mask, special-case branches, or load-call constants. No "
        "production retail-client Material/Technique winner may be selected from this server proof alone."
    )
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("exe", type=Path)
    p.add_argument("map", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = build(a.exe.resolve(), a.map.resolve())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "authority": result["authority"],
        "mpFlags": result["mpFlags"],
        "overrideRule": result["overrideRule"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

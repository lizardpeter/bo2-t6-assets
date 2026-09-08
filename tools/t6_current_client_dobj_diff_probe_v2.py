#!/usr/bin/env python3
"""Non-authoritative T6 DObj differential probe using retail-proven skeleton anchors.

The comparison client is never promoted as retail authority.  v2 uses byte
anchors and whole-function ranges already retained from the exact retail
root-translation proof to locate homologous skeleton helpers, then enumerates
callers and raw pointer chains to surviving DObj diagnostics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM

from t6_current_client_dobj_diff_probe_v1 import PE, ProbeError, NEEDLES, find_all

FORMAT = "t6-current-client-dobj-differential-probe-v2"
RETAIL_SHA = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"

# Exact byte witnesses already pinned by T6_RETAIL_XANIM_ROOT_TRANSLATION_PROOF_V1.
ANCHORS = {
    "rootNoParentPrologue": "83ec0c530fb6580503d9",
    "rootWithParentPrologue": "81ec940000000fb6490503c8",
    "nonRootPrologue": "83ec78558bac24800000000fb645050fb655042bd0",
    "nonRootParentListLookup": "8b4d0c894424108bc22b942494000000c1e0050fb62c11",
    "nonRootBindTranslationAdd": (
        "8bac248c0000008b75148d1452"
        "f30f100496f30f584010f30f114010"
        "f30f10449604f30f584014f30f114014"
        "f30f10449608f30f584018f30f114018"
    ),
}

RETAIL_RANGES = {
    "rootNoParent": (0x8D6100, 0x8D621A, "d9c24ad6bececdb1bb0ad589cf3ce11abe6e1e5d9156c7db02df19a6833f210e"),
    "rootWithParent": (0x8D6220, 0x8D6A09, "95d74b97dd45e934941f4679deb9ed5c375e03ffea36ec8de3359ee720eb5b1f"),
    "nonRoot": (0x8D6B50, 0x8D7212, "bf7fdb9128bdc11caa97e0338dd14495d1a4f94c1beab931abbf062c16b014eb"),
}


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def section_for_off(pe: PE, off: int) -> str | None:
    for s in pe.sections:
        if s["rawOff"] <= off < s["rawOff"] + s["rawSize"]:
            return s["name"]
    return None


def pointer_refs(data: bytes, pe: PE, va: int) -> list[dict]:
    raw = struct.pack("<I", va)
    rows = []
    for off in find_all(data, raw):
        rows.append({"fileOffset": off, "va": pe.off_to_va(off), "section": section_for_off(pe, off)})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--expected-bytes", type=int, required=True)
    ap.add_argument("--expected-sha256", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--disasm-out", type=Path, required=True)
    args = ap.parse_args()

    data = args.exe.read_bytes()
    actual_sha = sha256(data)
    if len(data) != args.expected_bytes or actual_sha != args.expected_sha256.lower():
        raise ProbeError(f"comparison identity mismatch bytes={len(data)} sha={actual_sha}")
    pe = PE(data)

    anchor_rows = {}
    anchor_vas = set()
    for label, hx in ANCHORS.items():
        raw = bytes.fromhex(hx)
        rows = []
        for off in find_all(data, raw):
            va = pe.off_to_va(off)
            rows.append({"fileOffset": off, "va": va, "section": section_for_off(pe, off)})
            if va is not None:
                anchor_vas.add(va)
        anchor_rows[label] = {"bytes": len(raw), "occurrenceCount": len(rows), "occurrences": rows}

    same_address = {}
    for label, (start, end, retail_hash) in RETAIL_RANGES.items():
        try:
            off = pe.va_to_off(start)
            raw = data[off:off + (end-start)]
            got = sha256(raw)
            same_address[label] = {
                "startVa": start,
                "endVa": end,
                "bytes": end-start,
                "retailSha256": retail_hash,
                "comparisonSha256": got,
                "exactAtSameAddress": got == retail_hash,
            }
        except Exception as exc:
            same_address[label] = {"startVa": start, "endVa": end, "error": repr(exc), "exactAtSameAddress": False}

    # Direct callers of any exact retail anchor occurrence in the comparison client.
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    callers = []
    for s in pe.sections:
        if not s["executable"]:
            continue
        raw = data[s["rawOff"]:s["rawOff"]+s["rawSize"]]
        for insn in md.disasm(raw, s["va"]):
            if insn.mnemonic != "call" or not insn.operands or insn.operands[0].type != X86_OP_IMM:
                continue
            target = int(insn.operands[0].imm)
            if target in anchor_vas:
                callers.append({"callVa": insn.address, "targetVa": target, "section": s["name"]})

    # Surviving DObj text may be reached indirectly through data/rdata tables.
    pointer_chains = []
    for label, needle in NEEDLES.items():
        for str_off in find_all(data, needle):
            str_va = pe.off_to_va(str_off)
            if str_va is None:
                continue
            level1 = pointer_refs(data, pe, str_va)
            level2 = []
            for r in level1:
                if r["va"] is not None:
                    level2.extend({"viaVa": r["va"], **x} for x in pointer_refs(data, pe, int(r["va"])))
            pointer_chains.append({
                "label": label,
                "stringVa": str_va,
                "level1Refs": level1,
                "level2Refs": level2,
            })

    # Emit bounded disassembly around helper callers.  No guessed function boundaries.
    lines = []
    windows = []
    for c in callers:
        center = c["callVa"]
        start = center - 0x100
        try:
            off = pe.va_to_off(start)
        except Exception:
            continue
        raw = data[off:off+0x280]
        insns = list(md.disasm(raw, start))
        lines.append(f"===== helper caller 0x{center:08X} -> 0x{c['targetVa']:08X} sha={sha256(raw)} =====")
        lines.extend(f"0x{i.address:08X}: {i.mnemonic:<8} {i.op_str}".rstrip() for i in insns)
        lines.append("")
        windows.append({"callVa": center, "targetVa": c["targetVa"], "windowStartVa": start, "bytes": len(raw), "sha256": sha256(raw)})

    doc = {
        "format": FORMAT,
        "authority": "NON_AUTHORITATIVE_CURRENT_CLIENT_DIFFERENTIAL_ONLY",
        "comparisonExecutable": {"bytes": len(data), "sha256": actual_sha, "imageBaseHex": f"0x{pe.image_base:08X}"},
        "retailAuthorityReference": {"sha256": RETAIL_SHA, "manifest": "manifests/xanim/T6_RETAIL_XANIM_ROOT_TRANSLATION_PROOF_V1.json"},
        "retailProvenAnchorMatches": anchor_rows,
        "retailWholeFunctionRangesAtSameAddress": same_address,
        "helperCallerCount": len(callers),
        "helperCallers": callers,
        "callerWindows": windows,
        "dobjDiagnosticPointerChains": pointer_chains,
        "proofBoundary": (
            "Every byte in this document comes from the SHA-pinned current Plutonium comparison client or from exact "
            "retail byte witnesses already retained in the root-translation proof. Matching a retail witness can locate "
            "homologous code, but no comparison-client-only byte, address, call, warning, pointer chain, or inferred "
            "DObj behavior is retail-authoritative."
        ),
    }
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(payload, encoding="utf-8")
    args.disasm_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "anchors": {k: v["occurrenceCount"] for k,v in anchor_rows.items()},
        "sameAddressWholeFunctionsExact": {k: v.get("exactAtSameAddress") for k,v in same_address.items()},
        "helperCallerCount": len(callers),
        "diagnosticPointerChainCount": len(pointer_chains),
        "manifestSha256": sha256(payload.encode()),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

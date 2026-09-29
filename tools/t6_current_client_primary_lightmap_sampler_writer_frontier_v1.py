#!/usr/bin/env python3
"""Project the exact +0x1610 dword-writer proof onto primary-lightmap slot 4.

The already-retained slot-6 proof closes the complete decoded writer denominator
for the packed dword at source+0x1610.  This tool does not re-disassemble the
client.  It reuses those exact writer/value proofs and asks a different question:
what do they imply for byte 0 of that same dword, i.e. codeImageSamplerStates[4]?

This deliberately does NOT claim a final slot-4 value when a writer proof only
bounds the packed dword.  It isolates the exact writers whose low byte still
depends on caller/runtime data.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

FMT = "t6-current-client-primary-lightmap-sampler-writer-frontier-v1"
SOURCE_FMT = "t6-current-client-shadowmap-sampler-sun-all-writer-state-byte-semantics-v1"
EXPECTED = [
    "0x004555a6", "0x009a7d3f", "0x009a7dd3", "0x009bcde7",
    "0x009bd388", "0x009c1dbb", "0x009c2a88",
]

def req(v, m):
    if not v:
        raise SystemExit(m)

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all-writers", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    src = json.loads(a.all_writers.read_text())
    req(src.get("format") == SOURCE_FMT, "source format drift")
    writers = src.get("writers", [])
    req([x.get("writerVa") for x in writers] == EXPECTED, "writer denominator drift")
    req(src.get("summary", {}).get("writerDenominatorComplete") is True,
        "source writer denominator is not closed")

    rows = []
    for w in writers:
        va = w["writerVa"]
        upper = int(w["packedUpperBound"])
        basis = w["basis"]
        if upper == 0:
            row = {
                "writerVa": va, "slot4ValueClosed": True, "slot4Value": 0,
                "basis": basis,
            }
        elif upper == 1:
            # These source proofs are not merely bounds: their bases say ECX=1/EBX=1.
            req(basis in {"ECX=1", "EBX=1"}, f"{va}: value-1 basis drift")
            row = {
                "writerVa": va, "slot4ValueClosed": True, "slot4Value": 1,
                "basis": basis,
            }
        else:
            # A packed <=0x15ff proof is sufficient to force byte2=0, but says
            # nothing constant about byte0.  Do not silently promote it.
            req(upper == 0x15ff, f"{va}: unexpected nonconstant packed bound {upper:#x}")
            row = {
                "writerVa": va,
                "slot4ValueClosed": False,
                "slot4AllowedByExistingProof": [0, 255],
                "packedUpperBound": upper,
                "basis": basis,
                "remainingProof": (
                    "identify the exact caller/runtime inputs reaching this writer "
                    "for lightmapSamplerPrimary and project the resulting low byte"
                ),
            }
        rows.append(row)

    unresolved = [x["writerVa"] for x in rows if not x["slot4ValueClosed"]]
    req(unresolved == ["0x009a7d3f", "0x009a7dd3"], "unexpected slot-4 frontier")

    doc = {
        "format": FMT,
        "authority": (
            "byte-0 projection of the complete exact current-client +0x1610 "
            "dword-writer denominator/value proofs"
        ),
        "geometry": {
            "samplerStateArrayOffset": 0x160c,
            "slotIndex": 4,
            "targetByteOffset": 0x1610,
            "packedDwordOffset": 0x1610,
            "byteIndex": 0,
            "accessor": "lightmapSamplerPrimary",
        },
        "source": {
            "path": str(a.all_writers).replace("\\", "/"),
            "sha256": sha(a.all_writers),
            "format": SOURCE_FMT,
        },
        "writers": rows,
        "summary": {
            "writerInstructionCount": len(rows),
            "writerDenominatorReusedFromExactProof": True,
            "slot4ExactWriterCount": len(rows) - len(unresolved),
            "slot4RuntimeDependentWriterCount": len(unresolved),
            "remainingWriterVAs": unresolved,
            "finalSlot4ValueClosed": False,
        },
        "proofBoundary": (
            "This closes which members of the already-complete +0x1610 writer "
            "denominator have a constant byte-0 value. It proves five writer values "
            "exactly (0/1) and narrows the primary-lightmap frontier to the two packed "
            "builders 0x009A7D3F and 0x009A7DD3. It does not claim every low-byte value "
            "0..255 is runtime-reachable, identify the lightmap caller path, order all "
            "writers at runtime, map numeric bytes to API sampler enums, or prove a "
            "historical executable build."
        ),
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Reclassify T6 +0x1610 overlap writers using exact base-object provenance.

This probe joins two already-retained SHA-pinned proofs:
- exact bodies/direct callers for 0x009A7D00 and 0x009A7D60;
- exact ABI/behavior of 0x00A72BF0 as an overlap-safe byte transfer helper.

The original displacement-overlap census treated writes at +0x1610 as possible
codeImageSamplerStates[4..7] writers. That is not sufficient object identity.
This projector proves the observed direct call occurrences pass stack-derived
local objects and that the builders use the object as a sliding byte-transfer
window. It therefore reclassifies those observed occurrences as displacement
collisions, not accepted GfxCmdBufSource sampler-state writer evidence.

It deliberately does not claim that an unobserved indirect caller can never call
these generic builders with some other object. The result is an evidence-policy
correction: displacement alone cannot enter the accepted sampler writer
denominator without base-object provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FORMAT = "t6-current-client-primary-lightmap-writer-object-provenance-v1"
CLIENT = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
CALLERS_FORMAT = "t6-current-client-primary-lightmap-sampler-callers-v1"


def req(cond: bool, message: str) -> None:
    if not cond:
        raise SystemExit(message)


def index_rows(rows):
    return {row["address"].lower(): row for row in rows}


def exact(row, va: str, mnemonic: str, op: str) -> None:
    req(row is not None, f"missing {va}")
    req(row["mnemonic"] == mnemonic and row["opStr"] == op,
        f"{va} drift: {(row['mnemonic'], row['opStr'])!r}")


def transfer_for(target, va: str):
    hits = [
        x for x in target["incomingTransfers"]
        if x["transfer"]["address"].lower() == va.lower()
    ]
    req(len(hits) == 1, f"expected one transfer at {va}, got {len(hits)}")
    return hits[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--callers", type=Path, required=True)
    ap.add_argument("--transfer-helper", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    callers = json.loads(a.callers.read_text())
    helper = json.loads(a.transfer_helper.read_text())

    req(callers.get("format") == CALLERS_FORMAT, "caller proof format drift")
    req(callers.get("client", {}).get("sha256") == CLIENT, "caller client drift")
    req(helper.get("client", {}).get("sha256") == CLIENT, "helper client drift")

    tf = callers["targetFunctions"]
    init = tf["0x009a7d00"]
    update = tf["0x009a7d60"]
    im = index_rows(init["instructions"])
    um = index_rows(update["instructions"])

    exact(im.get("0x009a7d2b"), "0x009A7D2B", "mov", "dword ptr [esi + 0x160c], 4")
    exact(im.get("0x009a7d3f"), "0x009A7D3F", "mov", "dword ptr [esi + 0x1610], eax")
    exact(im.get("0x009a7d45"), "0x009A7D45", "call", "0xa72bf0")

    exact(um.get("0x009a7d71"), "0x009A7D71", "mov", "dword ptr [esi + 0x160c], 0")
    exact(um.get("0x009a7d84"), "0x009A7D84", "mov", "edi, dword ptr [ecx + esi - 4]")
    exact(um.get("0x009a7d88"), "0x009A7D88", "mov", "dword ptr [esi], edi")
    exact(um.get("0x009a7dc4"), "0x009A7DC4", "lea", "eax, [esi + 4]")
    exact(um.get("0x009a7dc8"), "0x009A7DC8", "call", "0xa72bf0")
    exact(um.get("0x009a7dd3"), "0x009A7DD3", "mov", "dword ptr [esi + 0x1610], edi")

    targets = {x["targetVa"].lower(): x for x in callers["targets"]}
    init_call = transfer_for(targets["0x009a7d00"], "0x009AFF48")
    update_call = transfer_for(targets["0x009a7d60"], "0x009B007A")

    ib = index_rows(init_call["contextBefore"])
    ub = index_rows(update_call["contextBefore"])

    exact(ib.get("0x009aff37"), "0x009AFF37", "push", "eax")
    exact(ib.get("0x009aff38"), "0x009AFF38", "mov", "eax, dword ptr [esp + 0x1644]")
    exact(ib.get("0x009aff3f"), "0x009AFF3F", "lea", "ecx, [eax + edx]")
    exact(ib.get("0x009aff42"), "0x009AFF42", "push", "ecx")
    exact(ib.get("0x009aff43"), "0x009AFF43", "push", "eax")
    exact(ib.get("0x009aff44"), "0x009AFF44", "lea", "ecx, [esp + 0x2c]")

    exact(ub.get("0x009b0076"), "0x009B0076", "lea", "ecx, [esp + 0x20]")

    th = helper["transferHelper"]
    req(th["entry"].lower() == "0x00a72bf0", "transfer helper entry drift")
    req(th["abi"] == {"arg1": "destination", "arg2": "source", "arg3": "byte count"},
        "transfer helper ABI drift")
    req("rep movsd" in th["forwardEvidence"], "forward byte-transfer evidence drift")
    req("std; rep movsd; cld" in th["overlapEvidence"], "overlap-safe evidence drift")

    result = {
        "format": FORMAT,
        "authority": "join of retained exact SHA-pinned current-client machine-code proofs",
        "client": callers["client"],
        "observedDirectOccurrences": [
            {
                "builder": "0x009A7D00",
                "writer": "0x009A7D3F",
                "caller": "0x009AFF48",
                "baseObjectProvenance": "ECX = ESP + 0x2C immediately before direct call",
                "objectClass": "stack-derived local transfer window",
                "windowEvidence": [
                    "builder stores cursor/end/size metadata at +0x1604/+0x1608/+0x1610",
                    "builder calls 0x00A72BF0 with destination=self and byte count from the +0x1610 value",
                ],
                "samplerWriterClassification": "exclude-from-accepted-denominator",
            },
            {
                "builder": "0x009A7D60",
                "writer": "0x009A7DD3",
                "caller": "0x009B007A",
                "baseObjectProvenance": "ECX = ESP + 0x20 immediately before direct call",
                "objectClass": "stack-derived local sliding transfer window",
                "windowEvidence": [
                    "builder reads/writes payload at self and self+4",
                    "builder slides/copies bytes through 0x00A72BF0",
                    "builder updates cursor/end/span metadata at +0x1604/+0x1608/+0x1610",
                ],
                "samplerWriterClassification": "exclude-from-accepted-denominator",
            },
        ],
        "transferHelper": {
            "entry": th["entry"],
            "abi": th["abi"],
            "behavior": "overlap-safe memmove-style byte transfer",
        },
        "policyConclusion": {
            "oldRule": "displacement overlap at +0x1610 admitted a possible codeImageSamplerStates writer",
            "correctRule": "a sampler writer requires base-object provenance to the GfxCmdBufSource occurrence; displacement alone is evidence of layout overlap only",
            "reclassifiedWriterVAs": ["0x009A7D3F", "0x009A7DD3"],
            "acceptedAsPrimaryLightmapWriterEvidence": False,
        },
        "remainingFrontier": (
            "Trace writes from an object proven to be the GfxCmdBufSource/source occurrence "
            "used by the generic code-sampler consumers. Re-run the +0x1610 writer census "
            "with base-object provenance instead of raw displacement matching."
        ),
        "proofBoundary": (
            "This excludes the two observed direct-call occurrences from the accepted "
            "GfxCmdBufSource sampler-writer denominator. It does not prove the builder "
            "entry points can never be reached indirectly with another object, and it "
            "does not assign a final primary-lightmap sampler-state byte."
        ),
    }

    payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(payload)
    print(json.dumps({
        "proofSha256": hashlib.sha256(payload).hexdigest(),
        "reclassifiedWriterVAs": result["policyConclusion"]["reclassifiedWriterVAs"],
        "remainingFrontier": result["remainingFrontier"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

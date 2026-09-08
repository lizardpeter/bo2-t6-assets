#!/usr/bin/env python3
"""Measure exact relocation homology between retail-proven T6 skeleton code and current client.

NON-AUTHORITATIVE for retail-only DObj behavior.  The only retail inputs are byte
witnesses already retained in T6_RETAIL_XANIM_ROOT_TRANSLATION_PROOF_V1.
"""
from __future__ import annotations

import argparse, hashlib, json, struct
from pathlib import Path

from t6_current_client_dobj_diff_probe_v1 import PE, ProbeError, find_all
from t6_current_client_dobj_diff_probe_v2 import ANCHORS, RETAIL_RANGES, RETAIL_SHA

FORMAT = "t6-current-client-dobj-differential-probe-v3"
RETAIL_ANCHOR_VA = {
    "rootNoParentPrologue": 0x8D6100,
    "rootWithParentPrologue": 0x8D6220,
    "nonRootPrologue": 0x8D6B50,
    "nonRootParentListLookup": 0x8D6C20,
    "nonRootBindTranslationAdd": 0x8D7016,
}
RETAIL_CONSUMER_WITNESSES = {
    "consumerA_modelParentSentinel": (0x422A6F, "81faff000000"),
    "consumerA_nonRootStart": (0x422ACD, "0fb64d05034c2410"),
    "consumerB_modelParentSentinel": (0x5C6948, "81f9ff000000"),
    "consumerB_nonRootStart": (0x5C69B3, "0fb64805034c2414"),
}
RETAIL_CALL_SITES = {
    "consumerA_rootNoParent": (0x422A83, "rootNoParentPrologue"),
    "consumerA_rootWithParent": (0x422AC5, "rootWithParentPrologue"),
    "consumerA_nonRoot": (0x422AE2, "nonRootPrologue"),
    "consumerB_rootNoParent": (0x5C6962, "rootNoParentPrologue"),
    "consumerB_rootWithParent": (0x5C69A2, "rootWithParentPrologue"),
    "consumerB_nonRoot": (0x5C69C7, "nonRootPrologue"),
}


def sha256(b: bytes) -> str: return hashlib.sha256(b).hexdigest()


def read_va(pe: PE, data: bytes, va: int, n: int) -> bytes:
    off = pe.va_to_off(va)
    return data[off:off+n]


def rel32_target(pe: PE, data: bytes, va: int) -> int | None:
    try:
        raw = read_va(pe, data, va, 5)
    except Exception:
        return None
    if raw[0] not in (0xE8, 0xE9):
        return None
    rel = struct.unpack_from("<i", raw, 1)[0]
    return va + 5 + rel


def raw_rel32_callers(pe: PE, data: bytes, target: int) -> list[dict]:
    rows = []
    for s in pe.sections:
        if not s["executable"]:
            continue
        raw = data[s["rawOff"]:s["rawOff"]+s["rawSize"]]
        base = s["va"]
        for i in range(0, max(0, len(raw)-4)):
            if raw[i] != 0xE8:
                continue
            rel = struct.unpack_from("<i", raw, i+1)[0]
            va = base+i
            if va+5+rel == target:
                rows.append({"callVa": va, "section": s["name"]})
    return rows


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("exe",type=Path)
    ap.add_argument("--expected-bytes",type=int,required=True)
    ap.add_argument("--expected-sha256",required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    data=args.exe.read_bytes(); actual=sha256(data)
    if len(data)!=args.expected_bytes or actual!=args.expected_sha256.lower():
        raise ProbeError(f"comparison identity mismatch bytes={len(data)} sha={actual}")
    pe=PE(data)

    found={}
    shifts=[]
    for label,hx in ANCHORS.items():
        occ=[]
        for off in find_all(data,bytes.fromhex(hx)):
            va=pe.off_to_va(off)
            if va is not None: occ.append(va)
        found[label]=occ
        if len(occ)==1:
            shifts.append(occ[0]-RETAIL_ANCHOR_VA[label])
    unique_shifts=sorted(set(shifts))
    uniform_shift=unique_shifts[0] if len(shifts)==len(ANCHORS) and len(unique_shifts)==1 else None

    shifted_ranges={}
    if uniform_shift is not None:
        for label,(rstart,rend,rhash) in RETAIL_RANGES.items():
            cstart=rstart+uniform_shift
            raw=read_va(pe,data,cstart,rend-rstart)
            ch=sha256(raw)
            shifted_ranges[label]={
                "retailStartVa":rstart,"comparisonStartVa":cstart,"bytes":rend-rstart,
                "retailSha256":rhash,"comparisonSha256":ch,"byteIdenticalAfterRelocation":ch==rhash,
            }

    consumer_witnesses={}
    call_sites={}
    if uniform_shift is not None:
        for label,(rva,hx) in RETAIL_CONSUMER_WITNESSES.items():
            cva=rva+uniform_shift; want=bytes.fromhex(hx); got=read_va(pe,data,cva,len(want))
            consumer_witnesses[label]={"retailVa":rva,"comparisonVa":cva,"exact":got==want,"comparisonHex":got.hex(),"retailHex":hx}
        for label,(rva,target_label) in RETAIL_CALL_SITES.items():
            cva=rva+uniform_shift; target=rel32_target(pe,data,cva); expected=found[target_label][0] if len(found[target_label])==1 else None
            call_sites[label]={"retailVa":rva,"comparisonVa":cva,"targetLabel":target_label,"actualTargetVa":target,"expectedShiftedTargetVa":expected,"exactTarget":target==expected}

    callers={}
    for label in ("rootNoParentPrologue","rootWithParentPrologue","nonRootPrologue"):
        if len(found[label])==1:
            callers[label]=raw_rel32_callers(pe,data,found[label][0])
        else: callers[label]=[]

    doc={
        "format":FORMAT,
        "authority":"NON_AUTHORITATIVE_CURRENT_CLIENT_DIFFERENTIAL_ONLY",
        "comparisonExecutable":{"bytes":len(data),"sha256":actual},
        "retailAuthorityReference":{"sha256":RETAIL_SHA,"manifest":"manifests/xanim/T6_RETAIL_XANIM_ROOT_TRANSLATION_PROOF_V1.json"},
        "anchorOccurrences":found,
        "anchorShiftCandidates":shifts,
        "uniformRelocationDelta":uniform_shift,
        "uniformRelocationDeltaHex":None if uniform_shift is None else f"0x{uniform_shift:X}",
        "allFiveAnchorsUniqueAndUniformlyRelocated":uniform_shift is not None,
        "wholeRetailHelperBodiesAtShift":shifted_ranges,
        "retailConsumerWitnessesAtShift":consumer_witnesses,
        "retailConsumerCallsAtShift":call_sites,
        "rawRel32CallersOfShiftedHelpers":callers,
        "summary":{
            "allShiftedWholeHelperBodiesByteIdentical":bool(shifted_ranges) and all(x["byteIdenticalAfterRelocation"] for x in shifted_ranges.values()),
            "allShiftedConsumerWitnessesExact":bool(consumer_witnesses) and all(x["exact"] for x in consumer_witnesses.values()),
            "allShiftedConsumerCallTargetsExact":bool(call_sites) and all(x["exactTarget"] for x in call_sites.values()),
        },
        "proofBoundary":"A uniform relocation and byte identity can establish comparison-client homology only for retail byte ranges already independently retained. It cannot transfer authority to any unretained DObj constructor bytes or semantics."
    }
    payload=json.dumps(doc,indent=2,sort_keys=True)+"\n"; args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(payload,encoding="utf-8")
    print(json.dumps({"uniformShift":doc["uniformRelocationDeltaHex"],**doc["summary"],"callerCounts":{k:len(v) for k,v in callers.items()},"manifestSha256":sha256(payload.encode())},sort_keys=True))
    return 0

if __name__=="__main__": raise SystemExit(main())

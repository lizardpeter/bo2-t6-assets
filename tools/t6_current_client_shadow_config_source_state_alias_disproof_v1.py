#!/usr/bin/env python3
"""Prove that shadow-config +0x13A8 is NOT the T6 code-source-state base.

This is a negative/anti-alias proof. 0x00497450 writes offsets that numerically
coincide with code-constant slots, but the owning object topology makes a full
GfxCmdBufSourceState-style contract impossible at that location.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-shadow-config-source-state-alias-disproof-v1"
PTR_FMT="t6-current-client-shadow-config-pointer-table-xrefs-v1"
OBJ_FMT="t6-current-client-shadow-config-object-provenance-probe-v1"
TIME_FMT="t6-current-client-gametime-state-copy-probe-v1"
SAMP_FMT="t6-current-client-code-pixel-sampler-array-semantics-v1"

ENTRY_STRIDE=0x27F8
SUBOBJECT=0x13A8

def load(p:Path): return json.loads(p.read_text())
def sha(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()
def req(c,m):
    if not c: raise SystemExit(m)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--pointer-xrefs",type=Path,required=True)
    ap.add_argument("--object-proof",type=Path,required=True)
    ap.add_argument("--gametime-proof",type=Path,required=True)
    ap.add_argument("--sampler-proof",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    px,obj,gt,sp=map(load,[a.pointer_xrefs,a.object_proof,a.gametime_proof,a.sampler_proof])
    req(px.get("format")==PTR_FMT,"pointer-xref format drift")
    req(obj.get("format")==OBJ_FMT,"object-proof format drift")
    req(gt.get("format")==TIME_FMT,"gametime-proof format drift")
    req(sp.get("format")==SAMP_FMT,"sampler-proof format drift")
    req(px["target"]["perIndexStride"]==0x284e0,"outer pointer-table stride drift")
    req(px["target"]["consumerSubobjectOffset"]==SUBOBJECT,"shadow subobject offset drift")
    req(obj["target"]["perIndexStride"]==0x284e0 and obj["target"]["subobjectOffset"]==SUBOBJECT,
        "object provenance drift")

    # Freeze the two exact pointer-table stores. 0x43253f establishes every
    # indexed entry; 0x5e5e2f establishes index zero directly.
    dest=[h for h in px.get("hits",[]) if h.get("accessClass")=="destination-or-rmw"]
    req(len(dest)==2,"pointer-table destination denominator drift")
    by={h["instruction"]["address"]:h["instruction"] for h in dest}
    req(by["0x0043253f"]["opStr"]=="dword ptr [esi + 0x2fb838c], eax","indexed store drift")
    req(by["0x005e5e2f"]["opStr"]=="dword ptr [0x2fb838c], 0x2fb8488","index-zero store drift")

    # From exact instructions immediately preceding the indexed store:
    # eax = index*0x27F8 + 0x02FB8488
    idx=next(h for h in dest if h["instruction"]["address"]=="0x0043253f")
    ctx={x["address"]:x for x in idx["contextBefore"]}
    gates={
      "0x00432532":("mov","eax, edi"),
      "0x00432534":("imul","eax, eax, 0x27f8"),
      "0x0043253a":("add","eax, 0x2fb8488"),
    }
    for va,(mn,op) in gates.items():
        r=ctx.get(va); req(r and (r["mnemonic"],r["opStr"])==(mn,op),f"indexed topology drift {va}")
    req(ENTRY_STRIDE==0x27f8,"entry stride constant drift")

    gt_max=max(
      int(x["stateOffset"])+int(x["bytes"])
      for x in gt["copySemantics"]["copies"]
    )
    samp_image=int(sp["runtimeContract"]["codeImagesBaseOffset"])
    samp_state=int(sp["runtimeContract"]["codeImageSamplerStatesBaseOffset"])

    checks={
      "gametimeRequiredEnd":SUBOBJECT+gt_max,
      "codeImagesRequiredStart":SUBOBJECT+samp_image,
      "samplerStatesRequiredStart":SUBOBJECT+samp_state,
    }
    req(checks["gametimeRequiredEnd"]>ENTRY_STRIDE,"game-time range unexpectedly fits")
    req(checks["codeImagesRequiredStart"]>ENTRY_STRIDE,"codeImages unexpectedly fits")
    req(checks["samplerStatesRequiredStart"]>ENTRY_STRIDE,"sampler states unexpectedly fit")

    doc={
      "format":FORMAT,
      "authority":"SHA-classified current-client exact pointer-table initialization topology + independently proven source-state field/array offsets",
      "client":px["client"],
      "pointerTopology":{
        "outerIndexStride":0x284e0,
        "pointerTableBaseVa":"0x02fb838c",
        "indexedEntryFormula":"0x02FB8488 + index*0x27F8",
        "pointedEntryBaseVaIndex0":"0x02fb8488",
        "pointedEntryStride":ENTRY_STRIDE,
        "shadowConfigSubobjectOffset":SUBOBJECT,
        "shadowConfigSubobjectFormula":"(0x02FB8488 + index*0x27F8) + 0x13A8",
      },
      "independentSourceStateMinimums":{
        "gameTimeCopyHighestExclusiveOffset":gt_max,
        "codeImagesBaseOffset":samp_image,
        "codeImageSamplerStatesBaseOffset":samp_state,
      },
      "contradictions":{
        "subobjectPlusGameTimeRequiredEnd":checks["gametimeRequiredEnd"],
        "subobjectPlusCodeImagesBase":checks["codeImagesRequiredStart"],
        "subobjectPlusSamplerStatesBase":checks["samplerStatesRequiredStart"],
        "pointedEntryStride":ENTRY_STRIDE,
        "allExceedEntryStride":True,
      },
      "summary":{
        "pointerEntryTopologyClosed":True,
        "shadowConfigPlus13A8IsCodeSourceState":False,
        "offsetAliasDisproved":True,
        "enum37Enum38ProviderPromotionFrom00497450Forbidden":True,
      },
      "sources":{
        "pointerXrefs":{"path":str(a.pointer_xrefs),"sha256":sha(a.pointer_xrefs),"format":px["format"]},
        "shadowObject":{"path":str(a.object_proof),"sha256":sha(a.object_proof),"format":obj["format"]},
        "gameTimeState":{"path":str(a.gametime_proof),"sha256":sha(a.gametime_proof),"format":gt["format"]},
        "codeSamplerArrays":{"path":str(a.sampler_proof),"sha256":sha(a.sampler_proof),"format":sp["format"]},
      },
      "proofBoundary":"This is a negative identity proof. It proves that the per-index object reached through 0x02FB838C, specifically its +0x13A8 shadow-config subobject, cannot be the full current-client code-source-state base because independently proven source-state members would exceed the exact 0x27F8 pointed-entry stride. It does not identify the human type of the 0x27F8 object or locate the true enum37/38 provider by itself."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
    print(json.dumps(doc["contradictions"],indent=2,sort_keys=True))
if __name__=="__main__": main()

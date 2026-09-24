#!/usr/bin/env python3
"""Fail-closed reclassification of 0x009BEA80 as non-provider evidence for enum 60/61.

The candidate was discovered because it writes displacements numerically equal to
the enum-60/61 constant-value slots. This projector proves why that is insufficient:
- both direct call sites and argument/callback contract are exact;
- caller A sources ESI from context+8, not from an independently identified
  GfxCmdBufSourceState;
- the writer contains no exact access to enum60/61 version halfwords 0x1858/0x185A;
- the function writes many neighboring non-constant-looking fields and callback-owned
  structures.

The result is deliberately a rejection, not provider closure.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FMT="t6-current-client-spot-shadow-pixel-adjust-candidate-reclassification-v1"
WRITER_FMT="t6-current-client-spot-shadow-pixel-adjust-writer-probe-v1"
ENTRY_FMT="t6-current-client-spot-shadow-writer-entry-xrefs-v1"
CALL_FMT="t6-current-client-spot-shadow-writer-call-contract-probe-v1"

def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def req(c,m):
    if not c:raise SystemExit(m)
def ins_by(ranges,label):
    r=next(x for x in ranges if x["label"]==label);return r["instructions"]
def has(ins,addr,op=None):
    rows=[x for x in ins if x["address"].lower()==addr.lower()]
    if op is None:return len(rows)==1
    return len(rows)==1 and rows[0]["opStr"].lower()==op.lower()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--writer",type=Path,required=True);ap.add_argument("--entry-xrefs",type=Path,required=True)
    ap.add_argument("--call-contract",type=Path,required=True);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    w,e,c=load(a.writer),load(a.entry_xrefs),load(a.call_contract)
    req(w.get("format")==WRITER_FMT,"writer format drift")
    req(e.get("format")==ENTRY_FMT,"entry format drift")
    req(c.get("format")==CALL_FMT,"call format drift")
    req(w["client"]["sha256"]==e["client"]["sha256"]==c["client"]["sha256"],"client SHA disagreement")
    req(e["summary"]["decodedOperandXrefCount"]==2,"expected exact two direct calls")
    addrs=sorted(x["instruction"]["address"] for x in e["decodedOperandXrefs"])
    req(addrs==["0x009bf6f1","0x009c0211"],f"callsite drift {addrs}")
    ca=ins_by(c["ranges"],"callerA");cb=ins_by(c["ranges"],"callerB");we=ins_by(c["ranges"],"writerEntry")
    req(has(ca,"0x009bf6a6","esi, dword ptr [eax + 8]"),"callerA ESI source drift")
    req(has(ca,"0x009bf6aa","edi, dword ptr [eax + 4]"),"callerA EDI source drift")
    req(has(ca,"0x009bf6e5","0x9bea40") and has(ca,"0x009bf6ea","edx"),"callerA writer arguments drift")
    req(has(cb,"0x009c020a","0x9bea10") and has(cb,"0x009c020f","0"),"callerB writer arguments drift")
    req(has(we,"0x009beba3","eax, dword ptr [esp + 0xb8]"),"writer arg1 location drift")
    full=w["function"]["instructions"]
    version_refs=[x for x in full if "0x1858" in x["opStr"].lower() or "0x185a" in x["opStr"].lower()]
    req(not version_refs,f"candidate unexpectedly touches version slots: {version_refs}")
    value_touches=[x for x in w["storageTouches"] if x["accessor"] in {"spotShadowmapPixelAdjust","dlightSpotShadowmapPixelAdjust"}]
    req(value_touches,"expected value-displacement touches")
    doc={
      "format":FMT,
      "authority":"SHA-classified current-client exact writer/callsite/callback evidence",
      "client":w["client"],
      "candidate":{"startVa":w["function"]["startVa"],"functionSha256":w["function"]["sha256"],
        "exactDirectCallsites":addrs,"enum60or61ValueDisplacementTouchCount":len(value_touches),
        "enum60or61VersionSlotTouchCount":len(version_refs)},
      "entryContract":{
        "callerAContext":{"edi":"dword(context+4)","esi":"dword(context+8)","writerArg1":"EBX+1","writerCallback":"0x009BEA40"},
        "callerB":{"writerArg1":"0","writerCallback":"0x009BEA10"},
        "writerArg1Read":"[frame+0xB8] after exact prologue"},
      "classification":"rejected-as-runtime-provider-proof",
      "reasons":[
        "numeric displacement overlap with const-value slots is not object-identity proof",
        "callerA ESI is only proven as dword(context+8), not as GfxCmdBufSourceState",
        "writer has zero exact accesses to enum60/61 version slots 0x1858/0x185A",
        "provider promotion therefore remains unsupported despite exact live arithmetic"
      ],
      "summary":{"candidateRejectedForProviderPromotion":True,"providerClosed":False,
        "valueDisplacementTouchesRetainedAsLocatorEvidence":len(value_touches),"versionSlotTouches":0},
      "sources":{
        "writer":{"path":str(a.writer),"sha256":sha(a.writer)},
        "entryXrefs":{"path":str(a.entry_xrefs),"sha256":sha(a.entry_xrefs)},
        "callContract":{"path":str(a.call_contract),"sha256":sha(a.call_contract)}},
      "proofBoundary":"This proof rejects one tempting current-client provider candidate. It does not prove enum60/61 are never written elsewhere, does not assign physical meanings to the candidate's EDI/ESI structures, and does not weaken the unresolved runtime-provider gate."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()

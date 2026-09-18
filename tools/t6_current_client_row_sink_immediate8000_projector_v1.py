#!/usr/bin/env python3
"""Project all exact immediate-0x8000 contexts from the persisted current-client row-sink proof.

The original strict row detector required immediate name/+4/+8 stores and therefore can miss
register-propagated dynamic-name rows. This projector does no semantic promotion: it selects every
decoded immediate 0x8000 in the 18 exact direct-call contexts for sink 0x004174b0 and preserves a
larger local instruction window for symbolic follow-up.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

EXPECTED_FORMAT="t6-current-client-zone-row-sink-probe-v1"
EXPECTED_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
EXPECTED_SINK="0x004174b0"
TARGET=0x8000

def imm_values(ins):
    out=[]
    for op in ins.get("operands") or []:
        if op.get("type")=="imm" and isinstance(op.get("value"),int):
            out.append(op["value"]&0xffffffff)
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.source.read_bytes();doc=json.loads(raw)
    if doc.get("format")!=EXPECTED_FORMAT: raise SystemExit("source format drift")
    if doc.get("client",{}).get("sha256")!=EXPECTED_SHA: raise SystemExit("client SHA drift")
    if doc.get("sink",{}).get("address")!=EXPECTED_SINK: raise SystemExit("sink drift")
    inbound=doc.get("inboundDirectCalls")
    if not isinstance(inbound,list) or len(inbound)!=doc.get("summary",{}).get("inboundDirectCallCount"):
        raise SystemExit("inbound set mismatch")
    rows=[]
    for call in inbound:
        pre=call.get("precedingInstructions")
        if not isinstance(pre,list): raise SystemExit("missing preceding instructions")
        hits=[]
        for i,ins in enumerate(pre):
            if TARGET in imm_values(ins):
                hits.append({
                    "instructionIndex":i,
                    "instruction":ins,
                    "contextBefore":pre[max(0,i-24):i],
                    "contextAfter":pre[i+1:min(len(pre),i+25)],
                })
        if hits:
            rows.append({
                "callSite":call.get("call",{}).get("address"),
                "section":call.get("section"),
                "precedingInstructionCount":len(pre),
                "hits":hits,
                "strictRows":call.get("mapFlag8000RowCandidates") or [],
                "fullPrecedingInstructions":pre,
            })
    out={
      "format":"t6-current-client-row-sink-immediate-8000-contexts-v1",
      "source":{"path":str(a.source),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()},
      "client":doc["client"],"sink":EXPECTED_SINK,
      "inboundDirectCallCount":len(inbound),
      "callSitesWithImmediate8000":len(rows),
      "immediate8000HitCount":sum(len(x["hits"]) for x in rows),
      "rows":rows,
      "strictRowCount":sum(len(x["strictRows"]) for x in rows),
      "proofBoundary":"This is an exact selection from the persisted SHA-classified current-client row-sink proof. Immediate 0x8000 presence near an inbound call is not by itself a zone-row field, map classifier, source symbol, historical-retail fact, or Technique winner. Dynamic/register-propagated row semantics require separate data-flow proof."
    }
    payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
    print(json.dumps({"callSitesWithImmediate8000":len(rows),"immediate8000HitCount":out["immediate8000HitCount"],"strictRowCount":out["strictRowCount"],"callSites":[x["callSite"] for x in rows],"proofBytes":len(payload),"proofSha256":hashlib.sha256(payload).hexdigest()},indent=2,sort_keys=True))
if __name__=="__main__":main()

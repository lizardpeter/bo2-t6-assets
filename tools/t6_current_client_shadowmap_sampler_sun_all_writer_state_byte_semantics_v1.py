#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

FMT="t6-current-client-shadowmap-sampler-sun-all-writer-state-byte-semantics-v1"
EXPECTED=["0x004555a6","0x009a7d3f","0x009a7dd3","0x009bcde7","0x009bd388","0x009c1dbb","0x009c2a88"]

def req(v,m):
    if not v: raise SystemExit(m)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def imap(row):
    xs=row.get("contextBefore",[])+[row["instruction"]]+row.get("contextAfter",[])
    return {x["address"]:x for x in xs}
def exact(m,a,mn,op=None):
    x=m.get(a); req(x is not None,f"missing {a}")
    req(x["mnemonic"]==mn,f"{a} mnemonic drift")
    if op is not None: req(x["opStr"]==op,f"{a} operand drift")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--overlap",type=Path,required=True)
    ap.add_argument("--sources",type=Path,required=True)
    ap.add_argument("--edi",type=Path,required=True)
    ap.add_argument("--initializer",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    ov=json.loads(a.overlap.read_text())
    sr=json.loads(a.sources.read_text())
    ed=json.loads(a.edi.read_text())
    ini=json.loads(a.initializer.read_text())
    req(ov["format"]=="t6-current-client-sampler-state-byte-overlap-writers-v1","overlap format")
    req(sr["format"]=="t6-current-client-sampler-state-byte-writer-source-candidates-v1","source format")
    req(ed["format"]=="t6-current-client-9bcde7-edi-provenance-v1","edi format")
    req(ini["format"]=="t6-current-client-shadowmap-sampler-sun-state-byte-semantics-v1","init format")
    rows=ov["rows"]["shadowmapSamplerSun"]
    req([r["instruction"]["address"] for r in rows]==EXPECTED,"writer denominator drift")
    req(ov["summary"]["shadowmapSamplerSun"]["targetOffset"]==0x1612,"target offset drift")
    req(ini["summary"]["finalByteValue"]==0 and ini["summary"]["currentClientStateByteValueClosed"],"initializer drift")
    out=[]

    out.append({"writerVa":EXPECTED[0],"packedUpperBound":0,"targetByteValue":0,"basis":"exact initializer proof"})

    m=imap(rows[1])
    exact(m,"0x009a7d20","cmp","eax, 0x15ff")
    exact(m,"0x009a7d35","jbe","0x9a7d3c")
    exact(m,"0x009a7d37","mov","eax, 0x15ff")
    exact(m,"0x009a7d3f","mov","dword ptr [esi + 0x1610], eax")
    out.append({"writerVa":EXPECTED[1],"packedUpperBound":0x15ff,"targetByteValue":0,"basis":"unsigned cap <=0x15FF"})

    m=imap(rows[2])
    exact(m,"0x009a7dab","cmp","eax, 0x15fb")
    exact(m,"0x009a7db6","mov","edi, eax")
    exact(m,"0x009a7db8","jb","0x9a7dbf")
    exact(m,"0x009a7dba","mov","edi, 0x15fb")
    exact(m,"0x009a7dd0","add","edi, 4")
    exact(m,"0x009a7dd3","mov","dword ptr [esi + 0x1610], edi")
    out.append({"writerVa":EXPECTED[2],"packedUpperBound":0x15ff,"targetByteValue":0,"basis":"min(EAX,0x15FB)+4"})

    lm={x["address"]:x for x in ed["scan"]["localInstructions"]}
    exact(lm,"0x009bcd0c","xor","edi, edi")
    exact(lm,"0x009bcd31","test","eax, eax")
    exact(lm,"0x009bcd33","je","0x9bcd48")
    exact(lm,"0x009bcd41","pop","edi")
    exact(lm,"0x009bcd47","ret","")
    exact(lm,"0x009bcd48","mov","ebx, dword ptr [ebp + 8]")
    exact(lm,"0x009bcde7","mov","dword ptr [esi + 0x1610], edi")
    out.append({"writerVa":EXPECTED[3],"packedUpperBound":0,"targetByteValue":0,"basis":"EDI zero on writer branch; pop/ret is alternate arm"})

    for idx,addr,defa,reg,val in [
        (4,"0x009bd388","0x009bd35f","edx",0),
        (5,"0x009c1dbb","0x009c1db5","ecx",1),
        (6,"0x009c2a88","0x009c2a69","ebx",1),
    ]:
        m=imap(rows[idx])
        if val==0: exact(m,defa,"xor",f"{reg}, {reg}")
        else: exact(m,defa,"mov",f"{reg}, {val}")
        exact(m,addr,"mov")
        out.append({"writerVa":addr,"packedUpperBound":val,"targetByteValue":0,"basis":f"{reg.upper()}={val}"})

    req(len(out)==7 and all(x["packedUpperBound"]<0x10000 and x["targetByteValue"]==0 for x in out),"byte invariant")
    doc={
      "format":FMT,
      "authority":"joined exact current-client slot-6 writer denominator and value/range proofs",
      "geometry":{"samplerStateArrayOffset":0x160c,"slotIndex":6,"targetByteOffset":0x1612,"packedDwordOffset":0x1610,"byteIndex":2},
      "sources":{"overlapSha256":sha(a.overlap),"sourcesSha256":sha(a.sources),"ediSha256":sha(a.edi),"initializerSha256":sha(a.initializer)},
      "writers":out,
      "summary":{"writerInstructionCount":7,"writerDenominatorComplete":True,"allDecodedWritersForceTargetByteZero":True,"finalSamplerStateByteValue":0,"currentClientSamplerStateByteClosed":True},
      "proofBoundary":"Closes the current-client slot-6 sampler-state byte across the frozen decoded writer denominator. Image-resource identity, byte-to-API sampler interpretation, historical executable equivalence and final-frame effects remain separate gates."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__": main()

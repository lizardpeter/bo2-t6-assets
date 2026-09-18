#!/usr/bin/env python3
"""Project exact linked-record consumer semantics from the persisted global-xref proof.

Current-client only. Fail closed: this proves concrete +4/+0a/+0c access patterns
and a direct +4 return path without promoting duplicate winner authority.
"""
from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path

def collect(src):
    out={}
    for x in src["xrefs"]:
        for z in x["contextBefore"]+[x["instruction"]]+x["contextAfter"]:
            out[int(z["address"],16)]=z
    return out

def require(m,addr,mnemonic,needle):
    z=m.get(addr)
    if not z: raise SystemExit(f"missing instruction 0x{addr:08x}")
    if z["mnemonic"]!=mnemonic or needle not in z["opStr"]:
        raise SystemExit(f"drift at 0x{addr:08x}: {z}")
    return z

def main():
    ap=argparse.ArgumentParser();ap.add_argument("xref",type=Path);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    src=json.loads(a.xref.read_text())
    if src.get("format")!="t6-current-client-linked-record-global-xref-probe-v1": raise SystemExit("wrong input")
    m=collect(src)

    # Direct current-client lookup path. Exact bucket lookup begins from 0x131d740,
    # collision traversal uses +0x0a, secondary traversal uses +0x0c, and the
    # terminal secondary-chain record returns its +4 dword.
    exact=[
      require(m,0x00479c6b,"movzx","0x131d740"),
      require(m,0x00479c83,"add","0x14342e0"),
      require(m,0x00479ca4,"movzx","[esi + 0xa]"),
      require(m,0x00479cb2,"movzx","[esi + 0xc]"),
      require(m,0x00479cc6,"add","0x14342e0"),
      require(m,0x00479ccc,"movzx","[esi + 0xc]"),
      require(m,0x00479cd5,"mov","dword ptr [esi + 4]"),
      require(m,0x00479cdb,"ret",""),
    ]

    # Two independent enumerator/callback consumers corroborate that +4 is the
    # payload presented for both head records and +0x0c-linked records.
    consumers=[]
    for start,base,p0,pc,pa,p1 in [
      (0x004dce80,0x004dcec3,0x004dced2,0x004dcef2,0x004dcf1b,0x004dcf09),
      (0x005eb580,0x005eb5b3,0x005eb5c2,0x005eb5d3,0x005eb5fb,0x005eb5e9),
    ]:
        rows=[
          require(m,base,"add","0x14342e0"),
          require(m,p0,"mov","+ 4]"),
          require(m,pc,"movzx","+ 0xc]"),
          require(m,pa,"movzx","+ 0xa]"),
          require(m,p1,"mov","+ 4]"),
        ]
        consumers.append({"function":f"0x{start:08x}","instructions":rows})

    out={
      "format":"t6-current-client-linked-record-lookup-semantics-v1",
      "authority":"SHA-classified current Plutonium client plus persisted exact xref proof",
      "client":src["client"],
      "directLookup":{
        "function":"0x00479c40",
        "instructions":exact,
        "terminalReturnPayloadDwordOffset":4,
        "collisionLinkWordOffset":10,
        "secondaryLinkWordOffset":12,
      },
      "independentPayloadConsumers":consumers,
      "exactFindings":{
        "recordStrideBytes":16,
        "payloadDwordOffset":4,
        "zoneIndexByteOffset":8,
        "collisionLinkWordOffset":10,
        "secondaryLinkWordOffset":12,
        "directLookupReturnsPayloadDword":True,
        "independentPayloadConsumerCount":len(consumers),
      },
      "proofBoundary":"Current-client bytes prove the listed lookup/traversal and payload-access shapes. They do not alone establish which duplicate owner occupies the lookup-visible position after scalar relinking, and they do not establish historical-retail equivalence."
    }
    payload=json.dumps(out,indent=2,sort_keys=True)+"\n"
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(payload)
    print(json.dumps({"directLookup":"0x00479c40","independentPayloadConsumerCount":len(consumers),"sha256":hashlib.sha256(payload.encode()).hexdigest()},indent=2))
if __name__=="__main__":main()

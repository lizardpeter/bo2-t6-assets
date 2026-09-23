#!/usr/bin/env python3
"""Promote exact current-client gameTime transform semantics.

This combines the exact enum-25 destination proof with exact arithmetic bytes and
constants. It closes the transformation from scalar T to the four gameTime lanes,
but deliberately does not close the upstream producer of T at 0x03A3852C.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

ARITH_FMT="t6-current-client-gametime-arithmetic-probe-v1"
WRITE_FMT="t6-current-client-gametime-write-cluster-v1"
FORMAT="t6-current-client-gametime-transform-semantics-v1"

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--arithmetic",type=Path,required=True)
    ap.add_argument("--writes",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    ar=json.loads(a.arithmetic.read_text());wr=json.loads(a.writes.read_text())
    if ar.get("format")!=ARITH_FMT:raise SystemExit("arithmetic format drift")
    if wr.get("format")!=WRITE_FMT:raise SystemExit("write format drift")
    if ar["client"]["sha256"]!=wr["client"]["sha256"]:raise SystemExit("client identity mismatch")
    if wr["runtimeInput"]["accessor"]!="gameTime" or wr["runtimeInput"]["enumValue"]!=25:raise SystemExit("gameTime identity drift")
    cs={x["va"]:x for x in ar["embeddedConstants"]}
    expected={
      "0x00c59da4":0x80000000, # sign mask
      "0x00bd1200":0x4b000000, # 2^23
      "0x00d2b3c8":0x3f800000, # 1.0
      "0x00c63b24":0x40c90fdb, # 2*pi float32
    }
    for va,u in expected.items():
      if int(cs[va]["u32"])!=u:raise SystemExit(f"constant drift {va}: {cs[va]}")
    ins={x["address"]:x for x in ar["range"]["instructions"]}
    gates={
      "0x00733c9f":"f30f101d2c85a303", # T
      "0x00733cc2":"0f54c3",           # sign mask
      "0x00733cce":"f30fc2c101",       # abs(T)<2^23
      "0x00733cdc":"f30f58c1",         # + signed 2^23
      "0x00733ce0":"f30f5cc1",         # - signed 2^23 -> nearest integer
      "0x00733ce7":"f30f5ccb",         # rounded - T
      "0x00733ceb":"f30fc2cc06",       # >= signed zero
      "0x00733cf0":"0f54ce",           # select 1.0 correction
      "0x00733cf3":"f30f5cc1",         # rounded - correction = floor(T)
      "0x00733cf7":"0f28eb",           # preserve T
      "0x00733cfa":"f30f5cd8",         # T-floor(T)
      "0x00733d09":"f30f5905243bc600", # *2pi
      "0x00733d35":"d9fb",             # fsincos
      "0x00733d4b":"66ff051283a303",   # version++
      "0x00733d52":"f30f11059074a303", # lane0
      "0x00733d60":"f30f11059474a303", # lane1
      "0x00733d68":"f30f111d9874a303", # lane2
      "0x00733d70":"f30f112d9c74a303", # lane3
    }
    for va,b in gates.items():
      if ins.get(va,{}).get("bytes")!=b:raise SystemExit(f"instruction gate drift {va}: {ins.get(va)}")
    if ar["sourceScalar"]["va"]!="0x03a3852c":raise SystemExit("source scalar drift")
    if wr["runtimeInput"]["valueVas"]!=["0x03a37490","0x03a37494","0x03a37498","0x03a3749c"]:raise SystemExit("value slot drift")
    if wr["runtimeInput"]["versionVa"]!="0x03a38312":raise SystemExit("version slot drift")
    doc={
      "format":FORMAT,
      "authority":"SHA-classified current-client exact arithmetic bytes/constants + exact gameTime enum-25 slot writes",
      "client":ar["client"],
      "runtimeInput":wr["runtimeInput"],
      "sourceScalar":{"va":"0x03a3852c","symbolicName":"T","providerStatus":"unresolved"},
      "transform":{
        "floor":"floor(T), implemented by signed 2^23 float32 rounding plus conditional 1.0 correction",
        "fraction":"f = T - floor(T)",
        "phase":"theta = float32(f * 6.2831854820251465)",
        "lanes":[
          {"lane":0,"expression":"sin(theta)","x87":"second fstp after fsincos"},
          {"lane":1,"expression":"cos(theta)","x87":"first fstp after fsincos"},
          {"lane":2,"expression":"f"},
          {"lane":3,"expression":"T"}
        ],
        "version":"uint16 version slot at 0x03A38312 increments before value stores"
      },
      "summary":{"currentClientTransformClosed":True,"sourceScalarProviderClosed":False,"currentClientProviderClosed":False,
                 "retainedSpecialOccurrenceCount":wr["runtimeInput"]["totalOccurrences"]},
      "sources":{
        "arithmetic":{"path":str(a.arithmetic),"sha256":sha(a.arithmetic)},
        "writes":{"path":str(a.writes),"sha256":sha(a.writes)}
      },
      "proofBoundary":"Closes only the SHA-classified current-client transformation from scalar T at 0x03A3852C to gameTime lanes/version. The producer, units, update cadence and draw-time value of T remain unresolved, so the overall runtime provider is intentionally not marked closed. Historical-retail executable equivalence is also unproven."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()

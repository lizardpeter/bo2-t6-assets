#!/usr/bin/env python3
"""Validate direct retail dynamic full-quaternion XAnim fixtures through compiled-v19 interchange.

Authority is the exact expanded retail XFile bytes plus the six previously count-closed
MP corpus fixture offsets/fixed hashes. The proof normalizes each exact XAnimParts,
encodes its complete delta subsection with the source-closed compiled-v19 codec,
decodes it again, and compares quaternion rotations plus exact native key domains.
"""
from __future__ import annotations
import argparse,hashlib,json,math,struct
from pathlib import Path

from t6_xanim_normalize_v1 import normalize
from t6_compiled_xanim_v19_delta_v1 import encode_delta_section,decode_delta_section

FIXTURES={
 "mp_nuketown_2020":{
   "expandedSha256":"7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505",
   "expandedBytes":154653476,
   "assets":[
    (92960192,"fxanim_mp_nuked2025_car01_anim","5b6c3d1a26dc5e9c4f389e063d5c762ffef7a8ac47f2fe3c85d256d04e428633"),
    (92960792,"fxanim_mp_nuked2025_car02_anim","7011bb25984383933df6fc27c639c1aaba125da152ed82fb2a5d92225b54c850"),
   ]},
 "mp_studio":{
   "expandedSha256":"d2c09b730835df084108c19ac4edbeac84ac90cf60ad2e76c02919b58b572d30",
   "expandedBytes":139744323,
   "assets":[
    (139732939,"fxanim_mp_stu_pirate_captain_01_anim","3f17625ec00864d1d973dc14421d4a6849648193c8e0fdd0b6e759d53e49c4af"),
    (139733985,"fxanim_mp_stu_pirate_captain_02_anim","c6db711ec02a6a3cd17dbdbabb037f47f85a828e6615562fdada957077880ce8"),
    (139734977,"fxanim_mp_stu_pirate_oarsmen_01_anim","fad470d915563d3fa363d65ffa71c633101721b05416db7c7992ec453648876c"),
    (139735558,"fxanim_mp_stu_pirate_oarsmen_02_anim","6c3a191e8906bb174f8129c15f10e74d60a93aca465fa6cdd58d385273258951"),
   ]}
}
ROT_TOL=2e-7

def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def packed_hash(v)->str:return sha_bytes(json.dumps(v,sort_keys=True,separators=(",",":")).encode())

def rotation_error(a,b):
    if len(a)!=4 or len(b)!=4: raise ValueError("full quaternion must have 4 components")
    na=math.sqrt(sum(float(x)*x for x in a)); nb=math.sqrt(sum(float(x)*x for x in b))
    if na<=0 or nb<=0: raise ValueError("zero quaternion")
    dot=abs(sum(float(x)*y for x,y in zip(a,b))/(na*nb))
    return 1.0-min(1.0,dot)

def trans_equal(a,b):
    if a is None or b is None:return a is b
    if a.get("mode")!=b.get("mode"):return False
    if a["mode"]=="constant":
        return struct.pack("<3f",*a["value"])==struct.pack("<3f",*b["value"])
    return (a.get("indices")==b.get("indices")
      and bool(a.get("smallTrans"))==bool(b.get("smallTrans"))
      and a.get("quantizedFrames")==b.get("quantizedFrames")
      and struct.pack("<3f",*a["mins"])==struct.pack("<3f",*b["mins"])
      and struct.pack("<3f",*a["rawSize"])==struct.pack("<3f",*b["rawSize"]))

def one(zone,path,start,name,fixed_sha):
    data=path.read_bytes()
    got=sha_bytes(data[start:start+104])
    if got!=fixed_sha:raise SystemExit(f"{zone}:{name}: fixed SHA drift {got}")
    n=normalize(data,start)
    if n["name"]!=name:raise SystemExit(f"{zone}:{start}: exact name drift {n['name']!r}")
    h=n["header"]; d=n["delta"]
    if not h.get("bDelta3D") or h.get("bDelta"):
        raise SystemExit(f"{zone}:{name}: expected exact 3D delta flags")
    q=d.get("quat") if d else None
    if not q or q.get("mode")!="dynamic":
        raise SystemExit(f"{zone}:{name}: no dynamic full quaternion after normalization")
    if d.get("quat2") is not None:
        raise SystemExit(f"{zone}:{name}: unexpected quat2 alongside full quaternion")
    payload=encode_delta_section(d,h)
    dec=decode_delta_section(payload,h)
    dq=dec.get("quat")
    if not dq or dq.get("mode")!="dynamic":raise SystemExit(f"{zone}:{name}: compiled roundtrip lost full quat")
    if q["indices"]!=dq["indices"]:raise SystemExit(f"{zone}:{name}: quaternion key-domain mismatch")
    if len(q["rawInt16Frames"])!=len(dq["rawInt16Frames"]):raise SystemExit(f"{zone}:{name}: quaternion frame-count mismatch")
    errs=[rotation_error(a,b) for a,b in zip(q["rawInt16Frames"],dq["rawInt16Frames"])]
    mx=max(errs,default=0.0)
    if mx>ROT_TOL:raise SystemExit(f"{zone}:{name}: quaternion rotation error {mx} > {ROT_TOL}")
    if not trans_equal(d.get("trans"),dec.get("trans")):
        raise SystemExit(f"{zone}:{name}: translation roundtrip mismatch")
    return {
      "zone":zone,"assetStart":start,"name":name,"fixedSha256":fixed_sha,
      "assetSerializedEnd":n["assetSerializedEnd"],"assetSerializedSha256":n["assetSerializedSha256"],
      "numframes":h["numframes"],"framerate":h["framerate"],"frequency":h["frequency"],
      "bDelta":h["bDelta"],"bDelta3D":h["bDelta3D"],
      "quat":{
        "mode":"dynamic","keyCount":len(q["indices"]),"indices":q["indices"],
        "nativeRawInt16FramesSha256":packed_hash(q["rawInt16Frames"]),
        "compiledDecodedRawInt16FramesSha256":packed_hash(dq["rawInt16Frames"]),
        "maxRotationOneMinusAbsDot":mx,
      },
      "transMode":None if d.get("trans") is None else d["trans"].get("mode"),
      "compiledV19DeltaBytes":len(payload),"compiledV19DeltaSha256":sha_bytes(payload),
      "flatPoolsExhausted":n["allFlatPoolsExhausted"],
      "walkerBlockers":n["walkerBlockers"],
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--expanded",action="append",nargs=2,metavar=("ZONE","PATH"),required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    supplied={z:Path(p) for z,p in a.expanded}
    if set(supplied)!=set(FIXTURES):raise SystemExit(f"need exact zones {sorted(FIXTURES)}")
    sources=[]; rows=[]
    for zone,cfg in FIXTURES.items():
        p=supplied[zone]; raw=p.read_bytes(); got=sha_bytes(raw)
        if len(raw)!=cfg["expandedBytes"] or got!=cfg["expandedSha256"]:
            raise SystemExit(f"{zone}: expanded identity drift bytes={len(raw)} sha={got}")
        sources.append({"zone":zone,"file":p.name,"bytes":len(raw),"sha256":got})
        for start,name,fsha in cfg["assets"]: rows.append(one(zone,p,start,name,fsha))
    doc={
      "format":"t6-mp-xanim-dynamic-full-quat-compiled-v19-retail-proof-v1",
      "authority":"six direct dynamic full-quaternion XAnimParts fixtures in two SHA-pinned, count-closed retail MP expanded XFiles",
      "sources":sources,"rows":rows,
      "summary":{
        "zoneCount":len(sources),"fixtureCount":len(rows),
        "totalQuaternionKeyCount":sum(r["quat"]["keyCount"] for r in rows),
        "maxRotationOneMinusAbsDot":max(r["quat"]["maxRotationOneMinusAbsDot"] for r in rows),
        "allCompiledRoundTripsPassed":True,
        "allFlatPoolsExhausted":all(r["flatPoolsExhausted"] for r in rows),
        "walkerBlockerCount":sum(len(r["walkerBlockers"]) for r in rows),
      },
      "proofBoundary":"This directly validates the six observed MP dynamic full-quaternion delta fixtures through normalization and compiled-v19 interchange. Quaternion comparison is rotational equivalence because v19 stores an omitted component; raw source int16 frame identity is retained separately. It does not prove the unobserved constant full-quaternion serialized branch, Zombies/SP corpus closure, or runtime playback parity."
    }
    if len(rows)!=6:raise SystemExit("expected six fixtures")
    if doc["summary"]["walkerBlockerCount"]!=0:raise SystemExit("retail fixture walker blockers present")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()

#!/usr/bin/env python3
"""Exhaustively validate retail zm_prison constant delta branches through compiled-v19 interchange.

The SHA-pinned expanded zm_prison XFile is already count-closed at 1,434 XAnimParts.
This proof re-identifies every structural non-empty XAnim record using the strict
retail scanner, selects every constant translation and constant quat2 occurrence,
normalizes the owning asset, and round-trips its complete delta subsection through
the source-closed compiled-v19 codec.

Constant translations require exact IEEE-754 float32 byte identity. Constant
quat2 branches require exact first stored int16 component and rotation-equivalent
reconstruction of the omitted second component; original two-component int16
bytes remain hashed separately.
"""
from __future__ import annotations
import argparse,hashlib,json,math,struct
from pathlib import Path
import t6_xanim_retail_delta_branch_census_v1 as scan
from t6_xanim_normalize_v1 import normalize
from t6_compiled_xanim_v19_delta_v1 import encode_delta_section,decode_delta_section

EXP_SHA="e9d334a173d05b2854370822bc2cb16c9d5eb6226254aaf28b726cfedc340487"
EXP_BYTES=344067743
EXPECTED_XANIM=1434
EXPECTED_TRANS_CONST=38
EXPECTED_QUAT2_CONST=43
FORMAT="t6-zm-prison-xanim-constant-delta-compiled-v19-proof-v1"
ROT_TOL=2e-7
class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def sha(b):return hashlib.sha256(b).hexdigest()
def jsha(v):return sha(json.dumps(v,sort_keys=True,separators=(",",":")).encode())
def rot_err(a,b):
    req(len(a)==2 and len(b)==2,"quat2 frame width drift")
    na=math.sqrt(sum(float(x)*x for x in a));nb=math.sqrt(sum(float(x)*x for x in b))
    req(na>0 and nb>0,"zero quat2")
    dot=abs(sum(float(x)*y for x,y in zip(a,b))/(na*nb))
    return 1.0-min(1.0,dot)

def records(data):
    blocks,body,asset_count,expected=scan.parse_front(data)
    starts=set();out=[]
    for fps in (24.0,30.0):
        pat=struct.pack("<f",fps);search=body+48
        while True:
            hit=data.find(pat,search)
            if hit<0:break
            search=hit+1;start=hit-48
            if start<body or start in starts or start+scan.XANIM_SIZE>len(data):continue
            rec=scan.fixed(data,start)
            if not scan.valid_fixed(data,start,rec,blocks):continue
            try:end,name,delta=scan.walk(data,start,rec)
            except Exception:continue
            starts.add(start);out.append({"start":start,"end":end,"name":name,"rec":rec,"delta":delta})
    out.sort(key=lambda x:x["start"])
    return asset_count,expected,out

def f32eq(a,b):
    return struct.pack("<3f",*[float(x) for x in a])==struct.pack("<3f",*[float(x) for x in b])

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--expanded",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    data=a.expanded.read_bytes();req(len(data)==EXP_BYTES and sha(data)==EXP_SHA,"expanded zm_prison identity drift")
    asset_count,expected,recs=records(data);req(expected==EXPECTED_XANIM,f"XAsset expected count {expected}")
    # Empty placeholders do not occur in zm_prison, so structural scan must close directly.
    req(len(recs)==EXPECTED_XANIM,f"structural record count {len(recs)} != {EXPECTED_XANIM}")
    selected=[r for r in recs if (r["delta"].get("trans") or {}).get("mode")=="constant" or (r["delta"].get("quat2") or {}).get("mode")=="constant"]
    rows=[];tc=qc=0;maxerr=0.0
    for r in selected:
        n=normalize(data,r["start"]);req(n["name"]==r["name"],f"{r['start']}: normalize name drift")
        req(n["allFlatPoolsExhausted"] is True,f"{n['name']}: flat pools not exhausted")
        req(not n["walkerBlockers"],f"{n['name']}: walker blockers {n['walkerBlockers']}")
        d=n["delta"];h=n["header"];payload=encode_delta_section(d,h);dec=decode_delta_section(payload,h)
        row={"start":r["start"],"name":n["name"],"numframes":h["numframes"],"assetSerializedSha256":n["assetSerializedSha256"],"compiledV19Bytes":len(payload),"compiledV19Sha256":sha(payload)}
        tr=d.get("trans")
        if tr and tr.get("mode")=="constant":
            tc+=1;dt=dec.get("trans");req(dt and dt.get("mode")=="constant",f"{n['name']}: lost constant trans")
            req(f32eq(tr["value"],dt["value"]),f"{n['name']}: constant translation float32 mismatch")
            row["constantTranslation"]={"value":tr["value"],"float32BytesHex":struct.pack("<3f",*tr["value"]).hex(),"roundtripExactFloat32":True}
        q=d.get("quat2")
        if q and q.get("mode")=="constant":
            qc+=1;dq=dec.get("quat2");req(dq and dq.get("mode")=="constant",f"{n['name']}: lost constant quat2")
            raw=q["rawInt16"];got=dq["rawInt16"];err=rot_err(raw,got);maxerr=max(maxerr,err)
            req(err<=ROT_TOL,f"{n['name']}: quat2 rotation error {err}")
            # Compiled v19 stores one component for quat2. Its decoded first component
            # must be source-exact; second is reconstructed.
            req(int(got[0])==int(raw[0]),f"{n['name']}: stored quat2 component changed")
            row["constantQuat2"]={"nativeRawInt16":raw,"nativeRawInt16BytesHex":struct.pack("<2h",*raw).hex(),"compiledDecodedRawInt16":got,"firstStoredComponentExact":True,"rotationOneMinusAbsDot":err}
        rows.append(row)
    req(tc==EXPECTED_TRANS_CONST,f"constant trans count {tc} != {EXPECTED_TRANS_CONST}")
    req(qc==EXPECTED_QUAT2_CONST,f"constant quat2 count {qc} != {EXPECTED_QUAT2_CONST}")
    doc={
      "format":FORMAT,
      "authority":"SHA-pinned expanded retail zm_prison; strict count-closed XAnim scanner; direct normalized delta bytes; source-closed compiled-v19 codec",
      "source":{"file":a.expanded.name,"bytes":len(data),"sha256":sha(data),"xassetCount":asset_count,"expectedXAnimCount":expected,"structuralXAnimCount":len(recs)},
      "summary":{
        "selectedAssetCount":len(rows),"constantTranslationBranchCount":tc,"constantQuat2BranchCount":qc,
        "allSelectedFlatPoolsExhausted":True,"walkerBlockerCount":0,
        "allConstantTranslationsFloat32Exact":True,"allConstantQuat2StoredComponentsExact":True,
        "allConstantQuat2RotationsEquivalent":True,"maxConstantQuat2RotationOneMinusAbsDot":maxerr,
      },
      "rows":rows,"rowsSha256":jsha(rows),
      "proofBoundary":"Exhaustive over every constant translation and constant quat2 branch in the count-closed SHA-pinned zm_prison XFile. Translation float32 values are exact through compiled-v19. Quat2 compiled-v19 intentionally omits one component, so the source two-int16 frame is preserved as evidence while roundtrip promotion requires exact retained component plus rotational equivalence within 2e-7. This does not prove the still-unobserved constant full-quaternion branch or all-game corpus absence."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()

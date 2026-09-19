#!/usr/bin/env python3
"""Round-trip every dynamic full-quaternion branch observed in the 215-FastFile archive census.

The corpus proof identifies exactly four FastFiles containing 13 dynamic full-quat
branches. This tool requires exact expanded SHA identity for those four zones and
round-trips every recorded fixture through normalization + compiled-v19 interchange.
No example truncation is allowed: the corpus row's dynamicFullQuatCount must equal the
retained example count for each hit zone.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
from t6_xanim_normalize_v1 import normalize
from t6_compiled_xanim_v19_delta_v1 import encode_delta_section,decode_delta_section

CORPUS_FMT="t6-all-fastfile-xanim-branch-corpus-v1"
FORMAT="t6-all-fastfile-dynamic-full-quat-compiled-v19-proof-v1"
TOL=2e-7
class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def sha(b):return hashlib.sha256(b).hexdigest()
def jhash(v):return sha(json.dumps(v,sort_keys=True,separators=(",",":")).encode())
def rot(a,b):
    req(len(a)==4 and len(b)==4,"full quaternion width drift")
    na=math.sqrt(sum(float(x)*x for x in a));nb=math.sqrt(sum(float(x)*x for x in b));req(na>0 and nb>0,"zero quaternion")
    dot=abs(sum(float(x)*y for x,y in zip(a,b))/(na*nb))
    return 1.0-min(1.0,dot)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--corpus",type=Path,required=True);ap.add_argument("--expanded",action="append",nargs=2,metavar=("ZONE","PATH"),required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    corpus=json.loads(a.corpus.read_text());req(corpus.get("format")==CORPUS_FMT,"corpus format drift")
    s=corpus["summary"];req(s["archiveFastFileCount"]==215 and s["countClosedFastFileCount"]==215,"archive corpus no longer 215/215 count-closed")
    req(s["constantFullQuatObservedCountClosed"]==0,"constant full-quat now observed; this proof must be redesigned")
    req(s["dynamicFullQuatObservedCountClosed"]==13,"dynamic full-quat population drift")
    hits=corpus.get("dynamicFullQuatHitFastFiles",[]);req(len(hits)==4,"expected four dynamic-full-quat hit zones")
    by_zone={r["zoneName"]:r for r in corpus["rows"]}
    supplied={z:Path(p) for z,p in a.expanded};expected={x["zoneName"] for x in hits};req(set(supplied)==expected,f"expanded zone set {sorted(supplied)} != {sorted(expected)}")
    rows=[];maxerr=0.0
    for hit in sorted(hits,key=lambda x:x["zoneName"]):
        z=hit["zoneName"];zr=by_zone[z];p=supplied[z];raw=p.read_bytes()
        req(len(raw)==int(zr["expandedBytes"]) and sha(raw)==zr["expandedSha256"],f"{z}: expanded identity drift")
        examples=hit.get("dynamicFullQuatExamples",[]);req(len(examples)==int(hit["dynamicFullQuatCount"]),f"{z}: census examples are truncated")
        for ex in examples:
            st=int(ex["start"]);fixed=raw[st:st+104];req(sha(fixed)==ex["fixedSha256"],f"{z}/{ex.get('name')}: fixed SHA drift")
            n=normalize(raw,st);req(n["name"]==ex["name"],f"{z}/{st}: normalized name drift")
            req(n["allFlatPoolsExhausted"] is True and not n["walkerBlockers"],f"{z}/{n['name']}: normalization blockers")
            h=n["header"];d=n["delta"];q=d.get("quat") if d else None
            req(h.get("bDelta3D") is True and h.get("bDelta") is False,f"{z}/{n['name']}: 3D delta flag drift")
            req(q and q.get("mode")=="dynamic",f"{z}/{n['name']}: dynamic full-quat lost")
            payload=encode_delta_section(d,h);dec=decode_delta_section(payload,h);dq=dec.get("quat")
            req(dq and dq.get("mode")=="dynamic",f"{z}/{n['name']}: compiled full-quat lost")
            req(q["indices"]==dq["indices"],f"{z}/{n['name']}: key domain mismatch")
            req(len(q["rawInt16Frames"])==len(dq["rawInt16Frames"]),f"{z}/{n['name']}: key count mismatch")
            errs=[rot(x,y) for x,y in zip(q["rawInt16Frames"],dq["rawInt16Frames"])];mx=max(errs,default=0.0);maxerr=max(maxerr,mx);req(mx<=TOL,f"{z}/{n['name']}: rotation error {mx}")
            rows.append({
              "zone":z,"name":n["name"],"assetStart":st,"fixedSha256":ex["fixedSha256"],
              "assetSerializedSha256":n["assetSerializedSha256"],"numframes":h["numframes"],
              "keyCount":len(q["indices"]),"indices":q["indices"],
              "nativeRawFramesSha256":jhash(q["rawInt16Frames"]),
              "compiledDecodedFramesSha256":jhash(dq["rawInt16Frames"]),
              "maxRotationOneMinusAbsDot":mx,
              "compiledV19Bytes":len(payload),"compiledV19Sha256":sha(payload),
            })
    req(len(rows)==13,"expected all 13 dynamic full-quat branches")
    doc={
      "format":FORMAT,
      "authority":"complete dynamic-full-quaternion branch set from the 215/215 count-closed public FastFile corpus, exact expanded bytes, normalization, and source-closed compiled-v19 codec",
      "sourceCorpus":{"path":str(a.corpus),"sha256":sha(a.corpus.read_bytes())},
      "summary":{"hitZoneCount":4,"dynamicFullQuatFixtureCount":len(rows),"totalQuaternionKeyCount":sum(r["keyCount"] for r in rows),"maxRotationOneMinusAbsDot":maxerr,"allObservedArchiveDynamicFullQuatBranchesRoundTrip":True,"constantFullQuatObservedInArchive":0},
      "rows":rows,"rowsSha256":jhash(rows),
      "proofBoundary":"Direct compiled-v19 validation for every dynamic full-quaternion branch observed in the referenced 215-FastFile archive corpus. Quaternion comparison is rotational equivalence because compiled-v19 uses omitted-component storage; source raw frames are retained by digest. This does not expand the archive universe or convert the corpus-bounded zero constant-full-quat result into a claim about retail XFiles absent from that archive."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()

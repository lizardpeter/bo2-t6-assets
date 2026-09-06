#!/usr/bin/env python3
"""Aggregate retained third-person playeranim compatibility proofs into a body x selector census."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-player-character-animation-census-v1"
COMPAT_FORMATS={"t6-third-person-animation-compatibility-v1","t6-third-person-animation-compatibility-v2"}

def load(p:Path):
    d=json.loads(p.read_text(encoding="utf-8-sig"))
    if not isinstance(d,dict): raise ValueError(f"{p}: expected object")
    return d

def sha256(p:Path):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def build(profile_doc:dict,profile_path:Path,compatibility_paths:list[Path]):
    if profile_doc.get("format")!="t6-playeranim-selector-profile-census-v1": raise ValueError("unsupported profile census")
    profile_by_id={}
    for p in profile_doc.get("profiles") or []:
        pid=p.get("id") if isinstance(p,dict) else None
        if not isinstance(pid,str) or not pid: raise ValueError("profile missing id")
        if pid in profile_by_id: raise ValueError(f"duplicate profile id: {pid}")
        profile_by_id[pid]=p
    evidence={}; bodies=set()
    for path in compatibility_paths:
        d=load(path); compat_format=d.get("format")
        if compat_format not in COMPAT_FORMATS: raise ValueError(f"{path}: unsupported compatibility format {compat_format!r}")
        body=d.get("bodyModel"); prof=d.get("selectorProfile"); pid=prof.get("id") if isinstance(prof,dict) else None
        if not isinstance(body,str) or not body: raise ValueError(f"{path}: bodyModel missing")
        if pid not in profile_by_id: raise ValueError(f"{path}: profile {pid!r} not in supplied profile census")
        if prof.get("selectors")!=profile_by_id[pid].get("selectors"): raise ValueError(f"{path}: profile selectors disagree with census for {pid}")
        key=(body,pid); rec={"path":str(path),"sha256":sha256(path),"compatibilityFormat":compat_format,"allRequiredTracksCompatible":bool(d.get("allRequiredTracksCompatible")),"ownershipResolvedFromRetail":bool(d.get("ownershipResolvedFromRetail")),"resolutionFormat":d.get("resolutionFormat"),"summary":d.get("summary")}
        if key in evidence and evidence[key]!=rec: raise ValueError(f"conflicting duplicate compatibility proof for {body} / {pid}")
        evidence[key]=rec; bodies.add(body)
    cells=[]
    for body in sorted(bodies,key=str.casefold):
        for pid in sorted(profile_by_id,key=str.casefold):
            ev=evidence.get((body,pid)); closed=bool(ev and ev["allRequiredTracksCompatible"] and ev["ownershipResolvedFromRetail"])
            cells.append({"bodyModel":body,"profileId":pid,"selector":profile_by_id[pid]["selectors"],"memberWeaponsInSelectorSourceLayer":profile_by_id[pid].get("memberWeapons",[]),"status":"closed" if closed else ("retained-proof-failed" if ev else "pending-no-retained-proof"),"compatibilityProof":ev})
    closed=sum(x["status"]=="closed" for x in cells); failed=sum(x["status"]=="retained-proof-failed" for x in cells)
    return {"format":FORMAT,"authority":"aggregation of retained third-person animation compatibility proofs; no missing cross-product cell is inferred","acceptedCompatibilityFormats":sorted(COMPAT_FORMATS),"profileCensus":{"path":str(profile_path),"sha256":sha256(profile_path),"profileCount":len(profile_by_id)},"summary":{"bodyModels":len(bodies),"selectorProfiles":len(profile_by_id),"crossProductCells":len(cells),"closedCells":closed,"failedProofCells":failed,"pendingCells":len(cells)-closed-failed},"bodies":sorted(bodies,key=str.casefold),"cells":cells,"proofBoundary":"Closed means a retained compatibility-v1/v2 artifact exists for the exact body/profile pair and reports both retail ownership resolution and all required tracks compatible. Missing artifacts remain pending even if a prior run was verbally reported successful. Source-layer member weapons are informational and are not final named-weapon assignments."}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--profiles",type=Path,required=True); ap.add_argument("--compatibility",type=Path,action="append",default=[]); ap.add_argument("--out",type=Path,required=True); a=ap.parse_args()
    out=build(load(a.profiles),a.profiles,a.compatibility); a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps(out["summary"],indent=2,sort_keys=True)); return 0 if out["summary"]["failedProofCells"]==0 else 2
if __name__=="__main__": raise SystemExit(main())

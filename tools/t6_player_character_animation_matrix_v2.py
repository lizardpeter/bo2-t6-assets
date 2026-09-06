#!/usr/bin/env python3
"""Build a fail-closed multiplayer third-person body x playeranim selector matrix."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

FORMAT="t6-player-character-animation-matrix-v2"
COMPAT_FORMATS={"t6-third-person-animation-compatibility-v1","t6-third-person-animation-compatibility-v2"}

def load(path:Path):
    d=json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(d,dict):raise ValueError(f"{path}: expected object")
    return d

def sha256(path:Path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()

def build(profile_doc:dict,body_registry:dict,compat_items:list[tuple[Path,dict]]):
    if profile_doc.get("format")!="t6-playeranim-selector-profile-census-v1":
        raise ValueError("unsupported profile census")
    if body_registry.get("format")!="t6-player-body-identity-registry-v1":
        raise ValueError("unsupported body registry")
    profiles={}
    for p in profile_doc.get("profiles") or []:
        if not isinstance(p,dict) or not isinstance(p.get("id"),str):raise ValueError("invalid profile")
        if p["id"] in profiles:raise ValueError(f"duplicate profile {p['id']}")
        profiles[p["id"]]=p
    bodies={}
    for b in body_registry.get("bodies") or []:
        if not isinstance(b,dict) or not isinstance(b.get("name"),str):raise ValueError("invalid body row")
        if b["name"] in bodies:raise ValueError(f"duplicate body {b['name']}")
        bodies[b["name"]]=b
    evidence={}
    for path,d in compat_items:
        fmt=d.get("format")
        if fmt not in COMPAT_FORMATS:raise ValueError(f"{path}: unsupported compatibility format {fmt!r}")
        body=d.get("bodyModel"); prof=d.get("selectorProfile")
        pid=prof.get("id") if isinstance(prof,dict) else None
        if body not in bodies:raise ValueError(f"{path}: body {body!r} absent from body registry")
        if pid not in profiles:raise ValueError(f"{path}: profile {pid!r} absent from profile census")
        if prof.get("selectors")!=profiles[pid].get("selectors"):
            raise ValueError(f"{path}: profile selectors disagree with census for {pid}")
        key=(body,pid)
        if key in evidence:raise ValueError(f"duplicate compatibility evidence for {body}/{pid}")
        evidence[key]={
            "path":str(path),"sha256":sha256(path),"format":fmt,
            "allRequiredTracksCompatible":bool(d.get("allRequiredTracksCompatible")),
            "ownershipResolvedFromRetail":bool(d.get("ownershipResolvedFromRetail")),
            "summary":d.get("summary"),
            "resolutionFormat":d.get("resolutionFormat"),
        }
    cells=[]
    for body_name in sorted(bodies,key=str.casefold):
        b=bodies[body_name]; body_closed=b.get("retailIdentityStatus")=="retail-proven-full-body"
        for pid in sorted(profiles,key=str.casefold):
            p=profiles[pid]; ev=evidence.get((body_name,pid))
            if not body_closed:
                status="blocked-body-identity-unresolved"
            elif ev is None:
                status="pending-no-retained-proof"
            elif ev["allRequiredTracksCompatible"] and ev["ownershipResolvedFromRetail"]:
                status="closed"
            else:
                status="retained-proof-failed"
            cells.append({
                "bodyModel":body_name,
                "bodyIdentityStatus":b.get("retailIdentityStatus"),
                "profileId":pid,
                "selector":p.get("selectors"),
                "memberWeaponsInSelectorSourceLayer":p.get("memberWeapons",[]),
                "status":status,
                "compatibilityProof":ev,
            })
    counts={s:sum(c["status"]==s for c in cells) for s in (
        "closed","pending-no-retained-proof","blocked-body-identity-unresolved","retained-proof-failed")}
    return {
        "format":FORMAT,
        "authority":"cross-product of retail-gated player-body registry and reusable playeranim selector profiles with retained compatibility evidence",
        "acceptedCompatibilityFormats":sorted(COMPAT_FORMATS),
        "summary":{
            "bodyModels":len(bodies),
            "retailProvenBodies":sum(b.get("retailIdentityStatus")=="retail-proven-full-body" for b in bodies.values()),
            "unresolvedBodyCandidates":sum(b.get("retailIdentityStatus")!="retail-proven-full-body" for b in bodies.values()),
            "selectorProfiles":len(profiles),
            "crossProductCells":len(cells),
            "closedCells":counts["closed"],
            "pendingCompatibilityCells":counts["pending-no-retained-proof"],
            "blockedBodyIdentityCells":counts["blocked-body-identity-unresolved"],
            "failedProofCells":counts["retained-proof-failed"],
        },
        "cells":cells,
        "proofBoundary":"A cell can close only after the body registry has promoted that exact body from direct retail full-player proof and a retained compatibility-v1/v2 artifact independently closes the exact selector profile. Candidate body names never create animation compatibility evidence."
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--profiles",type=Path,required=True)
    ap.add_argument("--body-registry",type=Path,required=True)
    ap.add_argument("--compatibility",type=Path,action="append",default=[])
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    out=build(load(a.profiles),load(a.body_registry),[(p,load(p)) for p in a.compatibility])
    out["sources"]={
        "profiles":{"path":str(a.profiles),"sha256":sha256(a.profiles)},
        "bodyRegistry":{"path":str(a.body_registry),"sha256":sha256(a.body_registry)},
        "compatibility":[{"path":str(p),"sha256":sha256(p)} for p in a.compatibility],
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(out["summary"],indent=2,sort_keys=True))
    return 0 if out["summary"]["failedProofCells"]==0 else 2
if __name__=="__main__":raise SystemExit(main())

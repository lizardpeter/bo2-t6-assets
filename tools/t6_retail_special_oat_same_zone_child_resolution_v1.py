#!/usr/bin/env python3
"""Resolve retained special packed Technique/VS/PS children through same-zone OAT dumps.

The raw topology already proves each packed pointer's map, TechniqueSet, slot,
technique/pass when structurally available, and child kind. Pinned OAT resolves
those pointers while loading that exact zone and emits resolved TechniqueSet,
Technique, and shader artifacts. This projector joins ONLY within the same
world output root and exact structural key.

VertexDecl is deliberately not promoted to an asset identity because T6 OAT's
CommonTechniqueDumper emits routing semantics but discards the original
MaterialVertexDeclaration name/pointer identity.
"""
from __future__ import annotations

import argparse, hashlib, json
from pathlib import Path

import t6_oat_slot_shader_resolver_v1 as slot
import t6_oat_techset_binding_manifest_v1 as oat

FORMAT="t6-retail-special-oat-same-zone-child-resolution-v1"
TOPO_FORMAT="t6-retail-special-packed-reference-topology-v1"

class ResolutionError(RuntimeError): pass

def sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def parse_roots(values:list[str])->dict[str,Path]:
    out={}
    for raw in values:
        if "=" not in raw: raise ResolutionError(f"invalid --root {raw!r}")
        name,p=raw.split("=",1)
        if not name or name in out: raise ResolutionError(f"duplicate/empty map root {name!r}")
        q=Path(p).resolve()
        if not q.is_dir(): raise ResolutionError(f"{name}: OAT root absent: {q}")
        out[name]=q
    return out

def techset_bindings(root:Path,name:str):
    p=(root/"techsets"/f"{name}.techset").resolve()
    try:p.relative_to(root)
    except ValueError as e: raise ResolutionError(f"TechniqueSet escape {name!r}") from e
    if not p.is_file(): return None, None
    rows,errs=oat.parse_techset(p.read_text(encoding="utf-8",errors="strict"))
    if errs: raise ResolutionError(f"{name}: OAT techset parse errors {errs[:4]}")
    by_type={}
    for r in rows:
        tech=str(r["technique"])
        for typ in r["types"]:
            if typ in by_type and by_type[typ]!=tech:
                raise ResolutionError(f"{name}: duplicate type {typ!r}: {by_type[typ]!r} vs {tech!r}")
            by_type[typ]=tech
    return p,by_type

def technique_pass(root:Path,name:str,index:int):
    p=(root/"techniques"/f"{name}.tech").resolve()
    try:p.relative_to(root)
    except ValueError as e: raise ResolutionError(f"Technique escape {name!r}") from e
    if not p.is_file(): return None,None
    raw,errs=oat.split_top_level_passes(p.read_text(encoding="utf-8",errors="strict"))
    if errs: raise ResolutionError(f"{name}: split errors {errs[:4]}")
    if not 0<=index<len(raw): return p,None
    rec,errs=oat.parse_pass(raw[index],root)
    if errs: raise ResolutionError(f"{name} pass {index}: parse errors {errs[:4]}")
    rec["index"]=index
    return p,rec

def shader_stage(passrec:dict,kind:str):
    want="vertexShader" if kind=="packedVSObjectRef" else "pixelShader"
    rows=[x for x in passrec.get("shaders",[]) if x.get("kind")==want]
    if len(rows)!=1: return None, f"{want}-count-{len(rows)}"
    s=rows[0]
    b=s.get("binary")
    if not isinstance(b,dict): return None, "shader-binary-absent"
    return {
      "asset":s.get("name"),"shaderModel":s.get("model"),
      "relativeFile":b.get("path"),"bytes":b.get("size"),"sha256":b.get("sha256"),
      "argumentCount":len(s.get("arguments",[])),
    },None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--topology",type=Path,required=True)
    ap.add_argument("--root",action="append",required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--strict",action="store_true")
    a=ap.parse_args()
    topo=json.loads(a.topology.read_text())
    if topo.get("format")!=TOPO_FORMAT: raise SystemExit(f"topology format drift {topo.get('format')!r}")
    roots=parse_roots(a.root)
    rows=[]; counts={}
    cache_ts={}; cache_pass={}
    for src in topo.get("rows",[]):
        kind=str(src["kind"]); mapn=str(src["map"]); ts=str(src["techniqueSet"]); sl=int(src["techniqueSlot"])
        root=roots.get(mapn)
        base={k:src[k] for k in src}
        if root is None:
            status="unresolved-map-root-absent"; row={**base,"status":status}
        elif not 0<=sl<len(slot.TECHNIQUE_TYPE_NAMES):
            status="unresolved-technique-slot-range"; row={**base,"status":status}
        else:
            key=(mapn,ts)
            if key not in cache_ts: cache_ts[key]=techset_bindings(root,ts)
            tspath,bind=cache_ts[key]
            label=slot.TECHNIQUE_TYPE_NAMES[sl]
            if tspath is None:
                status="unresolved-oat-techniqueset-absent"; row={**base,"slotLabel":label,"status":status}
            else:
                resolved_tech=bind.get(label)
                if not resolved_tech:
                    status="unresolved-oat-slot-empty"; row={**base,"slotLabel":label,"status":status,
                      "oatTechniqueSetFile":tspath.relative_to(root).as_posix(),"oatTechniqueSetSha256":sha(tspath)}
                elif kind=="packedTechniqueRef":
                    status="resolved-oat-same-zone-technique"
                    tp=root/"techniques"/f"{resolved_tech}.tech"
                    row={**base,"slotLabel":label,"status":status,"resolvedTechnique":resolved_tech,
                      "oatTechniqueSetFile":tspath.relative_to(root).as_posix(),"oatTechniqueSetSha256":sha(tspath),
                      "oatTechniqueFile":tp.relative_to(root).as_posix() if tp.is_file() else None,
                      "oatTechniqueFileSha256":sha(tp) if tp.is_file() else None}
                else:
                    rawtech=src.get("technique")
                    if rawtech and str(rawtech)!=resolved_tech:
                        status="conflict-oat-slot-technique"
                        row={**base,"slotLabel":label,"status":status,"resolvedTechnique":resolved_tech,
                             "rawStructuralTechnique":rawtech}
                    else:
                        pi=int(src.get("passIndex",-1))
                        pkey=(mapn,resolved_tech,pi)
                        if pkey not in cache_pass:cache_pass[pkey]=technique_pass(root,resolved_tech,pi)
                        tpath,prec=cache_pass[pkey]
                        if tpath is None:
                            status="unresolved-oat-technique-absent"; row={**base,"slotLabel":label,"status":status,
                              "resolvedTechnique":resolved_tech}
                        elif prec is None:
                            status="unresolved-oat-pass-index"; row={**base,"slotLabel":label,"status":status,
                              "resolvedTechnique":resolved_tech,"oatTechniqueFile":tpath.relative_to(root).as_posix()}
                        elif kind in ("packedVSObjectRef","packedPSObjectRef","packedInlinePSNameRef"):
                            stage_kind="packedPSObjectRef" if kind=="packedInlinePSNameRef" else kind
                            sr,err=shader_stage(prec,stage_kind)
                            if err:
                                status="unresolved-oat-"+err
                                row={**base,"slotLabel":label,"status":status,"resolvedTechnique":resolved_tech,
                                  "oatTechniqueFile":tpath.relative_to(root).as_posix(),"oatPass":prec}
                            else:
                                status="resolved-oat-same-zone-shader"
                                row={**base,"slotLabel":label,"status":status,"resolvedTechnique":resolved_tech,
                                  "oatTechniqueFile":tpath.relative_to(root).as_posix(),"oatTechniqueFileSha256":sha(tpath),
                                  "resolvedShader":sr}
                        elif kind=="packedVertexDeclRef":
                            routing=prec.get("vertexRouting",[])
                            status="resolved-oat-same-zone-vertex-routing-only" if routing else "unresolved-oat-vertex-routing-empty"
                            row={**base,"slotLabel":label,"status":status,"resolvedTechnique":resolved_tech,
                              "oatTechniqueFile":tpath.relative_to(root).as_posix(),"oatTechniqueFileSha256":sha(tpath),
                              "resolvedVertexRouting":routing,
                              "identityBoundary":"OAT T6 conversion emits routing but not original MaterialVertexDeclaration identity; routing is not promoted as pointer identity."}
                        else:
                            status="unresolved-unsupported-kind";row={**base,"slotLabel":label,"status":status}
        counts[row["status"]]=counts.get(row["status"],0)+1
        rows.append(row)
    conflict=sum(v for k,v in counts.items() if k.startswith("conflict-"))
    exact=sum(v for k,v in counts.items() if k in ("resolved-oat-same-zone-technique","resolved-oat-same-zone-shader"))
    routing=counts.get("resolved-oat-same-zone-vertex-routing-only",0)
    unresolved=len(rows)-exact-routing
    summary={
      "topologyRowCount":len(rows),"sameZoneExactIdentityResolutionCount":exact,
      "sameZoneVertexRoutingOnlyCount":routing,"unresolvedOrConflictCount":unresolved,
      "conflictCount":conflict,"statusCounts":dict(sorted(counts.items())),
      "packedTechniqueResolvedCount":sum(r["status"]=="resolved-oat-same-zone-technique" for r in rows),
      "packedShaderOrNameResolvedCount":sum(r["status"]=="resolved-oat-same-zone-shader" for r in rows),
      "vertexDeclIdentityResolvedCount":0,
    }
    doc={"format":FORMAT,
      "authority":"exact raw special packed-reference topology + pinned OAT same-zone native pointer resolution/dump products",
      "sources":{"topology":{"path":str(a.topology),"sha256":sha(a.topology)},
                 "oatRoots":{k:str(v) for k,v in sorted(roots.items())}},
      "summary":summary,"rows":rows,
      "proofBoundary":"Technique and VS/PS/name rows resolve only through the exact same-world OAT TechniqueSet slot and exact Technique pass emitted after native T6 loader pointer resolution. No cross-zone winner, filename similarity, pointer arithmetic, adjacency, or shader appearance is used. VertexDecl rows retain only exact emitted routing semantics because OAT discards the original declaration identity; those rows are explicitly not counted as identity-resolved."}
    if a.strict and conflict: raise SystemExit(f"same-zone OAT conflicts: {conflict}")
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__": main()

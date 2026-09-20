#!/usr/bin/env python3
"""Join exact special packed VertexDecl tokens to native OAT declaration fields."""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path

FORMAT="t6-retail-special-vertexdecl-native-resolution-v1"
TOPO="t6-retail-special-packed-reference-topology-v1"
RX_OFF=re.compile(r"^T6_BLOCK5_OFFSET_(?:NATIVE|LOOKUP) raw=0x([0-9a-fA-F]+) decoded=0x([0-9a-fA-F]+) resolved=0x([0-9a-fA-F]+)(?: redirected=[01])?$")
RX_DECL=re.compile(r"^T6_VERTEXDECL_NATIVE ptr=0x([0-9a-fA-F]+) streamCount=(\d+) hasOptionalSource=(\d+) isLoaded=(\d+) routing=(.*)$")

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def roots(vals):
    out={}
    for v in vals:
        if "=" not in v:raise SystemExit(f"bad log spec {v!r}")
        m,p=v.split("=",1);q=Path(p)
        if m in out or not q.is_file():raise SystemExit(f"bad/duplicate log {v!r}")
        out[m]=q
    return out
def parse_log(path):
    offsets={};decls={}
    for line in path.read_text(errors="replace").splitlines():
        m=RX_OFF.match(line)
        if m:
            raw=int(m.group(1),16);decoded=int(m.group(2),16);ptr=int(m.group(3),16)
            offsets.setdefault(raw,set()).add((decoded,ptr));continue
        m=RX_DECL.match(line)
        if m:
            ptr=int(m.group(1),16);sc=int(m.group(2));opt=int(m.group(3));loaded=int(m.group(4));rt=m.group(5)
            routing=[]
            if rt:
                for x in rt.split(","):
                    a,b=x.split(":",1);routing.append([int(a),int(b)])
            rec=(sc,opt,loaded,tuple(tuple(x) for x in routing))
            decls.setdefault(ptr,set()).add(rec)
    return offsets,decls
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--topology",type=Path,required=True);ap.add_argument("--same-zone",type=Path,required=True)
    ap.add_argument("--log",action="append",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    top=json.loads(a.topology.read_text());same=json.loads(a.same_zone.read_text())
    if top.get("format")!=TOPO:raise SystemExit("topology format drift")
    if same.get("format")!="t6-retail-special-oat-same-zone-child-resolution-v1":raise SystemExit("same-zone format drift")
    logs=roots(a.log);parsed={m:parse_log(p) for m,p in logs.items()}
    targets=[r for r in top["rows"] if r["kind"]=="packedVertexDeclRef"]
    if len(targets)!=459:raise SystemExit(f"expected 459 VertexDecl occurrences, got {len(targets)}")
    byid={};rows=[];errors=[]
    for r in targets:
        m=r["map"];raw=int(r["raw"],16);ident=(m,int(r["block"]),int(r["offset"]),r["raw"])
        if m not in parsed:
            errors.append({"identity":ident,"error":"map-log-absent"});continue
        offsets,decls=parsed[m];pairs=offsets.get(raw,set())
        resolved=[]
        for decoded,ptr in sorted(pairs):
            for rec in sorted(decls.get(ptr,set())):
                sc,opt,loaded,routing=rec
                resolved.append({"decodedOffset":decoded,"resolvedPointerHex":f"0x{ptr:x}",
                    "streamCount":sc,"hasOptionalSource":bool(opt),"isLoaded":bool(loaded),
                    "routing":[list(x) for x in routing]})
        if not resolved:
            errors.append({"identity":ident,"error":"raw-token-or-native-declaration-unjoined","rawResolutionCount":len(pairs)});continue
        canonical={json.dumps({k:v for k,v in x.items() if k!="resolvedPointerHex"},sort_keys=True) for x in resolved}
        if len(canonical)!=1:
            errors.append({"identity":ident,"error":"conflicting-native-declaration-fields","variants":resolved});continue
        fieldrec=json.loads(next(iter(canonical)))
        if fieldrec["streamCount"]!=len(fieldrec["routing"]):
            errors.append({"identity":ident,"error":"stream-count-routing-count-mismatch","fields":fieldrec});continue
        prev=byid.get(ident)
        if prev is not None and prev!=fieldrec:
            errors.append({"identity":ident,"error":"same-identity-field-drift"});continue
        byid[ident]=fieldrec
        rows.append({**r,"nativeVertexDeclaration":fieldrec})
    unique_targets={(r["map"],int(r["block"]),int(r["offset"]),r["raw"]) for r in targets}
    summary={"vertexDeclOccurrenceCount":len(targets),"uniqueVertexDeclPointerIdentityCount":len(unique_targets),
      "joinedOccurrenceCount":len(rows),"joinedUniquePointerIdentityCount":len(byid),"errorCount":len(errors),
      "allVertexDeclOccurrencesNativeFieldClosed":len(rows)==len(targets) and len(byid)==len(unique_targets) and not errors,
      "distinctNativeDeclarationFieldTupleCount":len({json.dumps(v,sort_keys=True) for v in byid.values()}),
      "hasOptionalSourceTrueIdentityCount":sum(bool(v["hasOptionalSource"]) for v in byid.values()),
      "isLoadedTrueIdentityCount":sum(bool(v["isLoaded"]) for v in byid.values())}
    out={"format":FORMAT,"authority":"exact packed special topology + pinned OAT native block-5 offset resolution + pre-conversion T6 MaterialVertexDeclaration fields",
      "sources":{"topology":{"path":str(a.topology),"sha256":sha(a.topology)},"sameZone":{"path":str(a.same_zone),"sha256":sha(a.same_zone)},
        "logs":{m:{"path":str(p),"sha256":sha(p)} for m,p in sorted(logs.items())}},
      "summary":summary,"uniquePointerFields":[{"map":i[0],"block":i[1],"offset":i[2],"raw":i[3],"nativeVertexDeclaration":v} for i,v in sorted(byid.items())],
      "rows":rows,"errors":errors,
      "proofBoundary":"Each VertexDecl row is joined only by its exact same-map raw block-5 token through OAT's native offset conversion to the exact MaterialVertexDeclaration address observed before common-format conversion. All native serialized/runtime fields exposed by the T6 struct are retained: streamCount, hasOptionalSource, isLoaded, and numeric routing. Pointer addresses are process-local join keys only and are not treated as stable identities across runs."}
    if not summary["allVertexDeclOccurrencesNativeFieldClosed"]:raise SystemExit(json.dumps(summary,sort_keys=True))
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=="__main__":main()

#!/usr/bin/env python3
"""Anchor the exact hdrControl0.x terminal use in every generated Nuketown slot-4 PS.

The proof consumes the authoritative final-output DAG plus the exact runtime-input
census. It promotes only a literal DAG shape:
    o0.rgb root = sqrt(mul(preHdrNode, cb0[20].x))
with the multiply operands allowed in either stored order. No associative rewrite,
constant folding, or physical interpretation of hdrControl0 is performed.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FINAL="t6-generated-slot4-final-output-symbolic-v3"
RUNTIME="t6-nuketown-generated-final-output-runtime-input-census-v1"
FORMAT="t6-nuketown-generated-final-output-hdr-terminal-anchor-v1"
SYMBOL="cb0[20].x"
ACCESSOR="hdrControl0"
class E(RuntimeError):pass
def req(c,m):
    if not c: raise E(m)
def jhash(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def nodes(shader):
    out={}
    for r in shader.get("nodes",[]):
        i=int(r.get("id",-1));req(i>=0 and i not in out,f"{shader.get('sha256')}: invalid/duplicate node {i}")
        out[i]=r
    return out
def o0(shader):
    rows=[r for r in shader.get("outputs",[]) if int(r.get("register",-1))==0]
    req(len(rows)==1,f"{shader.get('sha256')}: expected one o0")
    out={}
    for r in rows[0].get("lanes",[]):
        ch=str(r.get("channel") or "")
        if ch in "xyz":
            req(r.get("written") is True and r.get("node") is not None,f"{shader.get('sha256')}: unwritten o0.{ch}")
            out[ch]=int(r["node"])
    req(set(out)==set("xyz"),f"{shader.get('sha256')}: incomplete o0.rgb")
    return out

def build(final,runtime):
    req(final.get("format")==FINAL,f"final format {final.get('format')!r}")
    req(runtime.get("format")==RUNTIME,f"runtime format {runtime.get('format')!r}")
    fs=final.get("summary",{});rs=runtime.get("summary",{})
    req(int(fs.get("uniquePixelShaderCount",-1))==34,"final shader population drift")
    req(int(rs.get("programCount",-1))==34 and int(rs.get("materialCount",-1))==120,"runtime population drift")
    dc=runtime.get("dynamicCodeConstants",[])
    req(len(dc)==1,"expected exactly one dynamic code-constant identity")
    ident=dc[0]
    req(ident.get("accessor")==ACCESSOR,f"dynamic accessor {ident.get('accessor')!r} != {ACCESSOR}")
    req(int(ident.get("resolvedEnumValue",-1))==123,"hdrControl0 enum drift")
    req(int(ident.get("materialInputOccurrenceCount",-1))==120,"hdrControl0 material occurrence drift")
    for m in runtime.get("materials",[]):
        c=m.get("cbufferInputs",[])
        req(len(c)==1,f"{m.get('material')}: expected one final-output cbuffer input")
        req(c[0].get("symbol")==SYMBOL and c[0].get("kind")=="t6CodeConstantDynamic",f"{m.get('material')}: cbuffer input is not exact hdr slot")
        req((c[0].get("dynamicIdentity") or {}).get("accessor")==ACCESSOR,f"{m.get('material')}: hdr accessor mismatch")

    rows=[];pre=set();shape_count=0
    for shader in sorted(final.get("shaders",[]),key=lambda x:str(x.get("sha256"))):
        sha=str(shader.get("sha256") or "");n=nodes(shader)
        syms=[i for i,r in n.items() if r.get("kind")=="symbol" and r.get("name")==SYMBOL]
        req(len(syms)==1,f"{sha}: exact symbol {SYMBOL} count {len(syms)}")
        sid=syms[0]; lanes={}
        for ch,root in sorted(o0(shader).items()):
            sr=n[root];req(sr.get("kind")=="op" and sr.get("op")=="sqrt" and len(sr.get("args",[]))==1,f"{sha} o0.{ch}: root is not unary sqrt")
            mul_id=int(sr["args"][0]);mr=n.get(mul_id)
            req(mr is not None and mr.get("kind")=="op" and mr.get("op")=="mul" and len(mr.get("args",[]))==2,f"{sha} o0.{ch}: sqrt child is not binary mul")
            args=[int(x) for x in mr["args"]]
            req(args.count(sid)==1,f"{sha} o0.{ch}: terminal mul does not contain exactly one hdr symbol")
            pre_id=args[1] if args[0]==sid else args[0]
            pre.add((sha,ch,pre_id));shape_count+=1
            lanes[ch]={
              "outputRootNode":root,"sqrtNode":root,"terminalMulNode":mul_id,
              "hdrSymbolNode":sid,"hdrSymbol":SYMBOL,"preHdrNode":pre_id,
              "literalShape":"sqrt(mul(preHdr, hdrControl0.x))"
            }
        rows.append({"sha256":sha,"techniqueSets":shader.get("techniqueSets",[]),"lanes":lanes})
    req(len(rows)==34 and shape_count==102,"expected 34 shaders / 102 RGB lane anchors")
    summary={
      "shaderCount":len(rows),"rgbLaneAnchorCount":shape_count,
      "dynamicConstantAccessor":ACCESSOR,"dynamicConstantEnumValue":123,
      "materialOccurrenceCount":120,
      "literalTerminalShapeCount":shape_count,
      "allRgbLanesLiteralSqrtMulHdr":True,
      "distinctPreHdrNodeInstances":len(pre),
    }
    return {
      "format":FORMAT,"summary":summary,"shaders":rows,"rowsSha256":jhash(rows),
      "proofBoundary":"Exact syntactic DAG anchor only: every generated Nuketown slot-4 o0.rgb lane is literally sqrt(mul(preHdrNode, cb0[20].x)), with cb0[20].x independently identified as T6 hdrControl0 enum 123 for all 120 material owners. The preHdr subtree is not algebraically rewritten or physically relabeled here, and the runtime numeric value/construction of hdrControl0.x remains unresolved."
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--final",type=Path,required=True);ap.add_argument("--runtime",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    d=build(json.loads(a.final.read_text()),json.loads(a.runtime.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    print(json.dumps(d["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()

#!/usr/bin/env python3
"""Compact sampler-state overlap writers into exact source-definition candidates.

Consumes the exhaustive byte-overlap denominator and, for each store, identifies
the stored operand, its nearest visible register definition in the frozen context,
and the destination-base register's nearest visible definition. This is a
fail-visible diagnostic reducer: it never promotes unresolved register provenance.
"""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path

FORMAT="t6-current-client-sampler-state-byte-writer-source-candidates-v1"
SRC="t6-current-client-sampler-state-byte-overlap-writers-v1"
REG=r"(?:e(?:ax|bx|cx|dx|si|di|bp|sp)|[abcd]x)"
DST_RE=re.compile(r"^(?:byte|word|dword|qword) ptr \[[^\]]+\],\s*(.+)$",re.I)
FIRST_RE=re.compile(r"^([^,]+)",re.I)
REG_FULL=re.compile(rf"^{REG}$",re.I)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def req(c,m):
    if not c:raise SystemExit(m)
def first_op(op):
    m=FIRST_RE.match(op or "");return m.group(1).strip().lower() if m else ""
def nearest_def(ctx,reg):
    reg=reg.lower()
    for x in reversed(ctx):
        if first_op(x.get("opStr",""))==reg:
            return x
    return None
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    d=json.loads(a.source.read_text());req(d.get("format")==SRC,"source format drift")
    out_rows={}
    counts={}
    for acc,rows in d.get("rows",{}).items():
        oo=[]
        for row in rows:
            w=row["instruction"];op=w.get("opStr","")
            m=DST_RE.match(op);req(m is not None,f"unsupported store operand {w['address']}: {op}")
            src=m.group(1).strip().lower()
            src_kind="immediate" if not REG_FULL.fullmatch(src) else "register"
            src_def=nearest_def(row.get("contextBefore",[]),src) if src_kind=="register" else None
            base=row.get("baseReg")
            base_def=nearest_def(row.get("contextBefore",[]),base) if base else None
            branches=[x for x in row.get("contextBefore",[])[-12:] if x.get("mnemonic","").startswith("j") or x.get("mnemonic") in {"cmp","test"}]
            oo.append({
              "writer":w,"baseReg":base,"coveredRange":row.get("coveredRange"),"storedOperand":src,
              "storedOperandKind":src_kind,"nearestStoredRegisterDefinition":src_def,
              "nearestBaseRegisterDefinition":base_def,"nearbyPredicates":branches,
            })
        out_rows[acc]=oo
        counts[acc]={"writerCount":len(oo),
                     "immediateWriterCount":sum(x["storedOperandKind"]=="immediate" for x in oo),
                     "registerWriterCount":sum(x["storedOperandKind"]=="register" for x in oo),
                     "registerWriterWithVisibleDefinitionCount":sum(bool(x["storedOperandKind"]=="register" and x["nearestStoredRegisterDefinition"]) for x in oo)}
    out={"format":FORMAT,"authority":"deterministic compact projection of exhaustive exact sampler-state byte-overlap writer census",
      "source":{"path":str(a.source),"sha256":sha(a.source),"format":d["format"]},
      "summary":counts,"rows":out_rows,
      "proofBoundary":"Diagnostic source-definition projection only. Immediate stores are exact values. A nearest visible register definition is not automatically the reaching definition across branches/calls; base-object identity, later writer ordering, resource ownership and historical-retail equivalence remain separate gates."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out,indent=2,sort_keys=True))
if __name__=="__main__":main()

#!/usr/bin/env python3
"""Final-output cbuffer signature v2: exact current OAT source namespaces.

v1 proved cb register/component -> exact same-CSO RDEF variable ranges and kept
verbatim `.tech` RHS expressions, but its source classifier only recognized
`material.*`/legacy `code.*`. v2 preserves every v1 byte-derived/RDEF row and
reclassifies the retained RHS using current OAT namespaces:
`material.*`, `constant.*`, and `sampler.*` (plus legacy `code.*`).
"""
from __future__ import annotations
import argparse,copy,hashlib,json
from collections import Counter
from pathlib import Path
from typing import Any
import t6_generated_final_output_cbuffer_signature_v1 as v1
from t6_tech_argument_source_identity_v2 import source_identity
FORMAT='t6-generated-final-output-cbuffer-signature-v2'
class FinalOutputCbufferSignatureV2Error(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def promote(base:dict)->dict:
 if base.get('format')!=v1.FORMAT:raise FinalOutputCbufferSignatureV2Error(f"unexpected v1 cbuffer format {base.get('format')!r}")
 out=copy.deepcopy(base);classes=Counter();namespaces=Counter();assignment_count=0
 for shader in out.get('shaders',[]):
  for item in shader.get('usedCbufferSymbols',[]):
   assignments=[]
   for row in item.get('techniqueAssignments',[]):
    identity=source_identity(row.get('sourceExpression'))
    assignments.append({'techniqueSet':row.get('techniqueSet'),**identity})
    classes[identity['sourceClass']]+=1;namespaces[str(identity['sourceNamespace']) if identity['sourceNamespace'] is not None else 'none']+=1;assignment_count+=1
   item['techniqueAssignments']=assignments
 out['format']=FORMAT;out['baseFormat']=v1.FORMAT
 out['summary']['techniqueAssignmentSourceClassCounts']=dict(sorted(classes.items()))
 out['summary']['techniqueAssignmentSourceNamespaceCounts']=dict(sorted(namespaces.items()))
 out['summary']['techniqueAssignmentCount']=assignment_count
 out['rowsSha256']=_jhash(out.get('shaders',[]))
 out['proofBoundary']=str(base.get('proofBoundary') or '')+' v2 reclassifies the verbatim retained `.tech` RHS with current OAT material./constant./sampler. namespaces; legacy code. remains compatibility-only. No runtime value or physical semantics are inferred.'
 return out

def build(final_output:dict,oat_root:Path)->dict:return promote(v1.build(final_output,Path(oat_root)))

def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--final-output',type=Path,required=True);p.add_argument('--oat-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.final_output.read_text()),a.oat_root);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())

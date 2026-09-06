#!/usr/bin/env python3
"""Material cbuffer value proof v3: corrected OAT namespace provenance.

Material values in v2 are byte-exact, but v2 consumed cbuffer signature v1.
v3 reruns the same exact retained-world MaterialConstantDef join against cbuffer
signature v2. `material.*` bindings remain the only values resolved here;
constant./sampler./legacy-code/unassigned/other sources remain unresolved.
"""
from __future__ import annotations
import argparse,copy,json
from pathlib import Path
import t6_generated_final_output_cbuffer_signature_v1 as cb1
import t6_generated_final_output_cbuffer_signature_v2 as cb2
import t6_generated_final_output_material_cbuffer_values_v2 as v2
FORMAT='t6-generated-final-output-material-cbuffer-values-v3'
class FinalOutputMaterialCbufferValueV3Error(RuntimeError):pass

def build(final_doc:dict,cbuffer_v2:dict,material_constants_doc:dict)->dict:
 if cbuffer_v2.get('format')!=cb2.FORMAT:raise FinalOutputMaterialCbufferValueV3Error(f"unexpected cbuffer v2 format {cbuffer_v2.get('format')!r}")
 # v1 material-value resolver only depends on the material.* assignment fields,
 # which v2 preserves while adding corrected namespace/kind metadata.
 compatible=copy.deepcopy(cbuffer_v2);compatible['format']=cb1.FORMAT
 try:out=v2.build(final_doc,compatible,material_constants_doc)
 except Exception as e:raise FinalOutputMaterialCbufferValueV3Error(str(e)) from e
 out['format']=FORMAT;out['baseFormat']=v2.FORMAT;out['sourceCbufferFormat']=cb2.FORMAT
 out['proofBoundary']=str(out.get('proofBoundary') or '')+' v3 reruns the material-only value join against corrected cbuffer signature v2; current OAT non-material namespaces remain explicitly unresolved.'
 return out

def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--final-output',type=Path,required=True);p.add_argument('--cbuffer-signature-v2',type=Path,required=True);p.add_argument('--material-constants',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=build(json.loads(a.final_output.read_text()),json.loads(a.cbuffer_signature_v2.read_text()),json.loads(a.material_constants.read_text()));a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())

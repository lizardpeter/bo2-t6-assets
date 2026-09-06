#!/usr/bin/env python3
"""Cross-prove generated specular transitions use exact RGB final-output factors.

This joins two independently recovered final-output anchors by canonical retail
material identity:
- RGB A/B/M/T factor anchor v1;
- specular XYZW state anchor v1.

For every specular layer, the specular shared factor/condition DAG hash must equal
the RGB shared factor/condition DAG hash for the same layer.  Operator families
must also agree (specular b <-> RGB blend, specular t <-> RGB threshold).

This closes the final-output instance of the retained "same RGB weight" claim
without assigning physical semantics to specular XYZW or the scalar itself.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from typing import Any

FORMAT='t6-generated-final-output-specular-rgb-factor-join-v1'
RGB_FORMAT='t6-generated-final-output-rgb-factor-anchor-v1'
SPEC_FORMAT='t6-generated-final-output-specular-state-anchor-v1'
OP_MAP={'b':'blend','t':'threshold'}
class SpecularRgbFactorJoinError(RuntimeError):pass

def _jhash(v:Any)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def _rows(doc,fmt,label):
 if doc.get('format')!=fmt:raise SpecularRgbFactorJoinError(f'unexpected {label} format {doc.get("format")!r}')
 out={}
 for row in doc.get('materials',[]):
  m=str(row.get('material') or '')
  if not m or m in out:raise SpecularRgbFactorJoinError(f'{label}: invalid/duplicate material {m!r}')
  out[m]=row
 return out

def build(rgb_doc,spec_doc,*,strict=True):
 rgb=_rows(rgb_doc,RGB_FORMAT,'RGB factor anchor');spec=_rows(spec_doc,SPEC_FORMAT,'specular anchor');rows=[];checks=0;mismatches=[]
 for material,srow in sorted(spec.items()):
  rrow=rgb.get(material)
  if rrow is None:raise SpecularRgbFactorJoinError(f'{material!r}: missing RGB factor anchor row')
  rsteps={int(x.get('layerIndex',-1)):x for x in rrow.get('steps',[])}
  if len(rsteps)!=len(rrow.get('steps',[])):raise SpecularRgbFactorJoinError(f'{material!r}: duplicate RGB layer index')
  joined=[]
  for s in srow.get('steps',[]):
   layer=int(s.get('layerIndex',-1));sop=str(s.get('operator') or '');expected=OP_MAP.get(sop)
   if expected is None:raise SpecularRgbFactorJoinError(f'{material!r} layer {layer}: unsupported specular operator {sop!r}')
   r=rsteps.get(layer)
   if r is None:raise SpecularRgbFactorJoinError(f'{material!r} layer {layer}: missing RGB layer step')
   rop=str(r.get('operation') or '');sh=str(s.get('sharedFactorSha256') or '');rh=str(r.get('sharedFactorSha256') or '')
   ok=(rop==expected and len(sh)==64 and sh==rh);checks+=1
   item={'layerIndex':layer,'specularOperator':sop,'rgbOperation':rop,'specularFactorSha256':sh,'rgbFactorSha256':rh,'operatorCompatible':rop==expected,'factorSha256Match':sh==rh,'exactMatch':ok}
   joined.append(item)
   if not ok:mismatches.append({'material':material,**item})
  rows.append({'material':material,'shaderSha256':srow.get('shaderSha256'),'stepCount':len(joined),'steps':joined,'allStepsMatch':all(x['exactMatch'] for x in joined)})
 if strict and mismatches:
  first=mismatches[0];raise SpecularRgbFactorJoinError(f"{len(mismatches)} specular/RGB factor mismatches; first={first}")
 summary={'specularMaterialCount':len(rows),'factorJoinCheckCount':checks,'exactMatchCount':checks-len(mismatches),'mismatchCount':len(mismatches),'fullyMatchedMaterialCount':sum(1 for r in rows if r['allStepsMatch']),'strict':bool(strict)}
 return {'format':FORMAT,'materials':rows,'summary':summary,'mismatches':mismatches,'rowsSha256':_jhash(rows),'proofBoundary':'Independent exact final-output RGB and specular recurrence anchors joined by canonical retail material/layer. Specular b/t factor/condition DAG hashes must equal RGB blend/threshold factor/condition hashes exactly. No physical interpretation of specular XYZW or factor value is assigned.'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--rgb',type=Path,required=True);p.add_argument('--specular',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--relaxed',action='store_true');a=p.parse_args();d=build(json.loads(a.rgb.read_text()),json.loads(a.specular.read_text()),strict=not a.relaxed);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())

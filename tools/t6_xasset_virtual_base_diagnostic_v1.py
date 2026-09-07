#!/usr/bin/env python3
"""Diagnose packed XAsset pointer-field VIRTUAL-base candidates without promoting one."""
from __future__ import annotations
import argparse,json,struct
from pathlib import Path
from t6_asset_types_v1 import TECHNIQUE_SET
from t6_material_techset_top_level_walk_v1 import FOLLOW,INSERT,parse_front
from t6_material_techset_resolve_v1 import report_materials

def front_detail(d:bytes):
 p=40;sc,sp,dc,dp,ac,ap=struct.unpack_from('<6I',d,p);p+=24
 script_ptrs_start=p
 scripts=[]
 if sc:
  vals=struct.unpack_from(f'<{sc}I',d,p);p+=4*sc
  for i,raw in enumerate(vals):
   if raw==FOLLOW:
    e=d.index(b'\0',p);scripts.append((i,p,e+1,d[p:e].decode('latin1')));p=e+1
 dep_ptrs_start=p;deps=[]
 if dc:
  vals=struct.unpack_from(f'<{dc}I',d,p);p+=4*dc
  for i,raw in enumerate(vals):
   if raw==FOLLOW:
    e=d.index(b'\0',p);deps.append((i,p,e+1,d[p:e].decode('latin1')));p=e+1
 return {'scriptCount':sc,'scriptPointerMode':f'0x{sp:08X}','scriptPointerArraySourceStart':script_ptrs_start,'scriptInlineCount':len(scripts),'scriptInlineBytes':sum(e-s for _,s,e,_ in scripts),'dependencyCount':dc,'dependencyPointerMode':f'0x{dp:08X}','dependencyPointerArraySourceStart':dep_ptrs_start,'dependencyInlineCount':len(deps),'dependencyInlineBytes':sum(e-s for _,s,e,_ in deps),'assetCount':ac,'assetPointerMode':f'0x{ap:08X}','assetArraySourceStart':p,'assetArrayBytes':8*ac,'assetBodySourceStart':p+8*ac,'dependencies':[x[3] for x in deps]}

def build(expanded:Path,report:Path):
 d=expanded.read_bytes();src,rows=report_materials(json.loads(report.read_text()))
 blocks,assets,body=parse_front(d);q=[i for i,a in enumerate(assets) if int(a['type'])==TECHNIQUE_SET and int(a['headerRaw']) in (FOLLOW,INSERT)]
 sets=[]
 for r in rows:
  off=int(r['techniqueSetPointer']['offset']);sets.append({off-4-8*i for i in q})
 shared=sorted(x for x in set.intersection(*sets) if x>=0)
 cand=[]
 for base in shared:
  maps=[];ok=True
  for r in rows:
   off=int(r['techniqueSetPointer']['offset']);delta=off-base-4
   if delta<0 or delta%8:ok=False;break
   qi=delta//8
   if qi>=len(assets):ok=False;break
   a=assets[qi]
   maps.append({'material':r['material'],'pointerOffset':off,'xassetIndex':qi,'xassetType':int(a['type']),'headerRaw':f"0x{int(a['headerRaw']):08X}",'inlineTechniqueSet':int(a['type'])==TECHNIQUE_SET and int(a['headerRaw']) in (FOLLOW,INSERT)})
  cand.append({'base':base,'baseHex':f'0x{base:X}','allMappingsStructurallyValid':ok and all(x['inlineTechniqueSet'] for x in maps),'mappings':maps})
 return {'format':'t6-xasset-virtual-base-diagnostic-v1','blockSizes':list(blocks),'front':front_detail(d),'candidateCount':len(cand),'candidates':cand,'noCandidatePromoted':True}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('expanded',type=Path);ap.add_argument('material_report',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();o=build(a.expanded,a.material_report);a.out.write_text(json.dumps(o,indent=2,sort_keys=True)+'\n');print(json.dumps(o,indent=2,sort_keys=True))
if __name__=='__main__':main()

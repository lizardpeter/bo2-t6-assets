#!/usr/bin/env python3
"""Build authoritative T6 world-vertex registry from all accepted retail proofs.

Evidence classes are intentionally separate:
- baseline direct retail vertex proofs;
- material-bound direct proofs (GfxSurface -> Material -> TechniqueSet + raw vd1);
- standalone/raw vd1 allocation censuses.
Formula knowledge alone never promotes a format, blocked/ambiguous evidence never
promotes a format, and any clean contradictory stride is a hard stop.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

SPECS={
0:("TEX_1_NRM_1",1,1,0,[]),1:("TEX_2_NRM_1",2,1,4,["uv1"]),2:("TEX_2_NRM_2",2,2,8,["uv1","normalTransform0"]),3:("TEX_3_NRM_1",3,1,8,["uv1","uv2"]),4:("TEX_3_NRM_2",3,2,12,["uv1","uv2","normalTransform0"]),5:("TEX_3_NRM_3",3,3,16,["uv1","uv2","normalTransform0","normalTransform1"]),6:("TEX_4_NRM_1",4,1,12,["uv1","uv2","uv3"]),7:("TEX_4_NRM_2",4,2,16,["uv1","uv2","uv3","normalTransform0"]),8:("TEX_4_NRM_3",4,3,20,["uv1","uv2","uv3","normalTransform0","normalTransform1"])}
DIRECT_PROOF_FORMATS={"t6-retail-world-formats-45-proof-v1","t6-retail-world-format-7-proof-v1"}
RAW_CENSUS_FORMATS={"t6-world-vd1-raw-census-v2","t6-world-vd1-layout-census-v1"}
class RegistryError(RuntimeError):pass

def load(path:Path)->dict:
 d=json.loads(path.read_text(encoding='utf-8'))
 if not isinstance(d,dict):raise RegistryError(f'{path}: top level must be an object')
 return d

def validate_baseline(d):
 if d.get('format')!='t6-world-vertex-format-census-v1':raise RegistryError(f"unsupported baseline {d.get('format')!r}")
 rows=d.get('formats')
 if not isinstance(rows,dict) or set(rows)!={str(i) for i in range(9)}:raise RegistryError('baseline formats must be exactly 0..8')
 for f,(name,uv,nrm,stride,fields) in SPECS.items():
  row=rows[str(f)]
  for k,v in {'name':name,'uvCount':uv,'normalCount':nrm,'vd1Stride':stride,'vd1Fields':fields}.items():
   if row.get(k)!=v:raise RegistryError(f'baseline format {f} {k}={row.get(k)!r} != {v!r}')

def map_format_rows(proof,m):
 pf=proof.get('format')
 if pf=='t6-retail-world-formats-45-proof-v1':
  rows=m.get('formats',{})
  if not isinstance(rows,dict):raise RegistryError('formats-45 proof map rows must be an object')
  return rows
 if pf=='t6-retail-world-format-7-proof-v1':
  row=m.get('format7')
  if not isinstance(row,dict):raise RegistryError('format-7 proof map lacks format7 row')
  return {'7':row}
 raise RegistryError(f'unsupported direct proof {pf!r}')

def validate_direct(d,source):
 if d.get('format') not in DIRECT_PROOF_FORMATS:raise RegistryError(f"{source}: unsupported direct proof {d.get('format')!r}")
 if int(d.get('summary',{}).get('contradictionCount',-1))!=0:raise RegistryError(f'{source}: direct proof summary contains contradictions')
 maps=d.get('maps')
 if not isinstance(maps,list) or not maps:raise RegistryError(f'{source}: direct proof has no maps')
 for m in maps:
  if not isinstance(m.get('map'),str) or not m['map']:raise RegistryError(f'{source}: map without name')
  for key,row in map_format_rows(d,m).items():
   f=int(key)
   if f not in SPECS:raise RegistryError(f'{source}: invalid format {f}')
   exp=SPECS[f][3]
   if int(row.get('contradictions',-1))!=0:raise RegistryError(f"{source}: {m['map']} format {f} contradictions")
   if int(row.get('directAllocationCount',0))<=0:raise RegistryError(f"{source}: {m['map']} format {f} has no direct allocations")
   if row.get('rawStrides')!=[exp]:raise RegistryError(f"{source}: {m['map']} format {f} rawStrides={row.get('rawStrides')!r} != [{exp}]")

def validate_raw(d,source):
 if d.get('format') not in RAW_CENSUS_FORMATS:raise RegistryError(f"{source}: unsupported raw census {d.get('format')!r}")
 obs=d.get('observedRawStrideByFormat')
 if not isinstance(obs,dict):raise RegistryError(f'{source}: raw census lacks observedRawStrideByFormat')
 blockers=d.get('blockers',[])
 if blockers is None:blockers=[]
 if not isinstance(blockers,list):raise RegistryError(f'{source}: blockers must be a list')
 for key,vals in obs.items():
  f=int(key)
  if f not in SPECS or not isinstance(vals,list):raise RegistryError(f'{source}: malformed raw stride row {key!r}')

def fixture_name(d,fallback):
 for k in ('map','mapName','worldName','zone'):
  v=d.get(k)
  if isinstance(v,str) and v:return v
 return fallback

def build_registry(baseline,direct_proofs,raw_censuses=None):
 raw_censuses=list(raw_censuses or [])
 validate_baseline(baseline)
 for s,p in direct_proofs:validate_direct(p,s)
 for s,r in raw_censuses:validate_raw(r,s)
 rows={}
 for f,(name,uv,nrm,stride,fields) in SPECS.items():
  base=baseline['formats'][str(f)];base_proven=bool(base.get('retailByteProven'));base_maps=sorted({str(x) for x in base.get('maps',[]) if str(x)})
  evidence=[];observed=set();contradictory=set();blocked=[];maps=set(base_maps);direct_raw_proven=False;standalone_raw_proven=False
  for source,proof in direct_proofs:
   for m in proof['maps']:
    row=map_format_rows(proof,m).get(str(f))
    if row is None:continue
    raw=sorted({int(x) for x in row['rawStrides']});contr=int(row.get('contradictions',0));clean=contr==0
    evidence.append({'fixture':m['map'],'source':source,'proofFormat':proof['format'],'evidenceClass':'material-bound-direct','directAllocationCount':int(row['directAllocationCount']),'observedRawStrides':raw,'sharedNonseparableCount':int(row.get('sharedNonseparableCount',0)),'contradictionCount':contr,'clean':clean})
    if clean:
     observed.update(raw)
     if stride in raw:maps.add(m['map']);direct_raw_proven=True
    contradictory.update(x for x in raw if x!=stride)
  for source,report in raw_censuses:
   vals=report.get('observedRawStrideByFormat',{}).get(str(f),[])
   raw=sorted({int(x) for x in vals})
   if not raw:continue
   blockers=list(report.get('blockers') or []);clean=not blockers;fixture=fixture_name(report,source)
   evidence.append({'fixture':fixture,'source':source,'proofFormat':report['format'],'evidenceClass':'standalone-raw-census','observedRawStrides':raw,'blockerCount':len(blockers),'clean':clean})
   if not clean:blocked.append(source);continue
   observed.update(raw)
   if stride in raw:maps.add(fixture);standalone_raw_proven=True
   contradictory.update(x for x in raw if x!=stride)
  matching=stride in observed;raw_proven=matching and not contradictory;proven=(base_proven or raw_proven) and not contradictory
  kinds=[]
  if base_proven:kinds.append('direct-retail-vertex-proof')
  if direct_raw_proven and not contradictory:kinds.append('material-bound-unambiguous-retail-vd1-allocation-stride')
  if standalone_raw_proven and not contradictory:kinds.append('unambiguous-retail-vd1-allocation-stride')
  rows[str(f)]={'format':f,'name':name,'sourceClosedFamily':{'uvCount':uv,'normalCount':nrm,'vd1Stride':stride,'vd1Fields':fields,'layoutRule':'vd0 owns uv0 + first normal/tangent basis; vd1 appends 4-byte half2 UV lanes then 4-byte packed normal-transform lanes'},'baselineDirectRetailProof':base_proven,'baselineMaps':base_maps,'rawAllocationEvidence':evidence,'cleanObservedRawStrides':sorted(observed),'matchingExpectedRawStrideObserved':matching,'rawStrideRetailProven':raw_proven,'contradictoryRawStrides':sorted(contradictory),'rawEvidenceWithBlockers':sorted(set(blocked)),'retailByteProven':proven,'exportEnabled':proven,'proofKinds':kinds,'retailProofMaps':sorted(maps),'status':'contradicted' if contradictory else 'export-enabled' if proven else 'pending-retail-byte-proof'}
 enabled=[i for i in range(9) if rows[str(i)]['exportEnabled']];pending=[i for i in range(9) if not rows[str(i)]['exportEnabled']];contr=[i for i in range(9) if rows[str(i)]['contradictoryRawStrides']]
 return {'format':'t6-world-vertex-format-registry-v1','sourceClosedFormatCount':9,'formats':rows,'coverage':{'exportEnabledCount':len(enabled),'exportEnabledFormats':enabled,'pendingCount':len(pending),'pendingFormats':pending,'contradictedCount':len(contr),'contradictedFormats':contr,'allFormatsExportEnabled':len(enabled)==9},'inputs':{'baselineFormat':baseline.get('format'),'baselineMapCount':len(baseline.get('maps',[])),'directRetailProofCount':len(direct_proofs),'directRetailProofSources':[s for s,_ in direct_proofs],'acceptedDirectRetailProofFormats':sorted(DIRECT_PROOF_FORMATS),'rawCensusCount':len(raw_censuses),'rawCensusSources':[s for s,_ in raw_censuses],'acceptedRawCensusFormats':sorted(RAW_CENSUS_FORMATS)},'policy':{'formulaAloneCannotEnableExport':True,'ambiguousRawAllocationCannotPromote':True,'rawCensusWithBlockersCannotPromote':True,'cleanContradictoryStrideDisablesFormat':True,'directExistingRetailProofRemainsValid':True,'pendingFormatPromotionRequiresExpectedUnambiguousRawStride':True,'materialBoundDirectProofAccepted':True},'proofBoundary':'exportEnabled certifies the serialized world-vertex binary layout needed for normalized geometry export. Packed normalTransformN words remain raw unless/until their downstream shader-space meaning is independently closed; this registry does not invent that renderer semantic.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--baseline',type=Path,required=True);ap.add_argument('--retail-proof',type=Path,action='append',default=[]);ap.add_argument('--raw-census',type=Path,action='append',default=[]);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 d=build_registry(load(a.baseline),[(str(p),load(p)) for p in a.retail_proof],[(str(p),load(p)) for p in a.raw_census]);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['coverage'],indent=2,sort_keys=True));return 3 if d['coverage']['contradictedCount'] else 0 if d['coverage']['allFormatsExportEnabled'] else 1
if __name__=='__main__':raise SystemExit(main())

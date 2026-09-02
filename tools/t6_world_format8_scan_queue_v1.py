#!/usr/bin/env python3
"""Build the exact remaining MP scan queue for T6 world vertex format 8."""
from __future__ import annotations
import argparse, json
from pathlib import Path

class QueueError(RuntimeError): pass

def load(p:Path)->dict:
 d=json.loads(p.read_text(encoding='utf-8'))
 if not isinstance(d,dict):raise QueueError(f'{p}: top level must be object')
 return d

def build(targets:dict, baseline:dict, fmt45:dict, registry:dict, absence:dict)->dict:
 if targets.get('format')!='t6-retail-mp-world-format-targets-v1':raise QueueError('wrong target manifest')
 if baseline.get('format')!='t6-world-vertex-format-census-v1':raise QueueError('wrong baseline census')
 if fmt45.get('format')!='t6-retail-world-formats-45-proof-v1':raise QueueError('wrong 4/5 proof')
 if registry.get('format')!='t6-world-vertex-format-registry-v1':raise QueueError('wrong registry')
 if absence.get('format')!='t6-retail-world-format-8-retained-absence-census-v1':raise QueueError('wrong absence census')
 maps=targets.get('maps',[])
 if len(maps)!=31:raise QueueError(f'expected 31 MP targets, got {len(maps)}')
 by_zone={str(x['zone']):x for x in maps}
 if len(by_zone)!=31:raise QueueError('duplicate MP target zones')
 cov=registry.get('coverage',{})
 if cov.get('exportEnabledFormats')!=list(range(8)) or cov.get('pendingFormats')!=[8]:raise QueueError(f'unexpected registry coverage {cov}')
 fmt8=registry['formats']['8']
 if fmt8.get('sourceClosedFamily',{}).get('vd1Stride')!=20 or fmt8.get('exportEnabled') is not False:raise QueueError('format 8 registry row is not pending stride20')
 if absence.get('xfileCount')!=18 or absence.get('format8StrongInlineHitCount')!=0:raise QueueError('retained absence census no longer closes at zero')
 audited={}
 for row in baseline.get('maps',[]):
  zone=str(row.get('map',''))
  if zone in by_zone:
   observed=sorted(int(x) for x in row.get('observedFormats',[]))
   if 8 in observed:raise QueueError(f'{zone}: baseline unexpectedly observes format8')
   audited[zone]={'zone':zone,'observedFormats':observed,'format8Observed':False,'proof':str(row.get('sourceReport','T6_WORLD_VERTEX_FORMAT_CENSUS_V1.json'))}
 for row in fmt45.get('maps',[]):
  zone=str(row.get('map',''))
  if zone in by_zone:
   observed=sorted(int(x) for x in row.get('groupFormatCounts',{}).keys())
   if 8 in observed:raise QueueError(f'{zone}: formats45 proof unexpectedly observes format8')
   audited[zone]={'zone':zone,'observedFormats':observed,'format8Observed':False,'proof':'manifests/world/T6_RETAIL_WORLD_FORMATS_45_PROOF_V1.json'}
 expected_audited={'mp_nuketown_2020','mp_raid','mp_hijacked'}
 if set(audited)!=expected_audited:raise QueueError(f'audited MP set changed: {sorted(audited)}')
 scan_order=[]
 for zone in targets.get('scanOrder',[]):
  zone=str(zone)
  if zone not in by_zone:raise QueueError(f'scanOrder contains unknown zone {zone}')
  if zone not in audited:scan_order.append(zone)
 if len(scan_order)!=28 or len(set(scan_order))!=28:raise QueueError('remaining scan order must contain exactly 28 unique maps')
 pending=[]
 for zone in scan_order:
  src=by_zone[zone]
  pending.append({'zone':zone,'path':src['path'],'bytes':int(src['bytes']),'sha256':str(src['sha256'])})
 return {'format':'t6-retail-mp-format8-scan-queue-v1','targetFormat':8,'expectedVd1Stride':20,'targetMapCount':31,'auditedMapCount':3,'auditedMaps':[audited[z] for z in sorted(audited)],'pendingMapCount':28,'scanOrder':scan_order,'pendingMaps':pending,'retainedContext':{'uniqueXFilesCensused':18,'strongInlineTechniqueSetsCensused':int(absence['strongInlineTechniqueSetCount']),'format8StrongInlineHits':0,'absenceManifest':'manifests/world/T6_RETAIL_WORLD_FORMAT_8_RETAINED_ABSENCE_CENSUS_V1.json'},'closureCondition':'Promote format 8 only from a clean direct/material-bound or standalone raw retail allocation with stride 20 and zero contradictory clean evidence, or from an exhaustive absence proof across the complete hash-pinned MP + Zombies target corpus.','proofBoundary':'The 28 pending MP identities are acquisition/scan targets, not evidence that any of them uses format 8. No map is prioritized by guessed visual complexity.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--targets',type=Path,required=True);ap.add_argument('--baseline',type=Path,required=True);ap.add_argument('--formats45-proof',type=Path,required=True);ap.add_argument('--registry',type=Path,required=True);ap.add_argument('--absence',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(load(a.targets),load(a.baseline),load(a.formats45_proof),load(a.registry),load(a.absence));a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({'audited':d['auditedMapCount'],'pending':d['pendingMapCount'],'targetFormat':8,'expectedStride':20},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())

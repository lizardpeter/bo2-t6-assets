#!/usr/bin/env python3
"""Build deterministic per-LOD hash index for source-derived Nuketown static XModel GLBs."""
import argparse, hashlib, json
from pathlib import Path
EXPECTED_EXPANDED='7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--extraction-manifest',type=Path,required=True);ap.add_argument('--model-root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 src=json.loads(a.extraction_manifest.read_text()); models=src.get('models',[])
 if len(models)!=349:raise SystemExit(f'expected 349 source static models, got {len(models)}')
 source_sha=((src.get('source') or {}).get('expandedSha256') or (src.get('source') or {}).get('sha256') or EXPECTED_EXPANDED)
 if source_sha!=EXPECTED_EXPANDED:raise SystemExit(f'expanded source mismatch: {source_sha}')
 out={'format':'t6-nuketown-fresh-static-model-index-v1','sourceExpandedSha256':EXPECTED_EXPANDED,'modelsExported':349,'models':[]}
 seen=set()
 for m in models:
  xa=int(m['xassetIndex']);stem=str(m['fileStem'])
  if xa in seen:raise SystemExit(f'duplicate xasset {xa}')
  seen.add(xa); files=[]
  for lod in m.get('lods',[]):
   i=int(lod['index']); rel=f'{stem}/{stem}_lod{i}.glb';p=a.model_root/rel
   if not p.is_file():raise SystemExit(f'missing {p}')
   b=p.read_bytes();files.append({'lod':i,'file':rel,'bytes':len(b),'sha256':sha(b)})
  if not any(int(x['lod'])==0 for x in files):raise SystemExit(f'xasset {xa}: missing lod0')
  out['models'].append({'xassetIndex':xa,'modelName':m.get('modelName'),'fileStem':stem,'files':files})
 a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({'modelsExported':349,'bytes':a.out.stat().st_size,'sha256':sha(a.out.read_bytes())},indent=2))
if __name__=='__main__':main()

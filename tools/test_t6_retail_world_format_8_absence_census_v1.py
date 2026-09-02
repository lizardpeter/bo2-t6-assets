#!/usr/bin/env python3
"""Regression for retained format-8 strong-inline absence census."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, tempfile
from pathlib import Path
EXPECTED_DIST={'0':1059,'1':78,'2':54,'3':46,'4':52,'5':26,'6':9,'7':8}
EXPECTED_SHA='d84280894a06796be90390a1f80bbbe9cb4be1ae2d002a938bc0938dd03a7bca'

def validate(d):
 assert d['format']=='t6-retail-world-format-8-retained-absence-census-v1'
 assert d['xfileCount']==18
 assert d['strongInlineTechniqueSetCount']==1332
 assert d['formatDistribution']==EXPECTED_DIST
 assert d['format8StrongInlineHitCount']==0 and d['format8StrongInlineHits']==[]
 assert len(d['xfiles'])==18
 assert all(x['format8Hits']==[] for x in d['xfiles'])
 assert len({x['expandedSha256'] for x in d['xfiles']})==18
 assert sum(x['strongInlineTechniqueSetCount'] for x in d['xfiles'])==1332

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/world/T6_RETAIL_WORLD_FORMAT_8_RETAINED_ABSENCE_CENSUS_V1.json'));ap.add_argument('--tool',type=Path,default=Path('tools/t6_retail_world_format_8_absence_census_v1.py'));ap.add_argument('--root',type=Path);a=ap.parse_args()
 raw=a.manifest.read_bytes();d=json.loads(raw);validate(d)
 assert hashlib.sha256(raw).hexdigest()==EXPECTED_SHA
 if a.root:
  with tempfile.TemporaryDirectory() as td:
   out=Path(td)/'rerun.json';subprocess.run([sys.executable,str(a.tool),'--root',str(a.root),'--out',str(out)],check=True);validate(json.loads(out.read_text()));assert out.read_bytes()==raw
 print('PASS: T6 retained format 8 absence census regression');return 0
if __name__=='__main__':raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path

def load(p:Path):
 s=importlib.util.spec_from_file_location('base',p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

def compact(d):
 s=d['summary']
 ancestry=d.get('normalNamedResourceAncestry')
 if ancestry is not None:
  resource_summary={'resourceNames':sorted({x['resourceName'] for x in ancestry}),
                    'sampleOpcodes':sorted({x['opcode'] for x in ancestry}),
                    'resourceRowCount':len(ancestry),
                    'resourcePatternCount':len(d.get('normalNamedResourcePatterns',[]))}
 else:resource_summary=d['normalNamedResourceSummary']
 alternates=d.get('alternateShaderRows',d.get('alternateShaderExamples',[]))
 return {'format':'t6-retail-reflection-probe-tangent-basis-normal-archive-v1',
         'producer':'tools/t6_retail_reflection_probe_tangent_basis_normal_archive_v1.py',
         'sources':d['sources'],'equations':d['equations'],
         'normalNamedResourceSummary':resource_summary,
         'standardShaderExamples':d['standardShaderExamples'][:2],
         'alternateShaderExamples':alternates[:3],
         'forensicDigests':{'allStandardShaderRowsSha256':s['shaderRowsSha256'],
                            'allAlternateShaderRowsSha256':s['alternateShaderRowsSha256'],
                            'allNormalResourceRowsSha256':s['normalResourceRowsSha256'],
                            'allNormalResourcePatternRowsSha256':s['normalResourcePatternRowsSha256']},
         'mapCoverage':d['mapCoverage'],'summary':s,
         'proofBoundary':d['proofBoundary']+' This archival wrapper intentionally omits the full forensic row arrays while retaining their deterministic SHA-256 digests; the exhaustive verifier remains tools/t6_retail_reflection_probe_tangent_basis_normal_v1.py.'}

def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--base-verifier',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
 for n in ('coordinate-verifier','weight-verifier','shared-verifier','surface-verifier','guard','mip-verifier','angular-verifier','semantic-verifier'):a.add_argument('--'+n,type=Path,required=True)
 q=a.parse_args();m=load(q.base_verifier);d=m.build(q.root,q.coordinate_verifier,q.weight_verifier,q.shared_verifier,q.surface_verifier,q.guard,q.mip_verifier,q.angular_verifier,q.semantic_verifier);o=compact(d);q.out.write_text(json.dumps(o,indent=2,sort_keys=True)+'\n');print(json.dumps(o['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()

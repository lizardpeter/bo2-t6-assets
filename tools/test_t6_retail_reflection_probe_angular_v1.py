#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
EXPECTED_SUMMARY={
 'retainedMapCount':5,'uniqueReflectionProbeShaderCount':5868,'reflectionCubeFetchCount':5888,
 'angularLinkedFetchCount':5682,'angularUnlinkedFetchCount':206,'sharedNormalizedPairCheckCount':5682,
 'sharedNormalizedPairFailureCount':0,'angularDp3SatCount':5682,'angularNegatedSecondOperandCount':5682,
 'angularMinus9Point28MulCount':5682,'angularExp2Count':5682,'angularMinCount':5682,
 'angularFactorShapeCount':5,'angularFactorShapeCounts':[4216,1386,40,20,20],
 'shaderRowsSha256':'a0e843474cf8f46a143551d327791fae2fff989adffb40a02b14f666ff377df1',
 'shapeRowsSha256':'6dba1ef84e88d9201946b7f478fe1ad22d29dfb137aaf3da2d3cada6148789b0',
 'shapeMipRowsSha256':'b343fe54e69a99863fde23ccba7b4b481a4ea2fa03238afda9eb1f2f60649348',
 'mipLinkRowsSha256':'42cf8c52470f2cf0bedcc8ade337984bed0b13c07791dbc5d50c15c4945543fe',
 'factorRootRowsSha256':'a6b4794666c18d0b8368bd3c48c8c5bf541a2cadc04b350224084f65c99abac8'}
EXPECTED_SHAPES={
 '68a3ca1b0207a8012c0f9dd8760eadcfa328f1768d61dc5240b3b2adfaa2e8d2':4216,
 '6cc8241a5800cd915304f8b6e96d16f98c0fdd49af25fc5d0a9d2315710bcbc4':1386,
 '009b5f1e5e328b5114948177fbfbe1cfcdd00a50c734ec72857651d0a8beb4ba':40,
 '4ca15be8491c8e7d22704ac528608cdc6eac6d61fa2efc8ea32540369c7a772b':20,
 'db3563b44bdd270cd3a1a63db4a9c0da5a1b3a94f3f2d138dc0dd9b40db40bdb':20}
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
def validate(d):
 assert d['format']=='t6-retail-reflection-probe-angular-v1'
 assert d['summary']==EXPECTED_SUMMARY
 assert d['angularCore']['D']=='saturate(dot(U, -V))'
 assert d['angularCore']['E']=='2^(-9.28 * D)'
 assert d['angularCore']['C']=='min(E, P)'
 assert d['angularCore']['minus9Point28Bits']=='c1147ae1'
 assert {x['shapeSha256']:x['count'] for x in d['angularFactorShapes']}==EXPECTED_SHAPES
 assert len(d['angularFactorShapes'])==5 and len(d['shapeMipCrossTab'])==6
 assert sum(x['count'] for x in d['shapeMipCrossTab'])==5682
 assert sum(x['count'] for x in d['mipLinkCrossTab'] if x['linkage']=='linked')==5682
 assert sum(x['count'] for x in d['mipLinkCrossTab'] if x['linkage']=='unlinked')==206
 assert sum(x['count'] for x in d['factorRootCounts'])==5888
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=Path('manifests/render/T6_RETAIL_REFLECTION_PROBE_ANGULAR_V1.json'))
 ap.add_argument('--verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_angular_v1.py'))
 ap.add_argument('--coordinate-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_coordinate_v1.py'))
 ap.add_argument('--mip-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_mip_v1.py'))
 ap.add_argument('--weight-verifier',type=Path,default=Path('tools/t6_retail_reflection_probe_weight_v1.py'))
 ap.add_argument('--guard',type=Path,default=Path('tools/t6_retail_lightmap_secondary_rdef_guard_v1.py'));ap.add_argument('--root',type=Path);a=ap.parse_args();d=json.loads(a.manifest.read_text());validate(d)
 if a.root:
  got=load(a.verifier,'angular').build(a.root,a.coordinate_verifier,a.mip_verifier,a.weight_verifier,a.guard);validate(got);assert got==d,'retail rerun differs from committed reflection angular manifest'
 print('PASS: T6 retained reflectionProbeSampler angular/material coupling regression')
if __name__=='__main__':main()

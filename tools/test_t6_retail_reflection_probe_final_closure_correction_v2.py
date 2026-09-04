#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent

def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m
sphere=load(HERE/'t6_retail_reflection_probe_sphere_elec_tc2_tc0_physical_closure_v2.py','sphere2')
driver=load(HERE/'t6_retail_reflection_probe_final_closure_driver_v2.py','driver2')

# Only exact normalized TC2/TC0 pixel family rows are eligible for the named sphere bank.
assert sphere.target_role(((('TEXCOORD',2),'xyz'),(('TEXCOORD',0),'xyz')))
assert not sphere.target_role(((('TEXCOORD',1),'xyz'),(('TEXCOORD',0),'xyz')))
assert not sphere.target_role(((('TEMP_OP50',0),'xyz'),(('TEXCOORD',0),'xyz')))
assert not sphere.target_role(((('TEXCOORD',2),'xy'),(('TEXCOORD',0),'xyz')))

# The corrected driver must invoke v2, with none of the old shifted-TBN dependency CLI.
rows=driver.build_commands(Path('/repo'),Path('/corpus'),Path('/out'))
sp=[x for x in rows if x[0]=='spherePhysical']
assert len(sp)==1
cmd=sp[0][1]
assert cmd[1].endswith('t6_retail_reflection_probe_sphere_elec_tc2_tc0_physical_closure_v2.py')
assert '--tangent-verifier' not in cmd and '--closure-verifier' not in cmd and '--shifted-verifier' not in cmd

ledger=json.loads((ROOT/'manifests/render/T6_RETAIL_REFLECTION_PROBE_CLOSURE_LEDGER_V2.json').read_text())
parts=ledger['preTempComponentBaseline']['components']
assert [x['closedFetchCount'] for x in parts]==[4086,995,616,11,54,22,24]
assert sum(x['closedFetchCount'] for x in parts)==5808==ledger['preTempComponentBaseline']['sumCheck']
assert ledger['tempComponentProof']['closedFetchCount']==15
assert ledger['measuredClosure']['closedFetchCount']==5823
assert ledger['measuredClosure']['remainingFetchCount']==65
u={x['family']:x['remainingFetchCount'] for x in ledger['unresolvedFamilies']}
assert u=={'TEXCOORD2/TEXCOORD1':21,'TEXCOORD3/TEXCOORD1':20,'TEXCOORD2/TEXCOORD0':24}
assert ledger['conditionalBoundary']['ifAllPendingFamiliesPass']['closedFetchCount']==5888
print('final reflection closure correction v2 regression: OK')

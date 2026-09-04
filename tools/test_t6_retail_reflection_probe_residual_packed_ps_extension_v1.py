#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

m=load(HERE/'t6_retail_reflection_probe_residual_packed_ps_extension_v1.py','residual')

# Direct identity must win without consulting aliases.
h='a'*64
assert m.resolved_ps_hash(('sha',h),{})==(h,['direct'])

# Packed PS identity is accepted only from an exact structural anchor.
p=('ptr','zm_tomb',5,1234)
assert m.resolved_ps_hash(p,{p:h})==(h,['crossMapPassKey'])
assert m.resolved_ps_hash(p,{})==(None,[])
assert m.resolved_ps_hash(None,{})==(None,[])

# Physical family dispatch is exact; do not silently reuse one semantic verifier.
class Base:
 def prove_vs(self,blob):return ('tc2',blob)
class Broad:
 def prove_vs_tc3(self,base,blob):return ('tc3',blob)
b=Base();q=Broad()
assert m.prove_family_vs('TEXCOORD2/TEXCOORD1',b,q,b'x')==('tc2',b'x')
assert m.prove_family_vs('TEXCOORD3/TEXCOORD1',b,q,b'y')==('tc3',b'y')
try:m.prove_family_vs('TEXCOORD9/TEXCOORD9',b,q,b'z')
except ValueError:pass
else:raise AssertionError('unknown family did not fail closed')

# Closure ledger must keep reproduced TEMP15 and conditional sphere closure separate.
ledger=json.loads((ROOT/'manifests/render/T6_RETAIL_REFLECTION_PROBE_CLOSURE_LEDGER_V1.json').read_text())
assert ledger['totalFetchCount']==5888
assert ledger['closureAccounting']['preTempComponentClosedFetchCount']==5808
assert ledger['closureAccounting']['tempComponentClosedFetchCount']==15
assert ledger['closureAccounting']['sumCheck']==5823
assert ledger['measuredClosure']['closedFetchCount']==5823
assert ledger['measuredClosure']['remainingFetchCount']==65
cond=ledger['conditionalNextBoundary']['ifSphereElectricGatePasses']
assert cond['closedFetchCount']==5847 and cond['remainingFetchCount']==41
assert cond['remainingFamilies']=={'TEXCOORD2/TEXCOORD1':21,'TEXCOORD3/TEXCOORD1':20}

assert m.EXPECTED_TC2_GLOBAL-m.EXPECTED_TC2_PRIOR_MAPPED==21
assert m.EXPECTED_TC3_GLOBAL-m.EXPECTED_TC3_PRIOR_MAPPED==20
assert m.EXPECTED_STRUCTURAL_PS_ANCHORS==76
print('residual packed-PS extension synthetic regression: OK')

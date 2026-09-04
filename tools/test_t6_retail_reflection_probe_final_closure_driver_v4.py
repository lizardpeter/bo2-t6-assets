#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parent

def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m);return m

d=load(HERE/'t6_retail_reflection_probe_final_closure_driver_v4.py','driver4')
c=load(HERE/'t6_retail_reflection_probe_residual_target_census_v1.py','targets')
repo=Path('/repo');root=Path('/corpus');out=Path('/out')
rows=d.build_commands(repo,root,out)
names=[x[0] for x in rows]
assert names.count('residualTargets')==1
assert names.index('residualTargets')<names.index('residualExact')<names.index('residualDifferential')
by={x[0]:x for x in rows}
assert by['sphereOwner'][1][1].endswith('t6_retail_reflection_probe_sphere_elec_packed_ps_probe_v2.py')
assert by['spherePairedVs'][1][1].endswith('t6_retail_reflection_probe_sphere_elec_paired_vs_probe_v2.py')
assert by['spherePhysical'][1][1].endswith('t6_retail_reflection_probe_sphere_elec_tc2_tc0_physical_closure_v2.py')
assert by['residualExact'][1][1].endswith('t6_retail_reflection_probe_residual_packed_ps_extension_v2.py')
assert by['residualDifferential'][1][1].endswith('t6_retail_reflection_probe_residual_packed_ps_differential_v2.py')
assert '--structural-extension' in by['residualDifferential'][1]
i=by['residualDifferential'][1].index('--structural-extension')
assert by['residualDifferential'][1][i+1].endswith('t6_retail_reflection_probe_residual_packed_ps_extension_v2.py')
assert by['residualTargets'][2].name=='T6_RETAIL_REFLECTION_PROBE_RESIDUAL_TARGET_CENSUS_V1.json'
assert c.TC2_COUNT==75 and c.TC3_COUNT==42
assert c.TC2_GLOBAL_ROWS_SHA256=='0d088b939b586ee46c7d69f7728046e0c377e12627f2883eba2786d25de5e5f3'
assert c.TC2_SHADER_SET_SHA256=='be9e44e06742a56170b91ce5f94173fee63c3fbc8c91aaf690cf712b2f8cc0a0'
assert c.TC3_GLOBAL_ROWS_SHA256=='cf865119d342260faae59ebd964fadcfe6ad40cfb6280e28fe5a4f3c19cb59a4'
# Validate target-stage acceptance/rejection without corpus.
good={'summary':{'tc2Texcoord1ShaderCount':75,'tc3Texcoord1ShaderCount':42,'combinedShaderCount':117,'tc2Texcoord1ShaderSetSha256':c.TC2_SHADER_SET_SHA256,'tc2Texcoord1GlobalRowsSha256':c.TC2_GLOBAL_ROWS_SHA256,'tc3Texcoord1GlobalRowsSha256':c.TC3_GLOBAL_ROWS_SHA256}}
d.validate_target_stage(good)
bad={'summary':dict(good['summary'],combinedShaderCount=116)}
try:d.validate_target_stage(bad)
except ValueError:pass
else:raise AssertionError('bad residual target census accepted')
print('final closure driver v4 routing regression: OK')

#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
from pathlib import Path

P=Path(__file__).with_name('t6_retail_reflection_probe_final_closure_driver_v1.py')
s=importlib.util.spec_from_file_location('m',P);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m)

families=['TEXCOORD2/TEXCOORD1','TEXCOORD3/TEXCOORD1']

def exact(tc2=(),tc3=()):
 return {'families':{
  families[0]:{'rows':[{'pixelShaderSha256':h,'allOwnerOccurrencesProven':True} for h in tc2]},
  families[1]:{'rows':[{'pixelShaderSha256':h,'allOwnerOccurrencesProven':True} for h in tc3]},
 }}
def diff(tc2=(),tc3=()):
 rows=[]
 for fam,vals in ((families[0],tc2),(families[1],tc3)):
  if vals:rows.append({'family':fam,'candidateSets':[{'shaderSha256':list(vals)}]})
 return {'promotedClusters':rows}

# Baseline if no pending stage passes.
a=m.account({}, {})
assert a['closedFetchCount']==5808 and a['remainingFetchCount']==80
assert a['unclosedPendingFamilies']=={
 'TEMP_COMPONENT':15,'SPHERE_ELECTRIC':24,
 'TEXCOORD2/TEXCOORD1':21,'TEXCOORD3/TEXCOORD1':20}

# Measured handoff boundary: TEMP15 passes, sphere and 41 residuals do not.
data={'temp15':{'summary':{'targetFetchCount':15}}}
ok={'temp15':True}
a=m.account(data,ok)
assert a['closedFetchCount']==5823 and a['remainingFetchCount']==65

# Conditional sphere boundary.
data['spherePhysical']={'summary':{'promotionApproved':True,'promotedShaderCount':24}}
ok['spherePhysical']=True
a=m.account(data,ok)
assert a['closedFetchCount']==5847 and a['remainingFetchCount']==41

# Mixed exact + differential residual promotion is additive only when SHA-disjoint.
data.update({
 'residualExact':exact(tc2=['a','b'],tc3=['c']),
 'residualDifferential':diff(tc2=['d','e','f'],tc3=['g','h'])})
ok.update({'residualExact':True,'residualDifferential':True})
a=m.account(data,ok)
assert a['residualFamilyPromotedFetchCount']==8
assert a['closedFetchCount']==5855 and a['remainingFetchCount']==33
assert a['residualFamilies'][families[0]]['remainingCount']==16
assert a['residualFamilies'][families[1]]['remainingCount']==17

# Exact/differential overlap must be fatal, never double-counted.
bad=dict(data);bad['residualDifferential']=diff(tc2=['a'],tc3=[])
try:m.account(bad,ok)
except ValueError:pass
else:raise AssertionError('exact/differential overlap was double-counted')

# Full closure arithmetic reaches 5,888 exactly.
full=dict(data)
full['residualExact']=exact(
 tc2=[f'a{i}' for i in range(11)],
 tc3=[f'b{i}' for i in range(10)])
full['residualDifferential']=diff(
 tc2=[f'c{i}' for i in range(10)],
 tc3=[f'd{i}' for i in range(10)])
a=m.account(full,ok)
assert a['closedFetchCount']==5888 and a['remainingFetchCount']==0 and a['closureComplete']

# A successful stage with a wrong internal count is rejected.
try:m.account({'temp15':{'summary':{'targetFetchCount':14}}},{'temp15':True})
except ValueError:pass
else:raise AssertionError('wrong TEMP15 target count accepted')
print('final reflection closure driver accounting regression: OK')

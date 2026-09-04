#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
from pathlib import Path

P=Path(__file__).with_name('t6_retail_reflection_probe_residual_packed_ps_differential_v1.py')
s=importlib.util.spec_from_file_location('m',P);m=importlib.util.module_from_spec(s);assert s.loader;s.loader.exec_module(m)

# Complete relative-spacing comparison, not absolute offset comparison.
assert m.max_spacing_residual([100,200,300],[1000,1102,1201])==2
assert m.max_spacing_residual([500,600],[9000,9100])==0
try:m.max_spacing_residual([1],[10])
except ValueError:pass
else:raise AssertionError('single-pointer spacing accepted')

objs=[
 {'sha256':'a','fixedStart':1000},
 {'sha256':'b','fixedStart':1102},
 {'sha256':'c','fixedStart':1201},
 {'sha256':'d','fixedStart':1600},
]
q=m.matching_object_sets([100,200,300],objs,3)
assert len(q)==1 and q[0]['shaderSha256']==['a','b','c'] and q[0]['maxDifferentialResidualBytes']==2
assert m.matching_object_sets([100],objs,99)==[]

# A second equally plausible whole set must remain ambiguous rather than selecting
# whichever combination appears first.
objs2=objs+[
 {'sha256':'e','fixedStart':2000},
 {'sha256':'f','fixedStart':2101},
 {'sha256':'g','fixedStart':2200},
]
q2=m.matching_object_sets([100,200,300],objs2,3)
sets={tuple(x['shaderSha256']) for x in q2}
assert ('a','b','c') in sets and ('e','f','g') in sets and len(q2)>=2

class Owner:
 @staticmethod
 def choose_unique_object_position(rows,sha):
  p=sorted({x['fixedStart'] for x in rows if x['sha256']==sha})
  return p[0] if len(p)==1 else None
struct={
 ('ptr','zm_tomb',5,100):'a',
 ('ptr','zm_tomb',5,200):'b',
 ('ptr','zm_tomb',5,300):'c',
}
direct={'zm_tomb':[
 {'sha256':'a','fixedStart':1100},
 {'sha256':'b','fixedStart':1202},
 {'sha256':'c','fixedStart':1301},
]}
cr=m.calibration_rows(Owner,struct,direct)
cb=m.calibration_bounds(cr)
assert cb[('zm_tomb',5)]['controlCount']==3
assert cb[('zm_tomb',5)]['pairwiseCount']==3
assert cb[('zm_tomb',5)]['maxPairwiseDifferentialDriftBytes']==2

# Duplicate direct object identity is not a valid unique calibration control.
direct2={'zm_tomb':direct['zm_tomb']+[{'sha256':'a','fixedStart':9999}]}
cr2=m.calibration_rows(Owner,struct,direct2)
assert len(cr2)==2 and all(x['sha256']!='a' for x in cr2)
print('residual packed-PS differential synthetic regression: OK')

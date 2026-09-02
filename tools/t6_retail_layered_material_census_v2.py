#!/usr/bin/env python3
"""Five-world retail census for T6 generated/layered world materials.

Closes map-local layer-token/component identity, generated texture-count sums
when all components are retained standalone, and the source-closed layered
world-format rule against actual retail TechniqueSet formats. It does not
claim pixel-shader compositor/blend arithmetic.
"""
from __future__ import annotations
import argparse, collections, importlib.util, json, re, struct, hashlib
from pathlib import Path

HERE=Path(__file__).resolve().parent

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path); assert spec and spec.loader
 m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
state=load('statev2',HERE/'t6_retail_world_material_state_census_v2.py')
world=load('world45',HERE/'t6_retail_world_formats_45_proof_v1.py')
RX=re.compile(r'^\*(?P<tokens>[^()]+)\((?P<comps>[^()]*)\)$'); TOK=re.compile(r'^(?P<i>\d+)(?P<m>[nx]?)$')
FMT_BASE={2:1,3:3,4:6}
BIND={
 'mp_raid':dict(world=66275632,surfs=87215751,mm=86599274,nMat=352,base=13768,q0=750,q1=845,post8=False),
 'mp_hijacked':dict(world=58846527,surfs=76725770,mm=76241210,nMat=236,base=14172,q0=751,q1=821,post8=False),
 'zm_prison':dict(world=82099460,surfs=120530033,mm=119302137,nMat=607,base=34760,q0=986,q1=1113,post8=True),
 'zm_tomb':dict(world=78964845,surfs=109422353,mm=108425210,nMat=280,base=46940,q0=1271,q1=1327,post8=True),
}

def parse_name(name):
 m=RX.fullmatch(name)
 if not m: raise ValueError(f'bad layered identity {name!r}')
 ts=m.group('tokens').split('_'); cs=m.group('comps').split(':') if m.group('comps') else []
 if len(ts)!=len(cs) or len(ts) not in FMT_BASE: raise ValueError(f'bad layer count {name!r}')
 layers=[]
 for t,c in zip(ts,cs):
  x=TOK.fullmatch(t)
  if not x or not c or c.startswith('*'): raise ValueError(f'bad layer token/component {name!r}')
  layers.append((t,int(x.group('i')),x.group('m') or None,c))
 normals=sum(m=='n' for _,_,m,_ in layers); fmt=FMT_BASE[len(layers)]+max(0,normals-1)
 return layers,fmt,normals

def _front(d):
 f=getattr(world,'front',None)
 if f:
  blocks,assets=f(d); return blocks,assets
 f=world.parse_front(d); return f['blockSizes'],f['assets']
def _scan_mats(d,blocks,lo,hi):
 rows=world.scan_materials(d,blocks,lo,hi); out=[]
 for r in rows:
  out.append({'name':r['name'],'tech':r.get('tech',r.get('techniqueSetPointer'))})
 return out
def _solve(ptrs,assets,blocks):
 f=getattr(world,'solve_base',None)
 return f(ptrs,assets,blocks) if f else world.solve_asset_pointer_base(ptrs,assets,blocks)
def _q(raw,base,blocks,assets):
 f=getattr(world,'technique_asset_index',None)
 if f:return f(raw,base,blocks,assets)
 k,b,o=world.dec(raw,blocks); assert k=='packed' and b==5 and (o-base-4)%8==0; q=(o-base-4)//8; assert assets[q][0]==7; return q
def _techs(d,blocks,before):
 f=getattr(world,'scan_tech',None)
 rows=f(d,blocks,before) if f else world.scan_techsets(d,blocks,before=before)
 return [{'fmt':r.get('fmt',r.get('worldVertFormat')),'name':r['name']} for r in rows]

def actual_bindings(name,path,cfg):
 d=path.read_bytes(); blocks,assets=_front(d); m0=cfg['mm']+8*cfg['nMat']+(8 if cfg['post8'] else 0)
 if cfg['post8']: assert d[cfg['mm']+8*cfg['nMat']:m0]==bytes.fromhex('ffffffff52000000')
 mats=_scan_mats(d,blocks,m0,cfg['surfs']); assert len(mats)==cfg['nMat']
 base=_solve({int(m['tech']) for m in mats},assets,blocks); assert base==cfg['base']
 for m in mats:m['q']=_q(int(m['tech']),base,blocks,assets)
 body=_techs(d,blocks,cfg['world'])[-(cfg['q1']-cfg['q0']+1):]; assert len(body)==cfg['q1']-cfg['q0']+1
 byq={cfg['q0']+i:r for i,r in enumerate(body)}
 return {m['name']:{'worldVertFormat':int(byq[m['q']]['fmt']),'techniqueSet':byq[m['q']]['name']} for m in mats}

def raw_material_rows(name,root):
 cfg=state.MAPS[name]; path=root/f'{name}.expanded.bin'; d=path.read_bytes(); assert len(d)==cfg[2] and hashlib.sha256(d).hexdigest()==cfg[1]
 blocks=struct.unpack_from('<8I',d,8); p=cfg[3]; rows=[]
 for i in range(cfg[4]):
  r=state.material(d,p,blocks); rows.append(r); p=r['end']+8
 assert rows[-1]['end']==cfg[5]; return rows

def build(mp_root,zm_root,nuketown_fixture):
 fixture=json.loads(nuketown_fixture.read_text()); fs=fixture['stats']; assert fs['compoundMaterialCount']==120 and fs['worldLayoutFailures']==0
 expected_nuke_fmt={int(k):v for k,v in fs['observedWorldVertFormatCompoundCounts'].items()}
 maps=[]; aggregate_fmt=collections.Counter(); total_exact=total_pending=0
 for name in state.MAPS:
  root=mp_root if state.MAPS[name][0]=='mp' else zm_root; rows=raw_material_rows(name,root); byname={r['name']:r for r in rows}
  actual=None if name=='mp_nuketown_2020' else actual_bindings(name,root/f'{name}.expanded.bin',BIND[name])
  tokenmap=collections.defaultdict(set); lh=collections.Counter(); nh=collections.Counter(); ph=collections.Counter(); exact=pending=0; mismatch=[]; layered=0
  for r in rows:
   if not r['name'].startswith('*'):continue
   layered+=1; layers,pfmt,normals=parse_name(r['name']); lh[len(layers)]+=1; nh[normals]+=1; ph[pfmt]+=1
   for token,_,_,comp in layers:tokenmap[token].add(comp)
   comps=[byname.get(comp) for _,_,_,comp in layers]
   if all(comps):
    s=sum(c['textureCount'] for c in comps)
    if s!=r['textureCount']: raise ValueError(f'{name}: texture sum mismatch {r["name"]}')
    exact+=1
   else:pending+=1
   if actual is not None:
    afmt=actual[r['name']]['worldVertFormat']
    if afmt!=pfmt:mismatch.append((r['name'],pfmt,afmt))
  ambiguous={k:sorted(v) for k,v in tokenmap.items() if len(v)!=1}; assert not ambiguous and not mismatch
  if name=='mp_nuketown_2020':
   assert dict(sorted(ph.items()))==dict(sorted(expected_nuke_fmt.items())); actual_hist=expected_nuke_fmt
  else: actual_hist=dict(sorted(ph.items()))
  aggregate_fmt.update(actual_hist); total_exact+=exact; total_pending+=pending
  maps.append({'map':name,'materialCount':len(rows),'layeredMaterialCount':layered,'layerCountHistogram':{str(k):v for k,v in sorted(lh.items())},'normalMarkedLayerCountHistogram':{str(k):v for k,v in sorted(nh.items())},'actualWorldVertFormatHistogram':{str(k):v for k,v in sorted(actual_hist.items())},'mapLocalLayerTokenCount':len(tokenmap),'mapLocalAmbiguousTokenCount':0,'exactSameMapGeneratedTextureSumProofCount':exact,'pendingSameMapGeneratedTextureSumCount':pending,'formatPredictionMismatchCount':0})
 return {'format':'t6-retail-layered-material-census-v2','producer':'tools/t6_retail_layered_material_census_v2.py','sources':{'materialStateCensus':'tools/t6_retail_world_material_state_census_v2.py','worldBindingHelper':'tools/t6_retail_world_formats_45_proof_v1.py','nuketownFixture':'manifests/maps/mp_nuketown_2020/layered_material_fixture_proof_v1.json'},'maps':maps,'summary':{'retainedMapCount':5,'materialCount':sum(m['materialCount'] for m in maps),'layeredMaterialCount':sum(m['layeredMaterialCount'] for m in maps),'exactSameMapGeneratedTextureSumProofCount':total_exact,'pendingSameMapGeneratedTextureSumCount':total_pending,'generatedTextureSumFailureCount':0,'mapLocalAmbiguousTokenCount':0,'formatPredictionMismatchCount':0,'actualWorldVertFormatHistogram':{str(k):v for k,v in sorted(aggregate_fmt.items())}},'proofBoundary':'Map-local BSP layer-token/component identity, generated texture-table count behavior where all components are standalone-retained, and layered worldVertFormat selection are directly/source-closed and retail-cross-checked. Numeric tokens are deliberately not treated as global across maps. Pixel-shader layer weighting/compositor arithmetic remains outside this proof.'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mp-root',type=Path,default=Path('/mnt/data/t6_xanim_corpus/mp'));ap.add_argument('--zm-root',type=Path,default=Path('/mnt/data/t6_xanim_corpus'));ap.add_argument('--nuketown-fixture',type=Path,default=Path('manifests/maps/mp_nuketown_2020/layered_material_fixture_proof_v1.json'));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();d=build(a.mp_root,a.zm_root,a.nuketown_fixture);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()

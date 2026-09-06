#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, copy, hashlib, json, struct, zlib
from pathlib import Path

M_PER_T6=0.0254
FORMAT='t6-nuketown-static-scene-rebuild-v2'
EXPECTED_EXPANDED='7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505'
EXPECTED_COEFF='cb78afcf9fd6abd008b2beeb56eedc355885bd681b384f92b261152c8eebb1e5'
EXPECTED_LIGHTING_JSON='99c6aa39f00e216b037f22019d3e11fc7d008f7a3af9ee965b71d25eb7fc0de7'
class RebuildError(RuntimeError):pass

def sha(b):return hashlib.sha256(b).hexdigest()
def read_glb(p):
 b=p.read_bytes(); magic,ver,total=struct.unpack_from('<4sII',b,0)
 if magic!=b'glTF' or ver!=2 or total!=len(b):raise RebuildError(f'{p}: invalid GLB2')
 o=12; js=None; bins=[]
 while o<total:
  n,t=struct.unpack_from('<I4s',b,o);o+=8;c=b[o:o+n];o+=n
  if t==b'JSON':js=json.loads(c)
  elif t==b'BIN\0':bins.append(c)
 if js is None or len(bins)!=1:raise RebuildError(f'{p}: expected one JSON/BIN')
 return js,bins[0]
def align4(b):
 while len(b)&3:b.append(0)
def write_glb(p,js,binbuf):
 align4(binbuf);js['buffers']=[{'byteLength':len(binbuf)}]
 jb=json.dumps(js,separators=(',',':'),ensure_ascii=False).encode();jb+=b' '*((-len(jb))&3)
 total=12+8+len(jb)+8+len(binbuf);out=bytearray(struct.pack('<4sII',b'glTF',2,total));out+=struct.pack('<I4s',len(jb),b'JSON')+jb;out+=struct.pack('<I4s',len(binbuf),b'BIN\0')+binbuf;p.write_bytes(out);return bytes(out)
def mm(a,b):return [[sum(a[r][k]*b[k][c] for k in range(3)) for c in range(3)] for r in range(3)]
def tr(a):return [[a[c][r] for c in range(3)] for r in range(3)]
C=[[1.,0.,0.],[0.,0.,1.],[0.,-1.,0.]];CI=[[1.,0.,0.],[0.,0.,-1.],[0.,1.,0.]]
def placement_matrix(inst):
 a=[[float(x) for x in row] for row in inst['axis']];r=mm(mm(C,tr(a)),CI);s=float(inst['scale']);r=[[x*s for x in row] for row in r];x,y,z=map(float,inst['origin']);tx,ty,tz=x*M_PER_T6,z*M_PER_T6,-y*M_PER_T6
 return [r[0][0],r[1][0],r[2][0],0.,r[0][1],r[1][1],r[2][1],0.,r[0][2],r[1][2],r[2][2],0.,tx,ty,tz,1.]
def load_lighting(path):
 stored=path.read_bytes();raw=zlib.decompress(base64.b64decode(stored))
 if sha(raw)!=EXPECTED_LIGHTING_JSON:raise RebuildError(f'lighting JSON SHA mismatch {sha(raw)}')
 j=json.loads(raw)
 if j.get('format')!='t6-nuketown-static-lighting-sh-v1' or len(j.get('staticLighting',[]))!=2992:raise RebuildError('bad static lighting manifest')
 if j['source']['expandedSha256']!=EXPECTED_EXPANDED or j['source']['coefficientPayloadSha256']!=EXPECTED_COEFF:raise RebuildError('lighting source identity mismatch')
 by={int(x['staticIndex']):x for x in j['staticLighting']}
 if len(by)!=2992:raise RebuildError('duplicate static lighting indices')
 return by,sha(stored),sha(raw)
def build(placements_path,model_root,index_path,lighting_path):
 placements=json.loads(placements_path.read_text());index=json.loads(index_path.read_text());lighting,lighting_stored_sha,lighting_json_sha=load_lighting(lighting_path)
 if len(placements.get('instances',[]))!=2992:raise RebuildError('expected 2992 placements')
 if int(index.get('modelsExported',-1))!=349 or index.get('sourceExpandedSha256')!=EXPECTED_EXPANDED:raise RebuildError('bad fresh model index')
 idx={int(m['xassetIndex']):m for m in index['models']}
 if len(idx)!=349:raise RebuildError('duplicate model xasset')
 js={'asset':{'version':'2.0','generator':'t6_nuketown_static_scene_rebuild_v2.py'},'scene':0,'scenes':[],'nodes':[],'meshes':[],'materials':[],'buffers':[{'byteLength':0}],'bufferViews':[],'accessors':[],'extras':{'T6':{'staticSceneRebuildV2':{'format':FORMAT,'map':'mp_nuketown_2020','sourceExpandedSha256':EXPECTED_EXPANDED,'staticPlacementCountSerialized':2992,'staticModelCount':349,'coordinateConversion':'T6 (x,y,z) Z-up -> glTF (x,z,-y) Y-up','metersPerT6Unit':M_PER_T6,'lighting':{'contract':'exact retail PC coefficient decode -> GfxLightingSH','coefficientPayloadSha256':EXPECTED_COEFF,'staticLightingJsonSha256':lighting_json_sha,'staticLightingStoredSha256':lighting_stored_sha,'staticLightingCount':2992},'policy':'fresh static source layer; no retained combined/full-map GLB used as geometry input'}}}}
 blob=bytearray();matcache={};mesh_by={}
 def mapmat(src):
  key=json.dumps(src,sort_keys=True,separators=(',',':'))
  if key in matcache:return matcache[key]
  i=len(js['materials']);matcache[key]=i;js['materials'].append(copy.deepcopy(src));return i
 for model in index['models']:
  xa=int(model['xassetIndex']);lod0=next((f for f in model.get('files',[]) if int(f.get('lod',-1))==0),None)
  if not lod0:raise RebuildError(f'xasset {xa}: no lod0')
  p=model_root/lod0['file'];pb=p.read_bytes()
  if sha(pb)!=lod0['sha256']:raise RebuildError(f'{p}: SHA mismatch')
  sj,sb=read_glb(p)
  if len(sj.get('meshes',[]))!=1:raise RebuildError(f'{p}: expected one mesh')
  bv0=len(js['bufferViews']);ac0=len(js['accessors']);align4(blob);bo=len(blob);blob.extend(sb)
  for v in sj.get('bufferViews',[]):
   nv=copy.deepcopy(v);nv['buffer']=0;nv['byteOffset']=bo+int(v.get('byteOffset',0));js['bufferViews'].append(nv)
  for a in sj.get('accessors',[]):
   na=copy.deepcopy(a);na['bufferView']=bv0+int(a['bufferView']);js['accessors'].append(na)
  nm=copy.deepcopy(sj['meshes'][0])
  for pr in nm.get('primitives',[]):
   pr['attributes']={k:ac0+int(v) for k,v in pr.get('attributes',{}).items()}
   if 'indices'in pr:pr['indices']=ac0+int(pr['indices'])
   if pr.get('material') is not None:pr['material']=mapmat(sj['materials'][int(pr['material'])])
  mesh_by[xa]=len(js['meshes']);js['meshes'].append(nm)
 js['nodes'].append({'name':'NUKETOWN_STATIC_XMODEL_PLACEMENTS_ARCHIVE','children':[],'extras':{'placementCount':2992,'uniqueXModels':349,'role':'full-archive','exactStaticLighting':True}})
 fx=[];coeff_indices=[];primary=[]
 for inst in placements['instances']:
  i=int(inst['index']);xa=int(inst['xassetIndex']);li=lighting.get(i)
  if xa not in idx or li is None:raise RebuildError(f'placement {i}: unresolved model/lighting')
  if int(li['colorsIndex'])!=int(inst['colorsIndex']) or int(li['primaryLightIndex'])!=int(inst['primaryLightIndex']) or int(li['visibility'])!=int(inst['visibility']):raise RebuildError(f'placement {i}: lighting join mismatch')
  name=inst.get('modelName') or f'xasset_{xa:04d}';shv=li['lightingSH']
  n={'name':f"static_{i:04d}__{str(name).replace('/','__')}",'mesh':mesh_by[xa],'matrix':placement_matrix(inst),'extras':{'staticModelInstanceIndex':i,'xassetIndex':xa,'modelName':name,'cullDistT6':float(inst.get('cullDist',0.0)),'smid':int(inst.get('smid',0)),'T6':{'colorsIndex':int(li['colorsIndex']),'primaryLightIndex':int(li['primaryLightIndex']),'visibility':int(li['visibility']),'gfxLightingSHV1':{'V0':shv['V0'],'V1':shv['V1'],'V2':shv['V2'],'float32Bits':shv['float32Bits']}}}}
  ni=len(js['nodes']);js['nodes'].append(n);js['nodes'][0]['children'].append(ni);coeff_indices.append(int(li['colorsIndex']));primary.append(int(li['primaryLightIndex']))
  if str(name).lower().startswith('fxanim_'):fx.append(i)
 if len(set(coeff_indices))!=2992:raise RebuildError('static coefficient indices lost uniqueness')
 js['scenes']=[{'name':'NUKETOWN_STATIC_ARCHIVE','nodes':[0],'extras':{'role':'archive','placementCount':2992,'exactStaticLighting':True}}]
 js['extras']['T6']['staticSceneRebuildV2'].update({'fxanimPlacementIndices':fx,'uniqueStaticCoefficientIndices':len(set(coeff_indices)),'primaryLight1StaticCount':sum(x==1 for x in primary)})
 return js,blob
def counts(js):
 prims=sum(len(m.get('primitives',[])) for m in js['meshes']);tris=sum(int(js['accessors'][p['indices']]['count'])//3 for m in js['meshes'] for p in m.get('primitives',[]) if isinstance(p.get('indices'),int))
 return {'meshCount':len(js['meshes']),'materialCount':len(js['materials']),'nodeCount':len(js['nodes']),'placementCount':len(js['nodes'][0]['children']),'primitiveDefinitions':prims,'triangleDefinitions':tris,'nodesWithExactStaticLighting':sum(1 for n in js['nodes'][1:] if n.get('extras',{}).get('T6',{}).get('gfxLightingSHV1'))}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--placements',type=Path,required=True);ap.add_argument('--model-root',type=Path,required=True);ap.add_argument('--index',type=Path,required=True);ap.add_argument('--lighting',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);a=ap.parse_args();js,blob=build(a.placements,a.model_root,a.index,a.lighting);out=write_glb(a.out,js,blob);m={'format':FORMAT,'output':{'file':a.out.name,'bytes':len(out),'sha256':sha(out)},'stats':counts(js),'source':{'placements':a.placements.name,'modelIndex':a.index.name,'lighting':a.lighting.name,'sourceExpandedSha256':EXPECTED_EXPANDED,'coefficientPayloadSha256':EXPECTED_COEFF},'validation':{'all349Lod0GlbHashesMatched':True,'all2992PlacementXassetsResolved':True,'all2992StaticLightingRecordsJoined':True,'uniqueStaticCoefficientIndices':2992,'oldCombinedGlbUsedAsGeometryInput':False}};a.manifest.write_text(json.dumps(m,indent=2,sort_keys=True)+'\n');print(json.dumps(m,indent=2,sort_keys=True))
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Normalize a retail T6 ClipMap walk into stable collision-domain JSON.

Owned serialized arrays are decoded to named fields where the T6 PC32 layout is
proven. Packed/reusable pointers that target other zone allocations remain explicit
dependencies instead of being guessed or flattened.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
from t6_clipmap_serialized_walker import ptr_kind
from t6_clipmap_serialized_walker_v3 import Walker

def sh(data): return hashlib.sha256(data).hexdigest()
def f3(d,o): return list(struct.unpack_from('<3f',d,o))
def f4(d,o): return list(struct.unpack_from('<4f',d,o))
def u32(d,o): return struct.unpack_from('<I',d,o)[0]
def i32(d,o): return struct.unpack_from('<i',d,o)[0]
def u16(d,o): return struct.unpack_from('<H',d,o)[0]
def i16(d,o): return struct.unpack_from('<h',d,o)[0]

def secmap(walk): return {s['name']:s for s in walk['sections']}

def decode_leaf(d,b):
 return {'firstCollAabbIndex':u16(d,b),'collAabbCount':u16(d,b+2),'brushContents':i32(d,b+4),'terrainContents':i32(d,b+8),'mins':f3(d,b+12),'maxs':f3(d,b+24),'leafBrushNode':i32(d,b+36),'cluster':i16(d,b+40)}

def normalize(data,start):
 walk=Walker(data,start).walk()
 if walk['blockers']: raise RuntimeError(f"walker blockers: {walk['blockers'][:3]}")
 s=secmap(walk); h=walk['header']; ci=h['info']
 out={'format':'t6-clipmap-normalized-v1','source':{'fixedStart':start,'serializedEnd':walk['assetSerializedEnd'],'serializedBytes':walk['assetSerializedBytes'],'serializedSha256':walk['assetSerializedSha256']},'counts':{},'dependencies':{},'materials':[],'brushSides':[],'leafBrushNodes':[],'brushVertices':[],'uinds':[],'brushes':[],'bspNodes':[],'bspLeaves':[],'terrain':{},'partitions':[],'aabbTrees':[],'subModels':[],'dynEntDefs':[],'constraints':{'count':h['num_constraints']},'mapEnts':walk['mapEnts'],'unexpandedSections':{}}
 out['counts']={k:ci[k] for k in ['planeCount','numMaterials','numBrushSides','leafbrushNodesCount','numLeafBrushes','numBrushVerts','nuinds','numBrushes']}
 out['counts'].update({k:h[k] for k in ['numStaticModels','numNodes','numLeafs','vertCount','triCount','partitionCount','aabbTreeCount','numSubModels','numClusters','clusterBytes','dynEntCount','num_constraints','max_ropes']})
 # Explicit cross-asset/reusable dependencies.
 for k in ['planes','leafbrushes']:
  p=ci['pointers'][k]
  if p['kind']=='packed': out['dependencies'][f'clipMap.info.{k}']={'pointer':p,'count':ci['planeCount' if k=='planes' else 'numLeafBrushes'],'status':'unresolved_cross_asset_or_reusable_virtual_block'}
 # ClipMaterial: name pointer + surfaceFlags + contents.
 ms=s.get('clipMap.info.materials.fixed')
 if ms:
  names={}
  for x in walk['sections']:
   if x['name'].startswith('clipMap.info.materials[') and x['name'].endswith('].name'): names[int(x['name'].split('[')[1].split(']')[0])]=x.get('text')
  for i in range(ci['numMaterials']):
   b=ms['start']+i*12
   out['materials'].append({'index':i,'name':names.get(i),'namePointer':ptr_kind(u32(data,b)),'surfaceFlags':i32(data,b+4),'contents':i32(data,b+8)})
 # Brush sides: T6 cbrushside_t = plane pointer + cflags + sflags.
 bs=s.get('clipMap.info.brushsides.fixed')
 if bs:
  for i in range(ci['numBrushSides']):
   b=bs['start']+i*12
   out['brushSides'].append({'index':i,'planePointer':ptr_kind(u32(data,b)),'cflags':i32(data,b+4),'sflags':i32(data,b+8)})
 # Leaf-brush nodes. Positive leafBrushCount selects the leaf pointer union; otherwise decode child split data.
 lbn=s.get('clipMap.info.leafbrushNodes.fixed')
 if lbn:
  nested_sections={x['name']:x for x in walk['sections'] if x['name'].startswith('clipMap.info.leafbrushNodes[') and x['name'].endswith('].brushes')}
  for i in range(ci['leafbrushNodesCount']):
   b=lbn['start']+20*i
   leaf_count=i16(data,b+2)
   node={'index':i,'axis':data[b],'leafBrushCount':leaf_count,'contents':i32(data,b+4)}
   if leaf_count>0:
    ptr=ptr_kind(u32(data,b+8))
    node['data']={'kind':'leaf','brushesPointer':ptr}
    sec=nested_sections.get(f'clipMap.info.leafbrushNodes[{i}].brushes')
    if sec:
     node['data']['brushes']=list(struct.unpack_from(f'<{leaf_count}H',data,sec['start']))
   else:
    node['data']={'kind':'children','dist':struct.unpack_from('<f',data,b+8)[0],'range':struct.unpack_from('<f',data,b+12)[0],'childOffset':list(struct.unpack_from('<2H',data,b+16))}
   out['leafBrushNodes'].append(node)
 # Global brush vertices + uinds.
 vv=s.get('clipMap.info.brushVerts')
 if vv: out['brushVertices']=[f3(data,vv['start']+12*i) for i in range(ci['numBrushVerts'])]
 us=s.get('clipMap.info.uinds')
 if us: out['uinds']=list(struct.unpack_from(f"<{ci['nuinds']}H",data,us['start']))
 # Brushes.
 br=s.get('clipMap.info.brushes.fixed')
 if br:
  for i in range(ci['numBrushes']):
   b=br['start']+96*i
   out['brushes'].append({'index':i,'mins':f3(data,b),'contents':i32(data,b+12),'maxs':f3(data,b+16),'numSides':u32(data,b+28),'sidesPointer':ptr_kind(u32(data,b+32)),'axialCFlags':list(struct.unpack_from('<6i',data,b+36)),'axialSFlags':list(struct.unpack_from('<6i',data,b+60)),'numVerts':u32(data,b+84),'vertsPointer':ptr_kind(u32(data,b+88))})
 # BSP nodes/leaves.
 ns=s.get('clipMap.nodes')
 if ns:
  for i in range(h['numNodes']):
   b=ns['start']+8*i; out['bspNodes'].append({'index':i,'planePointer':ptr_kind(u32(data,b)),'children':list(struct.unpack_from('<2h',data,b+4))})
 ls=s.get('clipMap.leafs')
 if ls: out['bspLeaves']=[dict(index=i,**decode_leaf(data,ls['start']+44*i)) for i in range(h['numLeafs'])]
 # Terrain collision.
 tv=s.get('clipMap.verts'); ti=s.get('clipMap.triIndices'); tw=s.get('clipMap.triEdgeIsWalkable')
 verts=[f3(data,tv['start']+12*i) for i in range(h['vertCount'])] if tv else []
 tris=[list(struct.unpack_from('<3H',data,ti['start']+6*i)) for i in range(h['triCount'])] if ti else []
 out['terrain']={'vertices':verts,'triangles':tris,'walkabilityBitset':{'bytes':tw['bytes'] if tw else 0,'sha256':sh(data[tw['start']:tw['end']]) if tw else None}}
 # Collision partitions. T6 layout: char triCount; pad[3]; int firstTri; int nuinds; int fuind.
 ps=s.get('clipMap.partitions')
 if ps:
  for i in range(h['partitionCount']):
   b=ps['start']+16*i
   out['partitions'].append({'index':i,'triCount':data[b],'firstTri':i32(data,b+4),'nuinds':i32(data,b+8),'fuind':i32(data,b+12)})
 # Collision AABB tree. T6 layout: vec3 origin; u16 materialIndex; u16 childCount; vec3 halfSize; union { firstChildIndex, partitionIndex }.
 ats=s.get('clipMap.aabbTrees')
 if ats:
  for i in range(h['aabbTreeCount']):
   b=ats['start']+32*i
   union_index=i32(data,b+28)
   child_count=u16(data,b+14)
   out['aabbTrees'].append({'index':i,'origin':f3(data,b),'materialIndex':u16(data,b+12),'childCount':child_count,'halfSize':f3(data,b+16),'indexUnion':{'raw':union_index,'firstChildIndex':union_index if child_count else None,'partitionIndex':union_index if child_count==0 else None}})
 # cmodel_t submodels.
 cm=s.get('clipMap.cmodels.fixed')
 if cm:
  for i in range(h['numSubModels']):
   b=cm['start']+76*i
   out['subModels'].append({'index':i,'mins':f3(data,b),'maxs':f3(data,b+12),'radius':struct.unpack_from('<f',data,b+24)[0],'infoPointer':ptr_kind(u32(data,b+28)),'leaf':decode_leaf(data,b+32)})
 # DynEntityDef list 0/1. Preserve all asset refs as zone pointers.
 for li in range(2):
  key=f'clipMap.dynEntDefList[{li}].fixed'; ds=s.get(key); count=h['dynEntCount'][li]
  if not ds: continue
  for i in range(count):
   b=ds['start']+84*i
   out['dynEntDefs'].append({'list':li,'index':i,'type':i32(data,b),'pose':{'quat':f4(data,b+4),'origin':f3(data,b+20)},'xModel':ptr_kind(u32(data,b+32)),'destroyedXModel':ptr_kind(u32(data,b+36)),'brushModel':u16(data,b+40),'physicsBrushModel':u16(data,b+42),'destroyFx':ptr_kind(u32(data,b+44)),'destroySound':u32(data,b+48),'destroyPieces':ptr_kind(u32(data,b+52)),'physPreset':ptr_kind(u32(data,b+56)),'physConstraints':list(struct.unpack_from('<4h',data,b+60)),'health':i32(data,b+68),'flags':u32(data,b+72),'contents':u32(data,b+76),'targetname':u16(data,b+80),'target':u16(data,b+82)})
 # Keep complex structures lossless in v1 with digest + location; field decode comes next.
 for name in ['clipMap.constraints.fixed','clipMap.staticModelList']:
  x=s.get(name)
  if x: out['unexpandedSections'][name]={'start':x['start'],'bytes':x['bytes'],'sha256':x['sha256']}
 out['normalizationStatus']={'decodedOwnedSections':['materials','brushSides','leafBrushNodes','brushVertices','uinds','brushes','bspNodes','bspLeaves','terrain','partitions','aabbTrees','subModels','dynEntDefs','mapEnts'],'unexpandedOwnedSections':sorted(out['unexpandedSections']),'unresolvedCrossAssetDependencies':sorted(out['dependencies']),'planePoolResolved':'clipMap.info.planes' not in out['dependencies'],'partitionAabbFieldsExpanded':True,'constraintFieldsExpanded':False,'losslessRawSectionDigestsPreserved':True}
 return out,walk

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('expanded',type=Path); ap.add_argument('--asset-start',type=lambda x:int(x,0),required=True); ap.add_argument('--out',type=Path,required=True); args=ap.parse_args(); data=args.expanded.read_bytes(); out,walk=normalize(data,args.asset_start); out['expandedSha256']=hashlib.sha256(data).hexdigest(); args.out.write_text(json.dumps(out,separators=(',',':'))+'\n'); print(json.dumps({'out':str(args.out),'bytes':args.out.stat().st_size,'serializedEnd':walk['assetSerializedEnd'],'counts':out['counts'],'dependencies':out['dependencies'],'status':out['normalizationStatus']},indent=2))
if __name__=='__main__': main()

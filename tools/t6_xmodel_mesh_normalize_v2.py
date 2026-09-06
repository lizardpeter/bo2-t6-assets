#!/usr/bin/env python3
"""Normalize inline or exact packed-name T6 PC32 XModel render surfaces into lossless mesh data.

v2 keeps v1 geometry semantics and additionally resolves packed VIRTUAL XModel names only through the proven StringTable logical mapping. It still fails closed on packed/reused surface data.
It supports the retail inline XSurface representation proven by the T6 XModel
walker, including:
- 32-byte GfxPackedVertex decode (xyz/color/half-float UV/packed normal/tangent)
- rigid XRigidVertList bone weights (boneOffset / sizeof(DObjSkelMat), 64 bytes)
- 1/2/3/4-bone vertsBlend encoding used by deformed surfaces
- 6-byte serialized XSurfaceTri16 triangles
- inline rigid collision-tree payload walking so source cursor stays exact

It does not decode/materialize Material assets; raw material pointer provenance is
preserved separately by the full XModel walker/sidecars.
"""
from __future__ import annotations
import argparse, hashlib, json, math, struct
from pathlib import Path

FOLLOWING=0xFFFFFFFF
INSERT=0xFFFFFFFE
XMODEL_FIXED=248
XMODEL_LOD_INFO=28
XSURFACE_FIXED=80
PACKED_VERTEX=32
RIGID_LIST=12
TREE_FIXED=40
TREE_NODE=16
TREE_LEAF=2
DOBJ_SKEL_MAT=64

class MeshError(RuntimeError): pass

def inline(p:int)->bool: return p in (FOLLOWING,INSERT)

def ptr_kind(p:int):
    if p==0: return {'raw':p,'rawHex':'0x00000000','kind':'null'}
    if p==FOLLOWING: return {'raw':p,'rawHex':'0xFFFFFFFF','kind':'following'}
    if p==INSERT: return {'raw':p,'rawHex':'0xFFFFFFFE','kind':'insert'}
    enc=(p-1)&0xffffffff
    return {'raw':p,'rawHex':f'0x{p:08X}','kind':'packed','block':enc>>29,'offset':enc&0x1fffffff}

def half(bits:int)->float:
    return struct.unpack('<e', struct.pack('<H',bits))[0]

def unpack_unit_third(p:int):
    out=[]
    for shift in (0,10,20):
        u=(p>>shift)&0x3ff
        u=(u - 2*(u&0x200) + 0x40400000)&0xffffffff
        f=struct.unpack('<f',struct.pack('<I',u))[0]
        out.append((f-3.0)*8208.0312)
    return out

def unpack_color(p:int): return [((p>>(8*i))&0xff)/255.0 for i in range(4)]
def unpack_uv(p:int): return [half(p&0xffff),half((p>>16)&0xffff)]

def sha(data,a,b): return hashlib.sha256(data[a:b]).hexdigest()

class Normalizer:
    def __init__(self,data:bytes,start:int,logical_to_text:dict[int,str]|None=None):
        self.data=data; self.start=start; self.pos=start; self.sections=[]; self.logical_to_text=logical_to_text
    def need(self,n,label):
        if self.pos+n>len(self.data): raise MeshError(f'{label}: out of bounds')
    def take(self,n,label,**meta):
        self.need(n,label); a=self.pos; self.pos+=n
        r={'name':label,'start':a,'end':self.pos,'bytes':n,'sha256':sha(self.data,a,self.pos)}; r.update(meta); self.sections.append(r); return a
    def u16(self,b,o): return struct.unpack_from('<H',self.data,b+o)[0]
    def i16(self,b,o): return struct.unpack_from('<h',self.data,b+o)[0]
    def u32(self,b,o): return struct.unpack_from('<I',self.data,b+o)[0]
    def walk_tree(self,label):
        b=self.take(TREE_FIXED,label+'.fixed')
        nc=self.u32(b,24); np=self.u32(b,28); lc=self.u32(b,32); lp=self.u32(b,36)
        if inline(np): self.take(nc*TREE_NODE,label+'.nodes',count=nc,recordBytes=TREE_NODE)
        elif np: raise MeshError(f'{label}: packed collision tree nodes not supported')
        if inline(lp): self.take(lc*TREE_LEAF,label+'.leafs',count=lc,recordBytes=TREE_LEAF)
        elif lp: raise MeshError(f'{label}: packed collision tree leafs not supported')
        return {'nodeCount':nc,'nodesPointer':ptr_kind(np),'leafCount':lc,'leafsPointer':ptr_kind(lp)}
    def decode_vertex(self,b):
        xyz=list(struct.unpack_from('<3f',self.data,b))
        if not all(math.isfinite(x) for x in xyz): raise MeshError(f'nonfinite vertex at {b}')
        binormal=struct.unpack_from('<f',self.data,b+12)[0]
        color=self.u32(b,16); uv=self.u32(b,20); normal=self.u32(b,24); tangent=self.u32(b,28)
        return {'position':xyz,'binormalSign':binormal,'colorRGBA':unpack_color(color),'texcoord0':unpack_uv(uv),
                'normal':unpack_unit_third(normal),'tangentXYZ':unpack_unit_third(tangent),
                'raw':{'color':f'0x{color:08X}','texcoord':f'0x{uv:08X}','normal':f'0x{normal:08X}','tangent':f'0x{tangent:08X}'}}
    def normalize(self):
        fixed=self.take(XMODEL_FIXED,'XModel.fixed')
        namep=self.u32(fixed,0); nb=self.data[fixed+4]; nr=self.data[fixed+5]; ns=self.data[fixed+6]; nl=self.u16(fixed,196)
        if inline(namep):
            e=self.data.index(b'\0',self.pos); name=self.data[self.pos:e].decode('latin1','replace'); self.take(e+1-self.pos,'XModel.name')
        else:
            np=ptr_kind(namep)
            if np.get('kind')!='packed' or np.get('block')!=5:
                raise MeshError(f'v2 requires inline or packed VIRTUAL XModel name; got {np}')
            if self.logical_to_text is None:
                raise MeshError('packed XModel name requires exact logical_to_text mapping')
            name=self.logical_to_text.get(int(np['offset']))
            if not isinstance(name,str) or not name:
                raise MeshError(f'packed XModel name VIRTUAL offset {np["offset"]} is not present in proven StringTable mapping')
            self.take(0,'XModel.name.packed',pointer=np,identity=name)
        # Skip inline skeleton arrays in serializer order. Fail on reuse to avoid source miswalk.
        for off,n,label in [(8,nb*2,'boneNames'),(12,(nb-nr),'parentList'),(16,(nb-nr)*8,'quats'),(20,(nb-nr)*16,'trans'),(24,nb,'partClassification'),(28,nb*32,'baseMat')]:
            p=self.u32(fixed,off)
            if inline(p): self.take(n,'XModel.'+label,count=(nb if label not in ('parentList','quats','trans') else nb-nr))
            elif p: raise MeshError(f'v1 requires inline {label}; got {ptr_kind(p)}')
        surfp=self.u32(fixed,32)
        if not inline(surfp): raise MeshError(f'v1 requires inline surfaces; got {ptr_kind(surfp)}')
        sfixed=self.take(ns*XSURFACE_FIXED,'XModel.surfs.fixed',count=ns,recordBytes=XSURFACE_FIXED)
        surfaces=[]
        for si in range(ns):
            b=sfixed+si*XSURFACE_FIXED
            tile=self.data[b]; rcount=self.data[b+1]; flags=self.u16(b,2); vc=self.u16(b,4); tc=self.u16(b,6); base=self.u16(b,8)
            trip=self.u32(b,12); blend_counts=[self.i16(b,16+2*i) for i in range(4)]; blendp=self.u32(b,24); tensionp=self.u32(b,28); vertp=self.u32(b,32); rigidp=self.u32(b,40)
            if any(x<0 for x in blend_counts): raise MeshError(f'surf{si}: negative blend counts')
            blend_words=blend_counts[0]+3*blend_counts[1]+5*blend_counts[2]+7*blend_counts[3]
            tension_count=sum(blend_counts)
            blend=[]
            if inline(blendp):
                a=self.take(blend_words*2,f'XModel.surfs[{si}].vertInfo.vertsBlend',count=blend_words,recordBytes=2)
                blend=list(struct.unpack_from('<'+'H'*blend_words,self.data,a))
            elif blendp: raise MeshError(f'surf{si}: packed vertsBlend unsupported')
            if inline(tensionp): self.take(tension_count*4,f'XModel.surfs[{si}].vertInfo.tensionData',count=tension_count,recordBytes=4)
            elif tensionp: raise MeshError(f'surf{si}: packed tension unsupported')
            if flags&1: raise MeshError(f'surf{si}: flags&1 has no inline verts0; unsupported in v1')
            if not inline(vertp): raise MeshError(f'surf{si}: verts0 not inline')
            va=self.take(vc*PACKED_VERTEX,f'XModel.surfs[{si}].verts0',count=vc,recordBytes=PACKED_VERTEX)
            vertices=[self.decode_vertex(va+i*PACKED_VERTEX) for i in range(vc)]
            rigid=[]
            if inline(rigidp):
                ra=self.take(rcount*RIGID_LIST,f'XModel.surfs[{si}].vertList.fixed',count=rcount,recordBytes=RIGID_LIST)
                for j in range(rcount):
                    rb=ra+j*RIGID_LIST; bo,vn,to,tn=struct.unpack_from('<4H',self.data,rb); treep=self.u32(rb,8)
                    if bo%DOBJ_SKEL_MAT: raise MeshError(f'surf{si} rigid{j}: boneOffset {bo} not multiple of {DOBJ_SKEL_MAT}')
                    joint=bo//DOBJ_SKEL_MAT
                    if joint>=nb: raise MeshError(f'surf{si} rigid{j}: joint {joint} >= {nb}')
                    row={'index':j,'boneOffset':bo,'joint':joint,'vertCount':vn,'triOffset':to,'triCount':tn,'collisionTreePointer':ptr_kind(treep)}
                    if inline(treep): row['collisionTree']=self.walk_tree(f'XModel.surfs[{si}].vertList[{j}].collisionTree')
                    elif treep: raise MeshError(f'surf{si} rigid{j}: packed collision tree unsupported')
                    rigid.append(row)
            elif rigidp: raise MeshError(f'surf{si}: packed rigid list unsupported')
            if not inline(trip): raise MeshError(f'surf{si}: triIndices not inline')
            ta=self.take(tc*6,f'XModel.surfs[{si}].triIndices',count=tc,recordBytes=6,nativeDestinationAlignment=16)
            triangles=[list(struct.unpack_from('<3H',self.data,ta+i*6)) for i in range(tc)]
            if any(max(t)>=vc for t in triangles): raise MeshError(f'surf{si}: triangle out of local range')
            # Weight assignment exactly follows OAT T6 converter: rigid vertices first, then blend buckets.
            joints=[]; weights=[]; handled=0
            for r in rigid:
                for _ in range(r['vertCount']): joints.append([r['joint'],0,0,0]); weights.append([1.0,0.0,0.0,0.0]); handled+=1
            o=0
            bucket_sizes=[1,3,5,7]
            for bucket,cnt in enumerate(blend_counts):
                for _ in range(cnt):
                    words=blend[o:o+bucket_sizes[bucket]]; o+=bucket_sizes[bucket]
                    if bucket==0: js=[words[0]//DOBJ_SKEL_MAT]; ws=[1.0]
                    else:
                        js=[words[0]//DOBJ_SKEL_MAT]; ws=[]
                        accum=0.0
                        for k in range(bucket):
                            ji=words[1+2*k]//DOBJ_SKEL_MAT; wi=words[2+2*k]/65535.0; js.append(ji); ws.append(wi); accum+=wi
                        ws=[1.0-accum]+ws
                    if any(j>=nb for j in js): raise MeshError(f'surf{si}: blend joint outside skeleton {js}')
                    if min(ws)<-1e-5 or abs(sum(ws)-1.0)>1e-5: raise MeshError(f'surf{si}: invalid weights {ws}')
                    joints.append((js+[0]*4)[:4]); weights.append((ws+[0.0]*4)[:4]); handled+=1
            if o!=len(blend): raise MeshError(f'surf{si}: blend words {o}!={len(blend)}')
            if handled>vc: raise MeshError(f'surf{si}: weighted vertices {handled}>{vc}')
            while handled<vc: joints.append([0,0,0,0]); weights.append([0.0,0.0,0.0,0.0]); handled+=1
            if sum(r['vertCount'] for r in rigid)+sum(blend_counts)!=vc:
                # T6 converter permits unweighted tail, retain it explicitly rather than fail.
                unweighted=vc-(sum(r['vertCount'] for r in rigid)+sum(blend_counts))
            else: unweighted=0
            surfaces.append({'index':si,'tileMode':tile,'flags':flags,'vertCount':vc,'triCount':tc,'baseVertIndex':base,
                             'blendCounts':blend_counts,'vertices':vertices,'triangles':triangles,'joints0':joints,'weights0':weights,
                             'rigidVertLists':rigid,'unweightedVertexCount':unweighted,
                             'pointers':{'verts0':ptr_kind(vertp),'vertList':ptr_kind(rigidp),'triIndices':ptr_kind(trip),'vertsBlend':ptr_kind(blendp)}})
        # LOD metadata lives in fixed header; 4 records x 28 bytes from +40.
        lods=[]
        for i in range(4):
            b=fixed+40+i*XMODEL_LOD_INFO
            lods.append({'index':i,'dist':struct.unpack_from('<f',self.data,b)[0],'numSurfs':self.u16(b,4),'surfIndex':self.u16(b,6),'partBits':[self.u32(b,8+4*k) for k in range(5)]})
        active=lods[:nl]
        for l in active:
            if l['surfIndex']+l['numSurfs']>ns: raise MeshError(f"LOD{l['index']} surface span out of range")
        span_start=self.start; span_end=self.pos
        return {'format':'t6-xmodel-mesh-normalized-v1','identity':{'name':name},'source':{'assetFixedStart':self.start,'meshOwnedSerializedEnd':span_end,
                'meshOwnedSerializedBytes':span_end-span_start,'meshOwnedSerializedSha256':sha(self.data,span_start,span_end)},
                'xmodel':{'numBones':nb,'numRootBones':nr,'numSurfs':ns,'numLods':nl,'lods':active},'surfaces':surfaces,'sections':self.sections,
                'validation':{'allLocalTriangleIndicesInRange':True,'DObjSkelMatBytes':DOBJ_SKEL_MAT,'sourceAlignmentPaddingBytes':0}}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('expanded',type=Path); ap.add_argument('--asset-start',required=True,type=lambda x:int(x,0)); ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args(); data=a.expanded.read_bytes()
    from t6_clipmap_normalize_v5 import parse_top_level_xasset_table
    from t6_clipmap_normalize_v6 import walk_map_prefix_stringtable
    table=parse_top_level_xasset_table(data); prefix=walk_map_prefix_stringtable(data,table)
    d=Normalizer(data,a.asset_start,logical_to_text=prefix['logicalToText']).normalize(); d['expandedSha256']=hashlib.sha256(data).hexdigest()
    text=json.dumps(d,indent=2,sort_keys=True)+'\n'; a.out.write_text(text,encoding='utf-8')
    print(json.dumps({'out':str(a.out),'bytes':len(text.encode()),'sha256':hashlib.sha256(text.encode()).hexdigest(),'name':d['identity']['name'],
                      'surfaces':len(d['surfaces']),'vertices':sum(s['vertCount'] for s in d['surfaces']),'triangles':sum(s['triCount'] for s in d['surfaces']),
                      'lod0':d['xmodel']['lods'][0] if d['xmodel']['lods'] else None},indent=2))
if __name__=='__main__': main()

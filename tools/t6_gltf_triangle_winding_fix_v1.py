#!/usr/bin/env python3
"""Fix T6 -> glTF triangle winding for glTF CCW front-face convention.

Recovered T6 world/XModel triangles use the opposite front-face winding from core glTF.
The historical exporter preserved T6 index order, so glTF consumers that honor CCW
front faces cull the intended exterior even though transformed vertex normals still
point in the correct direction.

This stage is map-agnostic. It validates the orientation using POSITION + NORMAL and
then swaps index 1/2 of each triangle. It never rotates geometry, changes normals,
or forces materials double-sided.
"""
from __future__ import annotations
import argparse, hashlib, json, math, struct
from pathlib import Path

CTYPE_FMT={5126:'f',5125:'I',5123:'H',5121:'B',5122:'h',5120:'b'}
TYPE_N={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}
INDEX_TYPES={5125:'I',5123:'H',5121:'B'}

def sha(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest()

def read_glb(path:Path):
    b=path.read_bytes(); magic,ver,total=struct.unpack_from('<4sII',b,0)
    if magic!=b'glTF' or ver!=2 or total!=len(b): raise ValueError('invalid GLB2')
    o=12; js=None; bins=[]
    while o<total:
        n,t=struct.unpack_from('<I4s',b,o);o+=8;c=b[o:o+n];o+=n
        if t==b'JSON': js=json.loads(c)
        elif t==b'BIN\0': bins.append(c)
    if js is None or len(bins)!=1: raise ValueError('expected one JSON and one BIN')
    return js,bytearray(bins[0])

def write_glb(path:Path,js,binbuf:bytearray):
    while len(binbuf)%4: binbuf.append(0)
    js['buffers'][0]['byteLength']=len(binbuf)
    jb=json.dumps(js,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    while len(jb)%4: jb+=b' '
    total=12+8+len(jb)+8+len(binbuf)
    out=bytearray(struct.pack('<4sII',b'glTF',2,total))
    out+=struct.pack('<I4s',len(jb),b'JSON')+jb
    out+=struct.pack('<I4s',len(binbuf),b'BIN\0')+binbuf
    path.write_bytes(out)

def accessor_offset_stride(js,ai):
    a=js['accessors'][ai]; bv=js['bufferViews'][a['bufferView']]
    nc=TYPE_N[a['type']]; fmt='<'+CTYPE_FMT[a['componentType']]*nc; sz=struct.calcsize(fmt)
    return bv.get('byteOffset',0)+a.get('byteOffset',0),bv.get('byteStride',sz),fmt,sz,a['count']

def read_accessor(js,binbuf,ai):
    off,stride,fmt,sz,count=accessor_offset_stride(js,ai)
    return [struct.unpack_from(fmt,binbuf,off+i*stride) for i in range(count)]

def vsub(a,b): return (a[0]-b[0],a[1]-b[1],a[2]-b[2])
def cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def dot(a,b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def norm(a): return math.sqrt(dot(a,a))

def orientation_stats(js,binbuf,max_triangles_per_primitive=64):
    signs=[]; primitive_rows=[]
    for mi,mesh in enumerate(js.get('meshes',[])):
        for pi,p in enumerate(mesh.get('primitives',[])):
            attrs=p.get('attributes') or {}
            if p.get('mode',4)!=4 or 'indices' not in p or 'POSITION' not in attrs or 'NORMAL' not in attrs: continue
            pos=read_accessor(js,binbuf,attrs['POSITION']); nrm=read_accessor(js,binbuf,attrs['NORMAL']); ind=[x[0] for x in read_accessor(js,binbuf,p['indices'])]
            if len(ind)%3: raise ValueError(f'mesh {mi} prim {pi}: triangle index count not divisible by 3')
            ds=[]
            step=max(1,(len(ind)//3)//max_triangles_per_primitive)
            for ti in range(0,len(ind)//3,step):
                i0,i1,i2=ind[3*ti:3*ti+3]
                c=cross(vsub(pos[i1],pos[i0]),vsub(pos[i2],pos[i0])); cn=norm(c)
                ns=(nrm[i0][0]+nrm[i1][0]+nrm[i2][0],nrm[i0][1]+nrm[i1][1]+nrm[i2][1],nrm[i0][2]+nrm[i1][2]+nrm[i2][2]); nn=norm(ns)
                if cn<1e-10 or nn<1e-10: continue
                d=dot(c,ns)/(cn*nn); ds.append(d); signs.append(d)
            if ds:
                ds2=sorted(ds); med=ds2[len(ds2)//2]
                primitive_rows.append({'meshIndex':mi,'primitiveIndex':pi,'sampleCount':len(ds),'medianNormalDot':med})
    if not signs: raise ValueError('no indexed triangle primitives with normals to validate')
    neg=sum(d<0 for d in signs); pos=sum(d>0 for d in signs)
    s=sorted(signs); med=s[len(s)//2]
    return {'sampleCount':len(signs),'negativeFraction':neg/len(signs),'positiveFraction':pos/len(signs),'medianNormalDot':med,'primitiveCount':len(primitive_rows)},primitive_rows

def flip_index_accessor(js,binbuf,ai):
    a=js['accessors'][ai]
    if a['type']!='SCALAR' or a['componentType'] not in INDEX_TYPES: raise ValueError(f'unsupported index accessor {ai}')
    count=a['count']
    if count%3: raise ValueError(f'index accessor {ai} count {count} not divisible by 3')
    bv=js['bufferViews'][a['bufferView']]
    fmt='<'+INDEX_TYPES[a['componentType']]; sz=struct.calcsize(fmt); stride=bv.get('byteStride',sz)
    if stride!=sz: raise ValueError(f'interleaved index accessor {ai} unsupported')
    off=bv.get('byteOffset',0)+a.get('byteOffset',0)
    for i in range(0,count,3):
        o1=off+(i+1)*sz; o2=off+(i+2)*sz
        v1=struct.unpack_from(fmt,binbuf,o1)[0]; v2=struct.unpack_from(fmt,binbuf,o2)[0]
        struct.pack_into(fmt,binbuf,o1,v2); struct.pack_into(fmt,binbuf,o2,v1)
    return count//3

def build(inp:Path,out:Path,manifest:Path):
    js,binbuf=read_glb(inp)
    before,_=orientation_stats(js,binbuf)
    if before['negativeFraction'] < 0.98 or before['medianNormalDot'] > -0.5:
        raise ValueError(f'input is not globally reverse-wound: {before}')
    used=[]; seen=set(); triangles=0
    for mesh in js.get('meshes',[]):
        for p in mesh.get('primitives',[]):
            if p.get('mode',4)!=4 or 'indices' not in p: continue
            ai=p['indices']
            if ai in seen: continue
            seen.add(ai); triangles+=flip_index_accessor(js,binbuf,ai); used.append(ai)
    js.setdefault('extras',{}).setdefault('T6',{})['triangleWindingFixV1']={
        'reason':'recovered T6 triangle order is opposite core glTF CCW front-face convention',
        'indexAccessorsFlipped':len(used),'trianglesFlipped':triangles,
        'inputOrientation':before,
        'proofBoundary':'indices only; positions, normals, tangents, UVs, transforms, materials and hierarchy unchanged'
    }
    write_glb(out,js,binbuf)
    js2,bin2=read_glb(out); after,_=orientation_stats(js2,bin2)
    if after['positiveFraction'] < 0.98 or after['medianNormalDot'] < 0.5:
        raise ValueError(f'orientation did not close after flip: {after}')
    if js2['buffers'][0]['byteLength']!=len(bin2): raise ValueError('buffer length mismatch')
    doc={'format':'t6-gltf-triangle-winding-fix-v1','input':{'file':inp.name,'bytes':inp.stat().st_size,'sha256':sha(inp)},
         'output':{'file':out.name,'bytes':out.stat().st_size,'sha256':sha(out)},
         'summary':{'indexAccessorsFlipped':len(used),'trianglesFlipped':triangles,'before':before,'after':after},
         'validation':{'beforeGloballyReversed':True,'afterMatchesVertexNormals':True,'glbReparse':'pass','bufferByteLengthMatches':'pass'},
         'proofBoundary':'Generic T6/glTF orientation repair. It reverses triangle index winding only after proving the input is globally opposite its own vertex normals.'}
    manifest.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')
    print(json.dumps(doc['summary'],indent=2)); print(json.dumps(doc['output'],indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--glb',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);a=ap.parse_args();build(a.glb,a.out,a.manifest)

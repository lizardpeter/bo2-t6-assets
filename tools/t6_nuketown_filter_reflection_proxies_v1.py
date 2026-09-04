#!/usr/bin/env python3
from __future__ import annotations
import argparse, collections, hashlib, json, math, struct
from pathlib import Path

CTYPE_FMT={5126:'f',5125:'I',5123:'H',5121:'B',5122:'h',5120:'b'}
TYPE_N={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}

def sha256_file(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read_glb(path:Path):
    b=path.read_bytes(); magic,ver,total=struct.unpack_from('<4sII',b,0)
    if magic!=b'glTF' or ver!=2 or total!=len(b): raise ValueError('invalid GLB')
    o=12; js=None; bins=[]
    while o<total:
        n,t=struct.unpack_from('<I4s',b,o);o+=8;c=b[o:o+n];o+=n
        if t==b'JSON': js=json.loads(c)
        elif t==b'BIN\0': bins.append(c)
    if js is None or len(bins)!=1: raise ValueError('expected one JSON and one BIN chunk')
    return js, bytearray(bins[0])

def write_glb(path:Path,js:dict,binbuf:bytearray):
    while len(binbuf)%4: binbuf.append(0)
    js['buffers'][0]['byteLength']=len(binbuf)
    jb=json.dumps(js,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    while len(jb)%4: jb+=b' '
    total=12+8+len(jb)+8+len(binbuf)
    out=bytearray(struct.pack('<4sII',b'glTF',2,total))
    out+=struct.pack('<I4s',len(jb),b'JSON')+jb
    out+=struct.pack('<I4s',len(binbuf),b'BIN\0')+binbuf
    path.write_bytes(out)

def read_accessor(js,binbuf,ai):
    a=js['accessors'][ai];bv=js['bufferViews'][a['bufferView']]
    fmt='<'+CTYPE_FMT[a['componentType']]*TYPE_N[a['type']];sz=struct.calcsize(fmt)
    off=bv.get('byteOffset',0)+a.get('byteOffset',0);stride=bv.get('byteStride',sz)
    return [struct.unpack_from(fmt,binbuf,off+i*stride) for i in range(a['count'])]

def core_horizontal_plane(js,binbuf,mesh_index=0):
    counts=collections.Counter()
    for pr in js['meshes'][mesh_index]['primitives']:
        pos=read_accessor(js,binbuf,pr['attributes']['POSITION'])
        ind=[x[0] for x in read_accessor(js,binbuf,pr['indices'])]
        for j in range(0,len(ind),3):
            a,b,c=[pos[ind[j+k]] for k in range(3)]
            if max(abs(a[1]-b[1]),abs(a[1]-c[1]),abs(b[1]-c[1]))<1e-5:
                counts[round((a[1]+b[1]+c[1])/3.0,4)]+=1
    if not counts: raise ValueError('no horizontal core triangles')
    plane,count=counts.most_common(1)[0]
    return plane,count,counts

def mesh_bounds(js):
    out=[]
    for mesh in js['meshes']:
        mn=[1e30]*3;mx=[-1e30]*3;ok=False
        for pr in mesh.get('primitives',[]):
            a=js['accessors'][pr['attributes']['POSITION']]
            if 'min' not in a or 'max' not in a: continue
            ok=True
            for k in range(3): mn[k]=min(mn[k],a['min'][k]);mx[k]=max(mx[k],a['max'][k])
        out.append((mn,mx) if ok else None)
    return out

def transform_point(m,p):
    x,y,z=p
    return (m[0]*x+m[4]*y+m[8]*z+m[12],
            m[1]*x+m[5]*y+m[9]*z+m[13],
            m[2]*x+m[6]*y+m[10]*z+m[14])

def world_y_bounds(node,mb):
    m=node['matrix'];mn,mx=mb[node['mesh']]
    ys=[transform_point(m,(x,y,z))[1]
        for x in (mn[0],mx[0]) for y in (mn[1],mx[1]) for z in (mn[2],mx[2])]
    return min(ys),max(ys),(min(ys)+max(ys))/2.0

def scale_norms(m):
    return [math.sqrt(m[c*4]**2+m[c*4+1]**2+m[c*4+2]**2) for c in range(3)]

def model_name(node_name):
    return node_name.split('__',1)[1] if '__' in node_name else node_name

def build(js,binbuf):
    plane,plane_triangles,plane_counts=core_horizontal_plane(js,binbuf,0)
    mb=mesh_bounds(js)
    rows=[]
    for i,n in enumerate(js.get('nodes',[])):
        if i<2 or 'matrix' not in n or n.get('mesh') is None: continue
        m=n['matrix']
        rows.append({
            'index':i,'node':n,'mesh':n['mesh'],'model':model_name(n.get('name','')),
            'x':m[12],'y':m[13],'z':m[14],'verticalBasis':m[5],
            'scale':scale_norms(m),'yBounds':world_y_bounds(n,mb)
        })
    bymesh=collections.defaultdict(list)
    for r in rows: bymesh[r['mesh']].append(r)

    proxy={}
    pair_rows=[]
    for mesh,rs in bymesh.items():
        for ia,a in enumerate(rs):
            for b in rs[ia+1:]:
                xz=math.hypot(a['x']-b['x'],a['z']-b['z'])
                if xz>0.20: continue
                if max(abs(a['scale'][k]-b['scale'][k]) for k in range(3))>0.03: continue
                midpoint=(a['y']+b['y'])/2.0
                if abs(midpoint-plane)>0.11: continue
                if a['verticalBasis']*b['verticalBasis']>=-0.2: continue
                residual=max(
                    abs(a['yBounds'][0]-(2*plane-b['yBounds'][1])),
                    abs(a['yBounds'][1]-(2*plane-b['yBounds'][0]))
                )
                if residual>0.20: continue
                if abs(a['yBounds'][2]-b['yBounds'][2])<1e-6:
                    low=a if a['verticalBasis']<b['verticalBasis'] else b
                    high=b if low is a else a
                else:
                    low=a if a['yBounds'][2]<b['yBounds'][2] else b
                    high=b if low is a else a
                evidence={
                    'kind':'same-mesh-planar-reflection-pair','proxyNode':low['index'],
                    'primaryNode':high['index'],'mesh':mesh,'model':low['model'],
                    'planeY':plane,'originMidpointY':midpoint,'horizontalOriginDistance':xz,
                    'mirroredBoundsResidual':residual,
                    'proxyYBounds':list(low['yBounds'][:2]),'primaryYBounds':list(high['yBounds'][:2]),
                    'proxyVerticalBasis':low['verticalBasis'],'primaryVerticalBasis':high['verticalBasis']
                }
                pair_rows.append(evidence)
                old=proxy.get(low['index'])
                if old is None or (residual,xz)<(old['mirroredBoundsResidual'],old['horizontalOriginDistance']):
                    proxy[low['index']]=evidence

    by_model=collections.defaultdict(list)
    for r in rows: by_model[r['model']].append(r)
    explicit=[]
    for r in rows:
        if '_reflection' not in r['model'].lower(): continue
        base=r['model'].replace('_reflection','')
        candidates=by_model.get(base,[])
        best=None
        for c in candidates:
            xz=math.hypot(r['x']-c['x'],r['z']-c['z'])
            midpoint=(r['y']+c['y'])/2.0
            if xz>0.20 or abs(midpoint-plane)>0.11: continue
            score=(abs(midpoint-plane),xz)
            if best is None or score<best[0]:best=(score,c,xz,midpoint)
        if best:
            _,c,xz,midpoint=best
            ev={'kind':'explicit-reflection-asset','proxyNode':r['index'],'primaryNode':c['index'],
                'proxyModel':r['model'],'primaryModel':c['model'],'planeY':plane,
                'originMidpointY':midpoint,'horizontalOriginDistance':xz,
                'proxyYBounds':list(r['yBounds'][:2]),'primaryYBounds':list(c['yBounds'][:2])}
        else:
            ev={'kind':'explicit-reflection-asset-name','proxyNode':r['index'],'primaryNode':None,
                'proxyModel':r['model'],'planeY':plane,'reason':'retail XModel name contains _reflection'}
        explicit.append(ev);proxy[r['index']]=ev

    parent=js['nodes'][1]
    children=parent.get('children',[])
    before=len(children)
    removed=[i for i in children if i in proxy]
    parent['children']=[i for i in children if i not in proxy]
    after=len(parent['children'])
    if before-after!=len(set(removed)): raise AssertionError('child removal mismatch')

    meta={
        'format':'t6-nuketown-reflection-proxy-filter-v1',
        'floorReflectionPlaneY':plane,'floorPlaneHorizontalTriangleCount':plane_triangles,
        'staticChildrenBefore':before,'staticChildrenAfter':after,
        'reflectionProxyNodesRemovedFromPrimaryScene':len(set(removed)),
        'sameMeshPairEvidenceCount':len([i for i in set(removed) if proxy[i]['kind']=='same-mesh-planar-reflection-pair']),
        'explicitReflectionAssetCount':len([i for i in set(removed) if proxy[i]['kind'].startswith('explicit-reflection')]),
        'note':'Proxy node definitions remain in the GLB for provenance but are unreachable from the primary scene graph. The unfiltered source GLB remains the full-fidelity archive artifact.'
    }
    js.setdefault('extras',{}).setdefault('T6',{})['reflectionProxyFilterV1']=meta
    return meta,[proxy[i] for i in sorted(set(removed))],pair_rows,plane_counts

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--in-glb',type=Path,required=True);ap.add_argument('--out-glb',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);a=ap.parse_args()
    js,binbuf=read_glb(a.in_glb);meta,removed,pairs,plane_counts=build(js,binbuf);write_glb(a.out_glb,js,binbuf)
    js2,bin2=read_glb(a.out_glb)
    if js2['buffers'][0]['byteLength']!=len(bin2): raise ValueError('buffer length mismatch')
    manifest={
        'format':'t6-nuketown-primary-scene-no-reflection-proxies-v1',
        'input':{'file':a.in_glb.name,'bytes':a.in_glb.stat().st_size,'sha256':sha256_file(a.in_glb)},
        'output':{'file':a.out_glb.name,'bytes':a.out_glb.stat().st_size,'sha256':sha256_file(a.out_glb)},
        'summary':meta,
        'topHorizontalCorePlanes':[{'y':y,'triangleCount':n} for y,n in plane_counts.most_common(10)],
        'removedProxyEvidence':removed,
        'validation':{'glbReparse':'pass','bufferByteLengthMatches':'pass','primaryStaticChildCount':len(js2['nodes'][1].get('children',[]))}
    }
    a.manifest.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps(meta,indent=2));print(manifest['output'])
if __name__=='__main__':main()

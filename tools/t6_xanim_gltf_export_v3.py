#!/usr/bin/env python3
"""Export retail T6 XModel mesh + skeleton + XAnim as self-contained glTF 2.0.

v3 adds actual render geometry and glTF skinning to the v2 animation export.
The normalized T6 mesh/skeleton/XAnim sidecars remain authoritative.

Coordinate strategy is unchanged:
- native T6 local mesh/bone/animation values are preserved;
- one wrapper rotates -90 degrees about X (Z-up -> glTF Y-up);
- one wrapper scale 0.0254 converts T6 inches to meters.

Inverse bind matrices are the inverse of XModel globalBaseMat transforms. This is
validated against the native hierarchy before export.
"""
from __future__ import annotations
import argparse, base64, json, math, struct
from pathlib import Path
from typing import Iterable

from t6_xanim_quaternion_semantics import augment_normalized_xanim, unit_xyzw
from t6_xanim_gltf_export_v2 import track_rotation, track_translation, delta_rotation, delta_translation

T6_UNIT_TO_METERS=0.0254
SQRT_HALF=math.sqrt(0.5)
T6_ZUP_TO_GLTF_YUP_XYZW=[-SQRT_HALF,0.0,0.0,SQRT_HALF]

class ExportError(RuntimeError): pass

class BufferBuilder:
    def __init__(self): self.data=bytearray(); self.views=[]; self.accessors=[]
    def align4(self):
        while len(self.data)%4:self.data.append(0)
    def add_raw(self,raw:bytes,*,component:int,count:int,type_name:str,name:str,minv=None,maxv=None):
        self.align4(); off=len(self.data);self.data.extend(raw);vi=len(self.views);self.views.append({'buffer':0,'byteOffset':off,'byteLength':len(raw),'name':name})
        a={'bufferView':vi,'componentType':component,'count':count,'type':type_name,'name':name}
        if minv is not None:a['min']=minv
        if maxv is not None:a['max']=maxv
        ai=len(self.accessors);self.accessors.append(a);return ai
    def f32(self,rows,*,type_name,name):
        comps={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[type_name]
        if type_name=='SCALAR': vals=[float(x) for x in rows];count=len(vals);nested=False
        else:
            if any(len(r)!=comps for r in rows):raise ExportError(f'{name}: malformed {type_name}')
            vals=[float(v) for r in rows for v in r];count=len(rows);nested=True
        if not all(math.isfinite(v) for v in vals):raise ExportError(f'{name}: nonfinite')
        minv=maxv=None
        if type_name=='SCALAR' and vals:minv=[min(vals)];maxv=[max(vals)]
        elif type_name=='VEC3' and rows:
            minv=[min(r[k] for r in rows) for k in range(3)];maxv=[max(r[k] for r in rows) for k in range(3)]
        return self.add_raw(struct.pack('<'+'f'*len(vals),*vals),component=5126,count=count,type_name=type_name,name=name,minv=minv,maxv=maxv)
    def u16(self,rows,*,type_name,name):
        comps={'SCALAR':1,'VEC4':4}[type_name]
        if type_name=='SCALAR': vals=[int(x) for x in rows];count=len(vals)
        else:
            if any(len(r)!=comps for r in rows):raise ExportError(f'{name}: malformed {type_name}')
            vals=[int(v) for r in rows for v in r];count=len(rows)
        if any(v<0 or v>65535 for v in vals):raise ExportError(f'{name}: u16 out of range')
        return self.add_raw(struct.pack('<'+'H'*len(vals),*vals),component=5123,count=count,type_name=type_name,name=name)

def qmul(a,b):
    ax,ay,az,aw=a;bx,by,bz,bw=b
    return [aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw,aw*bw-ax*bx-ay*by-az*bz]
def qrot(q,v):
    x,y,z,w=q;vx,vy,vz=v;tx=2*(y*vz-z*vy);ty=2*(z*vx-x*vz);tz=2*(x*vy-y*vx)
    return [vx+w*tx+y*tz-z*ty,vy+w*ty+z*tx-x*tz,vz+w*tz+x*ty-y*tx]
def qmat(q):
    x,y,z,w=unit_xyzw(q);xx=x*x;yy=y*y;zz=z*z;xy=x*y;xz=x*z;yz=y*z;wx=w*x;wy=w*y;wz=w*z
    return [[1-2*(yy+zz),2*(xy-wz),2*(xz+wy)],
            [2*(xy+wz),1-2*(xx+zz),2*(yz-wx)],
            [2*(xz-wy),2*(yz+wx),1-2*(xx+yy)]]
def inv_bind_matrix(q,t):
    R=qmat(q)
    # inverse rotation = transpose; inverse translation = -R^T t
    Rt=[[R[j][i] for j in range(3)] for i in range(3)]
    it=[-sum(Rt[i][j]*t[j] for j in range(3)) for i in range(3)]
    # glTF MAT4 is column-major
    return [Rt[0][0],Rt[1][0],Rt[2][0],0.0,
            Rt[0][1],Rt[1][1],Rt[2][1],0.0,
            Rt[0][2],Rt[1][2],Rt[2][2],0.0,
            it[0],it[1],it[2],1.0]
def mat4_mul(a,b):
    # column-major arrays
    out=[0.0]*16
    for c in range(4):
        for r in range(4):out[c*4+r]=sum(a[k*4+r]*b[c*4+k] for k in range(4))
    return out
def global_matrix(q,t):
    R=qmat(q)
    return [R[0][0],R[1][0],R[2][0],0,R[0][1],R[1][1],R[2][1],0,R[0][2],R[1][2],R[2][2],0,t[0],t[1],t[2],1]
def normalize3(v):
    n=math.sqrt(sum(x*x for x in v))
    if not math.isfinite(n) or n<=0:raise ExportError(f'invalid normal {v}')
    return [x/n for x in v]

def validate_bind_hierarchy(bones):
    mq=mt=0.0
    for b in bones:
        p=b.get('parentIndex');lq=b.get('localRotation',[0,0,0,1]);lt=b.get('localTranslation',[0,0,0]);gq=b['globalBaseMat']['quat'];gt=b['globalBaseMat']['trans']
        if p is None:pq=[0,0,0,1];pt=[0,0,0]
        else:pq=bones[int(p)]['globalBaseMat']['quat'];pt=bones[int(p)]['globalBaseMat']['trans']
        cq=qmul(pq,lq);rv=qrot(pq,lt);ct=[pt[i]+rv[i] for i in range(3)]
        qe=min(max(abs(cq[i]-gq[i]) for i in range(4)),max(abs(cq[i]+gq[i]) for i in range(4)));te=max(abs(ct[i]-gt[i]) for i in range(3));mq=max(mq,qe);mt=max(mt,te)
    if mq>2e-4 or mt>2e-3:raise ExportError(f'baseMat hierarchy mismatch q={mq} t={mt}')
    return {'maxQuaternionCompositionError':mq,'maxTranslationCompositionError':mt}

def export(mesh_doc,skeleton_doc,xanim_doc,lod=0):
    augment_normalized_xanim(xanim_doc)
    bones=skeleton_doc['skeleton']['bones'];tracks=xanim_doc.get('boneTracks',xanim_doc.get('tracks',[]));surfs=mesh_doc['surfaces']
    if mesh_doc['identity']['name']!=skeleton_doc['identity']['name']:raise ExportError('mesh/skeleton identity mismatch')
    bindcheck=validate_bind_hierarchy(bones)
    name_to_index={b['name']:int(b['index']) for b in bones}
    if len(name_to_index)!=len(bones):raise ExportError('duplicate bone names')
    bindings=[]
    for t in tracks:
        n=t['name']
        if n not in name_to_index:raise ExportError(f'animation track missing skeleton bone {n}')
        bi=name_to_index[n];sid=t.get('scriptString');bsid=bones[bi].get('scriptStringId')
        if sid is not None and bsid is not None and int(sid)!=int(bsid):raise ExportError(f'ScriptString mismatch {n}')
        bindings.append({'trackName':n,'boneIndex':bi,'scriptString':sid})
    lods=mesh_doc['xmodel']['lods'];lm=next((x for x in lods if x['index']==lod),None)
    if lm is None:raise ExportError(f'LOD{lod} unavailable')
    selected=surfs[lm['surfIndex']:lm['surfIndex']+lm['numSurfs']]
    # Skeleton nodes first, so joint indices map directly to glTF node indices.
    nodes=[]
    for b in bones:
        nodes.append({'name':b['name'],'translation':[float(x) for x in b['localTranslation']], 'rotation':unit_xyzw(b['localRotation']),
                      'extras':{'t6BoneIndex':b['index'],'scriptStringId':b.get('scriptStringId'),'partClassificationRaw':b.get('partClassificationRaw')}})
    roots=[];children={}
    for b in bones:
        i=int(b['index']);p=b.get('parentIndex')
        if p is None:roots.append(i)
        else:children.setdefault(int(p),[]).append(i)
    for p,ch in children.items():nodes[p]['children']=ch
    delta=xanim_doc.get('delta') or {};has_delta=bool(delta.get('trans') or delta.get('quat2') or delta.get('quat'))
    delta_node=None
    if has_delta:
        delta_node=len(nodes);nodes.append({'name':'__T6_DELTA_ROOT__','translation':[0,0,0],'rotation':[0,0,0,1],'children':list(roots),'extras':{'t6DeltaRoot':True}});parent_for_mesh=delta_node;wrapper_children=[delta_node]
    else:parent_for_mesh=None;wrapper_children=list(roots)
    buf=BufferBuilder();primitives=[]
    for s in selected:
        positions=[v['position'] for v in s['vertices']];normals=[normalize3(v['normal']) for v in s['vertices']];uv=[v['texcoord0'] for v in s['vertices']];colors=[v['colorRGBA'] for v in s['vertices']]
        joints=s['joints0'];weights=s['weights0'];indices=[i for tri in s['triangles'] for i in tri]
        if any(i>=len(positions) for i in indices):raise ExportError(f"surf{s['index']}: index out of range")
        for jrow,wrow in zip(joints,weights):
            if any(j>=len(bones) for j in jrow):raise ExportError('joint out of range')
            sm=sum(wrow)
            if abs(sm-1.0)>1e-5:raise ExportError(f'nonunit skin weights {wrow}')
        attrs={'POSITION':buf.f32(positions,type_name='VEC3',name=f"surf{s['index']}:POSITION"),
               'NORMAL':buf.f32(normals,type_name='VEC3',name=f"surf{s['index']}:NORMAL"),
               'TEXCOORD_0':buf.f32(uv,type_name='VEC2',name=f"surf{s['index']}:TEXCOORD_0"),
               'COLOR_0':buf.f32(colors,type_name='VEC4',name=f"surf{s['index']}:COLOR_0"),
               'JOINTS_0':buf.u16(joints,type_name='VEC4',name=f"surf{s['index']}:JOINTS_0"),
               'WEIGHTS_0':buf.f32(weights,type_name='VEC4',name=f"surf{s['index']}:WEIGHTS_0")}
        ia=buf.u16(indices,type_name='SCALAR',name=f"surf{s['index']}:INDICES")
        primitives.append({'attributes':attrs,'indices':ia,'mode':4,'extras':{'t6SurfaceIndex':s['index'],'baseVertIndex':s['baseVertIndex'],'tileMode':s['tileMode'],'flags':s['flags'],'rigidListCount':len(s['rigidVertLists'])}})
    mesh_index=0;meshes=[{'name':mesh_doc['identity']['name']+f'_lod{lod}','primitives':primitives,'extras':{'t6Lod':lod}}]
    ibms=[];max_ibm_error=0.0
    for b in bones:
        q=b['globalBaseMat']['quat'];t=b['globalBaseMat']['trans'];ibm=inv_bind_matrix(q,t);ibms.append(ibm)
        prod=mat4_mul(global_matrix(q,t),ibm);max_ibm_error=max(max_ibm_error,max(abs(prod[i]-(1.0 if i in (0,5,10,15) else 0.0)) for i in range(16)))
    if max_ibm_error>1e-5:raise ExportError(f'inverse bind validation error {max_ibm_error}')
    ibm_acc=buf.f32(ibms,type_name='MAT4',name='skin:inverseBindMatrices')
    skin={'joints':list(range(len(bones))),'inverseBindMatrices':ibm_acc,'name':mesh_doc['identity']['name']+'_skin'}
    if len(roots)==1:skin['skeleton']=roots[0]
    skins=[skin]
    mesh_node=len(nodes);nodes.append({'name':mesh_doc['identity']['name']+'_mesh','mesh':mesh_index,'skin':0,'extras':{'t6Lod':lod}})
    if parent_for_mesh is not None:nodes[parent_for_mesh].setdefault('children',[]).append(mesh_node)
    else:wrapper_children.append(mesh_node)
    wrapper=len(nodes);nodes.append({'name':'__T6_WORLD_TO_GLTF__','rotation':T6_ZUP_TO_GLTF_YUP_XYZW,'scale':[T6_UNIT_TO_METERS]*3,'children':wrapper_children,
                                     'extras':{'t6UnitMeters':T6_UNIT_TO_METERS,'axisConversion':'rotate -90deg X: T6 Z-up -> glTF Y-up'}})
    samplers=[];channels=[];fps=float(xanim_doc['header']['framerate'])
    def add_channel(node,path,times,values,type_name,extras):
        ia=buf.f32(times,type_name='SCALAR',name=f"{extras.get('trackName','delta')}:{path}:time");oa=buf.f32(values,type_name=type_name,name=f"{extras.get('trackName','delta')}:{path}:value")
        si=len(samplers);samplers.append({'input':ia,'output':oa,'interpolation':'LINEAR'});channels.append({'sampler':si,'target':{'node':node,'path':path},'extras':extras})
    for t in tracks:
        bi=name_to_index[t['name']];qr=track_rotation(t.get('quat') or {},fps,f"{t['name']} rotation")
        if qr:add_channel(bi,'rotation',qr[0],qr[1],'VEC4',{'trackName':t['name'],'t6TrackType':qr[2],'scriptString':t.get('scriptString')})
        tr=track_translation(t.get('trans') or {},fps,f"{t['name']} translation")
        if tr:add_channel(bi,'translation',tr[0],tr[1],'VEC3',{'trackName':t['name'],'t6TrackType':tr[2],'scriptString':t.get('scriptString')})
    if delta_node is not None:
        qr=delta_rotation(delta,fps)
        if qr:add_channel(delta_node,'rotation',qr[0],qr[1],'VEC4',{'trackName':'__T6_DELTA_ROOT__','t6DeltaType':qr[2]})
        tr=delta_translation(delta,fps)
        if tr:add_channel(delta_node,'translation',tr[0],tr[1],'VEC3',{'trackName':'__T6_DELTA_ROOT__','t6DeltaType':tr[2]})
    duration=max((a.get('max',[0])[0] for a in buf.accessors if a['type']=='SCALAR' and ':time' in a.get('name','')),default=0)
    gltf={'asset':{'version':'2.0','generator':'bo2-t6-assets t6_xanim_gltf_export_v3.py'},'scene':0,'scenes':[{'name':xanim_doc.get('name','T6 Animated XModel'),'nodes':[wrapper]}],
          'nodes':nodes,'meshes':meshes,'skins':skins,'animations':[{'name':xanim_doc.get('name'),'samplers':samplers,'channels':channels,
          'extras':{'T6':{'xanimName':xanim_doc.get('name'),'xmodelName':mesh_doc['identity']['name'],'lod':lod,'notifies':xanim_doc.get('notifies',[]),'binding':bindings,'durationSeconds':duration,
                           'bindHierarchyValidation':bindcheck,'maxInverseBindIdentityError':max_ibm_error,'losslessSidecars':['t6-xmodel-mesh-normalized-v1','t6-xmodel-skeleton-normalized-v2','t6-xanim-normalized-v1']}}}],
          'bufferViews':buf.views,'accessors':buf.accessors,'buffers':[{'byteLength':len(buf.data),'uri':'data:application/octet-stream;base64,'+base64.b64encode(buf.data).decode('ascii')}],
          'extras':{'T6':{'coordinateSystem':'native mesh/bone/track values under conversion wrapper','unitToMeters':T6_UNIT_TO_METERS}}}
    return gltf

def validate(g):
    if g['asset']['version']!='2.0':raise ExportError('not glTF2')
    raw=base64.b64decode(g['buffers'][0]['uri'].split(',',1)[1])
    if len(raw)!=g['buffers'][0]['byteLength']:raise ExportError('buffer length mismatch')
    for skin in g.get('skins',[]):
        if skin['inverseBindMatrices']>=len(g['accessors']):raise ExportError('skin IBM accessor invalid')
        if g['accessors'][skin['inverseBindMatrices']]['count']!=len(skin['joints']):raise ExportError('IBM/joint count mismatch')
    for m in g.get('meshes',[]):
        for p in m['primitives']:
            for ai in list(p['attributes'].values())+[p['indices']]:
                if ai>=len(g['accessors']):raise ExportError('primitive accessor invalid')
    for a in g.get('animations',[]):
        for c in a['channels']:
            s=a['samplers'][c['sampler']];ia=g['accessors'][s['input']];oa=g['accessors'][s['output']]
            if ia['count']!=oa['count']:raise ExportError('animation sampler count mismatch')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mesh_json',type=Path);ap.add_argument('skeleton_json',type=Path);ap.add_argument('xanim_json',type=Path);ap.add_argument('output_gltf',type=Path);ap.add_argument('--lod',type=int,default=0)
    a=ap.parse_args();mesh=json.loads(a.mesh_json.read_text());skel=json.loads(a.skeleton_json.read_text());anim=json.loads(a.xanim_json.read_text());g=export(mesh,skel,anim,a.lod);validate(g)
    text=json.dumps(g,indent=2,ensure_ascii=False)+'\n';a.output_gltf.write_text(text)
    print(json.dumps({'out':str(a.output_gltf),'bytes':len(text.encode()),'nodes':len(g['nodes']),'meshes':len(g['meshes']),'primitives':len(g['meshes'][0]['primitives']),'skins':len(g['skins']),'joints':len(g['skins'][0]['joints']),'channels':len(g['animations'][0]['channels']),'accessors':len(g['accessors']),'bufferBytes':g['buffers'][0]['byteLength'],'maxInverseBindIdentityError':g['animations'][0]['extras']['T6']['maxInverseBindIdentityError']},indent=2))
if __name__=='__main__':main()

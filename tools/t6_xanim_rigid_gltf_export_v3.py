#!/usr/bin/env python3
"""Add a retail-proven rigid T6 XModel mesh/skin to the v2 XAnim glTF export.

v3 keeps v2 quaternion/axis handling, adds rigid XSurface geometry and a skin,
and fixes a T6 semantic subtlety: for animated NON-ROOT bones, XAnim
translation is a delta. T6 adds XModel localTrans before parent composition, so
glTF translation keys are bindLocalTranslation + XAnim delta. Animated root
translation remains fail-closed until its separate runtime path is proven.
"""
from __future__ import annotations
import argparse, base64, copy, json, math, struct
from pathlib import Path
from t6_xanim_gltf_export_v2 import export_gltf as export_v2, validate_gltf as validate_v2, ExportError


def qnorm(q):
    n=math.sqrt(sum(float(x)*float(x) for x in q))
    if not math.isfinite(n) or n<=0: raise ExportError(f'bad quaternion norm {n}')
    return [float(x)/n for x in q]

def qmul(a,b):
    ax,ay,az,aw=a; bx,by,bz,bw=b
    return [aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw,aw*bw-ax*bx-ay*by-az*bz]
def qconj(q): return [-q[0],-q[1],-q[2],q[3]]
def qrot(q,v): return qmul(qmul(qnorm(q),[*v,0.0]),qconj(qnorm(q)))[:3]
def mat(q,t):
    x,y,z,w=qnorm(q); tx,ty,tz=map(float,t); xx,yy,zz=x*x,y*y,z*z; xy,xz,yz=x*y,x*z,y*z; wx,wy,wz=w*x,w*y,w*z
    return [1-2*(yy+zz),2*(xy+wz),2*(xz-wy),0,2*(xy-wz),1-2*(xx+zz),2*(yz+wx),0,2*(xz+wy),2*(yz-wx),1-2*(xx+yy),0,tx,ty,tz,1]
def invmat(q,t):
    qi=qconj(qnorm(q)); return mat(qi,qrot(qi,[-float(x) for x in t]))
def mmul(a,b): return [sum(a[k*4+r]*b[c*4+k] for k in range(4)) for c in range(4) for r in range(4)]
def ierr(m): return max(abs(m[c*4+r]-(1.0 if c==r else 0.0)) for c in range(4) for r in range(4))

def global_binds(bones):
    out=[]; max_ref=0.0
    for b in bones:
        i=int(b['index']); q=qnorm(b.get('localRotation',[0,0,0,1])); t=list(map(float,b.get('localTranslation',[0,0,0]))); p=b.get('parentIndex')
        if p is not None:
            pq,pt=out[int(p)]; q=qnorm(qmul(pq,q)); rt=qrot(pq,t); t=[pt[k]+rt[k] for k in range(3)]
        ref=b.get('globalBaseMat') or {}
        if ref:
            rq=qnorm(ref.get('quat',[0,0,0,1])); rt=list(map(float,ref.get('trans',[0,0,0]))); max_ref=max(max_ref,abs(1-abs(sum(q[k]*rq[k] for k in range(4)))),max(abs(t[k]-rt[k]) for k in range(3)))
        out.append((q,t))
    if max_ref>1e-4: raise ExportError(f'local bind hierarchy mismatch {max_ref}')
    return out,max_ref

def append_accessor(g,raw,ctype,count,typ,name,target=None,minv=None,maxv=None):
    data=g['_raw'];
    while len(data)%4:data.append(0)
    off=len(data); data.extend(raw); vi=len(g['bufferViews']); v={'buffer':0,'byteOffset':off,'byteLength':len(raw),'name':name}
    if target is not None:v['target']=target
    g['bufferViews'].append(v); a={'bufferView':vi,'componentType':ctype,'count':count,'type':typ,'name':name}
    if minv is not None:a['min']=minv
    if maxv is not None:a['max']=maxv
    ai=len(g['accessors']);g['accessors'].append(a);return ai
def f32acc(g,rows,typ,name,target=None):
    c={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[typ]; rr=[[float(x)] for x in rows] if typ=='SCALAR' else [[float(x) for x in r] for r in rows]
    if any(len(r)!=c for r in rr):raise ExportError(f'{name}: malformed {typ}')
    flat=[x for r in rr for x in r]
    if not all(map(math.isfinite,flat)):raise ExportError(f'{name}: nonfinite')
    mi=ma=None
    if rr and typ!='MAT4':mi=[min(r[i] for r in rr) for i in range(c)];ma=[max(r[i] for r in rr) for i in range(c)]
    return append_accessor(g,struct.pack('<'+'f'*len(flat),*flat),5126,len(rr),typ,name,target,mi,ma)
def u16acc(g,rows,typ,name,target=None):
    c={'SCALAR':1,'VEC4':4}[typ]; rr=[[int(x)] for x in rows] if typ=='SCALAR' else [[int(x) for x in r] for r in rows]; flat=[x for r in rr for x in r]
    if any(len(r)!=c for r in rr) or any(x<0 or x>65535 for x in flat):raise ExportError(f'{name}: bad u16')
    mi=ma=None
    if typ=='SCALAR' and flat:mi=[min(flat)];ma=[max(flat)]
    return append_accessor(g,struct.pack('<'+'H'*len(flat),*flat),5123,len(rr),typ,name,target,mi,ma)

def trans_values(track,bone):
    t=track.get('trans') or {}; typ=t.get('type')
    if not typ or typ=='NO_TRANS':return None
    if bone.get('parentIndex') is None:raise ExportError(f"animated root translation not source-closed: {bone['name']}")
    bind=list(map(float,bone.get('localTranslation',[0,0,0])))
    ds=t.get('decodedFrames') if typ in ('SMALL_TRANS','FULL_TRANS') else [t.get('constant')] if typ=='TRANS_NO_SIZE' else None
    if not ds or any(d is None for d in ds):raise ExportError(f"unsupported translation {typ}")
    return [[bind[k]+float(d[k]) for k in range(3)] for d in ds]

def export(skel,render,xanim):
    if not str(skel.get('format','')).startswith('t6-xmodel-skeleton-normalized-v2'):raise ExportError('unsupported skeleton')
    if render.get('format')!='t6-xmodel-rigid-render-normalized-v1':raise ExportError('unsupported render')
    if render['identity']['name']!=skel['identity']['name']:raise ExportError('model identity mismatch')
    if xanim.get('delta') and any((xanim['delta'].get(k) for k in ('trans','quat2','quat'))):raise ExportError('bound rigid v3 does not yet apply deltaPart')
    x=copy.deepcopy(xanim); g=export_v2(skel,x)
    uri=g['buffers'][0]['uri']; pre='data:application/octet-stream;base64,'
    g['_raw']=bytearray(base64.b64decode(uri[len(pre):])); bones=skel['skeleton']['bones']; byname={b['name']:b for b in bones}; tracks={t['name']:t for t in xanim.get('boneTracks',[])}
    corrected=0
    for ch in g['animations'][0]['channels']:
        if ch['target']['path']!='translation':continue
        name=ch.get('extras',{}).get('trackName'); b=byname.get(name); tr=tracks.get(name)
        if not b or not tr:raise ExportError(f'cannot bind translation {name}')
        vals=trans_values(tr,b)
        if vals is None:continue
        sm=g['animations'][0]['samplers'][ch['sampler']]; old=g['accessors'][sm['output']]
        if old['count']!=len(vals):raise ExportError(f'{name}: translated key count mismatch')
        sm['output']=f32acc(g,vals,'VEC3',f'{name}:translation:bindPlusDelta'); ch['extras']['t6Composition']='XModel localTranslation + XAnim translation delta'; corrected+=1
    binds,bind_ref_err=global_binds(bones); ibms=[]; ibm_err=0.0
    for q,t in binds:
        iv=invmat(q,t);ibms.append(iv);ibm_err=max(ibm_err,ierr(mmul(mat(q,t),iv)))
    if ibm_err>2e-5:raise ExportError(f'inverse-bind error {ibm_err}')
    ibma=f32acc(g,ibms,'MAT4','T6 inverse bind matrices')
    mats=[];prims=[];tv=tt=0; handles=render.get('materialHandles',[])
    for s in render['surfaces']:
        si=int(s['index']);vs=s['vertices'];ts=s['triangles'];j=[[int(v['jointIndex']),0,0,0] for v in vs]; w=[[1,0,0,0] for _ in vs]; inds=[int(i) for tri in ts for i in tri]
        attrs={'POSITION':f32acc(g,[v['position'] for v in vs],'VEC3',f's{si}:POSITION',34962),'NORMAL':f32acc(g,[v['normal'] for v in vs],'VEC3',f's{si}:NORMAL',34962),'TANGENT':f32acc(g,[v['tangent'] for v in vs],'VEC4',f's{si}:TANGENT',34962),'TEXCOORD_0':f32acc(g,[v['uv'] for v in vs],'VEC2',f's{si}:TEXCOORD_0',34962),'COLOR_0':f32acc(g,[v['color'] for v in vs],'VEC4',f's{si}:COLOR_0',34962),'JOINTS_0':u16acc(g,j,'VEC4',f's{si}:JOINTS_0',34962),'WEIGHTS_0':f32acc(g,w,'VEC4',f's{si}:WEIGHTS_0',34962)}
        ia=u16acc(g,inds,'SCALAR',f's{si}:indices',34963);mi=len(mats);mats.append({'name':f'T6_Surface_{si}_Material_Unresolved','pbrMetallicRoughness':{'baseColorFactor':[1,1,1,1],'metallicFactor':0,'roughnessFactor':1},'extras':{'T6':{'surfaceIndex':si,'materialHandlePointer':handles[si] if si<len(handles) else None,'exactMaterialNotDecoded':True}}});prims.append({'attributes':attrs,'indices':ia,'material':mi,'mode':4,'extras':{'T6':{'surfaceIndex':si,'baseVertIndex':s.get('baseVertIndex'),'tileMode':s.get('tileMode'),'flags':s.get('flags')}}});tv+=len(vs);tt+=len(ts)
    meshnode=len(g['nodes']);g['nodes'].append({'name':render['identity']['name'],'mesh':0,'skin':0,'extras':{'T6':{'renderFormat':render['format']}}});wrapper=next(i for i,n in enumerate(g['nodes']) if n.get('name')=='__T6_WORLD_TO_GLTF__');g['nodes'][wrapper].setdefault('children',[]).append(meshnode)
    roots=[int(b['index']) for b in bones if b.get('parentIndex') is None];g['meshes']=[{'name':render['identity']['name'],'primitives':prims,'extras':{'T6':{'totalVertices':tv,'totalTriangles':tt}}}];g['skins']=[{'name':render['identity']['name']+'_skin','inverseBindMatrices':ibma,'joints':list(range(len(bones)))}]
    if len(roots)==1:g['skins'][0]['skeleton']=roots[0]
    g['materials']=mats;g['asset']['generator']='bo2-t6-assets t6_xanim_rigid_gltf_export_v3.py';g['extras']['T6'].update({'renderFormat':render['format'],'modelName':render['identity']['name'],'maxInverseBindIdentityError':ibm_err,'maxBindHierarchyReferenceError':bind_ref_err,'translationCompositionCorrectedChannels':corrected});g['animations'][0]['extras']['T6']['rootTranslationPolicy']='reject animated root translation until separately source-closed';g['animations'][0]['extras']['T6']['translationCompositionCorrectedChannels']=corrected
    raw=bytes(g.pop('_raw'));g['buffers'][0]={'byteLength':len(raw),'uri':pre+base64.b64encode(raw).decode('ascii')};validate_v2(g);return g

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--skeleton',type=Path,required=True);ap.add_argument('--render',type=Path,required=True);ap.add_argument('--xanim',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();g=export(json.loads(a.skeleton.read_text()),json.loads(a.render.read_text()),json.loads(a.xanim.read_text()));a.out.write_text(json.dumps(g,indent=2,sort_keys=True)+'\n');print(json.dumps({'out':str(a.out),'nodes':len(g['nodes']),'vertices':g['meshes'][0]['extras']['T6']['totalVertices'],'triangles':g['meshes'][0]['extras']['T6']['totalTriangles'],'channels':len(g['animations'][0]['channels'])},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())

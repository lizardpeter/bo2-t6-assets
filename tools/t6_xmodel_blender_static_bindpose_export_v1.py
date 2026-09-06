#!/usr/bin/env python3
"""Export a normalized T6 XModel LOD as a Blender-safe static bind-pose GLB.

This is an inspection/export variant, not a replacement for the skinned exporter.
It preserves exact normalized retail mesh topology/attributes but removes the
armature/skin and bakes the T6 Z-up inch coordinates into glTF Y-up meters so
Blender imports the mesh directly in its expected Z-up orientation.

No material or texture identity is inferred here.
"""
from __future__ import annotations
import argparse, hashlib, json, math, struct
from pathlib import Path

SCALE = 0.0254
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942


def align4(buf: bytearray):
    while len(buf) % 4:
        buf.append(0)


def add_view(doc, buf, raw, target):
    align4(buf)
    off = len(buf)
    buf.extend(raw)
    i = len(doc['bufferViews'])
    doc['bufferViews'].append({'buffer':0,'byteOffset':off,'byteLength':len(raw),'target':target})
    return i


def add_accessor(doc, view, component, count, typ, minv=None, maxv=None):
    a={'bufferView':view,'componentType':component,'count':count,'type':typ}
    if minv is not None: a['min']=minv
    if maxv is not None: a['max']=maxv
    i=len(doc['accessors']); doc['accessors'].append(a); return i


def f32_rows(rows):
    vals=[float(v) for r in rows for v in r]
    return struct.pack('<'+'f'*len(vals),*vals)


def export(mesh_doc: dict, lod: int = 0) -> bytes:
    if mesh_doc.get('format') != 't6-xmodel-mesh-normalized-v1':
        raise ValueError(f"unsupported mesh format {mesh_doc.get('format')!r}")
    name=mesh_doc['identity']['name']
    lm=next((x for x in mesh_doc['xmodel']['lods'] if int(x['index'])==lod),None)
    if lm is None: raise ValueError(f'LOD{lod} unavailable')
    surfs=mesh_doc['surfaces'][lm['surfIndex']:lm['surfIndex']+lm['numSurfs']]
    doc={
      'asset':{'version':'2.0','generator':'bo2-t6-assets t6_xmodel_blender_static_bindpose_export_v1.py'},
      'scene':0,'scenes':[{'name':f'{name}_LOD{lod}_BINDPOSE','nodes':[0]}],
      'nodes':[{'name':f'{name}_LOD{lod}_BINDPOSE','mesh':0,'extras':{
          't6SourceModel':name,'t6StaticBindPose':True,'t6RigRemovedForVisualInspection':True,
          't6CoordinateBake':'T6 Z-up inches -> glTF Y-up meters; Blender import reconstructs T6 Z-up orientation'}}],
      'meshes':[{'name':f'{name}_LOD{lod}','primitives':[]}],
      'buffers':[{'byteLength':0}],'bufferViews':[],'accessors':[]}
    buf=bytearray()
    for s in surfs:
        pos=[]; norm=[]; uv=[]; col=[]
        for v in s['vertices']:
            x,y,z=map(float,v['position']); pos.append([x*SCALE,z*SCALE,-y*SCALE])
            nx,ny,nz=map(float,v['normal']); q=[nx,nz,-ny]; ln=math.sqrt(sum(a*a for a in q)); norm.append([a/ln for a in q] if ln else q)
            uv.append([float(a) for a in v['texcoord0']]); col.append([float(a) for a in v['colorRGBA']])
        inds=[int(i) for tri in s['triangles'] for i in tri]
        if inds and max(inds)>=len(pos): raise ValueError(f"surf{s['index']}: index outside local vertex range")
        if len(pos)>65535: raise ValueError(f"surf{s['index']}: requires >16-bit local indices")
        pv=add_view(doc,buf,f32_rows(pos),34962); nv=add_view(doc,buf,f32_rows(norm),34962); uvv=add_view(doc,buf,f32_rows(uv),34962); cv=add_view(doc,buf,f32_rows(col),34962)
        iv=add_view(doc,buf,struct.pack('<'+'H'*len(inds),*inds),34963)
        mins=[min(r[k] for r in pos) for k in range(3)]; maxs=[max(r[k] for r in pos) for k in range(3)]
        pa=add_accessor(doc,pv,5126,len(pos),'VEC3',mins,maxs); na=add_accessor(doc,nv,5126,len(norm),'VEC3'); ua=add_accessor(doc,uvv,5126,len(uv),'VEC2'); ca=add_accessor(doc,cv,5126,len(col),'VEC4'); ia=add_accessor(doc,iv,5123,len(inds),'SCALAR')
        doc['meshes'][0]['primitives'].append({'attributes':{'POSITION':pa,'NORMAL':na,'TEXCOORD_0':ua,'COLOR_0':ca},'indices':ia,'mode':4,'extras':{
            't6SurfaceIndex':s['index'],'t6BaseVertIndex':s['baseVertIndex'],'t6VertCount':s['vertCount'],'t6TriCount':s['triCount']}})
    align4(buf); doc['buffers'][0]['byteLength']=len(buf)
    jb=json.dumps(doc,separators=(',',':'),ensure_ascii=False).encode(); jb+=b' '*((-len(jb))%4); bb=bytes(buf)
    total=12+8+len(jb)+8+len(bb)
    out=bytearray(struct.pack('<4sII',b'glTF',2,total)); out+=struct.pack('<II',len(jb),JSON_CHUNK)+jb; out+=struct.pack('<II',len(bb),BIN_CHUNK)+bb
    return bytes(out)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('mesh_json',type=Path); ap.add_argument('output_glb',type=Path); ap.add_argument('--lod',type=int,default=0); a=ap.parse_args()
    mesh=json.loads(a.mesh_json.read_text(encoding='utf-8')); raw=export(mesh,a.lod); a.output_glb.write_bytes(raw)
    print(json.dumps({'out':str(a.output_glb),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},indent=2))


if __name__=='__main__': main()

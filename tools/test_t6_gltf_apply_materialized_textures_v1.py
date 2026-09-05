#!/usr/bin/env python3
from __future__ import annotations
import hashlib, io, json, struct, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image
HERE=Path(__file__).resolve().parent;TOOL=HERE/'t6_gltf_apply_materialized_textures_v1.py'
def sh(b):return hashlib.sha256(b).hexdigest()
def glb(path):
 js={'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':[]}],'nodes':[],'meshes':[],'materials':[{'name':'mat','pbrMetallicRoughness':{'baseColorFactor':[1,1,1,1],'metallicFactor':0,'roughnessFactor':1}}],'buffers':[{'byteLength':0}]};jb=json.dumps(js,separators=(',',':')).encode();jb+=b' ' * ((-len(jb))%4);bin=b'';total=12+8+len(jb)+8;path.write_bytes(struct.pack('<4sII',b'glTF',2,total)+struct.pack('<I4s',len(jb),b'JSON')+jb+struct.pack('<I4s',0,b'BIN\0'))
def png(color):
 im=Image.new('RGBA',(2,2),color);b=io.BytesIO();im.save(b,format='PNG');return b.getvalue()
def main():
 with tempfile.TemporaryDirectory() as td:
  r=Path(td);glb(r/'in.glb');a=png((255,0,0,255));n=png((128,128,255,255));(r/'a.png').write_bytes(a);(r/'n.png').write_bytes(n)
  mat={'format':'t6-ipak-iwi-materialization-v1','textures':[{'image':'a','pngFile':'a.png','pngSha256':sh(a),'iwiSha256':'1'*64,'nameHash':1,'dataHash':2,'iwi':{'width':2,'height':2,'flags':0},'crc29Validated':True,'exactKeyValidated':True},{'image':'n','pngFile':'n.png','pngSha256':sh(n),'iwiSha256':'2'*64,'nameHash':3,'dataHash':4,'iwi':{'width':2,'height':2,'flags':0},'crc29Validated':True,'exactKeyValidated':True}]};(r/'materialized.json').write_text(json.dumps(mat))
  plan={'format':'t6-character-material-binding-plan-v1','materials':[{'material':'mat','slots':[],'gltfVisualization':{'baseColor':{'image':'a','mode':'exact-Diffuse_Map-slot'},'normal':{'image':'n','mode':'exact-Normal_Map-slot'},'shaderApproximation':False}}],'surfaceBindings':[{'surfaceIndex':0,'material':'mat'}]};(r/'plan.json').write_text(json.dumps(plan))
  p=subprocess.run([sys.executable,str(TOOL),'--glb',str(r/'in.glb'),'--binding-plan',str(r/'plan.json'),'--materialized-manifest',str(r/'materialized.json'),'--out',str(r/'out.glb'),'--manifest',str(r/'out.json')],capture_output=True,text=True);assert p.returncode==0,(p.stdout,p.stderr);o=json.loads((r/'out.json').read_text());assert o['summary']['boundMaterials']==1 and o['summary']['uniqueEmbeddedPngs']==2
  b=(r/'out.glb').read_bytes();off=12;js=None
  while off<len(b):
   z,t=struct.unpack_from('<I4s',b,off);off+=8;c=b[off:off+z];off+=z
   if t==b'JSON':js=json.loads(c)
  m=js['materials'][0];assert m['pbrMetallicRoughness']['baseColorTexture']['index']!=m['normalTexture']['index'];assert len(js['images'])==2
 print('t6_gltf_apply_materialized_textures_v1: PASS');return 0
if __name__=='__main__':raise SystemExit(main())

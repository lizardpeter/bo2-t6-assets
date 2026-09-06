#!/usr/bin/env python3
from __future__ import annotations
import copy,hashlib,json,struct,subprocess,sys,tempfile,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;TOOL=HERE/'t6_gltf_apply_materialized_textures_v1.py'
def sh(b):return hashlib.sha256(b).hexdigest()
def chunk(k,p):return struct.pack('>I',len(p))+k+p+struct.pack('>I',zlib.crc32(k+p)&0xffffffff)
def png(color):
 raw=bytes([0,*color]);return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
def make_glb(path):
 js={'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':[]}],'nodes':[],'meshes':[],'materials':[{'name':'mat','pbrMetallicRoughness':{}}],'skins':[{'name':'sentinel','joints':[]}],'animations':[{'name':'sentinel','channels':[],'samplers':[]}],'buffers':[{'byteLength':0}]};jb=json.dumps(js,separators=(',',':')).encode();jb+=b' '*((-len(jb))%4);total=12+8+len(jb)+8;path.write_bytes(struct.pack('<4sII',b'glTF',2,total)+struct.pack('<I4s',len(jb),b'JSON')+jb+struct.pack('<I4s',0,b'BIN\0'))
def read_json(path):
 b=path.read_bytes();o=12
 while o<len(b):
  n,t=struct.unpack_from('<I4s',b,o);o+=8;c=b[o:o+n];o+=n
  if t==b'JSON':return json.loads(c)
 raise AssertionError('no JSON')
def main():
 with tempfile.TemporaryDirectory() as td:
  r=Path(td);make_glb(r/'in.glb');a=png((255,0,0,255));n=png((128,128,255,255));(r/'a.png').write_bytes(a);(r/'n.png').write_bytes(n)
  rows=[{'image':'a','pngFile':'a.png','pngSha256':sh(a),'iwiSha256':'1'*64,'nameHash':1,'dataHash':2,'iwi':{'width':1,'height':1,'flags':0},'crc29Validated':True,'exactKeyValidated':True},{'image':'n','pngFile':'n.png','pngSha256':sh(n),'iwiSha256':'2'*64,'nameHash':3,'dataHash':4,'iwi':{'width':1,'height':1,'flags':0},'crc29Validated':True,'exactKeyValidated':True}]
  mat={'format':'t6-ipak-iwi-materialization-v1','textures':rows};(r/'materialized.json').write_text(json.dumps(mat))
  plan={'format':'t6-character-material-binding-plan-v1','materials':[{'material':'mat','slots':[],'gltfVisualization':{'baseColor':{'image':'a','mode':'exact-Diffuse_Map-slot','exactStreamKey':{'nameHash':1,'dataHash':2}},'normal':{'image':'n','mode':'exact-Normal_Map-slot','exactStreamKey':{'nameHash':3,'dataHash':4}},'shaderApproximation':False}}],'surfaceBindings':[{'surfaceIndex':0,'material':'mat'}]};(r/'plan.json').write_text(json.dumps(plan))
  cmd=[sys.executable,str(TOOL),'--glb',str(r/'in.glb'),'--binding-plan',str(r/'plan.json'),'--materialized-manifest',str(r/'materialized.json'),'--out',str(r/'out.glb'),'--manifest',str(r/'out.json')];p=subprocess.run(cmd,capture_output=True,text=True);assert p.returncode==0,(p.stdout,p.stderr);proof=json.loads((r/'out.json').read_text());assert proof['summary']['boundMaterials']==1 and proof['summary']['uniqueEmbeddedPngs']==2;out=read_json(r/'out.glb');src=read_json(r/'in.glb');assert out['skins']==src['skins'] and out['animations']==src['animations'];assert 'baseColorTexture' in out['materials'][0]['pbrMetallicRoughness'] and 'normalTexture' in out['materials'][0]
  bad=copy.deepcopy(mat);bad['textures'][0]['dataHash']=5;(r/'bad.json').write_text(json.dumps(bad));cmd[cmd.index(str(r/'materialized.json'))]=str(r/'bad.json');cmd[cmd.index(str(r/'out.glb'))]=str(r/'bad.glb');cmd[cmd.index(str(r/'out.json'))]=str(r/'badproof.json');p=subprocess.run(cmd,capture_output=True,text=True);assert p.returncode!=0
 print('t6_gltf_apply_materialized_textures_v1: PASS')
if __name__=='__main__':main()

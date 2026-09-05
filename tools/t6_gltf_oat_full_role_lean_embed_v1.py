#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, hashlib, json, struct, zipfile
from collections import Counter, defaultdict
from pathlib import Path
JSON_CHUNK=0x4E4F534A;BIN_CHUNK=0x004E4942

def sha(b):return hashlib.sha256(b).hexdigest()
def read_glb(p):
 b=p.read_bytes();magic,ver,total=struct.unpack_from('<4sII',b,0)
 if magic!=b'glTF' or ver!=2 or total!=len(b):raise ValueError('bad glb')
 q=12;js=bb=None
 while q<len(b):
  ln,t=struct.unpack_from('<II',b,q);q+=8;c=b[q:q+ln];q+=ln
  if t==JSON_CHUNK:js=json.loads(c.rstrip(b' \0\t\r\n'))
  elif t==BIN_CHUNK:bb=bytearray(c)
 return js,bb
def write_glb(p,js,bb):
 j=copy.deepcopy(js);j['buffers'][0]['byteLength']=len(bb);jb=json.dumps(j,separators=(',',':'),ensure_ascii=False).encode();jb+=b' '*((-len(jb))%4);bd=bytes(bb);bd+=b'\0'*((-len(bd))%4);total=12+8+len(jb)+8+len(bd);o=bytearray(struct.pack('<4sII',b'glTF',2,total));o+=struct.pack('<II',len(jb),JSON_CHUNK)+jb;o+=struct.pack('<II',len(bd),BIN_CHUNK)+bd;p.write_bytes(o)
def mp(rec):return 'oat_dump\\materials\\'+rec.replace('/','\\')+'.json'
def ip(n):return 'oat_dump\\images\\'+n+'.dds'
def dds_info(b):
 if len(b)>=128 and b[:4]==b'DDS ':return {'bytes':len(b),'height':struct.unpack_from('<I',b,12)[0],'width':struct.unpack_from('<I',b,16)[0],'fourCC':b[84:88].decode('latin1','replace')}
 return {'bytes':len(b)}
def append_raw(js,bb,n,d):
 while len(bb)%4:bb.append(0)
 off=len(bb);bb.extend(d);js.setdefault('bufferViews',[]).append({'buffer':0,'byteOffset':off,'byteLength':len(d),'name':f'T6_OAT_RAW_DDS_{n}'});return len(js['bufferViews'])-1

def build(inp,zp,out,proof):
 js,bb=read_glb(inp);src=inp.read_bytes();used=sorted(set(pr['material'] for me in js.get('meshes',[]) for pr in me.get('primitives',[]) if isinstance(pr.get('material'),int)))
 existing=defaultdict(list)
 for ti,t in enumerate(js.get('textures',[])):
  if t.get('name'):existing[t['name']].append(ti)
 base={'file':inp.name,'bytes':len(src),'sha256':sha(src),'images':len(js.get('images',[])),'textures':len(js.get('textures',[])),'bufferViews':len(js.get('bufferViews',[])),'usedMaterials':len(used)}
 missing=Counter();mm=defaultdict(set);raw={};rawrows=[];mrows=[];rolec=Counter();total=avail=existingrefs=rawrefs=0
 with zipfile.ZipFile(zp) as z:
  zn=set(z.namelist())
  for mi in used:
   m=js['materials'][mi];name=m.get('name');tx=((m.get('extras') or {}).get('T6') or {});rec=tx.get('oatMaterialRecord') or name;pp=mp(rec)
   if pp not in zn:raise ValueError(f'missing material {mi} {name} {rec}')
   doc=json.loads(z.read(pp));roles=[]
   for oi,t in enumerate(doc.get('textures',[])):
    image=t.get('image');role=t.get('name') or f'unnamedRole{oi}';sem=t.get('semantic')
    if not image:continue
    total+=1;rolec[(role,sem)]+=1;r={'ordinal':oi,'role':role,'semantic':sem,'image':image,'samplerState':t.get('samplerState')};ddsp=ip(image)
    if ddsp not in zn:
     r['status']='retained-oat-dds-absent';missing[image]+=1;mm[image].add(name)
    else:
     avail+=1;dds=z.read(ddsp);info=dds_info(dds);r['ddsSha256']=sha(dds);r.update({k:v for k,v in info.items() if k!='bytes'});r['ddsBytes']=len(dds)
     if existing.get(image):
      existingrefs+=1;r['status']='exact-oat-dds-source-backed-existing-standard-texture';r['standardTextureIndices']=existing[image]
     else:
      rawrefs+=1
      if image not in raw:
       bvi=append_raw(js,bb,image,dds);raw[image]={'bufferView':bvi,'ddsSha256':sha(dds),**info};rawrows.append({'image':image,'bufferView':bvi,'ddsSha256':sha(dds),**info})
      r['status']='exact-oat-dds-embedded-losslessly';r['rawDdsBufferView']=raw[image]['bufferView']
    roles.append(r)
   m.setdefault('extras',{}).setdefault('T6',{})['oatFullTextureRolesLeanV22']={'record':rec,'source':'NUKETOWN_2025_TEXTURE_DUMP_R4.zip','roles':roles,'policy':'Use existing standard glTF texture when the same exact OAT image identity is already present; otherwise embed raw DDS losslessly. Core visible bindings unchanged.'};mrows.append({'materialIndex':mi,'material':name,'record':rec,'roleCount':len(roles),'roles':roles})
 top=js.setdefault('extras',{}).setdefault('T6',{});top['oatFullRoleLeanClosureV22']={'usedMaterials':len(used),'roleReferences':total,'availableRoleReferences':avail,'missingRoleReferences':sum(missing.values()),'roleRefsServedByExistingStandardTextureIdentity':existingrefs,'roleRefsServedByRawEmbeddedDds':rawrefs,'distinctRawDdsEmbedded':len(raw),'distinctMissingImageIdentities':sorted(missing),'source':'NUKETOWN_2025_TEXTURE_DUMP_R4.zip','policy':'Every available exact OAT input is retained either by an already-present same-identity standard glTF texture or lossless raw DDS embedded in a bufferView. Existing base/normal preview is not modified.'}
 write_glb(out,js,bb);ob=out.read_bytes();j2,b2=read_glb(out);invalid=[]
 for ti,t in enumerate(j2.get('textures',[])):
  s=t.get('source')
  if not isinstance(s,int) or not(0<=s<len(j2.get('images',[]))):invalid.append({'texture':ti,'source':s})
 ext=[i for i,x in enumerate(j2.get('images',[])) if 'uri' in x]
 result={'format':'t6-nuketown-v22-full-oat-texture-role-lean-closure-v1','base':base,'output':{'file':out.name,'bytes':len(ob),'sha256':sha(ob),'images':len(j2.get('images',[])),'textures':len(j2.get('textures',[])),'bufferViews':len(j2.get('bufferViews',[])),'usedMaterials':len(used),'roleReferences':total,'roleReferencesWithExactRetainedDds':avail,'roleReferencesMissingDds':sum(missing.values()),'roleRefsExistingStandardTextureIdentity':existingrefs,'roleRefsRawEmbeddedDds':rawrefs,'distinctRawDdsEmbedded':len(raw),'distinctMissingImages':len(missing),'invalidTextureSources':invalid,'externalImageCount':len(ext)},'missingExactImages':[{'image':n,'referenceCount':missing[n],'materials':sorted(mm[n])} for n in sorted(missing)],'roleCensus':[{'role':r,'semantic':s,'references':c} for (r,s),c in sorted(rolec.items(),key=lambda kv:(-kv[1],str(kv[0])))],'rawDdsClosures':rawrows,'materialClosures':mrows,'proofBoundary':'Every exact OAT DDS available for every used material role is represented in the candidate: an existing same-image-identity standard texture when already present, otherwise a byte-exact raw DDS bufferView. Only retained-source-absent image identities remain unresolved.'};proof.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['output'],indent=2));print(json.dumps(result['missingExactImages'],indent=2))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('input',type=Path);a.add_argument('oat_zip',type=Path);a.add_argument('output',type=Path);a.add_argument('proof',type=Path);x=a.parse_args();build(x.input,x.oat_zip,x.output,x.proof)

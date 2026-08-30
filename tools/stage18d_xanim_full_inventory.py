#!/usr/bin/env python3
"""Stage 18D: full raw T6 common_mp XAnim structural inventory.

Authority is the expanded retail XFile byte stream. No OAT executable/export is used.
The scan anchors on the independently observed T6 24/30 Hz framerate words, then
requires a valid 104-byte PC32 XAnimParts header plus a complete serialized child walk.
Acceptance is the exact XAsset-list count with zero structural overlaps.
"""
from pathlib import Path
import argparse,csv,json,struct,math,hashlib,re,importlib.util
FOLLOW=0xffffffff;INSERT=0xfffffffe;SHIFT=29;MASK=(1<<29)-1;XANIM=104

def lm(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def parse_front(d):
 blocks=list(struct.unpack_from('<8I',d,8));pos=40;sc,sp,dc,dp,ac,ap=struct.unpack_from('<6I',d,pos);pos+=24
 if sc:
  ptrs=struct.unpack_from(f'<{sc}I',d,pos);pos+=sc*4
  for p in ptrs:
   if p==FOLLOW:pos=d.find(b'\0',pos)+1
 if dc:
  ptrs=struct.unpack_from(f'<{dc}I',d,pos);pos+=dc*4
  for p in ptrs:
   if p==FOLLOW:pos=d.find(b'\0',pos)+1
 asset_array=pos
 xanim_count=0
 for i in range(ac):
  typ,_=struct.unpack_from('<II',d,asset_array+i*8)
  if typ==4:xanim_count+=1
 return blocks,asset_array+ac*8,ac,xanim_count

def pv(v,b,nonnull=False):
 if v==0:return not nonnull
 if v==FOLLOW:return True
 if v==INSERT:return not nonnull
 e=(v-1)&0xffffffff;bi=e>>SHIFT;off=e&MASK
 return bi<len(b) and off<b[bi]

def fixed(d,st):
 cs=struct.unpack_from('<6H',d,st+4);rds,idx=struct.unpack_from('<II',d,st+40);fr,fq,pl,le=struct.unpack_from('<4f',d,st+48);ptr=struct.unpack_from('<10I',d,st+64)
 return {'namep':struct.unpack_from('<I',d,st)[0],'cs':cs,'nf':cs[5],'flags':list(d[st+16:st+20]),'bone':list(d[st+24:st+34]),'notify':d[st+34],'asset':d[st+35],'default':d[st+36],'pad':d[st+37:st+40],'rds':rds,'idx':idx,'fr':fr,'fq':fq,'pl':pl,'le':le,'ptr':ptr}

def valid(d,st,r,b):
 np=r['namep']
 if np==0 or np==INSERT:return False
 if np!=FOLLOW and not pv(np,b,True):return False
 if any(x not in (0,1) for x in r['flags']) or r['default'] not in (0,1) or r['pad']!=b'\0\0\0':return False
 if r['asset'] not in (1,2,6) or r['notify']>128 or r['bone'][9]>255 or r['nf']>2048:return False
 if r['fr'] not in (24.0,30.0):return False
 if r['nf']>0 and abs(r['fq']-r['fr']/r['nf'])>2e-6:return False
 if r['rds']>2_000_000 or r['idx']>2_000_000:return False
 if any(not math.isfinite(x) or abs(x)>100000 for x in (r['fq'],r['pl'],r['le'])):return False
 if any(not pv(v,b,False) for v in r['ptr']):return False
 if np==FOLLOW:
  e=d.find(b'\0',st+104,min(len(d),st+104+161))
  if e<0 or e==st+104:return False
  raw=d[st+104:e]
  try:n=raw.decode('ascii')
  except:return False
  if not re.fullmatch(r'[A-Za-z0-9_./+\-]{2,160}',n):return False
 return True

def walk(d,st,r,delta):
 pos=st+104
 if r['namep']==FOLLOW: pos=d.find(b'\0',pos,pos+256)+1
 p=r['ptr'];nf=r['nf']
 if p[0]==FOLLOW:pos+=r['bone'][9]*2
 if p[8]==FOLLOW:pos+=r['notify']*8
 if p[9]==FOLLOW:
  tr,q2,q=struct.unpack_from('<3I',d,pos);pos+=12
  for cp,fn in ((tr,delta.parse_trans),(q2,delta.parse_quat2),(q,delta.parse_quat)):
   if cp==FOLLOW:_,pos=fn(d,pos,nf)
 arr=[(r['cs'][0],1,p[1]),(r['cs'][1],2,p[2]),(r['cs'][2],4,p[3]),(r['rds'],2,p[4]),(r['cs'][3],1,p[5]),(r['cs'][4],4,p[6]),(r['idx'],1 if nf<256 else 2,p[7])]
 for c,u,pp in arr:
  if pp==FOLLOW:pos+=c*u
 if pos>len(d):raise ValueError
 return pos

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stream',type=Path,required=True);ap.add_argument('--delta-parser',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 d=a.stream.read_bytes();b,body,ac,expected=parse_front(d);delta=lm(a.delta_parser,'delta')
 starts=set();recs=[]
 for fr in (24.0,30.0):
  pat=struct.pack('<f',fr);p=body+48
  while True:
   h=d.find(pat,p);p=h+1
   if h<0:break
   st=h-48
   if st<body or st in starts or st+104>len(d):continue
   r=fixed(d,st)
   if not valid(d,st,r,b):continue
   try:end=walk(d,st,r,delta)
   except:continue
   if end<=st or end>len(d):continue
   name=None
   if r['namep']==FOLLOW:
    e=d.find(b'\0',st+104,st+104+256);name=d[st+104:e].decode('ascii')
   starts.add(st);recs.append({'raw_struct_offset':st,'raw_end_offset':end,'name_kind':'inline' if r['namep']==FOLLOW else 'packed','name':name,'name_ptr_raw':f"0x{r['namep']:08X}",'numframes':r['nf'],'framerate':r['fr'],'frequency':r['fq'],'asset_type':r['asset'],'delta':r['flags'][1],'bone_name_count':r['bone'][9],'notify_count':r['notify']})
 recs.sort(key=lambda x:x['raw_struct_offset']);ss={x['raw_struct_offset'] for x in recs}
 for i,x in enumerate(recs):
  x['end_hits_record_start']=x['raw_end_offset'] in ss
  x['gap_to_next_structural_record']=None if i+1==len(recs) else recs[i+1]['raw_struct_offset']-x['raw_end_offset']
 inline=[x for x in recs if x['name_kind']=='inline'];packed=[x for x in recs if x['name_kind']=='packed']
 out={'stage':'18D full raw XAnim structural inventory','expanded_sha256':hashlib.sha256(d).hexdigest(),'raw_xasset_expected_xanim_count':expected,'structural_record_count':len(recs),'inline_record_count':len(inline),'packed_name_record_count':len(packed),'count_closes_exactly':len(recs)==expected,'end_hits_another_record_start':sum(x['end_hits_record_start'] for x in recs),'overlaps_next_structural_record':sum((x['gap_to_next_structural_record'] or 0)<0 for x in recs),'records':recs}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='records'},indent=2))
if __name__=='__main__':main()

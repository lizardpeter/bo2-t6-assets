#!/usr/bin/env python3
"""Synthetic regression for t6_ipak_exact_key_extract_v1.py."""
from __future__ import annotations
import json, struct, subprocess, sys, tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
TOOL=HERE/'t6_ipak_exact_key_extract_v1.py'

def make_ipak(path:Path, rows):
 idx_off=64;data_off=128;rel=0;index=[];payload=[]
 for dh,nh,blob in rows:index.append((dh,nh,rel,len(blob)));payload.append(blob);rel+=len(blob)
 ib=b''.join(struct.pack('<IIII',*r) for r in index);db=b''.join(payload);total=data_off+len(db);out=bytearray(total)
 out[:16]=struct.pack('<4sIII',b'KAPI',0x50000,total,2);out[16:32]=struct.pack('<IIII',1,idx_off,len(ib),len(index));out[32:48]=struct.pack('<IIII',2,data_off,len(db),len(index));out[idx_off:idx_off+len(ib)]=ib;out[data_off:data_off+len(db)]=db;path.write_bytes(out)

def target(name,nh,dh):return {'name':name,'nameHash':nh,'streamedPart0':{'dataHash':dh,'ipakIndex':0,'repositoryHint':'base.ipak'}}
def run(root:Path,rows,targets):
 make_ipak(root/'base.ipak',rows);(root/'targets.json').write_text(json.dumps({'exactStreamKeyImages':targets}),encoding='utf-8')
 return subprocess.run([sys.executable,str(TOOL),'--ipak',str(root/'base.ipak'),'--targets',str(root/'targets.json'),'--outdir',str(root/'out')],capture_output=True,text=True)

def main():
 with tempfile.TemporaryDirectory() as td:
  root=Path(td)/'ok';root.mkdir(parents=True);t1=target('one',0x11112222,0x01234567);t2=target('two',0x33334444,0x07654321)
  r=run(root,[(0x01234567,0x11112222,b'RIGHT1'),(0x05555555,0x11112222,b'WRONG_DATA'),(0x07654321,0x33334444,b'RIGHT2')],[t1,t2]);assert r.returncode==0,(r.stdout,r.stderr)
  m=json.loads((root/'out'/'manifest.json').read_text());assert m['summary']=={'requested':2,'recovered':2,'unresolved':0};got={x['image']:(root/'out'/x['outputFile']).read_bytes() for x in m['recovered']};assert got=={'one':b'RIGHT1','two':b'RIGHT2'}
 with tempfile.TemporaryDirectory() as td:
  root=Path(td)/'ambig';root.mkdir(parents=True);t=target('dup',0xAABBCCDD,0x01234567)
  r=run(root,[(0x01234567,0xAABBCCDD,b'A'),(0x01234567,0xAABBCCDD,b'B')],[t]);assert r.returncode==2,(r.stdout,r.stderr);m=json.loads((root/'out'/'manifest.json').read_text());assert m['summary']=={'requested':1,'recovered':0,'unresolved':1};assert m['unresolved'][0]['reason']=='ambiguous-exact-key'
 print('t6_ipak_exact_key_extract_v1: PASS');return 0
if __name__=='__main__':raise SystemExit(main())

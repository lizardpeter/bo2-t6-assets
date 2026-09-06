#!/usr/bin/env python3
"""Extract only exact T6 IPAK entries requested by a retail texture-key manifest.

This stage intentionally does not decompress the IPAK entry payload. It proves
selection first: every extracted record must match both exact retail nameHash and
exact retail dataHash. The small raw entries can then be fed to the separately
validated IWI/LZO decoder.

BO2/T6 IPAK: magic KAPI, version 0x50000, type-1 index and type-2 data sections;
index rows are <dataHash,nameHash,relativeOffset,entrySpan>.
"""
from __future__ import annotations
import argparse, hashlib, json, struct, zipfile
from pathlib import Path

IPAK_MAGIC=b'KAPI'; IPAK_VERSION=0x50000; ENTRY=struct.Struct('<IIII')
class IpakError(RuntimeError): pass

def sha256_file(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def parse_u32(v):
 if isinstance(v,int):return v&0xffffffff
 if isinstance(v,str):return int(v,0)&0xffffffff
 raise IpakError(f'not a u32: {v!r}')
def safe_name(s:str)->str:
 out=''.join(c if (c.isalnum() or c in '._-~') else '_' for c in s)
 return out[:180] or 'unnamed'

def parse_ipak(path:Path):
 size=path.stat().st_size
 with path.open('rb') as f:
  head=f.read(16)
  if len(head)!=16:raise IpakError('IPAK too small')
  magic,version,declared,nsec=struct.unpack('<4sIII',head)
  if magic!=IPAK_MAGIC:raise IpakError(f'wrong IPAK magic {magic!r}')
  if version!=IPAK_VERSION:raise IpakError(f'wrong IPAK version 0x{version:x}')
  sections=[]
  for i in range(nsec):
   raw=f.read(16)
   if len(raw)!=16:raise IpakError('truncated section table')
   typ,off,span,count=struct.unpack('<IIII',raw)
   if off+span>size:raise IpakError(f'section {i} outside file')
   sections.append({'type':typ,'offset':off,'size':span,'itemCount':count})
  data=next((s for s in sections if s['type']==2),None);idx=next((s for s in sections if s['type']==1),None)
  if not data or not idx:raise IpakError('missing data/index section')
  need=idx['itemCount']*ENTRY.size
  if need>idx['size']:raise IpakError('index item count exceeds index section')
  f.seek(idx['offset']);raw=f.read(need)
  if len(raw)!=need:raise IpakError('truncated index')
 rows=[]
 for i in range(idx['itemCount']):
  dh,nh,rel,span=ENTRY.unpack_from(raw,i*ENTRY.size)
  if rel+span>data['size']:raise IpakError(f'entry {i} outside data section')
  rows.append({'index':i,'dataHash':dh,'nameHash':nh,'relativeOffset':rel,'entrySpan':span,'absoluteOffset':data['offset']+rel})
 return {'fileSize':size,'declaredSize':declared,'version':version,'sections':sections,'dataSection':data,'indexSection':idx,'rows':rows}

def load_targets(path:Path,repository:str|None):
 d=json.loads(path.read_text(encoding='utf-8-sig'))
 raw=d.get('exactStreamKeyImages') if isinstance(d,dict) else d
 if isinstance(d,dict) and not isinstance(raw,list):raw=d.get('exactBaseIpakKeys')
 if not isinstance(raw,list):raise IpakError('manifest has no exactStreamKeyImages/exactBaseIpakKeys/list')
 out=[];seen=set()
 for x in raw:
  if not isinstance(x,dict):continue
  sp=x.get('streamedPart0') or {}
  repo=sp.get('repositoryHint') or x.get('repository')
  if repository and repo and repo.lower()!=repository.lower():continue
  name=x.get('name') or x.get('image')
  if not isinstance(name,str) or not name:raise IpakError('target missing name')
  nh=parse_u32(x.get('nameHash',x.get('nameHashHex')))
  dh=parse_u32(sp.get('dataHash',sp.get('dataHashHex',x.get('dataHash',x.get('dataHashHex')))))
  key=(nh,dh)
  if key in seen:continue
  seen.add(key);out.append({'image':name,'nameHash':nh,'nameHashHex':f'0x{nh:08x}','dataHash':dh,'dataHashHex':f'0x{dh:08x}','repositoryHint':repo,'ipakIndex':sp.get('ipakIndex',x.get('ipakIndex'))})
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--ipak',type=Path,required=True);ap.add_argument('--targets',type=Path,required=True);ap.add_argument('--outdir',type=Path,required=True);ap.add_argument('--repository',default='base.ipak');ap.add_argument('--expect-ipak-sha256');ap.add_argument('--zip',action='store_true');a=ap.parse_args()
 if not a.ipak.is_file():raise SystemExit(f'IPAK not found: {a.ipak}')
 sha=sha256_file(a.ipak)
 if a.expect_ipak_sha256 and sha.lower()!=a.expect_ipak_sha256.lower():raise SystemExit(f'IPAK SHA-256 mismatch: {sha}')
 targets=load_targets(a.targets,a.repository)
 if not targets:raise SystemExit('no targets after repository filter')
 info=parse_ipak(a.ipak);by={}
 for r in info['rows']:by.setdefault((r['nameHash'],r['dataHash']),[]).append(r)
 a.outdir.mkdir(parents=True,exist_ok=True);recovered=[];unresolved=[]
 with a.ipak.open('rb') as f:
  for t in targets:
   matches=by.get((t['nameHash'],t['dataHash']),[])
   if len(matches)!=1:
    unresolved.append({**t,'reason':'not-found' if not matches else 'ambiguous-exact-key','matchCount':len(matches)});continue
   r=matches[0];f.seek(r['absoluteOffset']);blob=f.read(r['entrySpan'])
   if len(blob)!=r['entrySpan']:raise IpakError(f"short read for {t['image']}")
   fn=f"{safe_name(t['image'])}__nh_{t['nameHash']:08x}__dh_{t['dataHash']:08x}.ipakentry";(a.outdir/fn).write_bytes(blob)
   recovered.append({**t,**r,'outputFile':fn,'entrySha256':hashlib.sha256(blob).hexdigest()})
 doc={'format':'t6-ipak-exact-key-extract-v1','selectionPolicy':'exact nameHash + exact dataHash only; no name-only fallback; ambiguous keys fail closed','source':{'path':str(a.ipak),'bytes':a.ipak.stat().st_size,'sha256':sha,'magic':'KAPI','versionHex':f"0x{info['version']:x}",'declaredSize':info['declaredSize'],'sections':info['sections']},'targetManifest':{'path':str(a.targets),'sha256':sha256_file(a.targets),'repositoryFilter':a.repository},'summary':{'requested':len(targets),'recovered':len(recovered),'unresolved':len(unresolved)},'recovered':recovered,'unresolved':unresolved,'proofBoundary':'This stage copies the exact indexed IPAK entry span only. It does not yet claim decompressed IWI/pixels or CRC validation of reconstructed IWI.'}
 (a.outdir/'manifest.json').write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 if a.zip:
  zp=a.outdir.with_suffix('.zip')
  with zipfile.ZipFile(zp,'w',compression=zipfile.ZIP_DEFLATED) as z:
   for p in sorted(a.outdir.iterdir()):
    if p.is_file():z.write(p,p.name)
  print(f'zip={zp}')
 print(json.dumps(doc['summary'],indent=2,sort_keys=True));return 2 if unresolved else 0
if __name__=='__main__':raise SystemExit(main())

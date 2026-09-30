#!/usr/bin/env python3
"""Recover temporary test fixtures from SHA-verified retained Ghidra evidence."""
import hashlib,io,json,os,pathlib,subprocess,tarfile,urllib.request,zipfile
REPO='lizardpeter/bo2-t6-assets'
TARGETS={
 '009f6c0f':(11033713166,'0280f06bba10f68f306f80c505784efc7472e3d9b01c266c9db9fb090e3c3689','28ea55108bd3acef24cd29332d76ae33828dc44082b42cba3e6b16d3fdc617a4'),
 '009f6d72':(11033373743,'fffb15f0f12cf846c1808f753bed5d68e9561ec0c6f49d3c81df7b5403f2bfad','6d730af6c9b8eebee629dfd4251fc6df5a6411cbc75c6ec63fa45b2fbfe273e6')}
generated=[]; manifest=[]
for va,(aid,ziphash,codehash) in TARGETS.items():
 request=urllib.request.Request(f'https://api.github.com/repos/{REPO}/actions/artifacts/{aid}/zip',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
 raw=urllib.request.urlopen(request).read(); assert hashlib.sha256(raw).hexdigest()==ziphash
 z=zipfile.ZipFile(io.BytesIO(raw)); name=next(n for n in z.namelist() if n.endswith('.tar.zst')); compressed=z.read(name)
 hname=next(n for n in z.namelist() if n.endswith('.sha256')); assert hashlib.sha256(compressed).hexdigest()==z.read(hname).decode().split()[0]
 data=subprocess.run(['zstd','-dc'],input=compressed,stdout=subprocess.PIPE,check=True).stdout
 t=tarfile.open(fileobj=io.BytesIO(data)); member=next(n for n in t.getnames() if n.endswith('disassembly/'+va+'.asm'))
 listing=t.extractfile(member).read().decode(); code=bytearray(); end=int(va,16)
 for line in listing.splitlines():
  if not line or line.startswith('#'):continue
  address,encoded,*_=line.split('\t'); assert int(address,16)==end
  instruction=bytes.fromhex(encoded); code.extend(instruction); end+=len(instruction)
 assert hashlib.sha256(code).hexdigest()==codehash
 generated.append('extern "C" const unsigned char ref_'+va+'[] __attribute__((section(".text"),aligned(16))) = {'+','.join(str(b) for b in code)+'};')
 manifest.append(dict(va=va,instruction_bytes=len(code),instruction_sha256=codehash,source_artifact_id=aid,source_zip_sha256=ziphash))
pathlib.Path('/tmp/t6_simd_reference.inc').write_text('\n'.join(generated)+'\n')
pathlib.Path('/tmp/t6_simd_fixture_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

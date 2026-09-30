#!/usr/bin/env python3
import argparse, hashlib, json, struct
def be32(b,o): return struct.unpack_from(">I",b,o)[0]
def align(v,a): return (v+a-1)&~(a-1)
def parse_dol(data):
    segs=[]
    for kind,count,oo,ao,so,flags in [("text",7,0x00,0x48,0x90,5),("data",11,0x1c,0x64,0xac,6)]:
        for i in range(count):
            off=be32(data,oo+i*4); addr=be32(data,ao+i*4); size=be32(data,so+i*4)
            if size:
                blob=data[off:off+size]
                if len(blob)!=size: raise ValueError(f"truncated DOL {kind}{i}")
                segs.append(dict(kind=kind,index=i,dol_offset=off,vaddr=addr,size=size,flags=flags,blob=blob,sha256=hashlib.sha256(blob).hexdigest()))
    return segs,be32(data,0xd8),be32(data,0xdc),be32(data,0xe0)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("dol"); ap.add_argument("elf"); ap.add_argument("manifest"); a=ap.parse_args()
    data=open(a.dol,"rb").read(); segs,bss_addr,bss_size,entry=parse_dol(data)
    phnum=len(segs)+(1 if bss_size else 0); ehsize=52; phentsize=32; phoff=ehsize; cur=align(ehsize+phnum*phentsize,4)
    for s in segs: cur=align(cur,4); s["elf_offset"]=cur; cur+=s["size"]
    ident=b"\x7fELF"+bytes([1,2,1,0])+bytes(8)
    hdr=struct.pack(">16sHHIIIIIHHHHHH",ident,2,20,1,entry,phoff,0,0,ehsize,phentsize,phnum,0,0,0)
    ph=[struct.pack(">IIIIIIII",1,s["elf_offset"],s["vaddr"],s["vaddr"],s["size"],s["size"],s["flags"],4) for s in segs]
    if bss_size: ph.append(struct.pack(">IIIIIIII",1,0,bss_addr,bss_addr,0,bss_size,6,4))
    out=bytearray(cur); out[:len(hdr)]=hdr; p=phoff
    for x in ph: out[p:p+32]=x; p+=32
    for s in segs: out[s["elf_offset"]:s["elf_offset"]+s["size"]]=s["blob"]
    open(a.elf,"wb").write(out)
    manifest={"format":"deterministic-dol-to-elf32be-v1","source_dol_sha256":hashlib.sha256(data).hexdigest(),"elf_sha256":hashlib.sha256(out).hexdigest(),"entry_point":f"0x{entry:08X}","bss_address":f"0x{bss_addr:08X}","bss_size":bss_size,"segments":[{k:(f"0x{v:08X}" if k=="vaddr" else v) for k,v in s.items() if k!="blob"} for s in segs]}
    with open(a.manifest,"w") as f: json.dump(manifest,f,indent=2); f.write("\n")
    for s in segs:
        got=hashlib.sha256(out[s["elf_offset"]:s["elf_offset"]+s["size"]]).hexdigest()
        if got!=s["sha256"]: raise SystemExit(f"ELF payload mismatch {s['kind']}{s['index']}")
    print(json.dumps({k:v for k,v in manifest.items() if k!="segments"},indent=2)); print("segments",len(segs))
if __name__=="__main__": main()

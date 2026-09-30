#!/usr/bin/env python3
import argparse, struct

def be32(b,o): return struct.unpack_from(">I",b,o)[0]
def align(v,a): return (v+a-1)&~(a-1)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("dol"); ap.add_argument("elf")
    a=ap.parse_args()
    d=open(a.dol,"rb").read()
    text_off=[be32(d,0x00+i*4) for i in range(7)]
    data_off=[be32(d,0x1c+i*4) for i in range(11)]
    text_addr=[be32(d,0x48+i*4) for i in range(7)]
    data_addr=[be32(d,0x64+i*4) for i in range(11)]
    text_size=[be32(d,0x90+i*4) for i in range(7)]
    data_size=[be32(d,0xac+i*4) for i in range(11)]
    bss_addr=be32(d,0xd8); bss_size=be32(d,0xdc); entry=be32(d,0xe0)
    segs=[]
    for offs,addrs,sizes,flags in ((text_off,text_addr,text_size,5),(data_off,data_addr,data_size,6)):
        for fo,va,sz in zip(offs,addrs,sizes):
            if sz: segs.append((fo,va,sz,flags))
    phnum=len(segs)+(1 if bss_size else 0)
    ehsize=52; phentsize=32; phoff=ehsize
    cursor=align(ehsize+phnum*phentsize,0x20)
    ph=[]; payload=[]
    for fo,va,sz,flags in segs:
        outoff=align(cursor,0x20)
        # Preserve congruence for loader expectations.
        mod=va & 0x1f
        if (outoff & 0x1f)!=mod: outoff += (mod-(outoff&0x1f)) & 0x1f
        ph.append((1,outoff,va,va,sz,sz,flags,0x20))
        payload.append((outoff,d[fo:fo+sz]))
        cursor=outoff+sz
    if bss_size: ph.append((1,0,bss_addr,bss_addr,0,bss_size,6,0x20))
    ident=bytearray(16); ident[:4]=b"\x7fELF"; ident[4]=1; ident[5]=2; ident[6]=1
    hdr=struct.pack(">16sHHIIIIIHHHHHH",bytes(ident),2,20,1,entry,phoff,0,0,ehsize,phentsize,phnum,0,0,0)
    out=bytearray(align(ehsize+phnum*phentsize,0x20))
    out[:len(hdr)]=hdr
    for i,p in enumerate(ph):
        out[phoff+i*phentsize:phoff+(i+1)*phentsize]=struct.pack(">IIIIIIII",*p)
    for off,blob in payload:
        if len(out)<off: out.extend(b"\0"*(off-len(out)))
        end=off+len(blob)
        if len(out)<end: out.extend(b"\0"*(end-len(out)))
        out[off:end]=blob
    open(a.elf,"wb").write(out)
    print(f"ELF entry=0x{entry:08X} phnum={phnum} bytes={len(out)}")

if __name__=="__main__": main()

#!/usr/bin/env python3
"""Prove current-client 0x009B59F0 is the libvpx v1.1.0 VP8 decoder callback.

The historical libvpx v1.1.0 32-bit vpx_codec_iface layout is:
  +0x00 name
  +0x04 abi_version
  +0x08 caps
  +0x0C init
  +0x10 destroy
  +0x14 ctrl_maps
  +0x18 get_mmap
  +0x1C set_mmap
  +0x20 dec.peek_si
  +0x24 dec.get_si
  +0x28 dec.decode
  +0x2C dec.get_frame
  +0x30..0x48 enc.* (7 pointers)

This proof finds the exact current-client string
"WebM Project VP8 Decoder v1.1.0", finds the unique .rdata pointer to it,
interprets the 19-dword interface table, and gates 0x009B59F0 at +0x28.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGET=0x009B59F0
NAME=b"WebM Project VP8 Decoder v1.1.0\x00"
FIELDS=[
 ("name",0x00),("abi_version",0x04),("caps",0x08),("init",0x0C),
 ("destroy",0x10),("ctrl_maps",0x14),("get_mmap",0x18),("set_mmap",0x1C),
 ("dec.peek_si",0x20),("dec.get_si",0x24),("dec.decode",0x28),("dec.get_frame",0x2C),
 ("enc.cfg_maps",0x30),("enc.encode",0x34),("enc.get_cx_data",0x38),
 ("enc.cfg_set",0x3C),("enc.get_glob_hdrs",0x40),("enc.get_preview",0x44),
 ("enc.mr_get_mem_loc",0x48),
]
HISTORICAL={
 "repo":"webmproject/libvpx",
 "ref":"v1.1.0",
 "internal_header":"vpx/internal/vpx_codec_internal.h",
 "internal_header_blob_sha":"0703d6a4f2c02adc6ea8eca7145fcb15819e7e02",
 "decoder_iface":"vp8/vp8_dx_iface.c",
 "decoder_iface_blob_sha":"37773dba5e19dd187080b5188e001249eb17df1e",
}

class E(RuntimeError):pass
def req(c,m):
    if not c: raise E(m)

def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    c=p+4;n=struct.unpack_from("<H",raw,c+2)[0];os=struct.unpack_from("<H",raw,c+16)[0];op=c+20
    base=struct.unpack_from("<I",raw,op+28)[0];so=op+os;ss=[]
    for i in range(n):
        q=so+i*40
        name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
        ss.append(dict(name=name,va=base+rva,rva=rva,rawSize=rs,rawOffset=ro,
                       executable=bool(ch&0x20000000),readable=bool(ch&0x40000000),writable=bool(ch&0x80000000)))
    return base,ss

def containing(ss,va):
    for s in ss:
        if s["va"]<=va<s["va"]+s["rawSize"]: return s
    return None

def read_cstr(raw,ss,va,limit=256):
    s=containing(ss,va);req(s is not None,f"unbacked string VA {va:#x}")
    o=s["rawOffset"]+(va-s["va"]);z=raw.find(b"\0",o,min(len(raw),o+limit));req(z>=0,"unterminated")
    return raw[o:z].decode("ascii","replace")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("exe",type=Path)
    ap.add_argument("--revision",required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    base,ss=pe(raw)

    # Find exact decoder version string.
    positions=[];p=0
    while True:
        j=raw.find(NAME,p)
        if j<0:break
        positions.append(j);p=j+1
    req(len(positions)==1,f"decoder string occurrence count {len(positions)}")
    file_off=positions[0]
    s=next((x for x in ss if x["rawOffset"]<=file_off<x["rawOffset"]+x["rawSize"]),None)
    req(s is not None,"decoder string not in PE section")
    string_va=s["va"]+(file_off-s["rawOffset"])
    req(read_cstr(raw,ss,string_va)==NAME[:-1].decode(),"decoder string mismatch")

    # Find exact dword pointer to string in mapped section bytes.
    ptr=struct.pack("<I",string_va)
    pointer_hits=[]
    for sec in ss:
        data=raw[sec["rawOffset"]:sec["rawOffset"]+sec["rawSize"]]
        pos=0
        while True:
            j=data.find(ptr,pos)
            if j<0:break
            pointer_hits.append({"section":sec["name"],"va":sec["va"]+j,"sectionOffset":j})
            pos=j+1
    req(len(pointer_hits)==1,f"name pointer count {len(pointer_hits)}: {pointer_hits}")
    table_va=pointer_hits[0]["va"]
    table_sec=containing(ss,table_va);req(table_sec is not None,"table unbacked")
    req(table_sec["name"]==".rdata",f"table section {table_sec['name']}")
    to=table_sec["rawOffset"]+(table_va-table_sec["va"])
    req(to+0x4c<=len(raw),"table truncated")

    rows=[]
    for name,off in FIELDS:
        val=struct.unpack_from("<I",raw,to+off)[0]
        row={"field":name,"offset":off,"offsetHex":f"0x{off:02X}","value":val,"valueHex":f"0x{val:08X}"}
        sv=containing(ss,val)
        if sv: row["pointsIntoSection"]=sv["name"]
        rows.append(row)
    vals={r["field"]:r["value"] for r in rows}

    # Exact structural gates from libvpx v1.1.0 decoder initializer.
    req(vals["name"]==string_va,"name field mismatch")
    req(vals["abi_version"]==4,f"unexpected ABI {vals['abi_version']}")
    req(vals["dec.decode"]==TARGET,f"decode slot drift {vals['dec.decode']:#x}")
    for f in ["init","destroy","get_mmap","set_mmap","dec.peek_si","dec.get_si","dec.decode","dec.get_frame"]:
        req(containing(ss,vals[f]) is not None and containing(ss,vals[f])["executable"],f"{f} not executable pointer")
    for f in ["enc.cfg_maps","enc.encode","enc.get_cx_data","enc.cfg_set","enc.get_glob_hdrs","enc.get_preview","enc.mr_get_mem_loc"]:
        req(vals[f]==0,f"decoder encoder-slot {f} is nonzero: {vals[f]:#x}")

    # Capture exact adjacent encoder identification string as independent family context,
    # but do not use it as the decoder identity gate.
    encoder_pat=b"WebM Project VP8 Encoder v1.1.0\x00"
    ep=raw.find(encoder_pat)
    encoder_va=None
    if ep>=0:
        es=next((x for x in ss if x["rawOffset"]<=ep<x["rawOffset"]+x["rawSize"]),None)
        if es: encoder_va=es["va"]+(ep-es["rawOffset"])

    doc={
      "format":"t6-current-client-9b59f0-libvpx-vp8-decoder-identity-v1",
      "authority":"SHA-pinned current-client exact vpx_codec_iface table joined to exact libvpx v1.1.0 source layout",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "historicalLibvpx":HISTORICAL,
      "decoderName":{"text":NAME[:-1].decode(),"va":f"0x{string_va:08X}","section":s["name"],"uniqueOccurrence":True},
      "interfaceTable":{"va":f"0x{table_va:08X}","section":table_sec["name"],"namePointerUnique":True,"fields":rows},
      "target":{"va":f"0x{TARGET:08X}","field":"dec.decode","fieldOffsetHex":"0x28"},
      "adjacentFamilyContext":{"encoderName":encoder_pat[:-1].decode(),"encoderNameVa":f"0x{encoder_va:08X}" if encoder_va else None},
      "summary":{
        "interfaceTableVa":f"0x{table_va:08X}",
        "decoderNameVa":f"0x{string_va:08X}",
        "abiVersion":vals["abi_version"],
        "capsHex":f"0x{vals['caps']:08X}",
        "decodeCallbackVa":f"0x{vals['dec.decode']:08X}",
        "zeroEncoderSlotCount":sum(vals[f]==0 for f in ["enc.cfg_maps","enc.encode","enc.get_cx_data","enc.cfg_set","enc.get_glob_hdrs","enc.get_preview","enc.mr_get_mem_loc"]),
        "identity":"0x009B59F0 is vpx_codec_vp8_dx.dec.decode for embedded libvpx v1.1.0"
      },
      "proofBoundary":"Proves the current-client data-table identity and callback slot exactly. It does not by itself assign every transitive callee of the decode callback to libvpx; those require exact call/dataflow joins from the callback path."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__": main()

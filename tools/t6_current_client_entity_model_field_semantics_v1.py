#!/usr/bin/env python3
"""Promote exact current-client entity 'model' field semantics from raw tables/code.

This proof derives the field definition from the client table at 0x00c77138 and
the switch dispatch at 0x005c2341. It promotes the '*' suffix path only if the
exact 'model' row dispatches to the observed branch and its field offset matches
the branch's dedicated 16-bit store.

It remains current-client authority only and does not claim that a particular
serialized MapEnt source necessarily reaches this parser.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-entity-model-field-semantics-v1"
TABLE_VA=0x00c77138
ROW_BYTES=0x14
TYPE_MAP_VA=0x005c2458
JUMP_TABLE_VA=0x005c2440
MODEL_BRANCH=0x005c23f0

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
      q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
      vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8)
      secs.append((name,ib+rva,rs,ro))
    return ib,secs
def off(secs,va,n=1):
    for name,start,rs,ro in secs:
      if start<=va and va+n<=start+rs:return name,ro+(va-start)
    raise E(f"VA 0x{va:08x}+{n} not raw-backed")
def read(raw,secs,va,n):
    _,o=off(secs,va,n);return raw[o:o+n]
def u32(raw,secs,va):return struct.unpack("<I",read(raw,secs,va,4))[0]
def cstr(raw,secs,va,limit=128):
    name,o=off(secs,va);end=o+limit;b=raw[o:end];z=b.find(b"\0");req(z>=0,f"unterminated string 0x{va:x}")
    return b[:z].decode("ascii","strict")
def bytes_at(raw,secs,va,h):
    b=bytes.fromhex(h);got=read(raw,secs,va,len(b));req(got==b,f"byte gate 0x{va:08x}: {got.hex()} != {h}")
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();digest=hashlib.sha256(raw).hexdigest();req(digest==CLIENT_SHA,f"SHA drift {digest}")
    ib,secs=pe(raw)

    # Freeze the exact table-search / type-dispatch machinery.
    gates={
      0x005c22c7:"8b06",       # row.name pointer
      0x005c22c9:"55",         # current key
      0x005c22ca:"50",         # row.name
      0x005c22cb:"e83041f8ff", # exact compare helper
      0x005c22d7:"83c614",     # next 20-byte field row
      0x005c2341:"8b460c",     # field type at +0x0c
      0x005c2344:"83f811",     # bounded <= 17
      0x005c2349:"0fb68858245c00",
      0x005c2350:"ff248d40245c00",
      0x005c23f0:"803f2a",     # first value byte == '*'
      0x005c23f3:"7516",
      0x005c23f5:"47",         # advance to suffix
      0x005c23f6:"57",
      0x005c23f7:"e81e0c4b00", # base-10 wrapper 0xa7301a
      0x005c23ff:"668983dc000000", # store low16 to entity+0xdc
      0x005c240c:"e80fd2ecff", # legacy xmodel prefix helper 0x48f620
      0x005c2418:"83c707",     # skip "xmodel/" or "xmodel\"
      0x0048f625:"6a06",
      0x0048f627:"68183dc300", # "xmodel"
      0x0048f63c:"3c2f",       # '/'
      0x0048f640:"3c5c",       # '\'
      0x00a73009:"6a0a",       # decimal base 10
      0x00a7300b:"6a00",       # null second arg
      0x00a7300d:"ff7508",     # input suffix
      0x00a73010:"e8354a0000", # converter
      0x00a7301a:"8bff",
      0x00a73020:"e9dfffffff", # thunk to wrapper
    }
    for va,h in gates.items():bytes_at(raw,secs,va,h)
    req(cstr(raw,secs,0x00c33d18)=="xmodel","legacy model literal drift")

    fields=[]
    for i in range(64):
      va=TABLE_VA+i*ROW_BYTES;ptr=u32(raw,secs,va)
      if ptr==0:break
      name=cstr(raw,secs,ptr)
      vals=struct.unpack("<IIIII",read(raw,secs,va,ROW_BYTES))
      fields.append({"index":i,"rowVa":f"0x{va:08x}","name":name,"namePointerVa":f"0x{ptr:08x}",
        "fieldOffset":vals[1],"dword8":vals[2],"fieldType":vals[3],"dword16":vals[4],
        "rawDwords":[f"0x{x:08x}" for x in vals]})
    req(fields,"empty field table")
    models=[x for x in fields if x["name"]=="model"];req(len(models)==1,f"model field rows={len(models)}")
    m=models[0];t=int(m["fieldType"]);req(0<=t<=0x11,f"model field type {t} outside switch")
    selector=read(raw,secs,TYPE_MAP_VA+t,1)[0]
    target=u32(raw,secs,JUMP_TABLE_VA+selector*4)
    req(target==MODEL_BRANCH,f"model dispatch target 0x{target:08x} != 0x{MODEL_BRANCH:08x}")
    req(int(m["fieldOffset"])==0xdc,f"model field offset 0x{m['fieldOffset']:x} != star-store +0xdc")
    type_map=list(read(raw,secs,TYPE_MAP_VA,0x12))
    maxsel=max(type_map);jumps=[u32(raw,secs,JUMP_TABLE_VA+i*4) for i in range(maxsel+1)]
    doc={
      "format":FORMAT,"authority":"SHA-classified current Plutonium client only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":digest,"imageBaseHex":f"0x{ib:08x}"},
      "fieldTable":{"va":f"0x{TABLE_VA:08x}","rowBytes":ROW_BYTES,"rows":fields},
      "modelField":{"row":m,"switchSelector":selector,"dispatchTargetVa":f"0x{target:08x}",
        "starPath":{"compareVa":"0x005c23f0","suffixAdvanceVa":"0x005c23f5","base10WrapperVa":"0x00a7301a",
          "storeVa":"0x005c23ff","store":"low 16 bits of conversion result -> entity + 0xDC"},
        "nonStarPath":{"legacyPrefixHelperVa":"0x0048f620","legacyPrefix":"xmodel/ or xmodel\\",
          "legacyPrefixSkipBytes":7,"modelPathCalls":["0x0040c6c0","0x005594d0"]}},
      "switch":{"typeMapVa":f"0x{TYPE_MAP_VA:08x}","typeMap":type_map,
        "jumpTableVa":f"0x{JUMP_TABLE_VA:08x}","jumpTargets":[f"0x{x:08x}" for x in jumps]},
      "summary":{"fieldDefinitionCount":len(fields),"modelFieldType":t,"modelFieldOffset":m["fieldOffset"],
        "modelDispatchExact":True,"starSuffixBase10PathExact":True,"legacyXmodelPrefixPathExact":True},
      "proofBoundary":"This proves the SHA-classified current client's exact entity key/value field-table entry named 'model' dispatches to a branch where '*' values advance past the star, pass the suffix through a base-10 conversion wrapper, and store the low 16-bit result into the exact model field at entity+0xDC; non-star values have an exact xmodel[/\\] legacy-prefix path. It does not by itself prove which serialized MapEnt/SpawnVar producer invokes this parser, the meaning of the resulting numeric brush-model index beyond this field representation, or historical-retail executable equivalence."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()

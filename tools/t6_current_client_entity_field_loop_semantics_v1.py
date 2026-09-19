#!/usr/bin/env python3
"""Exact current-client proof of the three-argument entity-field loop at 0x005c2280.

The semantic labels are promoted only where current-client dataflow independently
matches the public T6 SpawnVar/entity-field structure: arg1 has a count at +4 and
8-byte (key,value) pairs beginning at +8; arg2 is the entity base; the model
field dispatch is the separately byte-proven specialized branch.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-entity-field-loop-semantics-v1"
START=0x005c2280
END=0x005c2440

GATES={
  0x005c2280:"83ec10",
  0x005c2283:"8b442414",      # arg1
  0x005c2287:"83780400",      # [arg1+4] count
  0x005c228c:"8b5c241c",      # arg2 -> ebx after push ebx
  0x005c2290:"c744240400000000",
  0x005c2298:"0f8e81000000",
  0x005c22a0:"83c008",        # pair cursor = arg1 + 8
  0x005c22bb:"8b7804",        # value = pair[1]
  0x005c22be:"8b28",          # key = pair[0]
  0x005c22c0:"be3871c700",    # exact field table
  0x005c22d7:"83c614",        # 20-byte field rows
  0x005c230d:"8344242808",    # next SpawnVar pair, stride 8
  0x005c2312:"40",
  0x005c2317:"3b4104",        # loop against [arg1+4]
  0x005c231f:"8d9334010000",  # entity + 0x134
  0x005c232c:"8d8340010000",  # entity + 0x140
  0x005c2341:"8b460c",        # field type
  0x005c2344:"83f811",
  0x005c2349:"0fb68858245c00",
  0x005c2350:"ff248d40245c00",
  0x005c23f0:"803f2a",        # model value begins '*'
  0x005c23f5:"47",            # skip '*'
  0x005c23f7:"e81e0c4b00",    # decimal wrapper
  0x005c23ff:"668983dc000000",# low16 -> entity + 0xdc
  0x005c241b:"837c242c00",    # original third argument after saved regs/locals
}
SOURCE_LOCATOR={
 "repository":"builtbyxeno/OpenBO2",
 "commit":"a64812d21946baf710cec7fa26b98ad0d193903b",
 "gameSpawnPath":"src/code/src_noserver/game_mp/g_spawn_mp.cpp",
 "typesPath":"src/code/src_noserver/all_types.h",
 "declaration":"void G_ParseEntityFields(const SpawnVar *spawnVar, gentity_t *ent, int radiant_update)",
 "spawnVarLayout":"bool spawnVarsValid; int numSpawnVars; char *spawnVars[64][2]; int numSpawnVarChars; char spawnVarChars[2048]",
 "authority":"locator/type vocabulary only; current-client bytes below are semantic authority for this proof",
}

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;req(struct.unpack_from("<H",raw,opt)[0]==0x10b,"not PE32")
    ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
      q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
      vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);secs.append((name,ib+rva,rs,ro))
    return ib,secs
def read(raw,secs,va,n):
    for name,start,rs,ro in secs:
      if start<=va and va+n<=start+rs:return name,raw[ro+va-start:ro+va-start+n]
    raise E(f"unbacked VA 0x{va:08x}+{n}")
def gate(raw,secs,va,h):
    b=bytes.fromhex(h);_,got=read(raw,secs,va,len(b));req(got==b,f"0x{va:08x}: {got.hex()} != {h}")
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();digest=hashlib.sha256(raw).hexdigest();req(digest==CLIENT_SHA,f"SHA drift {digest}")
    ib,secs=pe(raw)
    for va,h in GATES.items():gate(raw,secs,va,h)
    sec,blob=read(raw,secs,START,END-START)
    doc={
      "format":FORMAT,"authority":"SHA-classified current Plutonium client semantics; public T6 source is locator/type vocabulary only",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":digest,"imageBaseHex":f"0x{ib:08x}"},
      "sourceLocator":SOURCE_LOCATOR,
      "function":{"startVa":f"0x{START:08x}","endVaExclusive":f"0x{END:08x}","section":sec,
        "bytes":len(blob),"sha256":hashlib.sha256(blob).hexdigest()},
      "arguments":{
        "arg1":{"role":"SpawnVar-shaped key/value set","evidence":[
          {"va":"0x005c2283","operation":"load arg1"},
          {"va":"0x005c2287","operation":"read dword count at arg1+4"},
          {"va":"0x005c22a0","operation":"first pair cursor arg1+8"},
          {"va":"0x005c22bb","operation":"load value pointer at pair+4"},
          {"va":"0x005c22be","operation":"load key pointer at pair+0"},
          {"va":"0x005c230d","operation":"advance pair cursor by 8"},
          {"va":"0x005c2317","operation":"loop index compared to dword count at arg1+4"}]},
        "arg2":{"role":"entity base","register":"ebx","evidence":[
          {"va":"0x005c228c","operation":"load original second stack argument into ebx"},
          {"va":"0x005c231f","operation":"address entity+0x134"},
          {"va":"0x005c232c","operation":"address entity+0x140"},
          {"va":"0x005c23ff","operation":"special model branch writes low16 result to entity+0xdc"}]},
        "arg3":{"role":"mode/radiant_update-shaped flag","evidence":[
          {"va":"0x005c241b","operation":"special non-star model path tests original third stack argument"}]}
      },
      "fieldDispatch":{"tableVa":"0x00c77138","rowBytes":20,"typeOffset":12,
        "modelDispatchVa":"0x005c23f0","modelStarSuffixDecimal":True,"modelDedicatedStoreOffset":220},
      "summary":{"spawnVarCountOffset":4,"spawnVarPairArrayOffset":8,"spawnVarPairStrideBytes":8,
        "entityArgumentIndex":2,"thirdModeArgumentIndex":3,"fieldRowBytes":20,
        "modelStarSuffixDecimalPathExact":True,"modelDedicatedStoreOffset":220},
      "proofBoundary":"This proves the SHA-classified current client's exact three-argument entity-field loop has the independently matching T6 SpawnVar-shaped layout and model dispatch. The public source declaration/layout is used only to name a byte-proven structure. This proof does not yet establish which MapEnt/entityString producer populated a specific SpawnVar instance, that +0xDC is consumed as ClipMap.subModels[N], or historical-retail executable equivalence."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()

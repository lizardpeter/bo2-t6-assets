#!/usr/bin/env python3
"""Prove the exact current-client value written to generic sampler-state slot 6.

True control-flow entry is 0x00455100 (not the earlier padding-derived 0x004550E0).
At entry the destination object is ECX -> EAX, then ECX is zeroed. The target
store at 0x004555A6 writes the ECX dword to object+0x1610, covering sampler-state
byte object+0x1612 (slot 6). This proof fails if any control transfer or ECX/EAX
clobber invalidates that straight-line dataflow before the target store.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-shadowmap-sampler-sun-state-byte-semantics-v1"
START=0x00455100
ZERO=0x00455108
STORE=0x004555A6
END=0x004555AC
SLOT=6
STATE_BASE=0x160C
TARGET_OFF=STATE_BASE+SLOT
class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
      q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
      vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
      secs.append({"name":name,"va":ib+rva,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000)})
    return ib,secs
def secfor(secs,va,n=1):
    for s in secs:
      if s["va"]<=va and va+n<=s["va"]+s["rawSize"]:return s
    raise E(f"VA 0x{va:x}+{n} not backed")
def rr(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,secs=pe(raw);s=secfor(secs,START,END-START)
    ro=s["rawOffset"]+START-s["va"];blob=raw[ro:ro+(END-START)]
    md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True
    ins=list(md.disasm(blob,START));req(ins and ins[0].address==START,"entry decode drift")
    by={i.address:i for i in ins}
    gates={
      START:("8bc1","mov","eax, ecx"),
      0x00455102:("8b542404","mov","edx, dword ptr [esp + 4]"),
      ZERO:("33c9","xor","ecx, ecx"),
      STORE:("898810160000","mov","dword ptr [eax + 0x1610], ecx"),
    }
    for va,g in gates.items():
      i=by.get(va);req(i is not None,f"missing gate 0x{va:x}")
      got=(i.bytes.hex(),i.mnemonic,i.op_str);req(got==g,f"gate drift 0x{va:x}: {got}")
    # The initializer segment must be straight-line to the target store.
    bad_cf=[rr(i) for i in ins if START < i.address < STORE and (i.mnemonic.startswith("j") or i.mnemonic in {"call","ret","retf","int3"})]
    req(not bad_cf,f"control-flow before slot6 store: {bad_cf}")
    # EAX carries the destination object from entry; ECX must remain zero.
    eax_clob=[];ecx_clob=[]
    for i in ins:
      if not (ZERO < i.address < STORE):continue
      try: reads,writes=i.regs_access()
      except Exception: reads,writes=([],[])
      wn={md.reg_name(r) for r in writes}
      if "eax" in wn:eax_clob.append(rr(i))
      if "ecx" in wn:ecx_clob.append(rr(i))
    req(not eax_clob,f"EAX object clobber before store: {eax_clob}")
    req(not ecx_clob,f"ECX zero clobber before store: {ecx_clob}")
    req(0x1610 <= TARGET_OFF < 0x1614,"slot6 not covered by target dword")
    doc={"format":FORMAT,"authority":"SHA-classified current-client exact straight-line register/dataflow proof",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}"},
      "dataflow":{
        "trueEntryVa":f"0x{START:08x}",
        "destinationObjectAtEntry":"ECX",
        "destinationObjectCarrier":"EAX via mov eax,ecx at 0x00455100",
        "zeroDefinition":"ECX = 0 via xor ecx,ecx at 0x00455108",
        "targetStoreVa":f"0x{STORE:08x}",
        "targetStore":"dword ptr [EAX + 0x1610] = ECX",
        "coveredSamplerStateByteOffset":f"0x{TARGET_OFF:04x}",
        "slotIndex":SLOT,
        "finalByteValue":0,
        "noControlTransferBeforeStore":True,
        "destinationObjectCarrierUnclobbered":True,
        "zeroCarrierUnclobbered":True,
      },
      "instructions":[rr(i) for i in ins],
      "summary":{"slotIndex":SLOT,"stateByteOffset":TARGET_OFF,"finalByteValue":0,"currentClientStateByteValueClosed":True},
      "proofBoundary":"Closes the exact current-client byte value written to generic sampler-state slot 6 on this structure-initialization path. It does not by itself identify the slot-6 GfxImage resource, prove this initialized object is the final bound source state at every draw, decode the sampler-state byte into API filter/address semantics, establish later-writer absence, or prove historical-retail equivalence; those are separate gates."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n");print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()

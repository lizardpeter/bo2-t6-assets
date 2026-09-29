#!/usr/bin/env python3
"""Prove that the observed 0x00455100 initializer object is incompatible with
T6's accepted current-client GfxCmdBufSourceState code-constant layout.

This is intentionally occurrence-scoped. It combines:
  * exact SHA-pinned 0x00455100 machine instructions,
  * the retained current-client source-state constant-cache layout
      source + 0x800 + enum*16 + lane*4,
  * exact current-client static accessor/enum identities.

The observed object writes self-relative pointers into offsets that, if the
object were the generic renderer source state, are typed float4 code-constant
lanes (sunDiffuse, lightingLookupScale, debugBumpmap, fogConsts2).

That is a structural type/layout contradiction for the two proven direct-call
occurrences. It does not exclude a hypothetical unobserved indirect call to
0x00455100 with an object of a different type.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
START=0x00455100
END=0x00455613
VALUE_BASE=0x800
VALUE_STRIDE=16

GATES={
  0x0045522E:("lea","edx, [eax + 0x6a8]"),
  0x00455234:("mov","dword ptr [edx + 0x400], edx"),
  0x0045523A:("mov","dword ptr [eax + 0xab8], edx"),
  0x00455240:("mov","dword ptr [eax + 0xabc], edx"),
  0x0045525E:("mov","edx, dword ptr [edx + 0x400]"),
  0x00455264:("mov","dword ptr [eax + 0xac4], edx"),
  0x0045529C:("lea","edx, [eax + 0xae8]"),
  0x004552A2:("mov","dword ptr [edx + 0x20], edx"),
  0x004555A6:("mov","dword ptr [eax + 0x1610], ecx"),
}

# Each conflict stores a self-relative pointer into a location that the accepted
# source-state contract classifies as one lane of float consts[enum][4].
CONFLICTS=[
  dict(storeVa=0x00455234,destOffset=0xAA8,valueOffset=0x6A8,enumValue=42,lane=2),
  dict(storeVa=0x0045523A,destOffset=0xAB8,valueOffset=0x6A8,enumValue=43,lane=2),
  dict(storeVa=0x00455240,destOffset=0xABC,valueOffset=0x6A8,enumValue=43,lane=3),
  dict(storeVa=0x00455264,destOffset=0xAC4,valueOffset=0x6A8,enumValue=44,lane=1),
  dict(storeVa=0x004552A2,destOffset=0xB08,valueOffset=0xAE8,enumValue=48,lane=2),
]
EXPECTED_ACCESSORS={
  42:("sunDiffuse","CONST_SRC_CODE_SUN_DIFFUSE"),
  43:("lightingLookupScale","CONST_SRC_CODE_LIGHTING_LOOKUP_SCALE"),
  44:("debugBumpmap","CONST_SRC_CODE_DEBUG_BUMPMAP"),
  48:("fogConsts2","CONST_SRC_CODE_FOG2"),
}

class ProofError(RuntimeError): pass
def req(c,m):
    if not c: raise ProofError(m)

def parse_pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0]
    req(raw[p:p+4]==b"PE\0\0","bad PE signature")
    coff=p+4
    n=struct.unpack_from("<H",raw,coff+2)[0]
    os=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20
    base=struct.unpack_from("<I",raw,opt+28)[0]
    so=opt+os
    secs=[]
    for i in range(n):
        q=so+i*40
        name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8)
        secs.append(dict(name=name,va=base+rva,rawSize=rs,rawOffset=ro))
    return base,secs
def sec_for(secs,va):
    for s in secs:
        if s["va"]<=va<s["va"]+s["rawSize"]: return s
    raise ProofError(f"unbacked VA 0x{va:08X}")
def row(i):
    return {"address":f"0x{i.address:08X}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("exe",type=Path)
    ap.add_argument("--revision",required=True)
    ap.add_argument("--initializer-proof",type=Path,required=True)
    ap.add_argument("--layout-proof",type=Path,required=True)
    ap.add_argument("--input-table-proof",type=Path,required=True)
    ap.add_argument("--object-proof",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()

    raw=a.exe.read_bytes()
    dg=hashlib.sha256(raw).hexdigest()
    req(dg==SHA,f"SHA drift {dg}")

    base,secs=parse_pe(raw)
    s=sec_for(secs,START)
    req(sec_for(secs,END-1)["name"]==s["name"],"initializer crosses section")
    ro=s["rawOffset"]+START-s["va"]
    blob=raw[ro:ro+(END-START)]
    md=Cs(CS_ARCH_X86,CS_MODE_32)
    ins=list(md.disasm(blob,START))
    by={i.address:i for i in ins}

    gated=[]
    for va,(mn,op) in GATES.items():
        i=by.get(va)
        req(i is not None,f"missing instruction 0x{va:08X}")
        req(i.mnemonic==mn and i.op_str==op,
            f"instruction drift 0x{va:08X}: {i.mnemonic} {i.op_str}")
        gated.append(row(i))

    init=load_json(a.initializer_proof)
    layout=load_json(a.layout_proof)
    table=load_json(a.input_table_proof)
    obj=load_json(a.object_proof)

    req(init["client"]["sha256"]==SHA,"initializer proof SHA drift")
    req(init["function"]["startVa"].lower()=="0x00455100","initializer proof start drift")
    req(init["summary"]["directCallerCount"]==2,"initializer direct-caller denominator drift")
    req(init["summary"]["slot4PackedWriteVa"].lower()=="0x004555a6","slot4 write drift")

    req(layout["format"]=="t6-current-client-light-block-provider-semantics-v1","layout proof format drift")
    # This retained proof explicitly records the independently proven source-state formulas.
    ss=layout["provider"]["sourceStateBase"]
    req(ss["independentValueLayout"]=="source + 0x800 + enum*16","value layout drift")
    req(ss["independentVersionLayout"]=="source + 0x17E0 + enum*2","version layout drift")

    req(table["client"]["sha256"]==SHA,"input table proof SHA drift")
    rows={int(x["enumValue"]):x for x in table["constants"]["rows"]}
    for ev,(acc,sym) in EXPECTED_ACCESSORS.items():
        q=rows.get(ev)
        req(q is not None,f"missing enum {ev}")
        req(q["status"]=="unique-exact-row",f"enum {ev} not unique exact")
        req(q["accessor"]==acc and q["enumSymbol"]==sym,
            f"enum {ev} identity drift: {q.get('accessor')} {q.get('enumSymbol')}")

    req(obj["client"]["sha256"]==SHA,"object proof SHA drift")
    req(obj["convergence"]["sameObjectFieldProven"] is True,"object convergence no longer proven")
    req(obj["convergence"]["ownerFieldOffset"].lower()=="0x5dac","object field offset drift")

    outrows=[]
    for c in CONFLICTS:
        expected=VALUE_BASE+c["enumValue"]*VALUE_STRIDE+c["lane"]*4
        req(expected==c["destOffset"],
            f"offset arithmetic drift for enum {c['enumValue']} lane {c['lane']}: {expected:x}")
        ident=rows[c["enumValue"]]
        outrows.append({
          "storeVa":f"0x{c['storeVa']:08X}",
          "destinationOffset":f"0x{c['destOffset']:X}",
          "storedValue":"self-relative pointer",
          "storedValueExpression":f"self+0x{c['valueOffset']:X}",
          "sourceStateInterpretation":{
            "formula":"source + 0x800 + enum*16 + lane*4",
            "enumValue":c["enumValue"],
            "lane":c["lane"],
            "accessor":ident["accessor"],
            "enumSymbol":ident["enumSymbol"],
            "staticIdentityStatus":ident["status"],
            "typedRole":"float4 code-constant lane",
          },
          "contradiction":"Observed object stores a self-relative pointer where accepted renderer source-state layout requires a code-constant float lane.",
        })

    doc={
      "format":"t6-current-client-initializer-source-state-incompatibility-v1",
      "authority":"SHA-pinned current-client machine code + accepted current-client source-state constant-cache layout + exact static code-input identities + exact direct-caller object convergence",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{base:08X}"},
      "initializer":{
        "startVa":"0x00455100","endVaExclusive":"0x00455613",
        "samplerOverlapWriteVa":"0x004555A6",
        "decodedDirectCallerCount":2,
        "observedDirectCallerObject":"same owner-relative field [owner+0x5DAC], proven by object-provenance v2",
      },
      "acceptedSourceStateContract":{
        "constantValueFormula":"source + 0x800 + enum*16 + lane*4",
        "constantVersionFormula":"source + 0x17E0 + enum*2",
        "samplerStateBaseOffset":"0x160C",
        "slot4PackedOverlapOffset":"0x1610",
      },
      "gatedInstructions":gated,
      "conflicts":outrows,
      "summary":{
        "conflictCount":len(outrows),
        "distinctConflictingEnums":sorted({x["sourceStateInterpretation"]["enumValue"] for x in outrows}),
        "allConflictRowsUseUniqueExactStaticIdentity":all(x["sourceStateInterpretation"]["staticIdentityStatus"]=="unique-exact-row" for x in outrows),
        "directObservedInitializerOccurrencesStructurallyIncompatibleWithGenericSourceState":True,
        "samplerOverlapInstructionHasAcceptedDirectSourceStateOccurrence":False,
      },
      "conclusion":(
        "For both decoded direct calls to 0x00455100, the passed object is structurally incompatible "
        "with the accepted current-client GfxCmdBufSourceState code-constant layout. Therefore the "
        "observed direct occurrences of 0x004555A6 cannot be admitted to the generic sampler-source "
        "writer denominator merely because they write +0x1610."
      ),
      "proofBoundary":(
        "This proof excludes the two decoded direct-call occurrences of 0x00455100/0x004555A6 from "
        "the accepted GfxCmdBufSourceState sampler-writer denominator. It does not prove that an "
        "unobserved indirect call can never invoke 0x00455100 with a different object. Accordingly "
        "the instruction has no accepted source-state occurrence, rather than a universal claim that "
        "the instruction could never operate on such an object."
      ),
      "sources":{
        "initializerProof":str(a.initializer_proof),
        "layoutProof":str(a.layout_proof),
        "inputTableProof":str(a.input_table_proof),
        "objectProof":str(a.object_proof),
      },
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))

if __name__=="__main__": main()

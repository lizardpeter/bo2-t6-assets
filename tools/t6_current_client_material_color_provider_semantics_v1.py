#!/usr/bin/env python3
"""Promote exact current-client materialColor runtime provider semantics.

Joins:
- exact render-command table identity for RC_SET_CUSTOM_CONSTANT and RC_SET_MATERIAL_COLOR;
- exact bounded current-client handler disassembly;
- exact retained-special static code-input identity for materialColor enum 46.

The generic custom-constant handler derives the current-client const-value/version
array bases. materialColor is promoted only if all four fixed float destinations
and its version destination equal enum 46 under those exact strides.
"""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path

FORMAT="t6-current-client-material-color-provider-semantics-v1"
PROBE_FORMAT="t6-current-client-custom-constant-and-material-color-handlers-v1"
TABLE_FORMAT="t6-current-client-render-command-table-locator-v1"
STATIC_FORMAT="t6-retail-special-omitted-code-input-static-identity-v1"
CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
ENUM=46

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def load(p:Path):return json.loads(p.read_text())
def sha(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()
def by_addr(r):
    return {int(x["address"],16):x for x in r["instructions"]}
def imm_hex(op:str)->int:
    m=re.search(r"0x([0-9a-fA-F]+)",op)
    if not m:raise E(f"no hex immediate in {op!r}")
    return int(m.group(1),16)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--probe",type=Path,required=True)
    ap.add_argument("--command-table",type=Path,required=True)
    ap.add_argument("--static-inputs",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    p=load(a.probe);t=load(a.command_table);s=load(a.static_inputs)
    req(p.get("format")==PROBE_FORMAT,"probe format drift")
    req(t.get("format")==TABLE_FORMAT,"table format drift")
    req(s.get("format")==STATIC_FORMAT,"static format drift")
    req(p["client"]["sha256"]==CLIENT_SHA and t["client"]["sha256"]==CLIENT_SHA,"client SHA drift")

    tables=t.get("functionTableCandidates",[])
    req(len(tables)>=1,"no render-command table")
    good=[]
    for tb in tables:
        h={int(x["index"]):x for x in tb.get("handlers",[])}
        if h.get(1,{}).get("name")=="RC_SET_CUSTOM_CONSTANT" and h.get(1,{}).get("va")=="0x00745b70" and h.get(2,{}).get("name")=="RC_SET_MATERIAL_COLOR" and h.get(2,{}).get("va")=="0x00745bc0":
            good.append(tb)
    req(len(good)==1,f"exact render-command table matches={len(good)}")

    sr=[x for x in s.get("rows",[]) if x.get("accessor")=="materialColor"]
    req(len(sr)==1,f"materialColor static rows={len(sr)}")
    si=sr[0]
    req(si.get("enumSymbol")=="CONST_SRC_CODE_MATERIAL_COLOR","enum symbol drift")
    req(int(si.get("enumValue"))==ENUM,"enum value drift")
    req(si.get("sourceClass")=="constant","source class drift")
    req(si.get("currentClientStatus")=="unique-exact-row","static row not unique")

    ranges={x["label"]:x for x in p["ranges"]}
    req(set(ranges)=={"customConstant","materialColor"},"handler population drift")
    cc=by_addr(ranges["customConstant"]);mc=by_addr(ranges["materialColor"])

    # Freeze the exact generic index/value/version machinery.
    gates={
      0x00745b86:("mov","ecx, dword ptr [esi + 4]"),
      0x00745b8c:("mov","eax, ecx"),
      0x00745b8e:("shl","eax, 4"),
      0x00745b91:("add","eax, 0x3a37300"),
      0x00745b96:("fstp","dword ptr [eax]"),
      0x00745b9b:("fstp","dword ptr [eax + 4]"),
      0x00745ba1:("fstp","dword ptr [eax + 8]"),
      0x00745ba7:("fstp","dword ptr [eax + 0xc]"),
      0x00745baa:("inc","word ptr [ecx*2 + 0x3a382e0]"),
      0x00745bb4:("movzx","ecx, word ptr [eax]"),
      0x00745bb7:("add","ecx, eax"),
      0x00745bb9:("mov","dword ptr [edi], ecx"),
    }
    for va,(mn,op) in gates.items():
        r=cc.get(va);req(r is not None and r["mnemonic"]==mn and r["opStr"]==op,f"custom gate drift 0x{va:x}: {r}")
    value_base=imm_hex(cc[0x00745b91]["opStr"])
    version_base=imm_hex(cc[0x00745baa]["opStr"])
    req(value_base==0x3a37300 and version_base==0x3a382e0,"generic base drift")

    # Freeze fixed materialColor transfers and command advance.
    expected=[
      (0x00745bd6,"movss","xmm0, dword ptr [esi + 4]",0x00745bdb,"dword ptr [0x3a375e0], xmm0"),
      (0x00745be3,"movss","xmm0, dword ptr [esi + 8]",0x00745be8,"dword ptr [0x3a375e4], xmm0"),
      (0x00745bf0,"movss","xmm0, dword ptr [esi + 0xc]",0x00745bf5,"dword ptr [0x3a375e8], xmm0"),
      (0x00745bfd,"movss","xmm0, dword ptr [esi + 0x10]",0x00745c09,"dword ptr [0x3a375ec], xmm0"),
    ]
    dests=[]
    src_offsets=[]
    for lva,lmn,lop,sva,sop in expected:
        lr=mc.get(lva);sr2=mc.get(sva)
        req(lr is not None and lr["mnemonic"]==lmn and lr["opStr"]==lop,f"load drift 0x{lva:x}")
        req(sr2 is not None and sr2["mnemonic"]=="movss" and sr2["opStr"]==sop,f"store drift 0x{sva:x}")
        src_offsets.append(int(re.search(r"\+ (0x[0-9a-f]+|[0-9]+)\]",lop).group(1),0))
        dests.append(imm_hex(sop))
    expected_dests=[value_base+ENUM*16+i*4 for i in range(4)]
    req(dests==expected_dests,f"materialColor destinations {dests} != enum46 {expected_dests}")
    version_addr=imm_hex(mc[0x00745c02]["opStr"])
    req(mc[0x00745c02]["mnemonic"]=="inc","material version op drift")
    req(version_addr==version_base+ENUM*2,f"material version addr 0x{version_addr:x}")
    for va,mn,op in [
      (0x00745c11,"mov","eax, dword ptr [edi]"),
      (0x00745c13,"movzx","ecx, word ptr [eax]"),
      (0x00745c16,"add","ecx, eax"),
      (0x00745c18,"mov","dword ptr [edi], ecx")]:
        r=mc.get(va);req(r is not None and r["mnemonic"]==mn and r["opStr"]==op,f"command advance drift 0x{va:x}")

    doc={
      "format":FORMAT,
      "authority":"SHA-classified current-client exact render-command table + handler dataflow + exact retained-special static code-input identity",
      "client":p["client"],
      "runtimeInput":{
        "accessor":"materialColor","enumSymbol":"CONST_SRC_CODE_MATERIAL_COLOR","enumValue":ENUM,
        "sourceClass":"constant","updateFrequency":si["updateFrequency"],
        "retainedSpecialOccurrences":si["totalOccurrences"],
        "currentClientStaticRowVa":si["currentClientStaticRowVa"],
      },
      "genericConstantStorage":{
        "valueBaseVa":f"0x{value_base:08x}","valueStrideBytes":16,
        "versionBaseVa":f"0x{version_base:08x}","versionStrideBytes":2,
        "indexSource":"RC_SET_CUSTOM_CONSTANT command dword at +4",
      },
      "materialColorProvider":{
        "renderCommand":"RC_SET_MATERIAL_COLOR","renderCommandIndex":2,"handlerVa":"0x00745bc0",
        "commandColorSourceOffsets":src_offsets,
        "componentCount":4,
        "destinationValueVas":[f"0x{x:08x}" for x in dests],
        "destinationValueIndex":ENUM,
        "versionVa":f"0x{version_addr:08x}","versionIndex":ENUM,
        "incrementsVersion":True,"advancesCommandByLeadingUint16Size":True,
      },
      "lineageDifference":{
        "note":"Pinned OpenBO2 locator source writes only three materialColor components in its loop, while the SHA-classified current client exact handler writes four. Current-client byte semantics are authoritative for this proof; the source-lineage loop is not substituted."
      },
      "sources":{
        "handlerProbe":{"path":str(a.probe),"sha256":sha(a.probe)},
        "renderCommandTable":{"path":str(a.command_table),"sha256":sha(a.command_table)},
        "retainedSpecialStaticInputs":{"path":str(a.static_inputs),"sha256":sha(a.static_inputs)},
      },
      "summary":{
        "currentClientProviderClosed":True,"componentCount":4,"enumValue":ENUM,
        "valueAddressRelationExact":True,"versionAddressRelationExact":True,"commandAdvanceExact":True,
      },
      "proofBoundary":"Closes materialColor provider semantics for the SHA-classified current client: command source offsets, all four float writes, exact code-constant index 46 destinations, version increment, and command-stream advance. It does not by itself prove historical-retail executable equivalence, the producer that enqueues RC_SET_MATERIAL_COLOR, or the draw-time materialColor values for every retained scene."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()

#!/usr/bin/env python3
"""Close current-client providers for shadowmapSamplerSpot (7) and attenuationSampler (15).

This is a proof join across independent exact evidence:
- generic CODE_PIXEL_SAMPLER runtime array semantics (+0x1530/+0x160C);
- exact retained-special accessor/enum denominator;
- exact light-writer provider proof establishing EBX as source-state and EBP as
  the selected 0x160-byte runtime record at the sole 0x786210 caller;
- exact current-client slot-pair instruction census.

Higher-level names for raw record fields remain deliberately unresolved.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FMT="t6-current-client-shadow-spot-attenuation-sampler-provider-semantics-v1"
ARR_FMT="t6-current-client-code-pixel-sampler-array-semantics-v1"
LIGHT_FMT="t6-current-client-light-block-provider-semantics-v1"
PAIR_FMT="t6-current-client-code-sampler-slot-pair-locator-v1"
DEN_FMT="t6-retail-special-omitted-code-input-static-identity-v1"
SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"

def load(p:Path): return json.loads(p.read_text())
def sh(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()
def req(c,m):
    if not c: raise SystemExit(m)
def one(rows,acc,img_addr,state_addr):
    rr=[x for x in rows if x.get("accessor")==acc
        and x.get("imageWrite",{}).get("instruction",{}).get("address")==img_addr
        and x.get("samplerStateWrite",{}).get("instruction",{}).get("address")==state_addr]
    req(len(rr)==1,f"{acc}: exact slot-pair count {len(rr)}")
    return rr[0]
def denrow(d,acc,enum):
    rr=[x for x in d["rows"] if x["accessor"]==acc]
    req(len(rr)==1,f"{acc}: denominator row count {len(rr)}")
    r=rr[0]; req(int(r["enumValue"])==enum,f"{acc}: enum drift {r['enumValue']}")
    req(r["sourceClass"]=="sampler",f"{acc}: source class {r['sourceClass']}")
    return r
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--array",type=Path,required=True)
    ap.add_argument("--light-provider",type=Path,required=True)
    ap.add_argument("--slot-pairs",type=Path,required=True)
    ap.add_argument("--denominator",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    arr,light,pairs,den=map(load,[a.array,a.light_provider,a.slot_pairs,a.denominator])
    req(arr.get("format")==ARR_FMT,"array format drift")
    req(light.get("format")==LIGHT_FMT,"light provider format drift")
    req(pairs.get("format")==PAIR_FMT,"slot-pair format drift")
    req(den.get("format")==DEN_FMT,"denominator format drift")
    req(arr["client"]["sha256"]==light["client"]["sha256"]==pairs["client"]["sha256"]==SHA,"client SHA disagreement")
    req(arr["summary"].get("arrayContractClosed") is True,"generic sampler array not closed")
    req(arr["summary"]["codeImagesBaseOffset"]==0x1530,"codeImages base drift")
    req(arr["summary"]["codeImageSamplerStatesBaseOffset"]==0x160c,"sampler-state base drift")
    req(light["summary"].get("currentClientProviderClosed") is True,"source-state/light provider proof not closed")
    ss=light["provider"]["sourceStateBase"]
    req(ss["callerFirstStackArgumentToEBX"]=="0x00786964","EBX source-state provenance drift")
    req(ss["EBXToWriterESI"]=="0x00786a72","EBX->ESI handoff drift")
    rec=light["provider"]["selectedRuntimeRecord"]
    req(rec["baseExpressionInstruction"]=="0x0078698f","selected record EBP provenance drift")
    req(int(rec["indexScaleBytes"])==0x160,"selected record stride drift")

    spot=one(pairs["rows"],"shadowmapSamplerSpot","0x00786a2e","0x00786a4f")
    atten=one(pairs["rows"],"attenuationSampler","0x00786221","0x00786227")
    ds=denrow(den,"shadowmapSamplerSpot",7)
    da=denrow(den,"attenuationSampler",15)

    req(spot["imageWrite"]["disp"]==0x154c and spot["samplerStateWrite"]["disp"]==0x1613,"slot7 offsets drift")
    req(atten["imageWrite"]["disp"]==0x156c and atten["samplerStateWrite"]["disp"]==0x161b,"slot15 offsets drift")
    req(spot["imageWrite"]["instruction"]["opStr"].lower()=="dword ptr [ebx + 0x154c], eax","slot7 image write drift")
    req(spot["samplerStateWrite"]["instruction"]["opStr"].lower()=="byte ptr [ebx + 0x1613], 0x65","slot7 state write drift")
    req(atten["imageWrite"]["instruction"]["opStr"].lower()=="dword ptr [esi + 0x156c], eax","slot15 image write drift")
    req(atten["samplerStateWrite"]["instruction"]["opStr"].lower()=="byte ptr [esi + 0x161b], 0x13","slot15 state write drift")

    # Exact caller dataflow around slot7 and the call into 0x786210 must all exist in spot context.
    ctx={x["address"]:x for x in spot["context"]}
    req(rec.get("auxPointerSource")=="record + 0x150 -> caller local -> writer EAX -> [EAX+4]","selected record aux-pointer provenance drift")
    required={
      "0x007869e8":"edx, dword ptr [ebp + 0x3c]",
      "0x007869eb":"edx, edx, 0x1e0",
      "0x007869f1":"edx, [edx + ecx + 0x48b670]",
      "0x00786a28":"eax, dword ptr [edx + 0x1bc]",
      "0x00786a65":"eax, dword ptr [esp + 0x14]",
      "0x00786a70":"edi, ebp",
      "0x00786a72":"esi, ebx",
      "0x00786a74":"0x786210",
    }
    for addr,op in required.items():
        req(addr in ctx and ctx[addr]["opStr"].lower()==op.lower(),f"slot7/caller gate drift {addr}: {ctx.get(addr)}")

    # Exact 0x786210 entry: incoming EAX is dereferenced at +4 before slot15 write.
    actx={x["address"]:x for x in atten["context"]}
    req(actx.get("0x00786216",{}).get("opStr","").lower()=="eax, dword ptr [eax + 4]","slot15 image source dereference drift")
    req(actx.get("0x0078621f",{}).get("opStr","").lower()=="0x78622e","slot15 null branch drift")

    inputs=[
      {
        "accessor":"shadowmapSamplerSpot","enumSymbol":ds["enumSymbol"],"enumValue":7,
        "sourceClass":"sampler","updateFrequency":ds["updateFrequency"],
        "retainedSpecialOccurrences":ds["totalOccurrences"],
        "provider":{
          "sourceStateRegister":"EBX",
          "codeImageSlot":{"offset":0x154c,"formula":"source + 0x1530 + 7*4","writerVa":"0x00786a2e"},
          "samplerStateSlot":{"offset":0x1613,"formula":"source + 0x160C + 7","writerVa":"0x00786a4f","exactByte":0x65},
          "imageSource":{
            "selectedRecord":"EBP = 0x4751D0 + source[0x1644] + callerIndex*0x160",
            "secondaryIndex":"uint32(selectedRecord+0x3C)",
            "secondaryRecord":"0x48B670 + source[0x1644] + secondaryIndex*0x1E0",
            "imagePointer":"uint32(secondaryRecord+0x1BC)"
          }
        }
      },
      {
        "accessor":"attenuationSampler","enumSymbol":da["enumSymbol"],"enumValue":15,
        "sourceClass":"sampler","updateFrequency":da["updateFrequency"],
        "retainedSpecialOccurrences":da["totalOccurrences"],
        "provider":{
          "sourceStateRegister":"ESI (exact EBX->ESI at 0x00786A72)",
          "codeImageSlot":{"offset":0x156c,"formula":"source + 0x1530 + 15*4","writerVa":"0x00786221"},
          "samplerStateSlot":{"offset":0x161b,"formula":"source + 0x160C + 15","writerVa":"0x00786227","exactByte":0x13},
          "imageSource":{
            "auxPointer":"uint32(selectedRecord+0x150), saved by caller and restored to EAX at 0x00786A65",
            "imagePointer":"uint32(auxPointer+4) at 0x00786216"
          }
        }
      }
    ]
    doc={
      "format":FMT,
      "authority":"SHA-classified current-client generic code-sampler resolver + exact source-state/runtime-record provenance + exact slot writers",
      "client":arr["client"],"runtimeInputs":inputs,
      "summary":{"currentClientProviderClosed":True,"runtimeInputCount":2,
        "retainedSpecialOccurrenceCount":sum(int(x["retainedSpecialOccurrences"]) for x in inputs),
        "genericSamplerArrayContractClosed":True,"sourceStateBaseClosed":True,
        "slot7ProviderClosed":True,"slot15ProviderClosed":True},
      "sources":{
        "array":{"path":str(a.array),"sha256":sh(a.array),"format":ARR_FMT},
        "lightProvider":{"path":str(a.light_provider),"sha256":sh(a.light_provider),"format":LIGHT_FMT},
        "slotPairs":{"path":str(a.slot_pairs),"sha256":sh(a.slot_pairs),"format":PAIR_FMT},
        "denominator":{"path":str(a.denominator),"sha256":sh(a.denominator),"format":DEN_FMT},
      },
      "proofBoundary":"Closes SHA-classified current-client provider mechanics for shadowmapSamplerSpot and attenuationSampler: exact codeSampler enum identity, generic runtime array contract, source-state base, source-record provenance, image-pointer source offsets, slot writes, and sampler-state bytes are all proven. Higher-level physical names/units for raw runtime-record fields, meaning of sampler-state byte encodings, historical-retail executable equivalence, universal draw-time resources, and framebuffer equivalence remain unproven."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()

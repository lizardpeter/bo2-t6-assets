#!/usr/bin/env python3
"""Promote the current-client generic T6 code-pixel-sampler array contract.

Joins two independent authorities without borrowing runtime values from source:
1) pinned OAT T6 asset definition:
   - MTL_ARG_CODE_PIXEL_SAMPLER == 4
   - MaterialShaderArgument union u follows 8 bytes of fixed fields.
2) SHA-classified current client:
   - exact type==4 dispatch;
   - exact +8 advance to the union/codeSampler dword;
   - exact generic indexed reads:
       image = source[index*4 + 0x1530]
       state = source[index + 0x160C]

The OAT source defines serialized type vocabulary/layout only. The runtime array
offsets and lookup behavior are current-client proof.
"""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path

FMT="t6-current-client-code-pixel-sampler-array-semantics-v1"
LOC_FMT="t6-current-client-code-image-array-layout-locator-v1"
OAT_COMMIT="9dca965366541504b71fa8cfb7ac049cb9b717e1"

def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def req(c,m):
    if not c:raise SystemExit(m)
def by_addr(rows):
    out={}
    for x in rows:out[x["address"].lower()]=x
    return out
def check_generic(hit,expected_image_addr,expected_state_addr):
    ins=hit["contextBefore"]+[hit["instruction"]]+hit["contextAfter"]
    m=by_addr(ins)
    req(hit["instruction"]["address"].lower()==expected_image_addr.lower(),"generic image address drift")
    req(expected_state_addr.lower() in m,f"missing generic state read {expected_state_addr}")
    img=hit["instruction"];st=m[expected_state_addr.lower()]
    req("+ eax*4 + 0x1530]" in img["opStr"].lower(),"image indexed lookup drift")
    req("+ eax + 0x160c]" in st["opStr"].lower(),"state indexed lookup drift")
    # Require type-4 dispatch and +8 advance / u.codeSampler dword load in local window.
    type4=[x for x in ins if x["mnemonic"]=="cmp" and "word ptr" in x["opStr"].lower() and x["opStr"].lower().endswith(", 4")]
    add8=[x for x in ins if x["mnemonic"] in {"add","lea"} and (" 8" in x["opStr"].lower() or "+ 8]" in x["opStr"].lower())]
    req(type4,f"{expected_image_addr}: no exact type==4 gate in context")
    req(add8,f"{expected_image_addr}: no +8 union advance in context")
    return {"imageRead":img,"stateRead":st,"type4Gates":type4,"unionAdvanceCandidates":add8}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--layout-proof",type=Path,required=True)
    ap.add_argument("--t6-assets-header",type=Path,required=True)
    ap.add_argument("--oat-commit",required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    req(a.oat_commit==OAT_COMMIT,f"OAT commit drift {a.oat_commit}")
    loc=load(a.layout_proof);req(loc.get("format")==LOC_FMT,"locator format drift")
    src=a.t6_assets_header.read_text(errors="strict")
    enum=re.search(r"MTL_ARG_CODE_PIXEL_SAMPLER\s*=\s*(0x[0-9a-fA-F]+|\d+)",src)
    req(enum and int(enum.group(1),0)==4,"pinned T6 code pixel sampler enum is not 4")
    # Serialized struct fixed prefix is 2+2+2+2 bytes before union u.
    struct=re.search(r"struct\s+MaterialShaderArgument\s*\{(?P<body>.*?)\};",src,re.S)
    req(struct,"MaterialShaderArgument struct absent")
    body=struct.group("body")
    order=[body.find(x) for x in ["MaterialShaderArgumentType type;","MaterialArgumentLocation location;","uint16_t size;","uint16_t buffer;","MaterialArgumentDef u;"]]
    req(all(x>=0 for x in order) and order==sorted(order),"MaterialShaderArgument member order drift")
    hits={x["instruction"]["address"].lower():x for x in loc.get("indexedScale4",[])}
    req("0x0077d758" in hits and "0x0077de62" in hits,"generic current-client lookup sites absent")
    p1=check_generic(hits["0x0077d758"],"0x0077d758","0x0077d75f")
    p2=check_generic(hits["0x0077de62"],"0x0077de62","0x0077de69")
    doc={
      "format":FMT,
      "authority":"pinned OAT T6 serialized argument vocabulary + SHA-classified current-client generic code-sampler lookup",
      "client":loc["client"],
      "pinnedSource":{"repository":"Laupetin/OpenAssetTools","commit":OAT_COMMIT,
        "path":str(a.t6_assets_header),"sha256":sha(a.t6_assets_header),
        "serializedArgument":{"codePixelSamplerType":4,"codeSamplerUnionOffset":8}},
      "runtimeContract":{"codeImagesBaseOffset":0x1530,"codeImageSamplerStatesBaseOffset":0x160C,
        "imageLookup":"source + codeSampler*4 + 0x1530",
        "samplerStateLookup":"source + codeSampler + 0x160C",
        "genericConsumers":[p1,p2]},
      "summary":{"codePixelSamplerType":4,"codeSamplerUnionOffset":8,
        "genericCurrentClientConsumerCount":2,"codeImagesBaseOffset":0x1530,
        "codeImageSamplerStatesBaseOffset":0x160C,"arrayContractClosed":True},
      "sources":{"layoutProof":{"path":str(a.layout_proof),"sha256":sha(a.layout_proof)}},
      "proofBoundary":"This closes the SHA-classified current client's generic code-pixel-sampler lookup contract and exact runtime array offsets. It does not identify the producer of any particular code-image slot, assign physical meaning to sampler-state byte values, or prove historical-retail executable equivalence."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()

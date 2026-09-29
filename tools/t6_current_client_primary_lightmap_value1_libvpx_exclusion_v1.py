#!/usr/bin/env python3
"""Join current-client libvpx VP8 decoder identity to the two value-1 +0x1610 writers.

This proof consumes only retained SHA-pinned proofs. It establishes that the
observed value-1 overlap-writer path is rooted in the exact embedded libvpx
v1.1.0 VP8 decoder callback at 0x009B59F0, not a renderer GfxCmdBufSourceState
path.

It does not claim the machine instructions can never be reached through some
unobserved alternate entry with unrelated objects; it excludes the proven
decode-rooted occurrences from the renderer writer denominator.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"

def req(c,m):
    if not c: raise RuntimeError(m)
def load(p): return json.loads(p.read_text())

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--decoder-proof",type=Path,required=True)
    ap.add_argument("--owner-proof",type=Path,required=True)
    ap.add_argument("--field-proof",type=Path,required=True)
    ap.add_argument("--path-proof",type=Path,required=True)
    ap.add_argument("--writer2-proof",type=Path,required=True)
    ap.add_argument("--writer1-proof",type=Path,required=True)
    ap.add_argument("--writers-proof",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()

    dec=load(a.decoder_proof); owner=load(a.owner_proof); fld=load(a.field_proof)
    path=load(a.path_proof); w2=load(a.writer2_proof); w1=load(a.writer1_proof)
    writers=load(a.writers_proof)

    # Same exact client for every machine-code proof that carries client identity.
    for name,d in [("decoder",dec),("owner",owner),("field",fld),("path",path),
                   ("writer2",w2),("writer1",w1),("writers",writers)]:
        c=d.get("client")
        if c is not None:
            req(c["sha256"]==SHA,f"{name} client SHA mismatch")

    # Root identity.
    req(dec["summary"]["decodeCallbackVa"]=="0x009B59F0","decode callback drift")
    req("libvpx v1.1.0" in dec["summary"]["identity"],"libvpx identity absent")
    req(dec["decoderName"]["text"]=="WebM Project VP8 Decoder v1.1.0","decoder name drift")
    req(dec["target"]["field"]=="dec.decode","callback field drift")

    # Exact decoder function boundary / arg1.
    req(owner["summary"]["correctFunctionStartVa"]=="0x009B59F0","owner entry drift")
    req(owner["summary"]["ediExpression"]=="arg1","owner arg1 drift")
    req(owner["summary"]["downstreamWriterBaseExpression"]=="*(arg1+0x110)+0xF00","owner expression drift")

    # Decoder callback passes its +0x110 field into the next function.
    req(fld["argFlow"]["call"]["address"]=="0x009B5C0A","field call VA drift")
    req(fld["argFlow"]["call"]["opStr"]=="0x9b7e80","field call target drift")
    req(fld["argFlow"]["ownerFieldLoad"]["address"]=="0x009B5B8C","field load VA drift")
    req(fld["argFlow"]["ownerFieldLoad"]["opStr"]=="ecx, dword ptr [edi + 0x110]","field load drift")
    req(fld["argFlow"]["conclusion"].startswith("0x009B7E80 arg1 = *(EDI+0x110)"),"field conclusion drift")

    # Path-sensitive continuation into 0x009C1EF0.
    req(path["summary"]["enclosingEntry"]=="0x009B7E80","enclosing entry drift")
    req(path["directEdgesToEnclosingEntry"][0]["address"]=="0x009B5C0A","upstream edge drift")
    req(path["path"]["branchToWriterContinuation"]["address"]=="0x009B8083","continuation branch drift")
    req(path["path"]["continuationSourceLoad"]["address"]=="0x009B80DA","continuation load drift")
    req(path["path"]["downstreamCall"]["address"]=="0x009B80E9","downstream call VA drift")
    req(path["path"]["downstreamCall"]["opStr"]=="0x9c1ef0","downstream target drift")
    req(path["summary"]["observedBranchFramePointerPreserved"] is True,"frame preservation not closed")

    # 0x009C2A88 is in the observed 0x009C1EF0 path with exact +0xF00 base.
    req(w2["summary"]["destinationBaseExpression"]=="callee_arg1 + 0xF00","writer2 base drift")
    req(w2["writer"]["va"]=="0x009C2A88","writer2 VA drift")
    req(w2["writer"]["slot4Value"]==1,"writer2 value drift")

    # 0x009C1DBB is reached from the same 0x009C1EF0 context and inherits EBX.
    req(w1["entry"]["va"]=="0x009C1D50","writer1 entry drift")
    req(w1["entry"]["writerVa"]=="0x009C1DBB","writer1 VA drift")
    req(w1["summary"]["directIncomingEdgeCount"]==1,"writer1 edge count drift")
    req(w1["incomingEdges"][0]["edge"]["address"]=="0x009C21B7","writer1 internal call drift")
    req(w1["summary"]["lastEbxDefinitions"][0]["address"]=="0x009C1EF4","writer1 EBX def drift")

    # Writer values from complete retained writer census.
    byva={x["writerVa"]:x for x in writers["writers"]}
    for va in ["0x009C1DBB","0x009C2A88"]:
        req(va in byva,f"{va} missing writer census")
        req(byva[va]["slot4Value"]==1,f"{va} slot4 value drift")

    chain=[
      "0x00CB5B78 vpx_codec_vp8_dx interface -> +0x28 dec.decode = 0x009B59F0",
      "0x009B59F0 arg1 -> EDI; 0x009B5B8C loads *(arg1+0x110)",
      "0x009B5C0A calls 0x009B7E80 with arg1 = *(decoder_arg1+0x110)",
      "0x009B8083 branch reaches 0x009B80DA with frame pointer intact",
      "0x009B80E9 calls 0x009C1EF0 with the same enclosing arg1",
      "0x009C1EF0 path reaches 0x009C2A88 at base arg1+0xF00",
      "0x009C21B7 calls 0x009C1D50 with live-in EBX from 0x009C1EF4; 0x009C1DBB writes the same slot on that observed context",
    ]

    doc={
      "format":"t6-current-client-primary-lightmap-value1-libvpx-exclusion-v1",
      "authority":"join of exact current-client libvpx interface identity and SHA-pinned path-sensitive writer provenance",
      "client":{"sha256":SHA},
      "rootIdentity":{
        "interfaceTableVa":dec["summary"]["interfaceTableVa"],
        "decoderName":dec["decoderName"]["text"],
        "decoderCallbackVa":"0x009B59F0",
        "decoderCallbackField":"vpx_codec_iface_t.dec.decode",
        "libvpxVersion":"1.1.0"
      },
      "exactObservedPath":chain,
      "value1Writers":[
        {"va":"0x009C1DBB","slot4Value":1,"classification":"libvpx-vp8-decode-rooted observed occurrence; exclude from renderer source-state denominator"},
        {"va":"0x009C2A88","slot4Value":1,"classification":"libvpx-vp8-decode-rooted observed occurrence; exclude from renderer source-state denominator"}
      ],
      "sources":{
        "decoderIdentity":str(a.decoder_proof),
        "ownerBoundary":str(a.owner_proof),
        "ownerField":str(a.field_proof),
        "pathSensitiveJoin":str(a.path_proof),
        "writer9C2A88":str(a.writer2_proof),
        "writer9C1DBB":str(a.writer1_proof),
        "completeWriterCensus":str(a.writers_proof)
      },
      "summary":{
        "excludedWriterVAs":["0x009C1DBB","0x009C2A88"],
        "excludedWriterValue":1,
        "root":"embedded libvpx v1.1.0 VP8 decoder callback",
        "rendererSourceStateOccurrenceAccepted":False,
        "primaryLightmapRendererWriterDenominatorEffect":"remove both value-1 overlap writers for the proven decode-rooted occurrences"
      },
      "proofBoundary":"Excludes the exact proven decode-rooted occurrences of 0x009C1DBB and 0x009C2A88 from the GfxCmdBufSourceState/lightmapSamplerPrimary writer denominator. It does not prove those instruction addresses are universally unreachable from all hypothetical indirect/internal entries with other object identities."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))

if __name__=="__main__": main()

#!/usr/bin/env python3
"""Bridge exact T6 PC-server PDB type inventory to current-client sampler layout.

Inputs are the generated PDB-derived CSV inventories from the pinned
bo2-pc-server-decompile revision plus the already-proven current-client generic
code-sampler array contract.

This tool is intentionally inventory-schema tolerant: it retains every row
whose values mention GfxCmdBufInput/GfxCmdBufSourceState, codeImages,
codeImageSamplerStates, or R_InitCmdBufSourceState, and separately indexes
numeric fields that equal the current-client offsets/stride.

It only promotes a type-layout match when the PDB inventory itself contains
the relevant exact type/member/offset evidence. Otherwise it reports the
frontier without guessing.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,re
from pathlib import Path

FORMAT="t6-pc-server-pdb-current-client-cmdbuf-layout-bridge-v1"
EXE_SHA="f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d"
PDB_SHA="7874efc2c9992467a72dbf48cc6f66d8cfa3c9a701275e41df1f8483a3d971fc"
IMAGE_OFF=0x1530
STATE_OFF=0x160C
OBJECT_STRIDE=0x1678

def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def read_csv_gz(path:Path):
    with gzip.open(path,"rt",encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def text(row):
    return " ".join(str(v or "") for v in row.values())

def normalize_num(v):
    s=str(v or "").strip().lower().replace("_","")
    if not s: return None
    # Do not treat arbitrary long hex-like symbol strings as numbers.
    try:
        if re.fullmatch(r"0x[0-9a-f]+",s): return int(s,16)
        if re.fullmatch(r"-?\d+",s): return int(s,10)
    except ValueError:
        return None
    return None

def numeric_hits(row,targets):
    hits=[]
    for k,v in row.items():
        n=normalize_num(v)
        if n in targets:
            hits.append({"field":k,"value":v,"numeric":n,"hex":f"0x{n:X}"})
    return hits

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--members",type=Path,required=True)
    ap.add_argument("--procedures",type=Path,required=True)
    ap.add_argument("--sampler-proof",type=Path,required=True)
    ap.add_argument("--source-repo",required=True)
    ap.add_argument("--source-commit",required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()

    sampler=json.loads(a.sampler_proof.read_text())
    rt=sampler["runtimeContract"]
    assert int(rt["codeImagesBaseOffset"])==IMAGE_OFF
    assert int(rt["codeImageSamplerStatesBaseOffset"])==STATE_OFF

    members=read_csv_gz(a.members)
    procs=read_csv_gz(a.procedures)

    terms=("gfxcmdbufinput","gfxcmdbufsourcestate","codeimages","codeimagesamplerstates")
    member_rows=[]
    for r in members:
        t=text(r).lower()
        if any(x in t for x in terms):
            rr=dict(r)
            rr["_numericTargetHits"]=numeric_hits(r,{IMAGE_OFF,STATE_OFF,OBJECT_STRIDE})
            member_rows.append(rr)

    proc_rows=[]
    for r in procs:
        t=text(r).lower()
        if "r_initcmdbufsourcestate" in t or ("gfxcmdbufsourcestate" in t and "gfxcmdbufinput" in t):
            proc_rows.append(dict(r))

    exact_numeric_rows=[]
    for r in members:
        hits=numeric_hits(r,{IMAGE_OFF,STATE_OFF,OBJECT_STRIDE})
        if hits:
            exact_numeric_rows.append({"row":dict(r),"hits":hits})

    def rows_with(term):
        return [r for r in member_rows if term in text(r).lower()]

    input_rows=rows_with("gfxcmdbufinput")
    source_rows=rows_with("gfxcmdbufsourcestate")
    code_images=rows_with("codeimages")
    sampler_states=rows_with("codeimagesamplerstates")

    # Conservative automatic classification: only call exact if a row that
    # names the member/type also carries the matching numeric offset.
    def row_has_term_and_num(rows,term,num):
        out=[]
        for r in rows:
            if term in text(r).lower():
                for h in r.get("_numericTargetHits",[]):
                    if h["numeric"]==num: out.append(r)
        return out
    image_exact=row_has_term_and_num(member_rows,"codeimages",IMAGE_OFF)
    state_exact=row_has_term_and_num(member_rows,"codeimagesamplerstates",STATE_OFF)
    stride_input=[r for r in input_rows if any(h["numeric"]==OBJECT_STRIDE for h in r.get("_numericTargetHits",[]))]

    doc={
      "format":FORMAT,
      "authority":"SHA-pinned PC dedicated-server PDB-derived inventory + independently closed SHA-pinned current-client sampler array offsets",
      "server":{"exeSha256":EXE_SHA,"pdbSha256":PDB_SHA,"inventoryRepository":a.source_repo,"inventoryCommit":a.source_commit,
                "membersGzipSha256":sha(a.members),"proceduresGzipSha256":sha(a.procedures)},
      "currentClient":{"samplerProofPath":str(a.sampler_proof),"samplerProofSha256":sha(a.sampler_proof),
                       "codeImagesBaseOffset":IMAGE_OFF,"codeImageSamplerStatesBaseOffset":STATE_OFF,
                       "pooledObjectStrideObserved":OBJECT_STRIDE},
      "inventorySummary":{"memberRowsTotal":len(members),"procedureRowsTotal":len(procs),
                          "relevantMemberRows":len(member_rows),"relevantProcedureRows":len(proc_rows),
                          "numericTargetRows":len(exact_numeric_rows),
                          "gfxCmdBufInputRows":len(input_rows),"gfxCmdBufSourceStateRows":len(source_rows),
                          "codeImagesRows":len(code_images),"codeImageSamplerStatesRows":len(sampler_states)},
      "matches":{"codeImagesExactOffsetRows":image_exact,
                 "codeImageSamplerStatesExactOffsetRows":state_exact,
                 "gfxCmdBufInputStride0x1678Rows":stride_input},
      "relevantMembers":member_rows,
      "relevantProcedures":proc_rows,
      "numericTargetRows":exact_numeric_rows,
      "classification":{
          "codeImagesOffsetPdbMatched":bool(image_exact),
          "codeImageSamplerStatesOffsetPdbMatched":bool(state_exact),
          "gfxCmdBufInputStridePdbMatched":bool(stride_input),
          "typeIdentityClosed":bool(image_exact and state_exact and stride_input),
      },
      "proofBoundary":"PDB inventory rows are authoritative only for the exact PC dedicated-server PDB revision. Matching offsets/size can support a cross-build type hypothesis but do not alone establish current-client type identity; machine-code use/initializer correspondence remains an independent evidence gate."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"inventorySummary":doc["inventorySummary"],"classification":doc["classification"]},indent=2,sort_keys=True))

if __name__=="__main__": main()

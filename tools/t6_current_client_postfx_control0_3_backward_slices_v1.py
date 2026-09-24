#!/usr/bin/env python3
"""Backward value slices for every frozen postFxControl0..3 writer.

This is a mechanical register-def/use projection over the exact frozen
instruction streams. It is designed to expose the minimal source loads and
arithmetic feeding each value/version write. It does not itself claim provider
semantics; a later fail-closed projector must validate the slices and branches.
"""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path

FORMAT="t6-current-client-postfx-control0-3-backward-slices-v1"
SOURCE_FORMAT="t6-current-client-postfx-control0-3-complete-writer-family-v1"
REG_RE=re.compile(r"\b(?:xmm(?:1[0-5]|[0-9])|e(?:ax|bx|cx|dx|si|di|bp|sp)|[abcd]x|[abcd][lh]|si|di|bp|sp)\b",re.I)
MEM_RE=re.compile(r"(?:\w+ ptr )?\[[^\]]+\]",re.I)
OVERWRITE={"mov","movss","movsd","movaps","movups","movd","movq","movzx","movsx","lea","cvtsi2ss","cvttss2si","movdqa","movdqu"}
RMW_PREFIX=("add","sub","mul","div","min","max","and","or","xor","shl","shr","sar","sal","shuf","unpck","pack","blend","pshuf","cvt")
MAX_BACK=420

ALIASES={
 "eax":"eax","ax":"eax","al":"eax","ah":"eax",
 "ebx":"ebx","bx":"ebx","bl":"ebx","bh":"ebx",
 "ecx":"ecx","cx":"ecx","cl":"ecx","ch":"ecx",
 "edx":"edx","dx":"edx","dl":"edx","dh":"edx",
 "esi":"esi","si":"esi","edi":"edi","di":"edi",
 "ebp":"ebp","bp":"ebp","esp":"esp","sp":"esp",
}
def canon(r:str)->str:
    x=r.lower()
    return ALIASES.get(x,x)
def regs(s:str):
    return {canon(x) for x in REG_RE.findall(s or "")}
def split_ops(s:str):
    # commas inside [] are not expected in this corpus; keep simple and fail-visible.
    return [x.strip() for x in (s or "").split(",")]
def dest_reg(ins):
    ops=split_ops(ins.get("opStr",""))
    if not ops:return None
    d=ops[0].lower().strip()
    m=REG_RE.fullmatch(d)
    return canon(m.group(0)) if m else None
def source_regs(ins):
    ops=split_ops(ins.get("opStr",""))
    if not ops:return set()
    out=set()
    for op in ops[1:]: out |= regs(op)
    return out
def is_overwrite(ins,d):
    mn=ins.get("mnemonic","").lower()
    ops=split_ops(ins.get("opStr",""))
    if mn in OVERWRITE:return True
    if mn=="xor" and len(ops)>=2 and canon(ops[0].lower())==canon(ops[1].lower()):return True
    if mn=="pxor" and len(ops)>=2 and canon(ops[0].lower())==canon(ops[1].lower()):return True
    return False
def write_source_regs(ins):
    ops=split_ops(ins.get("opStr",""))
    if len(ops)<2:return set()
    return regs(",".join(ops[1:]))
def sha(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()
def req(c,m):
    if not c:raise SystemExit(m)

def slice_one(ins,n):
    needed=write_source_regs(ins[n])
    chosen=[]
    lo=max(0,n-MAX_BACK)
    earliest=n
    for k in range(n-1,lo-1,-1):
        d=dest_reg(ins[k])
        if d and d in needed:
            chosen.append(ins[k]);earliest=k
            src=source_regs(ins[k])
            if is_overwrite(ins[k],d):
                needed.discard(d)
            # RMW instructions also consume dest; leave it needed.
            needed |= src
    chosen.reverse()
    # Preserve local branch/condition structure spanning the value slice.
    control=[]
    for x in ins[earliest:n]:
        mn=x.get("mnemonic","").lower()
        if mn.startswith("j") or mn in {"cmp","test","comiss","ucomiss","comisd","ucomisd","call"}:
            control.append(x)
    leaves=[]
    seen=set()
    for x in chosen:
        for m in MEM_RE.findall(x.get("opStr","")):
            if m not in seen:
                seen.add(m);leaves.append(m)
    return {"neededAtBoundary":sorted(needed),"instructions":chosen,"memoryLeaves":leaves,"control":control,
            "scanStartAddress":ins[lo]["address"] if ins else None,
            "earliestChosenAddress":ins[earliest]["address"] if ins and earliest<len(ins) else None}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    d=json.loads(a.source.read_text());req(d.get("format")==SOURCE_FORMAT,"source format drift")
    funcs=[];slice_count=0
    for f in d.get("functions",[]):
        ins=f["instructions"];by={x["address"]:i for i,x in enumerate(ins)}
        rows=[]
        for w in f.get("writes",[]):
            # Versions are retained too, but inc/add-immediate writes have no
            # source registers and naturally produce an empty value slice.
            n=by.get(w["instruction"]["address"]);req(n is not None,"write address drift")
            s=slice_one(ins,n)
            rows.append({"accessor":w["accessor"],"enumValue":w["enumValue"],"field":w["field"],
                         "targetVa":w["targetVa"],"write":w["instruction"],"slice":s})
            slice_count+=1
        funcs.append({"startVa":f["startVa"],"endVaExclusive":f["endVaExclusive"],
                      "directCallers":[{"call":c["call"],"contextBefore":c.get("contextBefore",[])[-24:],
                                        "contextAfter":c.get("contextAfter",[])[:8]} for c in f.get("directCallers",[])],
                      "slices":rows})
    out={"format":FORMAT,
         "authority":"mechanical backward register slices over SHA-frozen current-client postFx writer instructions",
         "source":{"path":str(a.source),"sha256":sha(a.source),"format":d["format"]},
         "summary":{"functionCount":len(funcs),"sliceCount":slice_count,
                    "accessorWriterDenominator":d.get("summary",{}).get("accessorWriterDenominator",{})},
         "functions":funcs,
         "proofBoundary":"Mechanical value-slice projection only. It preserves exact instructions and memory leaves feeding each frozen destination write, but does not prove branch reachability, source-record semantic names, historical-retail equivalence or provider closure."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()

#!/usr/bin/env python3
import argparse, hashlib, json, os, re, struct, urllib.request
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN

def u32be(b,o): return struct.unpack_from(">I", b, o)[0]

def dol_segments(data):
    segs=[]
    text_off=[u32be(data,0x00+i*4) for i in range(7)]
    data_off=[u32be(data,0x1c+i*4) for i in range(11)]
    text_addr=[u32be(data,0x48+i*4) for i in range(7)]
    data_addr=[u32be(data,0x64+i*4) for i in range(11)]
    text_size=[u32be(data,0x90+i*4) for i in range(7)]
    data_size=[u32be(data,0xac+i*4) for i in range(11)]
    for kind, offs, addrs, sizes in (("text",text_off,text_addr,text_size),("data",data_off,data_addr,data_size)):
        for i,(fo,va,sz) in enumerate(zip(offs,addrs,sizes)):
            if sz:
                segs.append({"kind":kind,"index":i,"file_offset":fo,"address":va,"size":sz})
    return segs

def extract(data,segs,addr,size):
    for s in segs:
        a=s["address"]; z=a+s["size"]
        if addr>=a and addr+size<=z:
            off=s["file_offset"]+(addr-a)
            return data[off:off+size], s
    raise ValueError(f"range 0x{addr:08X}+0x{size:X} is not contained in a DOL segment")

def imm(s):
    s=s.strip()
    try: return int(s,0)
    except: return None

def lift(ins):
    out={"state":"unsupported","semantic_kind":None,"pseudo_c":None,"confidence":None}
    if not ins: return out
    ops=[(i.mnemonic.lower(),i.op_str.lower()) for i in ins]
    # exact two-instruction leaf patterns
    if len(ops)==2 and ops[1][0]=="blr":
        m,o=ops[0]
        if m=="li":
            mm=re.fullmatch(r"r3,\s*(-?0x[0-9a-f]+|-?\d+)",o)
            if mm:
                v=imm(mm.group(1)); out.update(state="lifted",semantic_kind="return_constant",pseudo_c=f"int32_t f(void) {{ return {v}; }}",confidence="exact-instruction-template"); return out
        if m=="mr" and re.fullmatch(r"r3,\s*r4",o):
            out.update(state="lifted",semantic_kind="return_arg1",pseudo_c="uintptr_t f(uintptr_t arg0, uintptr_t arg1) { return arg1; }",confidence="exact-instruction-template"); return out
        if m=="addi":
            mm=re.fullmatch(r"r3,\s*r3,\s*(-?0x[0-9a-f]+|-?\d+)",o)
            if mm:
                v=imm(mm.group(1)); out.update(state="lifted",semantic_kind="return_arg0_plus_imm",pseudo_c=f"uintptr_t f(uintptr_t arg0) {{ return arg0 + ({v}); }}",confidence="exact-instruction-template"); return out
        load_types={"lwz":"uint32_t","lha":"int16_t","lhz":"uint16_t","lbz":"uint8_t"}
        if m in load_types:
            mm=re.fullmatch(r"r3,\s*(-?0x[0-9a-f]+|-?\d+)\(r3\)",o)
            if mm:
                d=imm(mm.group(1)); t=load_types[m]; out.update(state="lifted",semantic_kind=f"load_{m}_arg0",pseudo_c=f"{t} f(uintptr_t arg0) {{ return *({t} *)(arg0 + ({d})); }}",confidence="exact-instruction-template"); return out
        if m in {"lfs","lfd"}:
            mm=re.fullmatch(r"f1,\s*(-?0x[0-9a-f]+|-?\d+)\(r3\)",o)
            if mm:
                d=imm(mm.group(1)); t="float" if m=="lfs" else "double"; out.update(state="lifted",semantic_kind=f"load_{m}_arg0",pseudo_c=f"{t} f(uintptr_t arg0) {{ return *({t} *)(arg0 + ({d})); }}",confidence="exact-instruction-template"); return out
        store_types={"stw":"uint32_t","sth":"uint16_t","stb":"uint8_t"}
        if m in store_types:
            mm=re.fullmatch(r"r4,\s*(-?0x[0-9a-f]+|-?\d+)\(r3\)",o)
            if mm:
                d=imm(mm.group(1)); t=store_types[m]; out.update(state="lifted",semantic_kind=f"store_{m}_arg1_to_arg0",pseudo_c=f"void f(uintptr_t arg0, {t} arg1) {{ *({t} *)(arg0 + ({d})) = arg1; }}",confidence="exact-instruction-template"); return out
        if m=="stfs":
            mm=re.fullmatch(r"f1,\s*(-?0x[0-9a-f]+|-?\d+)\(r3\)",o)
            if mm:
                d=imm(mm.group(1)); out.update(state="lifted",semantic_kind="store_stfs_farg0_to_arg0",pseudo_c=f"void f(uintptr_t arg0, float farg0) {{ *(float *)(arg0 + ({d})) = farg0; }}",confidence="exact-instruction-template"); return out
        if m=="nop":
            out.update(state="lifted",semantic_kind="no_op_return",pseudo_c="void f(void) { return; }",confidence="exact-instruction-template"); return out
    if len(ops)>=1 and ops[0][0] in {"b","ba"}:
        out.update(state="classified",semantic_kind="tail_branch",confidence="exact-control-flow-template")
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--url",required=True); ap.add_argument("--expected-dol-sha256",required=True)
    ap.add_argument("--manifest",required=True); ap.add_argument("--out",required=True); ap.add_argument("--summary",required=True)
    a=ap.parse_args()
    dol="/tmp/rmge01_main.dol"
    urllib.request.urlretrieve(a.url,dol)
    data=open(dol,"rb").read()
    got=hashlib.sha256(data).hexdigest()
    if got.lower()!=a.expected_dol_sha256.lower():
        raise SystemExit(f"DOL SHA-256 mismatch: {got}")
    segs=dol_segments(data)
    md=Cs(CS_ARCH_PPC, CS_MODE_32|CS_MODE_BIG_ENDIAN)
    total=verified=lifted=classified=unsupported=0
    os.makedirs(os.path.dirname(a.out),exist_ok=True)
    with open(a.out,"w",encoding="utf-8") as fo:
        for line in open(a.manifest,encoding="utf-8"):
            if not line.strip(): continue
            total+=1; rec=json.loads(line); addr=int(rec["address"],16); size=int(rec["size"])
            blob,seg=extract(data,segs,addr,size)
            bh=hashlib.sha256(blob).hexdigest()
            if bh.lower()!=rec["expected_sha256"].lower():
                raise SystemExit(f"function byte mismatch {rec['id']} {bh} != {rec['expected_sha256']}")
            verified+=1
            ins=[{"address":f"0x{i.address:08X}","mnemonic":i.mnemonic,"op_str":i.op_str,"bytes":bytes(i.bytes).hex()} for i in md.disasm(blob,addr)]
            sem=lift([type("I",(),x) for x in ins])
            if sem["state"]=="lifted": lifted+=1
            elif sem["state"]=="classified": classified+=1
            else: unsupported+=1
            out={**rec,"dol_sha256":got,"byte_sha256":bh,"segment":seg,"bytes_hex":blob.hex(),"instructions":ins,**sem,
                 "producer":"smg-rmge01-exact-lift-v1","source_truth":"exact-retail-RMGE01-main.dol"}
            fo.write(json.dumps(out,separators=(",",":"))+"\n")
    summary={"producer":"smg-rmge01-exact-lift-v1","dol_sha256":got,"total":total,"byte_verified":verified,
             "template_lifted":lifted,"classified_only":classified,"unsupported":unsupported,
             "policy":"Only exact-byte-verified executable semantics are promoted; unsupported patterns remain raw disassembly evidence."}
    open(a.summary,"w",encoding="utf-8").write(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))

if __name__=="__main__": main()

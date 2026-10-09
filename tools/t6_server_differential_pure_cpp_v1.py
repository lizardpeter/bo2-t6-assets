#!/usr/bin/env python3
"""Compile Ghidra C-like pure-scalar function bodies to native C++, and
differentially execute original T6 PC x86 *instruction bytes* via Unicorn.

This is a limited, reproducible dynamic equivalence check, NOT proof over all
inputs or whole-game recompilation. Original bytes come exclusively from
validated contiguous exact Ghidra disassembly of the pinned original image.

Safety boundaries:
 * __cdecl scalar argument and result signatures only (<=4 arguments)
 * only scalar locals, if/else, comparisons, assignment, arithmetic, returns
 * no calls, pointers, globals, loops, inline asm, arrays, memory accesses,
   variable-sized operations, Ghidra synthetic opaque types, or floating point
 * native tests restricted to finite deterministic inputs with no division
 * no optimizations that assume signed wrap; compile with -fwrapv
 * every generated candidate must both compile and pass original x86 execution
"""
from __future__ import annotations

import argparse
import collections
import csv
import ctypes
import hashlib
import json
import random
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from t6_server_bulk_cpp_candidates_v1 import FUNC_RE, PARAM_RE, extract_balanced_body

TYPES={"bool":"bool","char":"char","uchar":"std::uint8_t","byte":"std::uint8_t",
       "short":"std::int16_t","ushort":"std::uint16_t","int":"std::int32_t",
       "uint":"std::uint32_t","long":"std::int32_t","ulong":"std::uint32_t"}
CASTS=set(TYPES)
ALLOWED_KEYWORDS={"if","else","return","true","false","sizeof","const","volatile"}
BAD_BODY=re.compile(r"(?m)\b(?:while|for|do|goto|switch|case|break|continue|throw|new|delete|asm|__asm|"
                    r"unaff_\w*|extraout_\w*|in_\w*|out_\w*)\b|->|[.[\]{}]|/|%|<<|>>")
IDENT=re.compile(r"\b[A-Za-z_]\w*\b")
TOKEN_FUNC=re.compile(r"\b([A-Za-z_]\w*)\s*\(")
VAR_DECL=re.compile(
    r"\b(?:bool|char|uchar|byte|short|ushort|int|uint|long|ulong)\s+"
    r"([A-Za-z_]\w*)\s*(?:[;=,])")
ASM_LINE=re.compile(r"^([0-9a-fA-F]{8})\t([0-9a-fA-F]+)\t(.+)$")
PAGE=0x1000
STACK_START=0x0ff00000
STACK_SIZE=0x20000
SENTINEL=0x13000000
BAD_SYMBOL_PREFIXES=("FUN_","thunk_","LAB_","_")
EDGE_VALUES=[0,1,2,3,7,15,31,32,63,127,255,256,0x7fffffff,
             0x80000000,0xffffffff,0xfffffffe,0x40000000,0xaaaaaaaa,0x55555555]

def parse_source(text:str,entry:str):
    m=FUNC_RE.search(text)
    if not m or m["rtype"] not in TYPES:
        return None,"unsupported_scalar_signature"
    name=m["name"]
    if name.startswith(BAD_SYMBOL_PREFIXES) or "FUN_" in name:
        return None,"anonymous_or_thunk"
    rawparams=m["params"].strip()
    args=[]
    if rawparams not in ("","void"):
        for param in rawparams.split(","):
            p=PARAM_RE.fullmatch(param)
            if p is None or p["type"] not in TYPES:
                return None,"non_scalar_argument"
            args.append((p["type"],p["name"]))
    if len(args)>4:
        return None,"more_than_four_arguments"
    body=extract_balanced_body(text,m.end()-1)
    if body is None:
        return None,"unbalanced_body"
    if BAD_BODY.search(body):
        # Permit braces for if/else blocks, but not additional punctuation.
        fixed=body.replace("{","").replace("}","")
        if BAD_BODY.search(fixed):
            return None,"effectful_or_complex_body"
    if not re.search(r"\breturn\b",body):
        return None,"no_explicit_return"
    # Exclude functions that branch into returns of unresolved or missing
    # values; compiler will catch errors but absence of inputs cannot.
    symbols=set(IDENT.findall(body))
    locals_=set(VAR_DECL.findall(body))
    allowed={p for _,p in args}|locals_|CASTS|ALLOWED_KEYWORDS
    unknown=sorted(symbols-allowed)
    if unknown:
        return None,"unknown_symbol_or_global"
    # Identifiers followed by "(" must be a scalar cast or if/sizeof.
    calls={x for x in TOKEN_FUNC.findall(body) if x not in CASTS|{"if","sizeof"}}
    if calls:
        return None,"unmodeled_function_calls"
    # No pointer operators (address-of, dereference) as the compiler would
    # otherwise permit a host-memory access unmodeled in the x86 sandbox.
    if re.search(r"(?<![&])&(?![&])|(?<![|])\|(?![|])",body):
        # Bitwise & / | on scalar locals is safe; permit.
        pass
    if re.search(r"\*\s*[A-Za-z_]\w+\s*(?:[;=)]|$)",body):
        return None,"potential_unmodeled_pointer"
    if re.search(r"\b(?:static|extern|register|union|struct|class)\b",body):
        return None,"nonlocal_storage"
    # Prevent functions with likely original x86 division traps.
    if re.search(r"(?<!/)/(?!/)|%",body):
        return None,"division_requires_sandbox"
    return {"entry":entry,"original_name":name,"return_type":m["rtype"],
            "arguments":args,"body":body}, "eligible_scalar_local"

def raw_x86_from_asm(text:str,entry:str):
    base=int(entry,16)
    parsed=[]
    for line in text.splitlines():
        m=ASM_LINE.fullmatch(line)
        if not m:
            continue
        address=int(m[1],16)
        raw=m[2]
        if len(raw)%2:
            return None,"bad_odd_length_opcode"
        try:
            code=bytes.fromhex(raw)
        except ValueError:
            return None,"bad_instruction_hex"
        if not code:
            return None,"empty_instruction"
        if "CALL" in m[3].upper() or re.search(r"\b(?:INT|SYSCALL|UD2)\b",m[3]):
            return None,"unmodeled_call_or_trap"
        parsed.append((address,code,m[3]))
    if not parsed or parsed[0][0]!=base:
        return None,"incorrect_start_va"
    assembled=bytearray()
    position=base
    for address,data,_ in parsed:
        if address!=position:
            return None,"disassembly_gap_or_overlap"
        assembled.extend(data)
        position+=len(data)
    if len(assembled)>512:
        return None,"large_original_instruction_body"
    if not re.search(r"\bRET\b",parsed[-1][2].upper()):
        return None,"no_final_x86_return"
    return bytes(assembled),"contiguous_exact_original_x86"

def cpp(candidate:dict):
    va=candidate["entry"][2:].lower()
    args=candidate["arguments"]
    sign=", ".join(f"{TYPES[t]} {p}" for t,p in args)
    names=", ".join(p for _,p in args)
    # Source body is a Ghidra C expression/statement tree, not a placeholder.
    # Long is x86 32-bit; replace only its type tokens, not identifier substrings.
    body=re.sub(r"\blong\b","std::int32_t",candidate["body"])
    sign=re.sub(r"\blong\b","std::int32_t",sign)
    ret=TYPES[candidate["return_type"]]
    return (
      f"static {ret} candidate_{va}({sign}) {{{body}}}\n"
      f'extern "C" std::uint32_t x86check_{va}({sign}) {{'
      f"return static_cast<std::uint32_t>(candidate_{va}({names}));}}\n"
    )

def emulator_eval(code:bytes,va:int,args:list[int]):
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
    from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EIP,UC_X86_REG_EAX
    cpu=Uc(UC_ARCH_X86,UC_MODE_32)
    page_start=va&~(PAGE-1)
    allocation=((va+len(code)+PAGE-1)&~(PAGE-1))-page_start
    cpu.mem_map(page_start,max(allocation,PAGE))
    cpu.mem_write(va,code)
    cpu.mem_map(STACK_START,STACK_SIZE)
    cpu.mem_map(SENTINEL,PAGE)
    esp=STACK_START+STACK_SIZE-0x100
    cpu.mem_write(esp,SENTINEL.to_bytes(4,"little"))
    for i,v in enumerate(args):
        cpu.mem_write(esp+4+i*4,(v&0xffffffff).to_bytes(4,"little"))
    cpu.reg_write(UC_X86_REG_ESP,esp)
    cpu.reg_write(UC_X86_REG_EIP,va)
    cpu.emu_start(va,SENTINEL,timeout=80_000,count=1000)
    if cpu.reg_read(UC_X86_REG_EIP)!=SENTINEL:
        raise RuntimeError("Original x86 did not return within deterministic budget")
    return cpu.reg_read(UC_X86_REG_EAX)&0xffffffff

def normalized_x86_return(value:int,rtype:str):
    if rtype=="bool":
        return value&0xff
    if rtype in ("char","uchar","byte"):
        return value&0xff
    if rtype in ("short","ushort"):
        return value&0xffff
    return value&0xffffffff

def cases(arity:int,seed:int,count:int):
    if arity==0:
        yield ()
        return
    rng=random.Random(seed)
    for v in EDGE_VALUES[:min(16,len(EDGE_VALUES))]:
        yield tuple((v if i==0 else EDGE_VALUES[(i+v)%len(EDGE_VALUES)])
                    for i in range(arity))
    for _ in range(count):
        yield tuple(rng.getrandbits(32) for _ in range(arity))

def verify_one(lib,candidate,code,count):
    fn=getattr(lib,"x86check_"+candidate["entry"][2:].lower())
    fn.argtypes=[ctypes.c_uint32]*len(candidate["arguments"])
    fn.restype=ctypes.c_uint32
    seed=int(hashlib.sha256(code).hexdigest()[:8],16)
    tests=0
    for args in cases(len(candidate["arguments"]),seed,count):
        native=int(fn(*args))&0xffffffff
        expected=normalized_x86_return(
            emulator_eval(code,int(candidate["entry"],16),list(args)),
            candidate["return_type"])
        if candidate["return_type"]=="bool":
            native=native&0xff
        if candidate["return_type"] in ("char","uchar","byte"):
            native=native&0xff
        if candidate["return_type"] in ("short","ushort"):
            native=native&0xffff
        if native!=expected:
            return False,tests,{"inputs":list(args),"retail_x86":expected,"native_cpp":native}
        tests+=1
    return True,tests,None

def run(root:Path,out:Path,limit:int=0,random_cases:int=64):
    records=[]
    stats=collections.Counter()
    shards=sorted(root.glob("t6-full-pc-ghidra-decompile-*"))
    if len(shards)!=8:
        raise ValueError(f"Required exact eight complete source shards, found {len(shards)}")
    for shard in shards:
        with (shard/"results.tsv").open(newline="",encoding="utf8") as f:
            rows=list(csv.DictReader(f,delimiter="\t"))
        stats["original_function_rows"]+=len(rows)
        for row in rows:
            if row["decompile_completed"]!="true":
                continue
            stats["ghidra_completed"]+=1
            stem=row["function_id"].rsplit(":",1)[-1]
            src=shard/"unreviewed"/(stem+".c")
            asm=shard/"disassembly"/(stem+".asm")
            if not src.is_file() or not asm.is_file():
                stats["missing_original_evidence"]+=1
                continue
            source=src.read_text(encoding="utf8",errors="replace")
            data,reason=parse_source(source,row["requested_va"].lower())
            stats[reason]+=1
            if not data:
                continue
            code,asm_status=raw_x86_from_asm(
                asm.read_text(encoding="utf8",errors="replace"),data["entry"])
            stats[asm_status]+=1
            if code is None:
                continue
            if any(t=="bool" for t,_ in data["arguments"]):
                # Original calling behavior for C++ bool arguments may
                # normalize input; restrict random and differential later.
                stats["bool_argument_requires_abi_review"]+=1
                continue
            data["original_sha256"]=hashlib.sha256(code).hexdigest()
            records.append((data,code))
    if stats["original_function_rows"]<27000:
        raise ValueError("Original image coverage too small")
    records.sort(key=lambda item:int(item[0]["entry"],16))
    if limit:
        records=records[:limit]
    out.mkdir(parents=True,exist_ok=True)
    (out/"candidates.hpp").write_text(
      "// Exact original-image scalar-only Ghidra bodies rendered as C++ test candidates.\n"
      "// They have NOT been manually reconstructed or retail-equivalence-proven.\n"
      "#include <cstdint>\n"
      "using uint=std::uint32_t; using ulong=std::uint32_t;\n"
      "using uchar=std::uint8_t; using byte=std::uint8_t;\n"
      "using ushort=std::uint16_t;\n\n"+
      "\n".join(cpp(data) for data,code in records),encoding="utf8")
    stats["native_cpp_candidates_generated"]=len(records)
    compile_result=subprocess.run(
        ["g++","-std=c++17","-O2","-fwrapv","-fPIC","-shared",
         "-x","c++",str(out/"candidates.hpp"),"-o",str(out/"candidate_shared.so")],
        text=True,capture_output=True)
    if compile_result.returncode:
        (out/"compiler_errors.txt").write_text(compile_result.stderr)
        stats["native_compiler_failed"]=1
        (out/"summary.json").write_text(json.dumps(dict(stats),indent=2)+"\n")
        raise RuntimeError("Compiler failed, see compiler_errors.txt")
    stats["native_cpp_compiler_accepted"]=len(records)
    try:
        import unicorn
    except ImportError:
        raise RuntimeError("pip install unicorn before differential verification")
    lib=ctypes.CDLL(str(out/"candidate_shared.so"))
    verified=[]
    rejected=[]
    for candidate,code in records:
        try:
            ok,count,detail=verify_one(lib,candidate,code,random_cases)
            stats["differential_inputs_executed"]+=count
            if ok:
                verified.append(candidate)
            else:
                rejected.append({"function":candidate["original_name"],
                                 "entry":candidate["entry"],"reason":"x86_output_mismatch",
                                 "first_differential_counterexample":detail})
        except Exception as error:
            rejected.append({"function":candidate["original_name"],
                             "entry":candidate["entry"],"reason":type(error).__name__,
                             "diagnostic":str(error)[:280]})
    stats["passed_limited_original_x86_differential"]=len(verified)
    stats["failed_or_not_executable_under_emulator"]=len(rejected)
    stats["random_cases_per_candidate"]=random_cases
    stats["verification_scope"]="Original disassembly bytes emulated as Win32 x86 __cdecl, native C++ built with -fwrapv; deterministic boundary and pseudorandom input tests. No semantic proof outside executed inputs, no ABI integration or complete game build."
    (out/"verified_candidates.json").write_text(json.dumps(verified,indent=2)+"\n")
    (out/"rejected_candidates.json").write_text(json.dumps(rejected,indent=2)+"\n")
    (out/"summary.json").write_text(json.dumps(dict(stats),indent=2)+"\n")
    (out/"verified_candidates.cpp").write_text(
        "#include <cstdint>\nusing uint=std::uint32_t; using ulong=std::uint32_t;\n"
        "using uchar=std::uint8_t; using byte=std::uint8_t;\n"
        "using ushort=std::uint16_t;\n\n"+
        "\n".join(cpp(x) for x in verified),encoding="utf8")
    return stats

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--limit",type=int,default=0)
    p.add_argument("--random-cases",type=int,default=64)
    a=p.parse_args()
    print(json.dumps(dict(run(a.input_root,a.output,a.limit,a.random_cases)),indent=2))

if __name__=="__main__":
    main()

#!/usr/bin/env python3
"""Reconstruct PDB-signature-matched one-call wrappers from entire BO2 PC image.

Use BOTH exact original x86 direct-call targets and a matching PDB-named callee
with known scalar signature. C++ wrappers are conservative review candidates,
not claims of complete byte matching or a standalone game executable.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0,str(Path(__file__).resolve().parent))
from t6_server_bulk_cpp_candidates_v1 import FUNC_RE, SCALARS, PARAM_RE, extract_balanced_body

RE_CDECL = re.compile(r"\b__cdecl\b")
CALL_RE = re.compile(r"\tCALL\s+(0x[0-9a-fA-F]{8})\b")
ONE_CALL = re.compile(
    r"^\s*(?P<mode>return\s+)?(?P<callee>[A-Za-z_]\w*)\s*"
    r"\((?P<actuals>[^()]*)\)\s*;\s*(?P<trailer>return\s*;\s*)?$",
    re.DOTALL,
)
LOCAL_CALL = re.compile(
    r"^\s*(?P<typ>bool|int|uint|long|ulong|short|ushort|char|uchar|byte)\s+"
    r"(?P<local>[A-Za-z_]\w*)\s*;\s*"
    r"(?P=local)\s*=\s*(?P<callee>[A-Za-z_]\w*)\("
    r"(?P<actuals>[^()]*)\)\s*;\s*return\s+(?P=local)\s*;\s*$",
    re.DOTALL,
)
INTEGER_LITERAL = re.compile(r"^(?:0[xX][0-9a-fA-F]+|\d+)[uU]?$")

class Record(NamedTuple):
    name: str
    entry: str
    rtype: str
    params: tuple[tuple[str,str],...]
    body: str
    id: str
    asm: str

def normalize_va(raw: str) -> str:
    return "0x"+raw.lower().removeprefix("0x").zfill(8)

def extract_records(root: Path) -> tuple[list[Record],collections.Counter]:
    stats = collections.Counter()
    collected=[]
    for shard in sorted(root.glob("t6-full-pc-ghidra-decompile-*")):
        results=shard/"results.tsv"
        if not results.is_file():
            raise ValueError(f"Missing original shard census {results}")
        with results.open(newline="",encoding="utf8") as f:
            lines=list(csv.DictReader(f,delimiter="\t"))
        stats["input_functions"]+=len(lines)
        for row in lines:
            if row.get("decompile_completed")!="true":
                continue
            stats["ghidra_decompiled"]+=1
            fid=row["function_id"]
            stem=fid.rsplit(":",1)[-1]
            path=shard/"unreviewed"/(stem+".c")
            asm=shard/"disassembly"/(stem+".asm")
            if not path.is_file() or not asm.is_file():
                stats["missing_source_or_original_x86"]+=1
                continue
            source=path.read_text(encoding="utf8",errors="replace")
            match=FUNC_RE.search(source)
            if not match:
                stats["unrecognized_scalar_or_void_signature"]+=1
                continue
            if match["name"].startswith(("FUN_", "thunk_", "LAB_","_")):
                stats["non_pdb_named_or_thunk"]+=1
                continue
            args=[]
            if match["params"].strip() not in ("","void"):
                for part in match["params"].split(","):
                    p=PARAM_RE.fullmatch(part)
                    if p is None or p["type"]=="void":
                        args=[];break
                    args.append((p["type"],p["name"]))
                if not args:
                    stats["complex_args"]+=1;continue
            body=extract_balanced_body(source,match.end()-1)
            if body is None:
                stats["unbalanced_body"]+=1;continue
            collected.append(Record(
                name=match["name"],entry=normalize_va(row["requested_va"]),
                rtype=match["rtype"],params=tuple(args),body=body,id=fid,
                asm=asm.read_text(encoding="utf8",errors="replace")))
    return collected,stats

def compile_wrappers(records: list[Record], stats: collections.Counter):
    names=collections.defaultdict(list)
    entry={r.entry:r for r in records}
    for r in records:
        names[r.name].append(r)
    generated=[]
    for record in records:
        stats["scanned_scalar_prototype"]=stats["scanned_scalar_prototype"]+1
        match=ONE_CALL.fullmatch(record.body)
        local_match=None
        if match is None:
            local_match=LOCAL_CALL.fullmatch(record.body)
            if local_match is None:
                stats["complex_or_not_single_call_body"]+=1
                continue
        callee_name=(match or local_match)["callee"]
        if callee_name==record.name:
            stats["recursive_function_excluded"]+=1
            continue
        if not names[callee_name]:
            stats["missing_matching_named_callee"]+=1
            continue
        actuals_raw=(match or local_match)["actuals"].strip()
        actuals=[x.strip() for x in actuals_raw.split(",")] if actuals_raw else []
        if any(not (re.fullmatch("[A-Za-z_]\\w*",x) or INTEGER_LITERAL.fullmatch(x))
               for x in actuals):
            stats["nontrivial_call_arguments"]+=1
            continue
        known_params={x[1] for x in record.params}
        if any(not (x in known_params or INTEGER_LITERAL.fullmatch(x)) for x in actuals):
            stats["argument_from_unknown_state"]+=1
            continue
        # Exact x86 CALL target is a distinct type check beyond pseudocode:
        # the same named callee must exist at the referenced original address.
        calls=CALL_RE.findall(record.asm)
        if len(calls)!=1:
            stats["not_exactly_one_direct_original_x86_call"]+=1
            continue
        address=normalize_va(calls[0])
        target=entry.get(address)
        if target is None or target.name!=callee_name:
            stats["original_x86_target_not_known_signature"]+=1
            continue
        if len(target.params)!=len(actuals):
            stats["call_arity_differs_from_pdb"]+=1
            continue
        if record.rtype!=target.rtype:
            stats["return_type_requires_conversion_review"]+=1
            continue
        # No hidden arguments permitted. Literal ints rely on normal ABI
        # promotion; require explicit callee scalar args (already parsed).
        for i,actual in enumerate(actuals):
            if not INTEGER_LITERAL.fullmatch(actual):
                caller_type=next((t for t,p in record.params if p==actual),None)
                callee_type=target.params[i][0]
                if caller_type!=callee_type:
                    stats["argument_types_need_review"]+=1
                    break
        else:
            if local_match is not None and (
                local_match["typ"]!=record.rtype):
                stats["temporary_type_mismatch"]+=1
                continue
            if match is not None and record.rtype!="void" and match["mode"] is None:
                stats["non_void_call_without_return"]+=1
                continue
            if match is not None and record.rtype=="void" and match["mode"] is not None:
                stats["void_return_expression"]+=1
                continue
            if match is not None and record.rtype!="void" and match["trailer"] is not None:
                stats["dead_trailing_return"]+=1
                continue
            sig=", ".join(f"{SCALARS[t]} {n}" for t,n in record.params)
            caller_ret=SCALARS[record.rtype]
            callee_sig=", ".join(f"{SCALARS[t]}" for t,n in target.params)
            extern=f"extern {caller_ret} {callee_name}({callee_sig});"
            call=f"{callee_name}({', '.join(actuals)});"
            body=f"return {call}" if record.rtype!="void" else call
            src=f"// Original PC {record.entry}, CALL {target.entry}; {record.id}\n"
            # Declarations must be at global scope to model the actual
            # original dependency, functions scoped by original entry for
            # avoiding accidental ODR collision in this candidate bundle.
            src+=extern+"\n"
            src+=f"namespace bo2_pc_va_{record.entry[2:]} {{\n"
            src+=f"{caller_ret} {record.name}({sig}) {{ {body} }}\n}}\n"
            generated.append((record,target,src))
            stats["verified_one_direct_call_cpp_candidate"]+=1
    return generated

def run(root: Path,out: Path):
    records,stats=extract_records(root)
    if stats["input_functions"] < 27000 or stats["ghidra_decompiled"] < 27000:
        raise ValueError("Original full-executable corpus truncated")
    pieces=compile_wrappers(records,stats)
    out.mkdir(parents=True,exist_ok=True)
    (out/"pdb_call_target_wrappers.cpp").write_text(
        "// Original PC x86 direct-call wrappers, independently compiled candidates.\n"
        "// Syntax compilation is NOT semantic equivalence proof or final game build.\n"
        "#include <cstdint>\n\n"+"\n".join(c for _,_,c in pieces),
        encoding="utf8")
    data=[{
        "original_function_va":r.entry,"original_function":r.name,
        "original_function_id":r.id,"callee_va":t.entry,
        "callee":t.name,"original_x86_direct_calls":1,
        "evidence":"Ghidra full-image typed scalar prototype and exact 0x CALL operand",
        "native_cpp_compile_gate":"not_yet_verified",
    } for r,t,_ in pieces]
    (out/"pdb_call_target_wrappers.json").write_text(json.dumps(data,indent=2)+"\n")
    stats["compiled_candidate_count_not_yet_tested"]=len(pieces)
    stats["scope"]="Original 27k Ghidra functions; exactly one named matching x86 direct-call target and matching scalar PDB signatures; still unreviewed C++ candidates."
    (out/"summary.json").write_text(json.dumps(dict(stats),indent=2)+"\n")
    print(json.dumps(dict(stats),indent=2))
    return len(pieces)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    run(a.input_root,a.output)

if __name__=="__main__":
    main()

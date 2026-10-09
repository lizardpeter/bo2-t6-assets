#!/usr/bin/env python3
"""Build target-x86 ABI-checked, collision-safe C++ type views from the
COMPLETE Ghidra/PDB type and field export.

This is a cross-translation-unit type library, not a pretend reconstruction of
the original classes: pointer fields are deliberately raw 32-bit target
addresses, nested fields without a verified representation remain bytes, and
any conflicting/malformed Ghidra layout is recorded rather than guessed.

Each uniquely identified Ghidra DataType path is preserved in type_map.json;
symbol collisions or conflict versions NEVER silently overwrite each other.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import keyword
import re
from pathlib import Path

SCALARS={
    "bool":("bool",1),"char":("char",1),"sbyte":("std::int8_t",1),
    "byte":("std::uint8_t",1),"uchar":("std::uint8_t",1),
    "short":("std::int16_t",2),"ushort":("std::uint16_t",2),
    "int":("std::int32_t",4),"uint":("std::uint32_t",4),
    "long":("std::int32_t",4),"ulong":("std::uint32_t",4),
    "longlong":("std::int64_t",8),"ulonglong":("std::uint64_t",8),
    "float":("float",4),"double":("double",8),
    "undefined1":("std::uint8_t",1),
    "undefined2":("std::uint16_t",2),
    "undefined4":("std::uint32_t",4),
    "undefined8":("std::uint64_t",8),
}
RESERVED=set(keyword.kwlist)|{
    "alignas","alignof","and","and_eq","asm","auto","bitand","bitor",
    "bool","break","case","catch","char","char8_t","char16_t",
    "char32_t","class","compl","concept","const","consteval",
    "constexpr","constinit","const_cast","continue","co_await",
    "co_return","co_yield","decltype","delete","do","double",
    "dynamic_cast","else","enum","explicit","export","extern",
    "false","float","for","friend","goto","if","inline","int",
    "long","mutable","namespace","new","noexcept","not","not_eq",
    "nullptr","operator","or","or_eq","private","protected","public",
    "register","reinterpret_cast","requires","return","short",
    "signed","sizeof","static","static_assert","static_cast","struct",
    "switch","template","this","thread_local","throw","true","try",
    "typedef","typeid","typename","union","unsigned","using","virtual",
    "void","volatile","wchar_t","while","xor","xor_eq",
}
ARRAY=re.compile(r"^/?(bool|char|byte|uchar|short|ushort|int|uint|long|ulong|float|double)\[(\d+)\]$")
VALID_NAME=re.compile(r"^[A-Za-z][A-Za-z_0-9]*$")
FALLBACK_LIMIT=1_000_000
MAX_NAMED_FIELDS=6000

def rows(path:Path):
    with path.open(encoding="utf8",newline="") as f:
        return list(csv.DictReader(f,delimiter="\t"))

def member_name(name:str, ordinal:int, used:set)->str:
    if VALID_NAME.fullmatch(name or "") and name not in RESERVED and not name.startswith("__"):
        candidate=name
    else:
        candidate=f"pdb_field_{ordinal}"
    if candidate in used:
        candidate=f"{candidate}_ordinal_{ordinal}"
    used.add(candidate)
    return candidate

def cpp_scalar(datatype:str,length:int) -> tuple[str,str,int] | None:
    """Return (C++ type, array suffix, element width), or None if unsafe."""
    base=datatype.rsplit("/",1)[-1].strip()
    m=ARRAY.fullmatch(base)
    if m:
        primitive,count=m.group(1),int(m.group(2))
        cpp,width=SCALARS[primitive]
        if 0<count<=FALLBACK_LIMIT and count*width==length:
            return cpp,f"[{count}]",width
    if base in SCALARS and SCALARS[base][1]==length:
        return SCALARS[base][0],"",length
    # Explicitly retain x86 pointers as raw 32-bit addresses, NEVER
    # native host pointers or silently invented nested struct pointers.
    if base.endswith("*") and length==4:
        return "std::uint32_t","",4
    return None

def emit_type(t:dict, fields:list[dict], stats:collections.Counter):
    kind=t["kind"]
    path=t["path"]
    size=int(t["length"])
    alignment=int(t["alignment"])
    name=t["cpp_name"]
    if size<=0 or size>FALLBACK_LIMIT:
        stats["types_invalid_or_oversized"]+=1
        return None
    if alignment not in (1,2,4,8,16) or size%alignment!=0:
        stats["types_invalid_alignment"]+=1
        return None
    if len(fields)>MAX_NAMED_FIELDS:
        stats["types_too_many_components"]+=1
        return None
    ordered=sorted(fields,key=lambda f:(int(f["offset"]),int(f["ordinal"])))
    bounds=[]
    for f in ordered:
        try:
            offset,length=int(f["offset"]),int(f["length"])
        except ValueError:
            stats["types_bad_field_metadata"]+=1
            return None
        if offset<0 or length<=0 or offset+length>size:
            stats["types_out_of_bounds_fields"]+=1
            return None
        bounds.append((offset,offset+length))
    overlapping=kind=="union" or any(
        bounds[i][0] < bounds[i-1][1]
        for i in range(1,len(bounds))
    )
    if overlapping:
        stats["types_opaque_due_to_union_or_overlap"]+=1
    align=f"alignas({alignment}) "
    head=[f"// Original Ghidra type: {path}",
          f"struct {align}{name} {{"]
    used=set()
    layout=[]
    pad=0
    typed=0
    opaque=0
    declaration_offsets=[]
    if not overlapping:
        for i,f in enumerate(ordered):
            offset,length=bounds[i][0],bounds[i][1]-bounds[i][0]
            if offset>pad:
                head.append(f"    std::uint8_t __pad_{i}[{offset-pad}];")
            field=member_name(f["field_name"],i,used)
            scalar=cpp_scalar(f["field_type_path"],length)
            if scalar is None:
                head.append(f"    std::uint8_t {field}[{length}];")
                opaque+=1
            else:
                cpp,suffix,width=scalar
                head.append(f"    {cpp} {field}{suffix};")
                typed+=1
                stats["scalar_or_target_pointer_fields_typed"]+=1
            declaration_offsets.append((field,offset))
            layout.append({
                "original_name":f["field_name"],"cpp_member":field,
                "original_type_path":f["field_type_path"],"offset":offset,
                "size":length,"representation":"typed" if scalar else "opaque_bytes",
            })
            pad=offset+length
        if pad<size:
            head.append(f"    std::uint8_t __tail[{size-pad}];")
        if not ordered:
            head.append(f"    std::uint8_t __storage[{size}];")
    else:
        head.append(f"    std::uint8_t __storage[{size}];")
        for i,f in enumerate(ordered):
            offset,length=bounds[i][0],bounds[i][1]-bounds[i][0]
            layout.append({
                "original_name":f["field_name"],"cpp_member":None,
                "original_type_path":f["field_type_path"],"offset":offset,
                "size":length,"representation":"overlapping_opaque",
            })
            opaque+=1
    head.append("};")
    head.append(f"static_assert(sizeof({name}) == {size}, \"Original x86 PDB type width\");")
    head.append(f"static_assert(alignof({name}) == {alignment}, \"Original x86 PDB type alignment\");")
    for member,off in declaration_offsets:
        head.append(
            f"static_assert(offsetof({name}, {member}) == {off}, "
            f"\"Original x86 PDB member offset\");")
    stats["views_emitted"]+=1
    stats["opaque_members"]+=opaque
    stats["member_offsets_asserted"]+=len(declaration_offsets)
    return "\n".join(head)+"\n",layout,{"typed":typed,"opaque":opaque,"overlapping":overlapping}

def generate(input_dir:Path, out:Path, shards:int=16):
    if not (1<=shards<=128):
        raise ValueError("shards must be 1..128")
    types=rows(input_dir/"types.tsv")
    fields=rows(input_dir/"fields.tsv")
    all_functions=rows(input_dir/"functions.tsv")
    if len(types)<25000 or len(fields)<65000 or len(all_functions)<27000:
        raise ValueError("Whole original Ghidra/PDB export is missing or truncated")
    stats=collections.Counter()
    stats["input_type_rows"]=len(types)
    stats["input_field_rows"]=len(fields)
    stats["input_function_rows"]=len(all_functions)
    mapping={}
    for t in types:
        if t["kind"] not in ("struct","union"):
            continue
        if t["path"] in mapping:
            raise ValueError("duplicate datatype full path: "+t["path"])
        original=t["name"]
        safe=re.sub(r"[^0-9A-Za-z_]","_",original)
        safe=safe[:48].strip("_") or "anonymous"
        if safe[0].isdigit():
            safe="type_"+safe
        symbol=f"{safe}_{hashlib.sha256(t['path'].encode()).hexdigest()[:12]}"
        record={**t,"cpp_name":"pdb_"+symbol}
        mapping[t["path"]]=record
    members=collections.defaultdict(list)
    for f in fields:
        if f["type_kind"] in ("struct","union") and f["type_path"] in mapping:
            members[f["type_path"]].append(f)
    out.mkdir(parents=True,exist_ok=True)
    shard_lines=[
        ["// Generated original BO2 PC x86 PDB ABI views; no synthetic gameplay logic.",
         "#pragma once","#include <cstddef>","#include <cstdint>",
         "namespace bo2_pdb_x86 {", ""]
        for _ in range(shards)
    ]
    exported=[]
    for path,t in sorted(mapping.items()):
        value=emit_type(t,members.get(path,[]),stats)
        if value is None:
            continue
        decl,field_map,meta=value
        index=int(hashlib.sha256(path.encode()).hexdigest()[:8],16)%shards
        shard_lines[index].append(decl)
        exported.append({
            "pdb_type_path":path,"original_pdb_name":t["name"],
            "original_kind":t["kind"],"cpp_name":t["cpp_name"],
            "type_size":int(t["length"]), "type_alignment":int(t["alignment"]),
            "shard":index,"fields":field_map,"layout":meta,
        })
    for i,lines in enumerate(shard_lines):
        lines.append("} // namespace bo2_pdb_x86")
        (out/f"pdb_types_{i:02d}.hpp").write_text("\n".join(lines)+"\n")
    (out/"pdb_layout_map.json").write_text(json.dumps(exported,indent=2)+"\n")
    source_names=collections.defaultdict(set)
    for e in exported:
        source_names[e["original_pdb_name"]].add((e["type_size"],e["type_alignment"]))
    conflict_names=sorted(k for k,v in source_names.items() if len(v)>1)
    (out/"conflicting_pdb_type_names.json").write_text(json.dumps(conflict_names,indent=2)+"\n")
    stats["PDB_compound_variants_seen"]=len(mapping)
    stats["distinct_CPP_layout_views_emitted"]=len(exported)
    stats["original_names_with_incompatible_layout_versions"]=len(conflict_names)
    stats["cpp_header_shards"]=shards
    stats["no_fabricated_cpp_game_functions"]=True
    stats["source"]="Original PC Server Ghidra/PDB types, fields and x86 explicit offsets"
    stats["boundary"]="Emitted types are collision-safe ABI representations; unresolved nested fields are opaque byte spans and target pointers are uint32_t. This is a compiler-checked type universe, not functioning recompilation."
    (out/"summary.json").write_text(json.dumps(dict(stats),indent=2)+"\n")
    return dict(stats)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--shards",type=int,default=16)
    a=p.parse_args()
    print(json.dumps(generate(a.input,a.output,a.shards),indent=2))

if __name__=="__main__":
    main()

#!/usr/bin/env python3
"""Build a graph-ready whole-executable mechanical inventory for the exact T6 current client.

The output is intentionally conservative:
- PE sections are exact binary-section occurrences.
- Imports are exact PE import occurrences.
- Strings are exact printable ASCII occurrences in mapped image sections.
- Function occurrences are ENTRY occurrences, not claimed full boundaries, unless a
  stronger structural basis exists. Entry candidates come from:
    * image entrypoint
    * exports
    * decoded direct relative CALL targets in executable sections
    * first decoded instruction after >=8-byte INT3 padding runs
- Direct calls are represented as exact callsite occurrences joined to target function
  entry occurrences where the target lies in an executable section.

No cross-build semantic family identity is inferred here.

It also writes graph-ready Cypher chunks so the inventory can be streamed directly into
the existing uregraph without moving the executable itself through MCP.
"""
from __future__ import annotations

import argparse, hashlib, json, re, struct
from pathlib import Path

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM

EXPECTED_SHA = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
BUILD_ID = "urn:ure:t6:re_Build:current-client-sha77031817"
ARTIFACT_ID = "urn:ure:t6:re_BinaryArtifact:current-client:770318175f0161aa"
PROJECT_ID = "urn:ure:t6:core_Project:black-ops-2:fd2705692f16c05f"
FMT = "t6-current-client-whole-image-mechanical-inventory-v1"

ASCII_RE = re.compile(rb"[\x20-\x7e]{4,}")

def q(s: str) -> str:
    # JSON encoding is valid Cypher double-quoted string syntax for our data subset.
    return json.dumps(s, ensure_ascii=False)

def hx(x: int) -> str:
    return f"0x{x:08X}"

def write_chunks(out_dir: Path, prefix: str, rows: list[dict], header: str, row_expr: str, chunk=250):
    paths=[]
    for ci in range(0,len(rows),chunk):
        batch=rows[ci:ci+chunk]
        payload=json.dumps(batch,separators=(",",":"),ensure_ascii=False)
        cypher=header + "\nWITH " + payload + " AS rows\nUNWIND rows AS row\n" + row_expr + "\n"
        p=out_dir / f"{prefix}_{ci//chunk:04d}.cypher"
        p.write_text(cypher,encoding="utf-8")
        paths.append(p.name)
    return paths

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("exe",type=Path)
    ap.add_argument("--revision",required=True)
    ap.add_argument("--out-dir",type=Path,required=True)
    args=ap.parse_args()

    raw=args.exe.read_bytes()
    sha=hashlib.sha256(raw).hexdigest()
    if sha != EXPECTED_SHA:
        raise SystemExit(f"SHA drift: {sha}")

    pe=pefile.PE(data=raw, fast_load=False)
    base=pe.OPTIONAL_HEADER.ImageBase
    ep=base+pe.OPTIONAL_HEADER.AddressOfEntryPoint

    sections=[]
    exec_ranges=[]
    for i,s in enumerate(pe.sections):
        name=s.Name.rstrip(b"\0").decode("ascii","replace")
        va=base+s.VirtualAddress
        raw_size=int(s.SizeOfRawData)
        virt_size=int(s.Misc_VirtualSize)
        sec={
            "ordinal":i,"name":name,"va":va,"rva":int(s.VirtualAddress),
            "raw_offset":int(s.PointerToRawData),"raw_size":raw_size,
            "virtual_size":virt_size,"characteristics":int(s.Characteristics),
            "executable":bool(s.Characteristics & 0x20000000),
            "readable":bool(s.Characteristics & 0x40000000),
            "writable":bool(s.Characteristics & 0x80000000),
        }
        sections.append(sec)
        if sec["executable"]:
            exec_ranges.append((va,va+max(raw_size,virt_size),sec))

    def exec_sec(va):
        for lo,hi,s in exec_ranges:
            if lo <= va < hi: return s
        return None

    # Exact imports.
    imports=[]
    for entry in getattr(pe,"DIRECTORY_ENTRY_IMPORT",[]) or []:
        dll=entry.dll.decode("ascii","replace")
        for imp in entry.imports:
            name=imp.name.decode("ascii","replace") if imp.name else None
            imports.append({
                "dll":dll,"name":name,"ordinal":imp.ordinal if imp.name is None else None,
                "iat_va":int(imp.address),
            })

    # Exports (if any).
    exports=[]
    if hasattr(pe,"DIRECTORY_ENTRY_EXPORT") and pe.DIRECTORY_ENTRY_EXPORT:
        for sym in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            if not sym.address: continue
            va=base+int(sym.address)
            exports.append({
                "va":va,
                "name":sym.name.decode("ascii","replace") if sym.name else None,
                "ordinal":int(sym.ordinal),
            })

    # Strings in mapped raw section data.
    strings=[]
    seen_string_va=set()
    for s in sections:
        ro=s["raw_offset"]; rs=s["raw_size"]
        if not rs: continue
        data=raw[ro:ro+rs]
        for m in ASCII_RE.finditer(data):
            va=s["va"]+m.start()
            if va in seen_string_va: continue
            seen_string_va.add(va)
            txt=m.group().decode("ascii","replace")
            strings.append({
                "va":va,"section":s["name"],"length":len(m.group()),
                "text":txt[:1024],
                "truncated":len(txt)>1024,
                "sha256":hashlib.sha256(m.group()).hexdigest(),
            })

    # Decode executable sections once.
    md=Cs(CS_ARCH_X86,CS_MODE_32)
    md.detail=True
    md.skipdata=True
    decoded={}
    direct_calls=[]
    starts={}  # va -> set bases

    def add_start(va,basis):
        if exec_sec(va):
            starts.setdefault(va,set()).add(basis)

    add_start(ep,"pe-entrypoint")
    for e in exports:
        add_start(e["va"],"pe-export")

    for s in sections:
        if not s["executable"] or not s["raw_size"]: continue
        data=raw[s["raw_offset"]:s["raw_offset"]+s["raw_size"]]
        ins=[i for i in md.disasm(data,s["va"]) if i.id]
        decoded[s["name"]]=ins

        # Structural starts after long INT3 padding.
        run=0
        for idx,i in enumerate(ins):
            if i.mnemonic=="int3":
                run+=1
                continue
            if run>=8:
                add_start(i.address,"post-int3-padding")
            run=0

        for i in ins:
            if i.mnemonic=="call" and len(i.operands)==1 and i.operands[0].type==X86_OP_IMM:
                target=int(i.operands[0].imm) & 0xffffffff
                if exec_sec(target):
                    add_start(target,"direct-call-target")
                    direct_calls.append({
                        "call_va":int(i.address),
                        "target_va":target,
                        "section":s["name"],
                        "bytes":i.bytes.hex(),
                    })

    # Function entry occurrence rows.
    functions=[]
    sorted_starts=sorted(starts)
    for va in sorted_starts:
        basis=sorted(starts[va])
        strongest=("post-int3-padding" if "post-int3-padding" in basis else
                   "pe-export" if "pe-export" in basis else
                   "pe-entrypoint" if "pe-entrypoint" in basis else
                   "direct-call-target")
        functions.append({
            "va":va,"section":exec_sec(va)["name"],
            "basis":";".join(basis),"strongest_basis":strongest,
        })

    # Assign each direct call to nearest preceding known entry in same executable section.
    # This is containment evidence only; without an exact end boundary it is marked candidate.
    by_sec={}
    for f in functions:
        by_sec.setdefault(f["section"],[]).append(f["va"])
    for vals in by_sec.values(): vals.sort()

    import bisect
    for c in direct_calls:
        vals=by_sec.get(c["section"],[])
        j=bisect.bisect_right(vals,c["call_va"])-1
        c["caller_entry_va"]=vals[j] if j>=0 else None

    out=args.out_dir
    out.mkdir(parents=True,exist_ok=True)
    cy=out/"cypher"; cy.mkdir(exist_ok=True)

    # Manifest/proof.
    manifest={
      "format":FMT,
      "authority":"exact SHA-pinned current-client whole-image mechanical inventory",
      "client":{"revision":args.revision,"bytes":len(raw),"sha256":sha,
                "imageBase":hx(base),"entrypointVa":hx(ep)},
      "counts":{
        "sections":len(sections),"imports":len(imports),"exports":len(exports),
        "strings":len(strings),"functionEntryOccurrences":len(functions),
        "directCalls":len(direct_calls),
        "directCallsWithCandidateCaller":sum(1 for x in direct_calls if x["caller_entry_va"] is not None),
      },
      "functionEntryBasisCounts":{},
      "proofBoundary":"Mechanical exact-binary inventory. Function nodes are entry occurrences with basis/confidence, not automatically exact full boundaries or semantic identities. Nearest-preceding caller association is candidate containment unless independently bounded.",
    }
    for f in functions:
        manifest["functionEntryBasisCounts"][f["strongest_basis"]]=manifest["functionEntryBasisCounts"].get(f["strongest_basis"],0)+1

    (out/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (out/"sections.json").write_text(json.dumps(sections,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (out/"imports.json").write_text(json.dumps(imports,indent=2,sort_keys=True)+"\n",encoding="utf-8")

    # Graph-ready row normalization.
    secrows=[{
      "id":f"urn:ure:t6:occ:section:current-client:{s['ordinal']:02d}:{s['name']}",
      "name":s["name"],"ordinal":s["ordinal"],"va":hx(s["va"]),"rva":hx(s["rva"]),
      "raw_offset":s["raw_offset"],"raw_size":s["raw_size"],"virtual_size":s["virtual_size"],
      "characteristics":s["characteristics"],"executable":s["executable"],
      "readable":s["readable"],"writable":s["writable"],
    } for s in sections]

    improws=[{
      "id":f"urn:ure:t6:occ:import:current-client:{i['iat_va']:08x}",
      "dll":i["dll"],"name":i["name"],"ordinal":i["ordinal"],"iat_va":hx(i["iat_va"]),
    } for i in imports]

    strrows=[{
      "id":f"urn:ure:t6:occ:string:current-client:{s['va']:08x}",
      "va":hx(s["va"]),"section":s["section"],"length":s["length"],"text":s["text"],
      "truncated":s["truncated"],"sha256":s["sha256"],
    } for s in strings]

    fnrows=[{
      "id":f"urn:ure:t6:occ:function:current-client:{f['va']:08x}",
      "va":hx(f["va"]),"section":f["section"],"basis":f["basis"],
      "strongest_basis":f["strongest_basis"],
    } for f in functions]

    callrows=[{
      "id":f"urn:ure:t6:occ:callsite:current-client:{c['call_va']:08x}",
      "call_va":hx(c["call_va"]),"target_va":hx(c["target_va"]),"section":c["section"],
      "bytes":c["bytes"],
      "caller_id":f"urn:ure:t6:occ:function:current-client:{c['caller_entry_va']:08x}" if c["caller_entry_va"] is not None else None,
      "target_id":f"urn:ure:t6:occ:function:current-client:{c['target_va']:08x}",
    } for c in direct_calls]

    header=f"MATCH (b:KGNode {{id:{q(BUILD_ID)}}}) MATCH (a:KGNode {{id:{q(ARTIFACT_ID)}}})"

    files={}
    files["sections"]=write_chunks(cy,"sections",secrows,header,
      """MERGE (n:KGNode {id:row.id})
SET n.kind='re:BinarySectionOccurrence', n.namespace='t6', n.build_id=b.id, n.artifact_id=a.id,
    n.display_name=row.name, n.ordinal=row.ordinal, n.address_space='va', n.address_start=row.va,
    n.rva=row.rva, n.raw_offset=row.raw_offset, n.raw_size=row.raw_size, n.virtual_size=row.virtual_size,
    n.characteristics=row.characteristics, n.executable=row.executable, n.readable=row.readable, n.writable=row.writable,
    n.producer='t6-current-client-whole-image-mechanical-inventory-v1'
MERGE (b)-[:HAS_OCCURRENCE]->(n)
MERGE (n)-[:DEFINED_IN]->(a)""",5000)

    files["imports"]=write_chunks(cy,"imports",improws,header,
      """MERGE (n:KGNode {id:row.id})
SET n.kind='core:Occurrence', n.occurrence_type='pe-import', n.namespace='t6', n.build_id=b.id, n.artifact_id=a.id,
    n.dll=row.dll, n.import_name=row.name, n.import_ordinal=row.ordinal, n.iat_va=row.iat_va,
    n.producer='t6-current-client-whole-image-mechanical-inventory-v1'
MERGE (b)-[:HAS_OCCURRENCE]->(n)
MERGE (n)-[:DEFINED_IN]->(a)""",5000)

    files["strings"]=write_chunks(cy,"strings",strrows,header,
      """MERGE (n:KGNode {id:row.id})
SET n.kind='core:Occurrence', n.occurrence_type='string-literal', n.namespace='t6', n.build_id=b.id, n.artifact_id=a.id,
    n.address_space='va', n.address_start=row.va, n.section_name=row.section, n.length=row.length,
    n.text=row.text, n.truncated=row.truncated, n.content_sha256=row.sha256,
    n.producer='t6-current-client-whole-image-mechanical-inventory-v1'
MERGE (b)-[:HAS_OCCURRENCE]->(n)
MERGE (n)-[:DEFINED_IN]->(a)""",5000)

    files["functions"]=write_chunks(cy,"functions",fnrows,header,
      """MERGE (n:KGNode {id:row.id})
ON CREATE SET n.kind='re:FunctionOccurrence', n.namespace='t6', n.build_id=b.id, n.artifact_id=a.id,
    n.display_name='sub_'+substring(row.va,2), n.address_space='va', n.address_start=row.va
SET n.entry_basis=row.basis, n.entry_strongest_basis=row.strongest_basis,
    n.boundary_state=CASE WHEN coalesce(n.boundary_state,'') STARTS WITH 'exact-' THEN n.boundary_state ELSE 'entry-only-mechanical-inventory' END,
    n.producer=CASE WHEN n.producer IS NULL THEN 't6-current-client-whole-image-mechanical-inventory-v1' ELSE n.producer END
MERGE (b)-[:HAS_OCCURRENCE]->(n)
MERGE (n)-[:DEFINED_IN]->(a)""",5000)

    call_header=f"MATCH (b:KGNode {{id:{q(BUILD_ID)}}}) MATCH (a:KGNode {{id:{q(ARTIFACT_ID)}}})"
    files["calls"]=write_chunks(cy,"calls",callrows,call_header,
      """MATCH (target:KGNode {id:row.target_id})
MERGE (c:KGNode {id:row.id})
SET c.kind='core:Occurrence', c.occurrence_type='direct-callsite', c.namespace='t6', c.build_id=b.id, c.artifact_id=a.id,
    c.address_space='va', c.address_start=row.call_va, c.target_va=row.target_va, c.section_name=row.section,
    c.instruction_bytes=row.bytes, c.caller_assignment_state=CASE WHEN row.caller_id IS NULL THEN 'unassigned' ELSE 'nearest-preceding-entry-candidate' END,
    c.producer='t6-current-client-whole-image-mechanical-inventory-v1'
MERGE (b)-[:HAS_OCCURRENCE]->(c)
MERGE (c)-[:DEFINED_IN]->(a)
MERGE (c)-[:CALLS_TARGET]->(target)
FOREACH (_ IN CASE WHEN row.caller_id IS NULL THEN [] ELSE [1] END |
  MERGE (caller:KGNode {id:row.caller_id})
  MERGE (caller)-[:HAS_CALLSITE]->(c)
)""",5000)

    graph_manifest={
      "format":"uregraph-cypher-chunk-manifest-v1",
      "graph":"uregraph",
      "sourceFormat":FMT,
      "buildId":BUILD_ID,
      "artifactId":ARTIFACT_ID,
      "files":files,
      "counts":manifest["counts"],
    }
    (out/"graph_manifest.json").write_text(json.dumps(graph_manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(manifest,indent=2,sort_keys=True))

if __name__=="__main__":
    main()

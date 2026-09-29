#!/usr/bin/env python3
"""Build authoritative exact-current-client analysis coverage summary.

This reports mechanical/Ghidra evidence coverage, not semantic reverse-engineering completion.
"""
from __future__ import annotations
import csv,json
from pathlib import Path

ROOT=Path("proof/current_client")
CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"

def loadj(p): return json.loads(Path(p).read_text(encoding="utf-8"))

def failures_from(path,group,shard=None):
    p=Path(path)
    if not p.exists(): return []
    with p.open(encoding="utf-8",newline="") as f:
        rows=list(csv.DictReader(f,dialect="excel-tab"))
    out=[]
    for r in rows:
        if r.get("decompile_completed")=="true": continue
        out.append({
          "group":group,"shard":shard,
          "function_id":r.get("function_id",""),
          "requested_va":r.get("requested_va",""),
          "tier":r.get("tier",""),
          "ghidra_name":r.get("ghidra_name",""),
          "decompiler_message":r.get("decompiler_message",""),
          "elapsed_ms":int(r.get("elapsed_ms") or 0),
          "instruction_count":int(r.get("instruction_count") or 0),
        })
    return out

def main():
    mechanical=loadj(ROOT/"whole_image_inventory_v1/manifest.json")
    v1=loadj(ROOT/"ghidra_low_hanging_v1/summary.json")
    v2=loadj(ROOT/"ghidra_low_hanging_v2/summary.json")
    v3=loadj(ROOT/"ghidra_low_hanging_v3/summary.json")
    th=loadj(ROOT/"ghidra_thunks_v1/summary.json")
    de=loadj(ROOT/"ghidra_deferred_v1/summary.json")

    failures=[]
    failures += failures_from(ROOT/"ghidra_low_hanging_v2/results.tsv","low_hanging_v2")
    for s in "abc":
        failures += failures_from(ROOT/f"ghidra_low_hanging_v3/shard-{s}/results.tsv","low_hanging_v3",s)
    for s in "abcd":
        failures += failures_from(ROOT/f"ghidra_deferred_v1/shard-{s}/results.tsv","deferred_v1",s)

    catalog=int(v1["catalog_functions"])
    low_selected=int(v1["selected_functions"])+int(v2["selected_functions"])+int(v3["selected_functions"])
    low_completed=int(v1["decompile_completed"])+int(v2["decompile_completed"])+int(v3["decompile_completed"])
    total_attempted=low_selected+int(th["selected_functions"])+int(de["selected_functions"])
    total_completed=low_completed+int(th["decompile_completed"])+int(de["decompile_completed"])
    total_failed=total_attempted-total_completed
    mech_entries=int(mechanical["counts"]["functionEntryOccurrences"])
    gap=mech_entries-catalog

    if total_attempted!=catalog:
        raise SystemExit(f"attempted {total_attempted} != catalog {catalog}")
    if total_failed!=len(failures):
        raise SystemExit(f"failure count {total_failed} != listed {len(failures)}")

    summary={
      "format":"t6-current-client-analysis-coverage-v1",
      "client_sha256":CLIENT_SHA,
      "authority":"exact SHA-pinned current-client mechanical inventory plus Ghidra 12.1.3 whole-catalog analysis",
      "mechanical":{
        "function_entry_candidates":mech_entries,
        "direct_calls":int(mechanical["counts"]["directCalls"]),
        "strings":int(mechanical["counts"]["strings"]),
        "imports":int(mechanical["counts"]["imports"]),
        "sections":int(mechanical["counts"]["sections"]),
      },
      "ghidra":{
        "catalog_functions":catalog,
        "catalog_attempted":total_attempted,
        "catalog_attempt_coverage_pct":round(100*total_attempted/catalog,6),
        "decompile_completed":total_completed,
        "decompile_failed":total_failed,
        "decompile_completion_pct":round(100*total_completed/catalog,6),
        "low_hanging_functions":low_selected,
        "low_hanging_completed":low_completed,
        "thunks":int(th["selected_functions"]),
        "thunks_completed":int(th["decompile_completed"]),
        "deferred_functions":int(de["selected_functions"]),
        "deferred_completed":int(de["decompile_completed"]),
        "mechanical_entry_candidates_not_exact_ghidra_functions":gap,
      },
      "failed_functions":failures,
      "proof_boundary":"Coverage describes exact mechanical/Ghidra evidence generation, not semantic reverse-engineering completion, accepted source reconstruction, or cross-build identity. Generated Ghidra C remains unreviewed evidence.",
    }

    out=ROOT/"analysis_coverage_v1"
    out.mkdir(parents=True,exist_ok=True)
    (out/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")

    fail_text=";".join(f["requested_va"] for f in failures)
    cypher=f"""MATCH (p:KGNode {{id:'urn:ure:t6:core_Project:black-ops-2:fd2705692f16c05f'}})
MATCH (b:KGNode {{id:'urn:ure:t6:re_Build:current-client-sha77031817'}})
MATCH (a:KGNode {{id:'urn:ure:t6:re_BinaryArtifact:current-client:770318175f0161aa'}})
MERGE (c:KGNode {{id:'urn:ure:t6:coverage:current-client-analysis-20260929-v1'}})
SET c.kind='core:CoverageSnapshot', c.namespace='t6',
    c.snapshot_key='current-client-analysis-20260929-v1',
    c.coverage_scope='exact-current-client-mechanical-ghidra-evidence',
    c.denominator_policy='Ghidra exact function catalog for decompile attempts; mechanical entry candidates reported separately',
    c.client_sha256='{CLIENT_SHA}',
    c.mechanical_function_entry_candidates={mech_entries},
    c.mechanical_direct_calls={int(mechanical["counts"]["directCalls"])},
    c.mechanical_strings={int(mechanical["counts"]["strings"])},
    c.mechanical_imports={int(mechanical["counts"]["imports"])},
    c.mechanical_sections={int(mechanical["counts"]["sections"])},
    c.ghidra_catalog_functions={catalog},
    c.ghidra_catalog_attempted={total_attempted},
    c.ghidra_decompile_completed={total_completed},
    c.ghidra_decompile_failed={total_failed},
    c.ghidra_completion_pct={round(100*total_completed/catalog,6)},
    c.low_hanging_functions={low_selected},
    c.low_hanging_completed={low_completed},
    c.thunk_functions={int(th["selected_functions"])},
    c.thunk_completed={int(th["decompile_completed"])},
    c.deferred_functions={int(de["selected_functions"])},
    c.deferred_completed={int(de["decompile_completed"])},
    c.mechanical_not_exact_ghidra_count={gap},
    c.failed_function_vas={json.dumps(fail_text)},
    c.proof_boundary='Mechanical/Ghidra evidence coverage only; not semantic RE completion or reconstructed-source coverage.'
MERGE (p)-[:HAS_COVERAGE_SNAPSHOT]->(c)
MERGE (c)-[:TARGETS_BUILD]->(b)
MERGE (c)-[:EVIDENCE_FOR]->(a)
RETURN c.id
"""
    (out/"coverage.cypher").write_text(cypher,encoding="utf-8")
    print(json.dumps({
      "mechanical_function_entry_candidates":mech_entries,
      "ghidra_catalog_functions":catalog,
      "attempted":total_attempted,
      "completed":total_completed,
      "failed":total_failed,
      "completion_pct":summary["ghidra"]["decompile_completion_pct"],
      "mechanical_gap":gap,
    },indent=2))

if __name__=="__main__": main()

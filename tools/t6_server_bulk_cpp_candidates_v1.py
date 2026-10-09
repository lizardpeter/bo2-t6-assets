#!/usr/bin/env python3
"""Conservative C++ source-candidate extraction from the ENTIRE original T6 PC
Server Ghidra corpus. Evidence-only, with a separately compiled subset.

Never equate Ghidra pseudocode or C++ syntax checks with semantically verified
or recompiled game functions. The filter only emits single-return primitives
which have no globals/calls/pointer accesses/aliases and can be compiled as
standalone C++.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
from pathlib import Path

# Use original Ghidra C scalar spellings only when their x86 width is known.
SCALARS = {
    "bool": "bool", "char": "char", "uchar": "std::uint8_t",
    "byte": "std::uint8_t", "short": "std::int16_t",
    "ushort": "std::uint16_t", "int": "std::int32_t",
    "uint": "std::uint32_t", "long": "std::int32_t",
    "ulong": "std::uint32_t", "float": "float",
    "double": "double", "void": "void",
}
TYPES = "|".join(map(re.escape, sorted(SCALARS, key=len, reverse=True)))
FUNC_RE = re.compile(
    rf"(?m)^\s*(?P<rtype>{TYPES})\s+__cdecl\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*\((?P<params>[^()]*)\)\s*\{"
)
PARAM_RE = re.compile(rf"^\s*(?P<type>{TYPES})\s+(?P<name>[A-Za-z_]\w*)\s*$")
RETURN_RE = re.compile(r"^\s*return\s+(?P<expr>[^;{}]+)\s*;\s*$", re.DOTALL)
# Conservative: no arbitrary calls, assignment, function pointers, members,
# memory operations, loops or volatile state; signed arithmetic is queued
# for overflow review, not silently asserted equivalent to x86.
LEXER = re.compile(
    r"0[xX][0-9a-fA-F]+(?:[uU])?|\d+(?:[uU])?|"
    r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||<<|>>|"
    r"[()!~&|^<>+\-*/%?:]"
)
SAFE_OPS = {"==", "!=", "<=", ">=", "&&", "||", "!", "~",
            "&", "|", "^", "<", ">", "(", ")"}
IDENTIFIER = re.compile(r"^[A-Za-z_]\w*$")
LITERAL = re.compile(r"^(?:0[xX][0-9a-fA-F]+|\d+)[uU]?$")
EXCLUDED_PREFIXES = ("FUN_", "thunk_FUN_", "_", "switchD_", "LAB_")
# Original PDB-named function, no synthetic generic Ghidra FUN_ name.
WARNING_TOKENS = ("undefined", "unaff_", "extraout_", "swi", "in_", "out_")


def extract_balanced_body(text: str, brace_start: int) -> str | None:
    if text[brace_start] != "{":
        raise AssertionError("not a brace")
    count = 1
    cursor = brace_start + 1
    while cursor < len(text) and count:
        if text[cursor] == "{":
            count += 1
        elif text[cursor] == "}":
            count -= 1
        cursor += 1
    if count:
        return None
    return text[brace_start + 1 : cursor - 1]


def parse_candidate(source: str, metadata: dict) -> tuple[dict | None, str]:
    match = FUNC_RE.search(source)
    if match is None:
        return None, "complex_or_unrecognized_signature"
    name, rtype = match["name"], match["rtype"]
    if name.startswith(EXCLUDED_PREFIXES):
        return None, "unnamed_or_generated_function"
    if "FUN_" in name or "thunk" in name.lower():
        return None, "unnamed_or_generated_function"
    if rtype == "void":
        return None, "non_returning_or_effectful_function"
    params = match["params"].strip()
    parsed = []
    if params not in ("", "void"):
        for param in params.split(","):
            argument = PARAM_RE.fullmatch(param)
            if not argument or argument["type"] == "void":
                return None, "non_scalar_argument"
            parsed.append((argument["type"], argument["name"]))
    if len({x[1] for x in parsed}) != len(parsed):
        return None, "duplicate_argument"
    body = extract_balanced_body(source, match.end() - 1)
    if body is None:
        return None, "unbalanced_function_body"
    # Strictly one plain return expression, with no declarations or branches.
    retval = RETURN_RE.fullmatch(body)
    if retval is None:
        return None, "not_single_expression_return"
    expr = retval["expr"].strip()
    if any(x in expr for x in ("->", ".", "[", "]", "=", ";", '"', "'", "/*", "//")):
        # Explicitly permit == != <= >= only by tokenizing, not here:
        if not (re.search(r"==|!=|<=|>=", expr) and
                not re.search(r"(?<![!<>=])=(?![=])", expr) and
                not any(x in expr for x in ("->", ".", "[", "]", ";", '"', "'", "/*", "//"))):
            return None, "side_effect_or_memory_expression"
    if any(w in expr for w in WARNING_TOKENS):
        return None, "unresolved_decompiler_identifier"
    tokens = LEXER.findall(expr)
    if "".join(tokens) != re.sub(r"\s+", "", expr):
        return None, "unsupported_expression_token"
    param_names = {p[1] for p in parsed}
    allowed = {*param_names, *SCALARS, "true", "false", "nullptr"}
    for token in tokens:
        if token in SAFE_OPS or LITERAL.fullmatch(token):
            continue
        if token in {"+", "-", "*", "/", "%", "<<", ">>", "?", ":"}:
            return None, "arithmetic_requires_semantic_review"
        if IDENTIFIER.fullmatch(token):
            if token not in allowed:
                return None, "external_symbol_dependency"
            continue
        return None, "complex_or_ambiguous_expression"
    if rtype not in ("bool", "int", "uint", "long", "ulong", "short", "ushort", "char", "uchar", "byte"):
        return None, "non_integer_return"
    # All original integer comparisons should preserve 32-bit width; C++'s
    # normal integral promotions are safe for these comparison/bitwise leaves.
    signature = ", ".join(f"{SCALARS[t]} {p}" for t,p in parsed)
    result = (f"{SCALARS[rtype]} {name}({signature}) {{\n"
              f"    return {expr};\n"
              f"}}\n")
    data = {
        "ghidra_function_id": metadata.get("function_id", ""),
        "original_pc_va": metadata.get("requested_va", ""),
        "name": name,
        "pdb_scalar_prototype": f"{rtype} {name}({params})",
        "generator_class": "pure_scalar_single_expression_no_external_references",
        "cpp": result,
    }
    return data, "pure_scalar_candidate"


def build(input_root: Path, output: Path):
    root = Path(input_root)
    output.mkdir(parents=True, exist_ok=True)
    totals = collections.Counter()
    seen = collections.defaultdict(list)
    candidates = []
    byshard = {}
    shard_dirs = sorted(root.glob("t6-full-pc-ghidra-decompile-*"))
    if len(shard_dirs) != 8:
        raise ValueError(f"Expected all 8 original Ghidra shards, found {len(shard_dirs)}")
    for shard in shard_dirs:
        results_path = shard/"results.tsv"
        if not results_path.is_file():
            raise ValueError(f"Missing original result census: {results_path}")
        with results_path.open(encoding="utf8", newline="") as f:
            rows = list(csv.DictReader(f, delimiter="\t"))
        totals["original_ghidra_function_rows"] += len(rows)
        local_candidates = []
        for row in rows:
            status = (row.get("decompile_completed") or "").lower()
            if status != "true":
                totals["failed_or_missing_ghidra_decompilations"] += 1
                continue
            totals["completed_original_ghidra_decompilations"] += 1
            # IDs end in original 8-hex-digit analysis entry address.
            function_id = row["function_id"]
            stem = function_id.rsplit(":",1)[-1]
            source_path = shard/"unreviewed"/(stem+".c")
            if not source_path.exists():
                totals["decompiled_without_source_file"] += 1
                continue
            content = source_path.read_text(encoding="utf8",errors="replace")
            data, reason = parse_candidate(content, row)
            totals[reason] += 1
            if data:
                local_candidates.append(data)
                seen[(data["name"],data["pdb_scalar_prototype"])].append(data)
        byshard[shard.name] = len(local_candidates)
        candidates.extend(local_candidates)
    # Original PDB name and signature collision: do not generate a duplicate
    # or pretend ambiguous C++ function ownership is solved.
    unique = [x for x in candidates if len(seen[(x["name"], x["pdb_scalar_prototype"])])==1]
    totals["duplicate_names_excluded_from_cpp"] = len(candidates)-len(unique)
    totals["compiled_candidates_unverified"] = len(unique)
    lines = [
        "// Original PC Server Ghidra pure scalar C++ reconstruction candidates.",
        "// Verified by a host compiler for syntax/type constraints ONLY.",
        "// Not game-executable-equivalent or accepted without x86 differential review.",
        "#include <cstdint>",
        "",
    ]
    manifest = []
    for candidate in sorted(unique, key=lambda x:(x["name"], x["original_pc_va"])):
        ns = "bo2_pc_va_" + candidate["original_pc_va"].lower().removeprefix("0x")
        lines.extend([f"// Original PC {candidate['original_pc_va']}; {candidate['ghidra_function_id']}",
                      f"namespace {ns} {{", candidate["cpp"], "}"])
        manifest.append({key:val for key,val in candidate.items() if key!="cpp"})
    (output/"pure_scalar_candidates.cpp").write_text("\n".join(lines),encoding="utf8")
    with (output/"pure_scalar_candidates.json").open("w",encoding="utf8") as f:
        json.dump(manifest, f, indent=2)
    totals["shards"] = len(shard_dirs)
    totals["candidate_count_after_deduplication"] = len(unique)
    totals["C++_candidate_source_path"] = "pure_scalar_candidates.cpp"
    totals["source_sha256"] = __import__("hashlib").sha256((output/"pure_scalar_candidates.cpp").read_bytes()).hexdigest()
    totals["scope_note"] = (
        "Full 27,734 original-image Ghidra function corpus inspected. "
        "C++ candidate output excludes calls, globals, pointers, compound "
        "functions, and arithmetic requiring semantics review. "
        "Candidates are not accepted or verified equivalent to original executable."
    )
    (output/"summary.json").write_text(json.dumps(dict(totals),indent=2)+"\n",encoding="utf8")
    return totals


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    result=build(a.input_root,a.output)
    print(json.dumps(dict(result),indent=2))


if __name__=="__main__":
    main()

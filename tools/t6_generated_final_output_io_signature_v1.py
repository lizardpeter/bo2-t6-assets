#!/usr/bin/env python3
"""Bind generated final-output DAG input/output registers to exact DXBC semantics.

Consumes ``t6-generated-slot4-final-output-symbolic-v3`` plus the exact OAT
shader dump root.  Each shader CSO is reopened by the already-recorded relative
path, re-hashed, and its strict ISGN/OSGN tables are parsed.

Every raw input symbol ``vN.<lane>`` used by the expression DAG must map to an
exact ISGN register. Every written output register must map to OSGN. No semantic
identity is inferred from register number.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import t6_dxbc_signature_v1 as signatures
import t6_generated_slot4_final_output_symbolic_v3 as symbolic_v3

FORMAT = "t6-generated-final-output-io-signature-v1"
INPUT_RE = re.compile(r"^v(\d+)\.([xyzw])$")


class GeneratedFinalOutputIoSignatureError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _shader_path(root: Path, relative: str) -> Path:
    root = root.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise GeneratedFinalOutputIoSignatureError(
            f"shader relative path escapes OAT root: {relative!r}"
        ) from exc
    if not candidate.is_file():
        raise GeneratedFinalOutputIoSignatureError(f"exact OAT shader file does not exist: {candidate}")
    return candidate


def build(final_output: dict, *, oat_root: Path, strict_nuketown: bool = False) -> dict:
    if final_output.get("format") != symbolic_v3.FORMAT:
        raise GeneratedFinalOutputIoSignatureError(
            f"unsupported final-output format {final_output.get('format')!r}"
        )
    shaders = final_output.get("shaders")
    if not isinstance(shaders, list) or not shaders:
        raise GeneratedFinalOutputIoSignatureError("final-output manifest has no shaders")

    rows = []
    input_symbol_checks = 0
    output_register_checks = 0
    semantic_use = {}
    for shader in shaders:
        sha = str(shader.get("sha256") or "").lower()
        relative = str(shader.get("relativeFile") or "")
        if not sha or not relative:
            raise GeneratedFinalOutputIoSignatureError(
                f"shader row lacks SHA/relativeFile: {shader.get('sha256')!r}"
            )
        path = _shader_path(Path(oat_root), relative)
        blob = path.read_bytes()
        actual = hashlib.sha256(blob).hexdigest()
        if actual != sha:
            raise GeneratedFinalOutputIoSignatureError(
                f"shader {sha}: exact OAT file SHA changed to {actual}"
            )
        try:
            io = signatures.parse_io_signatures(blob)
        except Exception as exc:
            raise GeneratedFinalOutputIoSignatureError(
                f"shader {sha}: signature parse failed: {exc}"
            ) from exc

        in_entries = io["input"]["entries"]
        out_entries = io["output"]["entries"]
        in_by_reg = {int(row["register"]): row for row in in_entries}
        out_by_reg = {int(row["register"]): row for row in out_entries}

        used_input_components = set()
        used_input_registers = set()
        for node in shader.get("nodes", []):
            if node.get("kind") != "symbol":
                continue
            match = INPUT_RE.fullmatch(str(node.get("name") or ""))
            if not match:
                continue
            register = int(match.group(1)); lane = match.group(2)
            entry = in_by_reg.get(register)
            if entry is None:
                raise GeneratedFinalOutputIoSignatureError(
                    f"shader {sha}: DAG input v{register}.{lane} absent from ISGN"
                )
            lane_index = "xyzw".index(lane)
            if not (int(entry["mask"]) & (1 << lane_index)):
                raise GeneratedFinalOutputIoSignatureError(
                    f"shader {sha}: DAG reads v{register}.{lane} outside ISGN mask 0x{int(entry['mask']):x}"
                )
            used_input_registers.add(register)
            used_input_components.add((register, lane))
            input_symbol_checks += 1
            semantic_use[entry["semantic"]] = semantic_use.get(entry["semantic"], 0) + 1

        used_outputs = set()
        for output in shader.get("outputs", []):
            register = int(output.get("register", -1))
            written = any(bool(lane.get("written")) for lane in output.get("lanes", []))
            if not written:
                continue
            if register not in out_by_reg:
                raise GeneratedFinalOutputIoSignatureError(
                    f"shader {sha}: written output o{register} absent from OSGN"
                )
            used_outputs.add(register)
            output_register_checks += 1

        rows.append({
            "sha256": sha,
            "relativeFile": relative,
            "techniqueSets": sorted(str(x) for x in shader.get("techniqueSets", [])),
            "inputSignature": io["input"],
            "outputSignature": io["output"],
            "usedInputRegisters": sorted(used_input_registers),
            "usedInputComponents": [f"v{reg}.{lane}" for reg, lane in sorted(used_input_components)],
            "usedInputSemantics": sorted({in_by_reg[reg]["semantic"] for reg in used_input_registers}),
            "usedOutputRegisters": sorted(used_outputs),
            "signatureSha256": _jhash(io),
        })

    if strict_nuketown:
        strict = final_output.get("strictNuketown")
        if not isinstance(strict, dict) or strict.get("map") != symbolic_v3.MAP:
            raise GeneratedFinalOutputIoSignatureError(
                "strict Nuketown signature binding requires symbolic-v3 strictNuketown block"
            )
        if len(rows) != 34:
            raise GeneratedFinalOutputIoSignatureError(
                f"strict Nuketown shader count {len(rows)} != 34"
            )

    return {
        "format": FORMAT,
        "sourceFormat": symbolic_v3.FORMAT,
        "shaders": rows,
        "summary": {
            "shaderCount": len(rows),
            "inputSymbolCheckCount": input_symbol_checks,
            "outputRegisterCheckCount": output_register_checks,
            "semanticUseCounts": dict(sorted(semantic_use.items())),
            "signatureRowsSha256": _jhash(rows),
            "strictNuketown": bool(strict_nuketown),
        },
        "proofBoundary": (
            "Exact OAT CSO SHA recheck plus strict SM4 ISGN/OSGN register-to-semantic binding for every raw vN input "
            "symbol and every written output register in the final-output DAG. No register-number semantic inference."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--final-output", type=Path, required=True)
    p.add_argument("--oat-root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--strict-nuketown", action="store_true")
    a = p.parse_args()
    source = json.loads(a.final_output.read_text(encoding="utf-8"))
    result = build(source, oat_root=a.oat_root, strict_nuketown=a.strict_nuketown)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

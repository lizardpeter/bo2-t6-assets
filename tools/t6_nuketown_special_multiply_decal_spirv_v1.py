#!/usr/bin/env python3
"""Translate the exact Nuketown multiply-decal shader pair and audit raw SPIR-V.

This is an independent public-oracle check of the retail DXBC -> SPIR-V boundary.
It reuses only the already source-closed special-census stage locator, SHA-checks
both exact shader payloads again, invokes vkd3d-compiler without semantic
rewriting, validates the raw modules with spirv-val, and reads descriptor names
and decorations from spirv-dis text.

The Rust runtime has a separate canonical descriptor rebinder. This tool does
not reproduce or bless that implementation; it proves that the pinned retail
modules themselves translate and expose exactly the descriptor population that
special replay expects: VS {cb0_0, cb3_0} and PS {s0, t0}.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import t6_nuketown_special_multiply_decal_vs_symbolic_v1 as pair

FORMAT = "t6-nuketown-special-multiply-decal-spirv-v1"
TECHNIQUE_SET = pair.TECHNIQUE_SET
VS_SHA256 = pair.VS_SHA256
PS_SHA256 = pair.PS_SHA256
EXPECTED = {
    "vs": {"cb0_0", "cb3_0"},
    "ps": {"s0", "t0"},
}

_NAME_RE = re.compile(r'^\s*OpName\s+(%\S+)\s+"([^"]+)"\s*$')
_DECORATE_RE = re.compile(r"^\s*OpDecorate\s+(%\S+)\s+(DescriptorSet|Binding)\s+(\d+)\s*$")


class SpecialSpirvError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(*argv: str) -> None:
    proc = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode:
        raise SpecialSpirvError(
            f"command failed ({proc.returncode}): {' '.join(argv)}\n{proc.stdout[-8000:]}"
        )


def disassemble(path: Path) -> str:
    proc = subprocess.run(
        ["spirv-dis", str(path), "-o", "-"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.returncode:
        raise SpecialSpirvError(f"spirv-dis failed for {path}:\n{proc.stdout[-8000:]}")
    return proc.stdout


def descriptor_rows(disassembly: str) -> list[dict[str, Any]]:
    names: dict[str, str] = {}
    decorations: dict[str, dict[str, int]] = {}
    for line in disassembly.splitlines():
        if match := _NAME_RE.match(line):
            names[match.group(1)] = match.group(2)
            continue
        if match := _DECORATE_RE.match(line):
            target, kind, value = match.groups()
            decorations.setdefault(target, {})[kind] = int(value)

    rows = []
    for target, values in decorations.items():
        if "Binding" not in values:
            continue
        name = names.get(target)
        if not name:
            raise SpecialSpirvError(
                f"SPIR-V descriptor {target} has Binding decoration but no OpName"
            )
        rows.append(
            {
                "id": target,
                "name": name,
                "descriptorSet": values.get("DescriptorSet", 0),
                "binding": values["Binding"],
            }
        )
    rows.sort(key=lambda row: (row["descriptorSet"], row["binding"], row["name"]))
    return rows


def translate(stage: str, raw: bytes, expected_sha: str, out_dir: Path) -> dict[str, Any]:
    actual = sha256(raw)
    if actual != expected_sha:
        raise SpecialSpirvError(f"{stage} exact DXBC SHA {actual} != pinned {expected_sha}")

    dxbc = out_dir / f"{stage}_{expected_sha}.dxbc"
    spv = out_dir / f"{stage}_{expected_sha}.raw.spv"
    dxbc.write_bytes(raw)
    run("vkd3d-compiler", "-x", "dxbc-tpf", "-b", "spirv-binary", "-o", str(spv), str(dxbc))
    run("spirv-val", str(spv))
    spv_raw = spv.read_bytes()
    dis = disassemble(spv)
    descriptors = descriptor_rows(dis)
    actual_names = {row["name"] for row in descriptors}
    if actual_names != EXPECTED[stage]:
        raise SpecialSpirvError(
            f"{stage} raw SPIR-V descriptors {sorted(actual_names)} != exact expected {sorted(EXPECTED[stage])}"
        )
    return {
        "stage": stage,
        "dxbcSha256": expected_sha,
        "dxbcBytes": len(raw),
        "rawSpirvSha256": sha256(spv_raw),
        "rawSpirvBytes": len(spv_raw),
        "descriptors": descriptors,
    }


def build(census_path: Path, out_dir: Path) -> dict[str, Any]:
    census = json.loads(census_path.read_text(encoding="utf-8"))
    if census.get("format") != "t6-nuketown-special-material-census-v1":
        raise SpecialSpirvError(f"unexpected special census format {census.get('format')!r}")

    group, owner = pair.selected_group(census)
    vs_raw, _vs_stage = pair.exact_stage(group, owner, "vertexShader", VS_SHA256)
    ps_raw, _ps_stage = pair.exact_stage(group, owner, "pixelShader", PS_SHA256)

    out_dir.mkdir(parents=True, exist_ok=True)
    vs = translate("vs", vs_raw, VS_SHA256, out_dir)
    ps = translate("ps", ps_raw, PS_SHA256, out_dir)
    doc = {
        "format": FORMAT,
        "map": "mp_nuketown_2020",
        "techniqueSet": TECHNIQUE_SET,
        "vertexShader": vs,
        "pixelShader": ps,
        "proofBoundary": (
            "Exact native-OAT-selected special shader bytes are independently SHA-256 verified, "
            "translated by vkd3d-compiler without semantic rewriting, accepted by spirv-val, and "
            "audited from spirv-dis decorations. The raw module descriptor-name sets must be exactly "
            "VS={cb0_0,cb3_0} and PS={s0,t0}. This proof does not assign runtime fog values or "
            "claim equivalence of any later descriptor rebinding implementation."
        ),
    }
    stable = json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    doc["proofSha256"] = sha256(stable)
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--special-census", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.special_census, args.out_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "vs": doc["vertexShader"],
        "ps": doc["pixelShader"],
        "proofSha256": doc["proofSha256"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

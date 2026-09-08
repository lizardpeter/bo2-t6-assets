#!/usr/bin/env python3
"""Fail-closed T6 PC dedicated-server attachment timing composition proof.

Inputs are the exact Ghidra decompile + disassembly evidence files from the
SHA-pinned PC dedicated-server reconstruction.  This script proves only the
seven timing helpers whose complete arithmetic is visible in those functions.
It does not promote dedicated-server semantics to the retail client.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SOURCE_REPO = "lizardpeter/bo2-pc-server-decompile"
SOURCE_COMMIT = "504c0d8516c50195342c8a064b2f2571b109659d"
PC_SERVER_EXE_SHA256 = "f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d"
PC_SERVER_PDB_SHA256 = "7874efc2c9992467a72dbf48cc6f66d8cfa3c9a701275e41df1f8483a3d971fc"

SPECS = [
    dict(name="BG_GetFireTime", cid="cf_71eea2ace5e894d7", va="009796b0",
         base_getter="BG_GetWeaponDef", base_field="iFireTime", scale_field="fFireTimeScale"),
    dict(name="BG_GetReloadTime", cid="cf_9cd45d5d43dcd6c0", va="00979710",
         base_getter="BG_GetWeaponVariantDef", base_field="iReloadTime", scale_field="fReloadTimeScale"),
    dict(name="BG_GetReloadEmptyTime", cid="cf_346232a648091034", va="00979770",
         base_getter="BG_GetWeaponVariantDef", base_field="iReloadEmptyTime", scale_field="fReloadEmptyTimeScale"),
    dict(name="BG_GetReloadAddTime", cid="cf_ee8a908bb0093f69", va="009797d0",
         base_getter="BG_GetWeaponDef", base_field="iReloadAddTime", scale_field="fReloadAddTimeScale"),
    dict(name="BG_GetReloadQuickTime", cid="cf_09ada0add4364913", va="00979830",
         base_getter="BG_GetWeaponVariantDef", base_field="iReloadQuickTime", scale_field="fReloadQuickTimeScale"),
    dict(name="BG_GetReloadQuickEmptyTime", cid="cf_1a5c94b0b0af689c", va="00979890",
         base_getter="BG_GetWeaponVariantDef", base_field="iReloadQuickEmptyTime", scale_field="fReloadQuickEmptyTimeScale"),
    dict(name="BG_GetReloadQuickAddTime", cid="cf_c2e03ad474b9a6e7", va="009798f0",
         base_getter="BG_GetWeaponDef", base_field="iReloadQuickAddTime", scale_field="fReloadQuickAddTimeScale"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise SystemExit(f"{label}: required evidence missing: {needle!r}")


def prove_one(root: Path, spec: dict) -> dict:
    c_path = root / f"{spec['cid']}.c"
    asm_path = root / f"{spec['cid']}.asm"
    if not c_path.is_file() or not asm_path.is_file():
        raise SystemExit(f"{spec['name']}: missing .c/.asm evidence pair")

    c = c_path.read_text(encoding="utf-8-sig")
    asm = asm_path.read_text(encoding="utf-8-sig")
    label = spec["name"]

    require(c, f"canonical_id: {spec['cid']}", label)
    require(c, f"requested_va: 0x{spec['va']}", label)
    require(c, f"ghidra_name: {label}", label)
    require(c, f"{spec['base_getter']}(param_1)", label)
    require(c, "BG_GetWeaponAttachments(param_1,&apWStack_10)", label)
    require(c, "fVar3 = __real_3f800000", label)
    require(c, f"fVar3 = fVar3 * apWStack_10[iVar2]->{spec['scale_field']}", label)
    require(c, "while (iVar2 < 3)", label)
    require(c, f"return (int)((float)pWVar1->{spec['base_field']} * fVar3);", label)

    require(asm, f"canonical_id: {spec['cid']}", label)
    require(asm, f"entry_point: {spec['va']}", label)
    require(asm, f"ghidra_name: {label}", label)

    # Fail closed if the generated function unexpectedly gained a second return
    # expression or a different attachment iteration bound.
    returns = re.findall(r"\breturn\b", c)
    if len(returns) != 1:
        raise SystemExit(f"{label}: expected exactly one decompiled return, got {len(returns)}")

    return {
        "function": label,
        "canonicalId": spec["cid"],
        "entryPoint": "0x" + spec["va"],
        "baseGetter": spec["base_getter"],
        "baseField": spec["base_field"],
        "attachmentScaleField": spec["scale_field"],
        "maxAttachmentSlotsVisited": 3,
        "initialScale": 1.0,
        "composition": "product_across_equipped_attachments_in_returned_attachment_order",
        "effectiveValue": f"int(base.{spec['base_field']} * product(attachment.{spec['scale_field']}))",
        "decompileSha256": sha256(c_path),
        "disassemblySha256": sha256(asm_path),
    }


def build(root: Path) -> dict:
    rows = [prove_one(root, s) for s in SPECS]
    return {
        "format": "t6-pc-server-attachment-timing-runtime-v1",
        "source": {
            "repository": SOURCE_REPO,
            "commit": SOURCE_COMMIT,
            "pcServerExeSha256": PC_SERVER_EXE_SHA256,
            "pcServerPdbSha256": PC_SERVER_PDB_SHA256,
        },
        "summary": {
            "formulaCount": len(rows),
            "allMultiplicative": True,
            "maxAttachmentSlotsVisited": 3,
            "retailClientPromotionBlocked": True,
        },
        "formulas": rows,
        "derivedRules": {
            "effectiveRpmFromEffectiveFireTimeMs": "60000 / effectiveFireTimeMs",
            "rpmDerivationPrecondition": "effectiveFireTimeMs > 0 and retail iFireTime millisecond semantics independently closed",
        },
        "proofBoundary": (
            "Authoritative only for the seven named attachment timing helpers in the exact SHA-pinned "
            "T6 PC dedicated-server evidence. The function identities/prototypes originate from the exact PDB-backed "
            "reconstruction and each emitted row is paired with its exact decompile and instruction listing. "
            "This proves multiplicative composition across up to three returned attachment slots for these timing fields. "
            "It does not prove retail-client equivalence, attachment selection/order semantics beyond BG_GetWeaponAttachments, "
            "or composition rules for damage range, ADS, clip size, recoil, spread, sway, movement, or other fields."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.source_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

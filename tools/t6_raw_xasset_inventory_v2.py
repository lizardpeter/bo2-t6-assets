#!/usr/bin/env python3
"""Backward-compatible T6 raw XAsset inventory adapter v2.

Extends tools/t6_raw_xasset_inventory.py without changing its proven v1 byte
semantics. v2 restores the richer interfaces required by later retained Stage
18D dependency/animation tools:

- `parse_front(...)["assets"]`: every top-level XAsset header with exact raw
  type/header fields and decoded zone-pointer metadata.
- `parse_front(...)["script_strings"]`: the complete indexed ScriptString table
  used by XAnim bone/notetrack resolution.
- `decode_zone_pointer(...)`: compatibility alias exposing the historical
  `valid_for_declared_block_size` spelling.

The physical stream cursor/layout remains exactly the v1 parser's layout. This
adapter never walks asset bodies or invents names from header proximity.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import struct
from pathlib import Path

BASE_PATH = Path(__file__).with_name("t6_raw_xasset_inventory.py")


def _load_base():
    spec = importlib.util.spec_from_file_location("t6_raw_xasset_inventory_v1", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_base = _load_base()
ASSET_TYPES = _base.ASSET_TYPES
BLOCK_NAMES = _base.BLOCK_NAMES
PTR_FOLLOWING = _base.PTR_FOLLOWING
PTR_INSERT = _base.PTR_INSERT
WVD_SIZE = _base.WVD_SIZE
WVD_FIELDS = _base.WVD_FIELDS


def decode_zone_pointer(value: int, blocks: list[int]) -> dict:
    out = dict(_base.zone_pointer(value, blocks))
    if out.get("kind") == "packed":
        out["valid_for_declared_block_size"] = bool(out.get("valid", False))
    else:
        out["valid_for_declared_block_size"] = True
    return out


def zone_pointer(value: int, blocks: list[int]) -> dict:
    """Preserve v1 caller spelling while returning the richer v2 record."""
    return decode_zone_pointer(value, blocks)


def _read_script_strings(data: bytes) -> list[str | None]:
    if len(data) < 64:
        raise ValueError("expanded stream too small for T6 XAssetList")
    count, strings_ptr = struct.unpack_from("<II", data, 40)
    if count == 0:
        return []
    if strings_ptr != PTR_FOLLOWING:
        raise ValueError("ScriptStringList pointer is not inline FOLLOWING")
    table = 64
    table_end = table + count * 4
    if table_end > len(data):
        raise ValueError("ScriptString pointer table outside expanded stream")
    raw_ptrs = struct.unpack_from(f"<{count}I", data, table)
    pos = table_end
    strings: list[str | None] = []
    for index, raw in enumerate(raw_ptrs):
        if raw == 0:
            strings.append(None)
            continue
        if raw != PTR_FOLLOWING:
            raise ValueError(
                f"ScriptString[{index}] uses unsupported serialized pointer 0x{raw:08X}"
            )
        end = data.find(b"\0", pos)
        if end < 0:
            raise ValueError(f"unterminated ScriptString[{index}] at {pos}")
        strings.append(data[pos:end].decode("latin1"))
        pos = end + 1
    return strings


def _asset_rows(data: bytes, asset_array: int, asset_count: int, blocks: list[int]) -> list[dict]:
    end = asset_array + asset_count * 8
    if asset_array < 0 or end > len(data):
        raise ValueError("XAsset array outside expanded stream")
    rows = []
    for index in range(asset_count):
        pos = asset_array + index * 8
        asset_type, header_raw = struct.unpack_from("<II", data, pos)
        if not 0 <= asset_type < len(ASSET_TYPES):
            raise ValueError(f"bad XAsset type {asset_type} at index {index}")
        rows.append({
            "index": index,
            "type_index": asset_type,
            "type": ASSET_TYPES[asset_type],
            "raw_offset": pos,
            "header_raw": f"0x{header_raw:08X}",
            "header_raw_u32": header_raw,
            "header": decode_zone_pointer(header_raw, blocks),
        })
    return rows


def parse_front(data: bytes) -> dict:
    out = _base.parse_front(data)
    blocks = list(out.get("_blocks", []))
    if len(blocks) != 8:
        raise ValueError("v1 parser did not retain the eight T6 block sizes")
    script_strings = _read_script_strings(data)
    if len(script_strings) != int(out["script_string_count"]):
        raise ValueError("ScriptString count mismatch with v1 parser")
    assets = _asset_rows(data, int(out["asset_array_raw_offset"]), int(out["asset_count"]), blocks)
    out["script_strings"] = script_strings
    out["script_string_validation"] = {
        "count": len(script_strings),
        "nullCount": sum(value is None for value in script_strings),
        "allIndicesPreserved": True,
    }
    out["assets"] = assets
    out["asset_header_summary"] = {
        "count": len(assets),
        "packed": sum(a["header"]["kind"] == "packed" for a in assets),
        "following": sum(a["header"]["kind"] == "following" for a in assets),
        "insert": sum(a["header"]["kind"] == "insert" for a in assets),
        "null": sum(a["header"]["kind"] == "null" for a in assets),
        "invalidPacked": sum(
            a["header"]["kind"] == "packed" and not a["header"]["valid_for_declared_block_size"]
            for a in assets
        ),
    }
    return out


def fixed_wvd(data: bytes, start: int, blocks: list[int]):
    # Keep the exact v1 field interpretation but emit v2 pointer metadata.
    out = {"raw_struct_offset": start, "raw_struct_size": WVD_SIZE}
    for name, (off, kind) in WVD_FIELDS.items():
        if kind == "u8":
            value = data[start + off]
        elif kind == "i32":
            value = struct.unpack_from("<i", data, start + off)[0]
        elif kind == "u32":
            value = struct.unpack_from("<I", data, start + off)[0]
        elif kind == "f32":
            value = struct.unpack_from("<f", data, start + off)[0]
        else:
            raw = struct.unpack_from("<I", data, start + off)[0]
            value = {"raw": f"0x{raw:08X}", "decoded": decode_zone_pointer(raw, blocks)}
        out[name] = value
    return out


def locate_wvd(data: bytes, name: str, blocks: list[int]):
    needle = name.encode("ascii") + b"\0"
    found = []
    pos = 0
    while True:
        at = data.find(needle, pos)
        if at < 0:
            break
        start = at - WVD_SIZE
        if start >= 0:
            name_ptr = struct.unpack_from("<I", data, start)[0]
            variants = struct.unpack_from("<i", data, start + 4)[0]
            weap = struct.unpack_from("<I", data, start + 8)[0]
            if name_ptr == PTR_FOLLOWING and -1 <= variants <= 100 and weap != 0:
                rec = fixed_wvd(data, start, blocks)
                rec.update(
                    internal_name=name,
                    raw_internal_name_offset=at,
                    status="exact_inline_fixed_record",
                )
                found.append(rec)
        pos = at + 1
    if len(found) == 1:
        return found[0]
    return {
        "internal_name": name,
        "status": "ambiguous_or_missing",
        "candidate_count": len(found),
        "candidates": found,
    }


def root_names(path: Path) -> list[str]:
    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(value, list):
            return [str(x) for x in value]
        if isinstance(value, dict) and isinstance(value.get("weapon_variant_roots"), list):
            return [
                str(r["internal_name"])
                for r in value["weapon_variant_roots"]
                if isinstance(r, dict) and r.get("internal_name")
            ]
        raise ValueError("roots JSON must be a list or contain weapon_variant_roots[]")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f)
        return [
            r.get("internal_name") or r.get("name")
            for r in rows
            if r.get("internal_name") or r.get("name")
        ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--roots", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    data = args.expanded.read_bytes()
    result = parse_front(data)
    blocks = result.pop("_blocks")
    result["format"] = "t6-raw-xasset-inventory-v2"
    result["format_proof"] = {
        "pointer_bits": 32,
        "offset_block_bit_count": 3,
        "packed_pointer_block_shift": 29,
        "packed_pointer_offset_mask": "0x1FFFFFFF",
        "weapon_variant_def_pc32_fixed_size": WVD_SIZE,
        "physical_stream_alignment_rule": "destination XBlock alignment consumes no source bytes",
        "baseParser": str(BASE_PATH.name),
        "restoredInterfaces": ["assets", "script_strings", "decode_zone_pointer"],
    }
    if args.roots:
        names = root_names(args.roots)
        roots = [locate_wvd(data, name, blocks) for name in names]
        result["weapon_variant_roots"] = roots
        result["weapon_variant_root_summary"] = {
            "requested": len(names),
            "exact": sum(r["status"] == "exact_inline_fixed_record" for r in roots),
            "unresolved": [
                r["internal_name"] for r in roots if r["status"] != "exact_inline_fixed_record"
            ],
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "expanded_sha256": hashlib.sha256(data).hexdigest(),
        "script_string_validation": result["script_string_validation"],
        "asset_count": result["asset_count"],
        "asset_header_summary": result["asset_header_summary"],
        "weapon_variant_root_summary": result.get("weapon_variant_root_summary"),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Prove the T6 MP camo equip/runtime selector mapping from exact retail tables
and the exact PDB-backed CoDMPServer_PC reference build.

This proof deliberately separates three identities:
  * attachment-table weapon-option identity (UI/CAC)
  * group-local camo subindex packed into renderOptions
  * weaponoptions.csv render selector / WeaponCamo target

The bridge is executable semantics, not friendly-name matching.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

FORMAT = "t6-mp-camo-equip-runtime-proof-v1"

PINNED = {
    "exe": {
        "bytes": 13711872,
        "sha256": "f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d",
    },
    "pdb": {
        "bytes": 49196032,
        "sha256": "7874efc2c9992467a72dbf48cc6f66d8cfa3c9a701275e41df1f8483a3d971fc",
    },
    "attachmentTable": {
        "bytes": 14564,
        "sha256": "85fea798aa4bde355374bdc5177f1e6b6f6d8ad2f7ce8aa78bc968e4f8a8094b",
    },
    "weaponOptions": {
        "bytes": 18269,
        "sha256": "91e266ade3c58661d7324ae9c89516ae089b3c97338836731ba5de6e1fa9f748",
    },
}

FUNCTION_RANGES = {
    "WeaponOptions::InitWeaponOptions": {
        "start": 0x004CEC60, "end": 0x004CEEF0,
        "sha256": "6998fd304a25abe9117add3787a89b5cb4d2c78675838ddccf6330ff672c3406",
    },
    "WeaponOptions::IsValidRenderOption": {
        "start": 0x004CF310, "end": 0x004CF3B0,
        "sha256": "c73792792297bcf54061d346ad7e6d1b5195d5b56fe57f9411f33bf949d51d2e",
    },
    "PlayerCmd_calcWeaponOptions": {
        "start": 0x005C1FE0, "end": 0x005C2480,
        "sha256": "4f6528c531db1699b2150e0fae0d671d0b91d865b582b33e1f71cbbbdc445930",
    },
    "BG_GetWeaponOptionSubIndex": {
        "start": 0x00972310, "end": 0x00972370,
        "sha256": "43296c8e87f737a9b986e1bfc3d5a20ce42e2fa8ef0a19ca89fbfcaf6e2e6ea6",
    },
    "BG_GetWeaponOptionNumFromIndexAndGroup": {
        "start": 0x00972440, "end": 0x00972490,
        "sha256": "5fb9395f1762409532a7d1f6823a9bb76c40f5e19e936be9299aa7f509934593",
    },
    "BG_LoadWeaponOptions": {
        "start": 0x00972AE0, "end": 0x00972C50,
        "sha256": "5ed28e815e80a424886d892ac7691d603aa63981b4c07fd900616f7da536d02b",
    },
}

EXPECTED_LOADOUT_ENUM = {
    "LOADOUTSLOT_PRIMARY_CAMO": 4,
    "LOADOUTSLOT_SECONDARY_CAMO": 14,
    "LOADOUTSLOT_KNIFE_CAMO": 20,
}
EXPECTED_OPTION_GROUP_ENUM = {
    "WEAPONOPTION_GROUP_CAMO": 0,
    "WEAPONOPTION_GROUP_TAG": 1,
    "WEAPONOPITON_GROUP_EMBLEM": 2,
    "WEAPONOPTION_GROUP_RETICLE": 3,
    "WEAPONOPTION_GROUP_LENS": 4,
    "WEAPONOPTION_GROUP_RETICLE_COLOR": 5,
    "WEAPONOPTION_GROUP_COUNT": 6,
}

LF_FIELDLIST = 0x1203
LF_ENUMERATE = 0x1502
LF_ENUM = 0x1507


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_pinned(label: str, data: bytes) -> None:
    want = PINNED[label]
    if len(data) != want["bytes"] or _sha(data) != want["sha256"]:
        raise ValueError(
            f"{label}: identity mismatch: bytes={len(data)} sha256={_sha(data)}"
        )


def _pe_sections(data: bytes) -> tuple[int, list[tuple[int, int, int, int]]]:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("not a PE image")
    _, nsects, _, _, _, opt_size, _ = struct.unpack_from("<HHIIIHH", data, pe + 4)
    opt = pe + 24
    if struct.unpack_from("<H", data, opt)[0] != 0x10B:
        raise ValueError("expected PE32 optional header")
    image_base = struct.unpack_from("<I", data, opt + 28)[0]
    sec = opt + opt_size
    rows = []
    for i in range(nsects):
        off = sec + i * 40
        virtual_size, virtual_address, raw_size, raw_ptr = struct.unpack_from(
            "<IIII", data, off + 8
        )
        rows.append((virtual_address, virtual_size, raw_ptr, raw_size))
    return image_base, rows


def _read_va(data: bytes, start: int, end: int) -> bytes:
    base, sections = _pe_sections(data)
    rva = start - base
    size = end - start
    for va, vs, raw_ptr, raw_size in sections:
        if va <= rva and rva + size <= va + max(vs, raw_size):
            off = raw_ptr + (rva - va)
            return data[off:off + size]
    raise ValueError(f"VA range {start:#x}..{end:#x} is not file-backed")


def _verify_function_ranges(exe: bytes) -> dict[str, Any]:
    out = {}
    for name, spec in FUNCTION_RANGES.items():
        blob = _read_va(exe, spec["start"], spec["end"])
        got = _sha(blob)
        if got != spec["sha256"]:
            raise ValueError(f"{name}: exact function-range hash mismatch {got}")
        out[name] = {
            "startHex": f"0x{spec['start']:08X}",
            "endHex": f"0x{spec['end']:08X}",
            "bytes": len(blob),
            "sha256": got,
        }
    return out


def _msf_streams(pdb: bytes) -> list[bytes]:
    if not pdb.startswith(b"Microsoft C/C++ MSF 7.00"):
        raise ValueError("unexpected PDB/MSF signature")
    block_size, _, _, directory_bytes, _, block_map = struct.unpack_from("<6I", pdb, 32)
    n_dir_blocks = math.ceil(directory_bytes / block_size)
    map_off = block_map * block_size
    dir_blocks = struct.unpack_from("<" + "I" * n_dir_blocks, pdb, map_off)
    directory = b"".join(
        pdb[b * block_size:(b + 1) * block_size] for b in dir_blocks
    )[:directory_bytes]
    n_streams = struct.unpack_from("<I", directory, 0)[0]
    sizes = list(struct.unpack_from("<" + "I" * n_streams, directory, 4))
    pos = 4 + 4 * n_streams
    block_lists: list[list[int]] = []
    for size in sizes:
        if size == 0xFFFFFFFF:
            block_lists.append([])
            continue
        n = math.ceil(size / block_size) if size else 0
        blocks = list(struct.unpack_from("<" + "I" * n, directory, pos)) if n else []
        pos += 4 * n
        block_lists.append(blocks)
    if pos != len(directory):
        raise ValueError("MSF stream directory did not parse exactly")
    streams = []
    for size, blocks in zip(sizes, block_lists):
        if size in (0, 0xFFFFFFFF):
            streams.append(b"")
        else:
            streams.append(
                b"".join(pdb[b * block_size:(b + 1) * block_size] for b in blocks)[:size]
            )
    return streams


def _tpi_records(pdb: bytes) -> dict[int, tuple[int, bytes]]:
    streams = _msf_streams(pdb)
    if len(streams) <= 2:
        raise ValueError("PDB has no TPI stream")
    tpi = streams[2]
    if len(tpi) < 56:
        raise ValueError("short TPI stream")
    _, header_size, ti_begin, ti_end, record_bytes = struct.unpack_from("<IIIII", tpi, 0)
    pos = header_size
    limit = header_size + record_bytes
    out: dict[int, tuple[int, bytes]] = {}
    ti = ti_begin
    while ti < ti_end:
        if pos + 2 > limit:
            raise ValueError("TPI record length overrun")
        rec_len = struct.unpack_from("<H", tpi, pos)[0]
        body = tpi[pos + 2:pos + 2 + rec_len]
        if len(body) != rec_len or len(body) < 2:
            raise ValueError("truncated TPI record")
        out[ti] = (struct.unpack_from("<H", body, 0)[0], body)
        pos += 2 + rec_len
        ti += 1
    if ti != ti_end or pos != limit:
        raise ValueError("TPI record census mismatch")
    return out


def _numeric(body: bytes, pos: int) -> tuple[int, int]:
    code = struct.unpack_from("<H", body, pos)[0]
    pos += 2
    if code < 0x8000:
        return code, pos
    formats = {
        0x8000: ("<b", 1), 0x8001: ("<h", 2), 0x8002: ("<H", 2),
        0x8003: ("<i", 4), 0x8004: ("<I", 4),
    }
    if code not in formats:
        raise ValueError(f"unsupported CodeView numeric leaf {code:#x}")
    fmt, size = formats[code]
    return struct.unpack_from(fmt, body, pos)[0], pos + size


def _fieldlist_enumerators(body: bytes) -> dict[str, int]:
    if struct.unpack_from("<H", body, 0)[0] != LF_FIELDLIST:
        raise ValueError("enum field list has wrong leaf")
    pos = 2
    out: dict[str, int] = {}
    while pos < len(body):
        if body[pos] >= 0xF0:
            skip = body[pos] & 0x0F
            pos += skip if skip else 1
            continue
        leaf = struct.unpack_from("<H", body, pos)[0]
        if leaf != LF_ENUMERATE:
            raise ValueError(f"unexpected field-list leaf {leaf:#x}")
        pos += 4
        value, pos = _numeric(body, pos)
        end = body.index(0, pos)
        name = body[pos:end].decode("utf-8")
        pos = end + 1
        if name in out and out[name] != value:
            raise ValueError(f"divergent duplicate enumerator {name}")
        out[name] = value
    return out


def _find_enum(pdb: bytes, type_name: str) -> dict[str, int]:
    records = _tpi_records(pdb)
    hits = []
    needle = type_name.encode() + b"\0"
    for ti, (leaf, body) in records.items():
        if leaf != LF_ENUM or needle not in body:
            continue
        count, _props = struct.unpack_from("<HH", body, 2)
        field_list = struct.unpack_from("<I", body, 10)[0]
        enum_name_pos = 14
        end = body.index(0, enum_name_pos)
        if body[enum_name_pos:end].decode("utf-8") != type_name:
            continue
        fld = records.get(field_list)
        if fld is None:
            raise ValueError(f"{type_name}: missing field-list type {field_list:#x}")
        values = _fieldlist_enumerators(fld[1])
        if len(values) != count:
            raise ValueError(f"{type_name}: {len(values)} enumerators != declared {count}")
        hits.append((ti, values))
    if len(hits) != 1:
        raise ValueError(f"{type_name}: exact enum occurrence count {len(hits)} != 1")
    return hits[0][1]


def _csv_rows(data: bytes, width: int) -> list[list[str]]:
    rows = list(csv.reader(data.decode("utf-8-sig").splitlines()))
    if not rows or any(len(r) != width for r in rows):
        raise ValueError(f"CSV width is not uniformly {width}")
    return rows


def build_table_mapping(attachment_csv: bytes, weaponoptions_csv: bytes,
                        *, require_pinned: bool = True) -> dict[str, Any]:
    if require_pinned:
        _require_pinned("attachmentTable", attachment_csv)
        _require_pinned("weaponOptions", weaponoptions_csv)

    attachment_rows = _csv_rows(attachment_csv, 20)[1:]
    option_rows = _csv_rows(weaponoptions_csv, 24)[1:]
    weaponoption_rows = [r for r in attachment_rows if r[2] == "weaponoption"]
    camo_ui = [r for r in weaponoption_rows if r[1] == "camo"]
    if len(weaponoption_rows) != 99 or len(camo_ui) != 46:
        raise ValueError(
            f"attachmenttable canary changed: weaponoptions={len(weaponoption_rows)} camos={len(camo_ui)}"
        )
    if camo_ui[0][4] != "camo_none":
        raise ValueError("first camo group entry is not exact camo_none")

    ui_by_subindex = {subindex: row for subindex, row in enumerate(camo_ui)}
    if len(ui_by_subindex) != len(camo_ui):
        raise ValueError("duplicate generated camo subindex")

    render_rows = [r for r in option_rows if r[1] == "camo"]
    if len(render_rows) != 45:
        raise ValueError(f"weaponoptions camo row count {len(render_rows)} != 45")
    render_by_id: dict[int, list[str]] = {}
    for row in render_rows:
        try:
            selector = int(row[0], 10)
            material_raw = int(row[3], 10)
            target = int(row[4], 10)
        except ValueError as exc:
            raise ValueError(f"malformed numeric camo row {row[:5]!r}") from exc
        if selector <= 0 or selector > 127:
            raise ValueError(f"camo selector {selector} outside renderOptions 7-bit domain")
        if selector in render_by_id:
            raise ValueError(f"duplicate camo selector id {selector}")
        if material_raw not in (0, 1) or target <= 0:
            raise ValueError(f"invalid camo target tuple {row[:5]!r}")
        render_by_id[selector] = row
    if sorted(render_by_id) != list(range(1, 46)):
        raise ValueError("weaponoptions camo IDs are not exact contiguous 1..45")

    mappings = []
    for selector in range(1, 46):
        ui = ui_by_subindex.get(selector)
        render = render_by_id[selector]
        if ui is None:
            raise ValueError(f"no attachment-table camo at runtime subindex {selector}")
        material = bool(int(render[3]))
        target_one = int(render[4])
        mappings.append({
            "renderOptionCamoId": selector,
            "runtimeGroupSubIndex": selector,
            "attachmentTableAuthoredOptionIndex": int(ui[0]),
            "attachmentTableDisplayName": ui[3],
            "attachmentTableReference": ui[4],
            "weaponOptionsReference": render[2],
            "referenceStringsIdentical": ui[4] == render[2],
            "isMaterialCamo": material,
            "oneBasedWeaponCamoTargetIndex": target_one,
            "zeroBasedWeaponCamoTargetIndex": target_one - 1,
            "runtimeTargetArray": "camoMaterials" if material else "camoSets",
        })

    renamed = [m for m in mappings if not m["referenceStringsIdentical"]]
    if len(renamed) != 6:
        raise ValueError(f"renamed runtime bridge count {len(renamed)} != 6")
    return {
        "weaponoptionRows": weaponoption_rows,
        "camoUiRows": camo_ui,
        "renderRows": render_rows,
        "mappings": mappings,
        "renamed": renamed,
    }


def build(exe: bytes, pdb: bytes, attachment_csv: bytes, weaponoptions_csv: bytes,
          *, require_pinned: bool = True) -> dict[str, Any]:
    if require_pinned:
        _require_pinned("exe", exe)
        _require_pinned("pdb", pdb)
        _require_pinned("attachmentTable", attachment_csv)
        _require_pinned("weaponOptions", weaponoptions_csv)

    function_ranges = _verify_function_ranges(exe)
    loadout = _find_enum(pdb, "loadoutSlot_t")
    option_groups = _find_enum(pdb, "eWeaponOptionGroup")
    for name, value in EXPECTED_LOADOUT_ENUM.items():
        if loadout.get(name) != value:
            raise ValueError(f"{name}: PDB value {loadout.get(name)!r} != {value}")
    for name, value in EXPECTED_OPTION_GROUP_ENUM.items():
        if option_groups.get(name) != value:
            raise ValueError(f"{name}: PDB value {option_groups.get(name)!r} != {value}")

    table = build_table_mapping(attachment_csv, weaponoptions_csv, require_pinned=False)
    weaponoption_rows = table["weaponoptionRows"]
    camo_ui = table["camoUiRows"]
    render_rows = table["renderRows"]
    mappings = table["mappings"]
    renamed = table["renamed"]

    return {
        "format": FORMAT,
        "source": {
            "serverExe": {"bytes": len(exe), "sha256": _sha(exe)},
            "serverPdb": {"bytes": len(pdb), "sha256": _sha(pdb)},
            "attachmentTable": {"bytes": len(attachment_csv), "sha256": _sha(attachment_csv)},
            "weaponOptions": {"bytes": len(weaponoptions_csv), "sha256": _sha(weaponoptions_csv)},
        },
        "functionRangeProofs": function_ranges,
        "pdbEnums": {
            "loadoutCamoSlots": {k: loadout[k] for k in EXPECTED_LOADOUT_ENUM},
            "weaponOptionGroups": {k: option_groups[k] for k in EXPECTED_OPTION_GROUP_ENUM},
        },
        "runtimeSemantics": {
            "attachmentTableSource": "mp/attachmenttable.csv",
            "weaponOptionsSourceMp": "mp/weaponoptions.csv",
            "weaponOptionsSourceZombies": "mp/weaponoptions_zm.csv",
            "camoWeaponOptionGroup": 0,
            "primaryCamoLoadoutSlot": 4,
            "secondaryCamoLoadoutSlot": 14,
            "knifeCamoLoadoutSlot": 20,
            "renderOptionsCamoBitRange": "bits 0..6",
            "renderOptionsCamoMaskHex": "0x7F",
            "attachmentTableToRenderSelectorBridge": (
                "BG_LoadWeaponOptions assigns source-order group-local subindices; "
                "PlayerCmd_calcWeaponOptions obtains BG_GetWeaponOptionSubIndex for the "
                "primary/secondary/knife camo loadout slot and packs it into renderOptions "
                "bits 0..6; WeaponOptions::InitWeaponOptions keys camoLookupTable by the "
                "decimal camo ID in weaponoptions.csv."
            ),
            "weaponOptionsColumn3": "isMaterialCamo boolean",
            "weaponOptionsColumn4": "one-based WeaponCamo target index",
            "targetSelection": (
                "IsValidRenderOption subtracts one from the selected target index and "
                "indexes camoSets when isMaterialCamo=false or camoMaterials when true."
            ),
        },
        "summary": {
            "attachmentTableWeaponOptionRows": len(weaponoption_rows),
            "attachmentTableCamoRowsIncludingNone": len(camo_ui),
            "weaponOptionsNonNoneCamoRows": len(render_rows),
            "closedNonNoneCamoSelectorCount": len(mappings),
            "directReferenceIdentityCount": len(mappings) - len(renamed),
            "runtimeOrdinalBridgeRenameCount": len(renamed),
            "materialCamoSelectorCount": sum(m["isMaterialCamo"] for m in mappings),
            "camoSetSelectorCount": sum(not m["isMaterialCamo"] for m in mappings),
            "all45SelectorTargetsClosed": True,
        },
        "runtimeOrdinalRenames": [
            {
                "camoId": m["renderOptionCamoId"],
                "attachmentTableReference": m["attachmentTableReference"],
                "weaponOptionsReference": m["weaponOptionsReference"],
                "targetArray": m["runtimeTargetArray"],
                "oneBasedTargetIndex": m["oneBasedWeaponCamoTargetIndex"],
            }
            for m in renamed
        ],
        "camoSelectors": mappings,
        "proofBoundary": (
            "This proof is exact for the pinned CoDMPServer_PC.exe/PDB build and the "
            "SHA-pinned retail patch_mp StringTables. The six differing friendly/reference "
            "strings are bridged only because the executable carries the attachment-table "
            "group-local subindex into renderOptions bits 0..6 and uses that same integer "
            "as the weaponoptions.csv camo ID. No name similarity or source-row adjacency "
            "is used as an alias rule. The dedicated-server BG_LoadWeaponOptions table has "
            "72 runtime entries while the current retail attachmenttable has 99 authored "
            "weaponoption rows; this proof closes camo selector identity but does not claim "
            "that this server build can host all 99 current attachment-table options. "
            "Retail t6mp.exe equivalence remains a separate client-authority gate."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", type=Path, required=True)
    ap.add_argument("--pdb", type=Path, required=True)
    ap.add_argument("--attachment-table", type=Path, required=True)
    ap.add_argument("--weapon-options", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(
        args.exe.read_bytes(), args.pdb.read_bytes(),
        args.attachment_table.read_bytes(), args.weapon_options.read_bytes()
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

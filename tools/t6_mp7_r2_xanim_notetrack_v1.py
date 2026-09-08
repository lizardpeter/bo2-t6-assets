#!/usr/bin/env python3
"""Close MP7 base-viewmodel XAnim/notetrack records from current retail R2 bytes.

Authority:
  * MP7 target membership comes from native OAT Weapon InfoString rows freshly
    dumped from SHA-pinned current R2 FastFiles. Asset-name prefix matching is
    not used to select targets.
  * XAnim structure, ScriptStrings, bone names, notifies, and serialized ranges
    come from the freshly expanded SHA-pinned current R2 common_mp FastFile.

The walker is fail-closed and reproduces the exact Stage18D 104-byte PC32
XAnimParts layout, including inline delta-track children. It does not promote
float-space delta dequantization or runtime notify dispatch semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
from collections import Counter
from pathlib import Path
from typing import Any

FORMAT = "t6-mp7-r2-xanim-notetrack-v1"
FOLLOW = 0xFFFFFFFF
INSERT = 0xFFFFFFFE
SHIFT = 29
MASK = (1 << 29) - 1
XANIM_SIZE = 104
NAME_RE = re.compile(r"[A-Za-z0-9_./+\-]{2,160}")
EXPECTED_COMMON_MP_SHA256 = "93fe48b0f0d8cc6844be875ccad94e0cfcf635f62eeff00ac33f2f668a77cb77"
EXPECTED_EXPANDED_BYTES = 206_493_911
# Exact digest retained by the Stage18D full-inventory and delta proofs and
# independently reproduced by the current-R2 source-closed C expander.
EXPECTED_EXPANDED_SHA256 = "fbd91d0ede8e27bcaaf7af9638a7118050f27519524be36e9234f980bd6170ce"


def sha256_bytes(data: bytes | memoryview) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_info_rows(path: Path, header: str = "WEAPONFILE") -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith(header + "\\"):
        raise ValueError(f"{path}: expected {header!r} header")
    parts = text[len(header) + 1 :].split("\\")
    if len(parts) % 2:
        raise ValueError(f"{path}: odd InfoString token count {len(parts)}")
    occurrence: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for i in range(0, len(parts), 2):
        name, value = parts[i], parts[i + 1]
        rows.append({
            "rowIndex": len(rows),
            "name": name,
            "nameOccurrence": occurrence[name],
            "value": value,
        })
        occurrence[name] += 1
    return rows


def is_xanim_reference_field(name: str) -> bool:
    # OAT emits the WeaponDef XAnim asset-reference slots with *Anim names;
    # dtp_in/loop/out are the three source-schema exceptions. This classification
    # uses field identity only, never the referenced animation asset name.
    return name.endswith("Anim") or name in {"dtp_in", "dtp_loop", "dtp_out"}


def animation_uses(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if is_xanim_reference_field(row["name"]) and row["value"]:
            value = row["value"]
            if not NAME_RE.fullmatch(value):
                raise ValueError(f"animation field {row['name']}: malformed asset reference {value!r}")
            out.append({
                "rowIndex": row["rowIndex"],
                "field": row["name"],
                "fieldOccurrence": row["nameOccurrence"],
                "xanim": value,
            })
    return out


def close_weapon_membership(weapon_paths: dict[str, Path]) -> dict[str, Any]:
    if len(weapon_paths) < 2:
        raise ValueError("at least two physical MP7 Weapon copies are required")
    per_zone = []
    canonical_uses = None
    for zone, path in sorted(weapon_paths.items()):
        rows = parse_info_rows(path)
        uses = animation_uses(rows)
        identity = [(u["field"], u["fieldOccurrence"], u["xanim"]) for u in uses]
        if canonical_uses is None:
            canonical_uses = identity
        elif identity != canonical_uses:
            raise ValueError(f"{zone}: MP7 Weapon XAnim field uses diverge across physical copies")
        per_zone.append({
            "zone": zone,
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "emittedFieldRowCount": len(rows),
            "animationUseCount": len(uses),
            "animationUses": uses,
        })
    assert canonical_uses is not None
    unique = []
    for _, _, name in canonical_uses:
        if name not in unique:
            unique.append(name)
    if len(canonical_uses) != 36:
        raise ValueError(f"expected 36 source-authored non-empty MP7 animation-field uses, got {len(canonical_uses)}")
    if len(unique) != 23:
        raise ValueError(f"expected 23 unique source-authored MP7 base XAnims, got {len(unique)}")
    return {
        "physicalCopies": per_zone,
        "animationUseCountPerCopy": len(canonical_uses),
        "uniqueTargetCount": len(unique),
        "targetNamesInFirstUseOrder": unique,
        "roleUses": [
            {"field": field, "fieldOccurrence": occ, "xanim": name}
            for field, occ, name in canonical_uses
        ],
        "roleTableInvariantAcrossCopies": True,
    }


def read_cstring(data: bytes, pos: int, max_bytes: int = 4096) -> tuple[str, int]:
    end = data.find(b"\0", pos, min(len(data), pos + max_bytes))
    if end < 0:
        raise ValueError(f"unterminated cstring at {pos}")
    raw = data[pos:end]
    try:
        value = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError(f"non-ASCII cstring at {pos}") from exc
    return value, end + 1


def parse_front(data: bytes) -> dict[str, Any]:
    if len(data) < 64:
        raise ValueError("expanded stream too short")
    block_sizes = list(struct.unpack_from("<8I", data, 8))
    pos = 40
    script_count, script_ptr, dep_count, dep_ptr, asset_count, asset_ptr = struct.unpack_from("<6I", data, pos)
    pos += 24

    script_ptrs = list(struct.unpack_from(f"<{script_count}I", data, pos)) if script_count else []
    pos += script_count * 4
    script_strings: list[str | None] = []
    script_rows = []
    for sid, ptr in enumerate(script_ptrs):
        value = None
        raw_off = None
        raw_end = None
        if ptr == FOLLOW:
            raw_off = pos
            value, pos = read_cstring(data, pos)
            raw_end = pos
        elif ptr in (0, INSERT):
            pass
        else:
            # Packed ScriptString targets are intentionally not guessed into raw
            # stream offsets. A target reference to one will fail closed below.
            pass
        script_strings.append(value)
        script_rows.append({
            "id": sid,
            "pointerRaw": f"0x{ptr:08X}",
            "value": value,
            "rawOffset": raw_off,
            "rawEndOffset": raw_end,
        })

    dep_ptrs = list(struct.unpack_from(f"<{dep_count}I", data, pos)) if dep_count else []
    pos += dep_count * 4
    dependency_strings = []
    for i, ptr in enumerate(dep_ptrs):
        value = None
        if ptr == FOLLOW:
            value, pos = read_cstring(data, pos)
        dependency_strings.append({"index": i, "pointerRaw": f"0x{ptr:08X}", "value": value})

    asset_array = pos
    if asset_array + asset_count * 8 > len(data):
        raise ValueError("raw XAsset array exceeds expanded stream")
    xanim_count = 0
    for i in range(asset_count):
        typ, _ = struct.unpack_from("<II", data, asset_array + i * 8)
        if typ == 4:
            xanim_count += 1
    body = asset_array + asset_count * 8
    return {
        "blockSizes": block_sizes,
        "scriptStringCount": script_count,
        "scriptStringPointerRaw": f"0x{script_ptr:08X}",
        "scriptStrings": script_strings,
        "scriptRows": script_rows,
        "dependencyCount": dep_count,
        "dependencyPointerRaw": f"0x{dep_ptr:08X}",
        "dependencies": dependency_strings,
        "assetCount": asset_count,
        "assetPointerRaw": f"0x{asset_ptr:08X}",
        "xanimAssetCount": xanim_count,
        "assetArrayOffset": asset_array,
        "bodyOffset": body,
    }


def pointer_valid(value: int, block_sizes: list[int], nonnull: bool = False) -> bool:
    if value == 0:
        return not nonnull
    if value == FOLLOW:
        return True
    if value == INSERT:
        return not nonnull
    encoded = (value - 1) & 0xFFFFFFFF
    block = encoded >> SHIFT
    off = encoded & MASK
    return block < len(block_sizes) and off < block_sizes[block]


def fixed_record(data: bytes, start: int) -> dict[str, Any]:
    counts = struct.unpack_from("<6H", data, start + 4)
    random_short_count, index_count = struct.unpack_from("<II", data, start + 40)
    framerate, frequency, primed_length, loop_entry = struct.unpack_from("<4f", data, start + 48)
    ptrs = struct.unpack_from("<10I", data, start + 64)
    return {
        "namePtr": struct.unpack_from("<I", data, start)[0],
        "counts": counts,
        "numframes": counts[5],
        "flags": list(data[start + 16 : start + 20]),
        "boneCount": list(data[start + 24 : start + 34]),
        "notifyCount": data[start + 34],
        "assetType": data[start + 35],
        "isDefault": data[start + 36],
        "pad": data[start + 37 : start + 40],
        "randomDataShortCount": random_short_count,
        "indexCount": index_count,
        "framerate": framerate,
        "frequency": frequency,
        "primedLength": primed_length,
        "loopEntry": loop_entry,
        "ptrs": ptrs,
    }


def valid_record(data: bytes, start: int, record: dict[str, Any], block_sizes: list[int]) -> bool:
    name_ptr = record["namePtr"]
    if name_ptr in (0, INSERT):
        return False
    if name_ptr != FOLLOW and not pointer_valid(name_ptr, block_sizes, True):
        return False
    if any(x not in (0, 1) for x in record["flags"]):
        return False
    if record["isDefault"] not in (0, 1) or record["pad"] != b"\0\0\0":
        return False
    if record["assetType"] not in (1, 2, 6):
        return False
    if record["notifyCount"] > 128 or record["boneCount"][9] > 255 or record["numframes"] > 2048:
        return False
    if record["framerate"] not in (24.0, 30.0):
        return False
    if record["numframes"] > 0 and abs(record["frequency"] - record["framerate"] / record["numframes"]) > 2e-6:
        return False
    if record["randomDataShortCount"] > 2_000_000 or record["indexCount"] > 2_000_000:
        return False
    if any(not math.isfinite(x) or abs(x) > 100000 for x in (record["frequency"], record["primedLength"], record["loopEntry"])):
        return False
    if any(not pointer_valid(v, block_sizes, False) for v in record["ptrs"]):
        return False
    if name_ptr == FOLLOW:
        try:
            name, _ = read_cstring(data, start + XANIM_SIZE, 161)
        except ValueError:
            return False
        if not NAME_RE.fullmatch(name):
            return False
    return True


def require_room(data: bytes, pos: int, count: int, label: str) -> int:
    end = pos + count
    if count < 0 or end < pos or end > len(data):
        raise ValueError(f"{label}: serialized range out of bounds")
    return end


def parse_indices(data: bytes, pos: int, count: int, unit: int) -> tuple[list[int], int]:
    end = require_room(data, pos, count * unit, "delta indices")
    if unit == 1:
        return list(data[pos:end]), end
    return (list(struct.unpack_from(f"<{count}H", data, pos)) if count else []), end


def walk_trans(data: bytes, pos: int, numframes: int) -> int:
    require_room(data, pos, 4, "trans header")
    size = struct.unpack_from("<H", data, pos)[0]
    small = data[pos + 2]
    if small not in (0, 1):
        raise ValueError("bad smallTrans")
    if size == 0:
        return require_room(data, pos, 16, "trans constant")
    count = size + 1
    unit = 1 if numframes < 256 else 2
    require_room(data, pos, 32, "trans keyed header")
    frames_ptr = struct.unpack_from("<I", data, pos + 28)[0]
    _, p = parse_indices(data, pos + 32, count, unit)
    if frames_ptr == FOLLOW:
        p = require_room(data, p, count * (3 if small else 6), "trans frames")
    elif frames_ptr == INSERT:
        raise ValueError("inline trans frames use INSERT pointer")
    return p


def walk_quat2(data: bytes, pos: int, numframes: int) -> int:
    require_room(data, pos, 4, "quat2 header")
    size = struct.unpack_from("<H", data, pos)[0]
    if size == 0:
        return require_room(data, pos, 8, "quat2 constant")
    count = size + 1
    unit = 1 if numframes < 256 else 2
    require_room(data, pos, 8, "quat2 keyed header")
    frames_ptr = struct.unpack_from("<I", data, pos + 4)[0]
    _, p = parse_indices(data, pos + 8, count, unit)
    if frames_ptr == FOLLOW:
        p = require_room(data, p, count * 4, "quat2 frames")
    elif frames_ptr == INSERT:
        raise ValueError("inline quat2 frames use INSERT pointer")
    return p


def walk_quat(data: bytes, pos: int, numframes: int) -> int:
    require_room(data, pos, 4, "quat header")
    size = struct.unpack_from("<H", data, pos)[0]
    if size == 0:
        return require_room(data, pos, 12, "quat constant")
    count = size + 1
    unit = 1 if numframes < 256 else 2
    require_room(data, pos, 8, "quat keyed header")
    frames_ptr = struct.unpack_from("<I", data, pos + 4)[0]
    _, p = parse_indices(data, pos + 8, count, unit)
    if frames_ptr == FOLLOW:
        p = require_room(data, p, count * 8, "quat frames")
    elif frames_ptr == INSERT:
        raise ValueError("inline quat frames use INSERT pointer")
    return p


def walk_record(data: bytes, start: int, record: dict[str, Any]) -> dict[str, Any]:
    pos = start + XANIM_SIZE
    inline_name = None
    name_raw_range = None
    if record["namePtr"] == FOLLOW:
        name_start = pos
        inline_name, pos = read_cstring(data, pos, 256)
        name_raw_range = [name_start, pos]

    ptrs = record["ptrs"]
    bone_ids = None
    bone_range = None
    if ptrs[0] == FOLLOW:
        bone_start = pos
        count = record["boneCount"][9]
        bone_end = require_room(data, pos, count * 2, "bone ScriptStrings")
        bone_ids = list(struct.unpack_from(f"<{count}H", data, pos)) if count else []
        pos = bone_end
        bone_range = [bone_start, bone_end]

    notifies = None
    notify_range = None
    if ptrs[8] == FOLLOW:
        notify_start = pos
        notify_end = require_room(data, pos, record["notifyCount"] * 8, "XAnimNotifyInfo")
        notifies = []
        for i in range(record["notifyCount"]):
            off = pos + i * 8
            sid = struct.unpack_from("<H", data, off)[0]
            pad = data[off + 2 : off + 4]
            time = struct.unpack_from("<f", data, off + 4)[0]
            if pad != b"\0\0":
                raise ValueError("notify padding is non-zero")
            if not math.isfinite(time):
                raise ValueError("notify time is non-finite")
            notifies.append({"index": i, "scriptStringId": sid, "serializedTimeFloat": time, "rawOffset": off})
        pos = notify_end
        notify_range = [notify_start, notify_end]

    if ptrs[9] == FOLLOW:
        require_room(data, pos, 12, "XAnimDeltaPart")
        trans, quat2, quat = struct.unpack_from("<3I", data, pos)
        pos += 12
        for child_ptr, walker in ((trans, walk_trans), (quat2, walk_quat2), (quat, walk_quat)):
            if child_ptr == FOLLOW:
                pos = walker(data, pos, record["numframes"])
            elif child_ptr == INSERT:
                raise ValueError("delta child pointer is INSERT")

    arrays = [
        (record["counts"][0], 1, ptrs[1], "dataByte"),
        (record["counts"][1], 2, ptrs[2], "dataShort"),
        (record["counts"][2], 4, ptrs[3], "dataInt"),
        (record["randomDataShortCount"], 2, ptrs[4], "randomDataShort"),
        (record["counts"][3], 1, ptrs[5], "randomDataByte"),
        (record["counts"][4], 4, ptrs[6], "randomDataInt"),
        (record["indexCount"], 1 if record["numframes"] < 256 else 2, ptrs[7], "indices"),
    ]
    for count, unit, ptr, label in arrays:
        if ptr == FOLLOW:
            pos = require_room(data, pos, count * unit, label)

    if pos <= start or pos > len(data):
        raise ValueError("invalid walked XAnim range")
    return {
        "end": pos,
        "name": inline_name,
        "nameRawRange": name_raw_range,
        "boneScriptStringIds": bone_ids,
        "boneRawRange": bone_range,
        "notifies": notifies,
        "notifyRawRange": notify_range,
    }


def scan_xanims(data: bytes, front: dict[str, Any]) -> list[dict[str, Any]]:
    body = front["bodyOffset"]
    block_sizes = front["blockSizes"]
    starts: set[int] = set()
    records: list[dict[str, Any]] = []
    for framerate in (24.0, 30.0):
        pattern = struct.pack("<f", framerate)
        p = body + 48
        while True:
            hit = data.find(pattern, p)
            if hit < 0:
                break
            p = hit + 1
            start = hit - 48
            if start < body or start in starts or start + XANIM_SIZE > len(data):
                continue
            fixed = fixed_record(data, start)
            if not valid_record(data, start, fixed, block_sizes):
                continue
            try:
                walked = walk_record(data, start, fixed)
            except Exception:
                continue
            end = walked["end"]
            starts.add(start)
            records.append({
                "rawStructOffset": start,
                "rawEndOffset": end,
                "serializedBytes": end - start,
                "serializedSha256": sha256_bytes(memoryview(data)[start:end]),
                "nameKind": "inline" if fixed["namePtr"] == FOLLOW else "packed",
                "name": walked["name"],
                "namePtrRaw": f"0x{fixed['namePtr']:08X}",
                "numframes": fixed["numframes"],
                "framerate": fixed["framerate"],
                "frequency": fixed["frequency"],
                "assetType": fixed["assetType"],
                "deltaFlag": fixed["flags"][1],
                "boneNameCount": fixed["boneCount"][9],
                "notifyCount": fixed["notifyCount"],
                "boneScriptStringIds": walked["boneScriptStringIds"],
                "notifies": walked["notifies"],
            })
    records.sort(key=lambda r: r["rawStructOffset"])
    starts_sorted = {r["rawStructOffset"] for r in records}
    for i, row in enumerate(records):
        next_start = records[i + 1]["rawStructOffset"] if i + 1 < len(records) else None
        row["endHitsRecordStart"] = row["rawEndOffset"] in starts_sorted
        row["gapToNextStructuralRecord"] = None if next_start is None else next_start - row["rawEndOffset"]
    return records


def resolve_script_string(script_strings: list[str | None], sid: int, context: str) -> str:
    if sid < 0 or sid >= len(script_strings):
        raise ValueError(f"{context}: ScriptString id {sid} out of range")
    value = script_strings[sid]
    if value is None:
        raise ValueError(f"{context}: ScriptString id {sid} is not inline-resolved")
    return value


def build(stream: Path, common_mp_ff: Path, weapon_paths: dict[str, Path]) -> dict[str, Any]:
    ff_sha = hashlib.sha256(common_mp_ff.read_bytes()).hexdigest()
    if ff_sha != EXPECTED_COMMON_MP_SHA256:
        raise ValueError(f"common_mp FastFile SHA mismatch: {ff_sha}")
    data = stream.read_bytes()
    expanded_sha = hashlib.sha256(data).hexdigest()
    if len(data) != EXPECTED_EXPANDED_BYTES or expanded_sha != EXPECTED_EXPANDED_SHA256:
        raise ValueError(f"expanded common_mp canary mismatch: bytes={len(data)} sha256={expanded_sha}")

    membership = close_weapon_membership(weapon_paths)
    front = parse_front(data)
    records = scan_xanims(data, front)
    if len(records) != front["xanimAssetCount"]:
        raise ValueError(f"structural XAnim count {len(records)} != XAsset-list count {front['xanimAssetCount']}")
    overlaps = [r for r in records if (r["gapToNextStructuralRecord"] is not None and r["gapToNextStructuralRecord"] < 0)]
    if overlaps:
        raise ValueError(f"{len(overlaps)} structural XAnim overlaps")
    if front["assetCount"] != 6082:
        raise ValueError(f"expected retail common_mp XAsset count 6082, got {front['assetCount']}")
    if front["xanimAssetCount"] != 4233:
        raise ValueError(f"expected retail common_mp XAnim count 4233, got {front['xanimAssetCount']}")
    if front["scriptStringCount"] != 1189:
        raise ValueError(f"expected retail common_mp ScriptString count 1189, got {front['scriptStringCount']}")

    by_name: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if record["name"] is not None:
            by_name.setdefault(record["name"], []).append(record)

    target_rows = []
    for name in membership["targetNamesInFirstUseOrder"]:
        hits = by_name.get(name, [])
        if len(hits) != 1:
            raise ValueError(f"target XAnim {name!r}: expected one exact inline structural record, got {len(hits)}")
        src = hits[0]
        if src["boneScriptStringIds"] is None:
            raise ValueError(f"target XAnim {name!r}: bone ScriptString array is not inline")
        if src["notifies"] is None:
            raise ValueError(f"target XAnim {name!r}: notify array is not inline")
        bone_names = [resolve_script_string(front["scriptStrings"], sid, f"{name} bone") for sid in src["boneScriptStringIds"]]
        notifies = []
        for n in src["notifies"]:
            nn = dict(n)
            nn["name"] = resolve_script_string(front["scriptStrings"], n["scriptStringId"], f"{name} notify")
            notifies.append(nn)
        role_uses = [u for u in membership["roleUses"] if u["xanim"] == name]
        target_rows.append({
            "name": name,
            "weaponRoleUses": role_uses,
            "rawStructOffset": src["rawStructOffset"],
            "rawEndOffset": src["rawEndOffset"],
            "serializedBytes": src["serializedBytes"],
            "serializedSha256": src["serializedSha256"],
            "numframes": src["numframes"],
            "framerate": src["framerate"],
            "frequency": src["frequency"],
            "assetType": src["assetType"],
            "deltaFlag": src["deltaFlag"],
            "boneNameCount": src["boneNameCount"],
            "boneScriptStringIds": src["boneScriptStringIds"],
            "boneNames": bone_names,
            "notifyCount": src["notifyCount"],
            "notifies": notifies,
        })

    if len(target_rows) != 23:
        raise ValueError("target closure count changed")
    return {
        "format": FORMAT,
        "authority": {
            "weaponAnimationMembership": "native OAT Weapon InfoString rows freshly dumped from SHA-pinned current R2 retail FastFiles",
            "xanimSerializedRecords": "freshly expanded SHA-pinned current R2 common_mp.ff bytes",
            "runtimeRetailClientWinnerSelected": False,
            "historicalStage18dUsedAsAuthority": False,
        },
        "source": {
            "commonMpFastFile": {"path": str(common_mp_ff), "bytes": common_mp_ff.stat().st_size, "sha256": ff_sha},
            "expandedCommonMp": {"path": str(stream), "bytes": len(data), "sha256": expanded_sha},
        },
        "weaponMembership": membership,
        "front": {
            "blockSizes": front["blockSizes"],
            "scriptStringCount": front["scriptStringCount"],
            "inlineResolvedScriptStringCount": sum(v is not None for v in front["scriptStrings"]),
            "dependencyCount": front["dependencyCount"],
            "assetCount": front["assetCount"],
            "xanimAssetCount": front["xanimAssetCount"],
            "assetArrayOffset": front["assetArrayOffset"],
            "bodyOffset": front["bodyOffset"],
        },
        "fullInventory": {
            "structuralRecordCount": len(records),
            "inlineNameRecordCount": sum(r["nameKind"] == "inline" for r in records),
            "packedNameRecordCount": sum(r["nameKind"] == "packed" for r in records),
            "overlapCount": 0,
            "endHitsAnotherRecordStartCount": sum(bool(r["endHitsRecordStart"]) for r in records),
        },
        "targets": target_rows,
        "summary": {
            "weaponPhysicalCopyCount": len(membership["physicalCopies"]),
            "weaponAnimationUseCountPerCopy": membership["animationUseCountPerCopy"],
            "uniqueTargetXAnimCount": len(target_rows),
            "fullXAnimInventoryCount": len(records),
            "targetNotifyCount": sum(r["notifyCount"] for r in target_rows),
            "targetWithNotifiesCount": sum(r["notifyCount"] > 0 for r in target_rows),
            "targetBoneReferenceCount": sum(r["boneNameCount"] for r in target_rows),
        },
        "proofBoundary": (
            "Target membership is selected only by source Weapon XAnim-reference fields and is invariant across the two physical current-R2 MP7 Weapon copies. "
            "Every target XAnim is a unique structurally valid inline-name record in the complete current-R2 common_mp XAnim census. "
            "Bone and notify names are resolved only through the serialized ScriptString table. Serialized notify float values are preserved exactly; runtime dispatch semantics, time-unit interpretation, delta dequantization, and the active retail-client Weapon copy remain unpromoted."
        ),
    }


def parse_labeled_paths(values: list[str]) -> dict[str, Path]:
    out = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"expected LABEL=PATH, got {raw!r}")
        label, path = raw.split("=", 1)
        if not label or label in out:
            raise ValueError(f"invalid/duplicate label {label!r}")
        p = Path(path)
        if not p.is_file():
            raise ValueError(f"{label}: missing {p}")
        out[label] = p
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", type=Path, required=True)
    ap.add_argument("--common-mp-ff", type=Path, required=True)
    ap.add_argument("--weapon", action="append", default=[], metavar="LABEL=PATH")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.stream, args.common_mp_ff, parse_labeled_paths(args.weapon))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    for row in doc["targets"]:
        print(f"{row['name']} frames={row['numframes']} fps={row['framerate']:g} notifies={row['notifyCount']} sha256={row['serializedSha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

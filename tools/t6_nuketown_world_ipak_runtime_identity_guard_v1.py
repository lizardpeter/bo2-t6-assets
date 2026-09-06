#!/usr/bin/env python3
"""Verify Nuketown GfxWorld streamed-image identity exactly as retail T6 PC does.

Retail PC evidence:
  IPak_CompareImagePartHashes @ 0x00921A60 orders image parts by
    (GfxImage::hash [+0x4c], GfxStreamedPartInfo::hash [+0x28]).
  IPak_BuildAdjacencyInfo @ 0x00921B30 joins that pair against each
    IPakIndexEntry (nameHash, dataHash) before filling runtime part fields.

Therefore a same-name IPAK payload with the wrong dataHash is NOT an exact
retail match, and a dataHash-only alias with a different nameHash is also NOT
an exact match. This guard deliberately fails closed on both.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from collections import Counter, defaultdict
from pathlib import Path

FIXED = 0x50
OFF_BASE_SIZE = 0x0C
OFF_DIMS = 0x14
OFF_STREAMING = 0x1B
OFF_PART = 0x24
OFF_PART_HASH = 0x28
OFF_PART_COUNT = 0x3C
OFF_NAME_PTR = 0x48
OFF_IMAGE_HASH = 0x4C


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def r_hash_string(s: str) -> int:
    h = 0
    for c in s.encode("latin1"):
        h = ((33 * h) ^ (c | 0x20)) & 0xFFFFFFFF
    return h


def load_ipak_index(path: Path):
    b = path.read_bytes()
    magic, ver, total, section_count = struct.unpack_from("<4sIII", b, 0)
    if magic != b"KAPI" or ver != 0x50000 or total != len(b):
        raise ValueError("not a T6 PC IPAK")
    sections = [struct.unpack_from("<IIII", b, 16 + 16*i) for i in range(section_count)]
    index = [s for s in sections if s[0] == 1]
    if len(index) != 1:
        raise ValueError("expected one IPAK index section")
    _, off, size, count = index[0]
    if count * 16 > size:
        raise ValueError("invalid IPAK index section")
    rows = [struct.unpack_from("<IIII", b, off + 16*i) for i in range(count)]
    # On-disk order is dataHash, nameHash, relativeOffset, rawSize.
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expanded", type=Path, required=True)
    ap.add_argument("--materials", type=Path, required=True)
    ap.add_argument("--ipak", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    expanded = a.expanded.read_bytes()
    mats = json.loads(a.materials.read_text(encoding="utf-8"))["materials"]
    entries = load_ipak_index(a.ipak)
    tuple_count = Counter((e[0], e[1]) for e in entries)  # (dataHash,nameHash)
    by_name = defaultdict(list)
    by_data = defaultdict(list)
    for e in entries:
        by_data[e[0]].append(e)
        by_name[e[1]].append(e)

    seen = set()
    rows = []
    special_shadow = 0
    all_levelsize_exact = True
    all_runtime_tail_zero = True

    for mat in mats:
        for tex in mat.get("textures", []):
            im = tex.get("image") or {}
            if not im.get("inline") or not im.get("name"):
                continue
            name = im["name"]
            key = (name, int(im.get("semantic", tex.get("semantic", -1))))
            if key in seen:
                continue
            seen.add(key)
            start = int(im["start"])
            fixed = expanded[start:start+FIXED]
            if len(fixed) != FIXED:
                raise ValueError(f"{name}: truncated GfxImage")

            image_hash = struct.unpack_from("<I", fixed, OFF_IMAGE_HASH)[0]
            expected_hash = r_hash_string(name)
            if name == ",shadow" and image_hash == 0 and int(im.get("hash", 0)) == 0:
                special_shadow += 1
                continue
            if image_hash != expected_hash or int(im.get("hash", -1)) != expected_hash:
                raise ValueError(f"{name}: image hash mismatch")
            if struct.unpack_from("<I", fixed, OFF_NAME_PTR)[0] != 0xFFFFFFFF:
                raise ValueError(f"{name}: name pointer is not FOLLOWING")
            if fixed[OFF_STREAMING] != int(im.get("streaming", -1)):
                raise ValueError(f"{name}: streaming mismatch")
            if fixed[OFF_PART_COUNT] != int(im.get("streamedPartCount", -1)):
                raise ValueError(f"{name}: streamedPartCount mismatch")
            if fixed[OFF_PART_COUNT] != 1:
                raise ValueError(f"{name}: expected one streamed part for this census")

            level_count_and_size = struct.unpack_from("<I", fixed, OFF_PART)[0]
            level_count = level_count_and_size & 0xF
            level_size = level_count_and_size >> 4
            part_hash = struct.unpack_from("<I", fixed, OFF_PART_HASH)[0]
            base_size = struct.unpack_from("<I", fixed, OFF_BASE_SIZE)[0]
            width, height, depth = struct.unpack_from("<HHH", fixed, OFF_DIMS)
            runtime_tail = fixed[OFF_PART+8:OFF_PART+24]
            all_levelsize_exact &= level_size == base_size + 64
            all_runtime_tail_zero &= runtime_tail == b"\0" * 16

            exact_count = tuple_count[(part_hash, image_hash)]
            names = by_name.get(image_hash, [])
            datas = by_data.get(part_hash, [])
            if exact_count == 1:
                cls = "exact_runtime_tuple"
            elif len(names) == 1:
                cls = "same_name_wrong_payload_hash"
            elif len(datas) == 1:
                cls = "same_payload_hash_wrong_name"
            else:
                cls = "absent_from_map_ipak"

            rows.append({
                "image": name,
                "material": mat["name"],
                "semantic": int(tex.get("semantic", -1)),
                "imageHash": image_hash,
                "streamedPartHash": part_hash,
                "classification": cls,
                "exactTupleCount": exact_count,
                "nameHashCandidateCount": len(names),
                "dataHashCandidateCount": len(datas),
                "levelCount": level_count,
                "levelSize": level_size,
                "baseSize": base_size,
                "width": width,
                "height": height,
                "depth": depth,
            })

    counts = Counter(r["classification"] for r in rows)
    summary = {
        "rows": len(rows),
        "specialZeroHashShadowSkipped": special_shadow,
        "ipakEntries": len(entries),
        "classificationCounts": dict(sorted(counts.items())),
        "allLevelSizeEqualsBaseSizePlusIwiHeader64": bool(all_levelsize_exact),
        "allSerializedPartRuntimeFieldsZeroBeforeIpSharedIndexJoin": bool(all_runtime_tail_zero),
    }
    doc = {
        "format": "t6-nuketown-world-ipak-runtime-identity-v1",
        "map": "mp_nuketown_2020",
        "source": {
            "expanded": {"bytes": a.expanded.stat().st_size, "sha256": sha256(a.expanded)},
            "materials": {"bytes": a.materials.stat().st_size, "sha256": sha256(a.materials)},
            "ipak": {"bytes": a.ipak.stat().st_size, "sha256": sha256(a.ipak)},
        },
        "retailPcEvidence": {
            "IPak_CompareImagePartHashes": "0x00921A60",
            "IPak_BuildAdjacencyInfo": "0x00921B30",
            "joinKey": "(GfxImage.hash@+0x4c,GfxStreamedPartInfo.hash@+0x28)==(IPAK.nameHash,IPAK.dataHash)",
        },
        "summary": summary,
        "rows": rows,
    }
    a.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

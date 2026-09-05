#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import ctypes
import ctypes.util
import hashlib
import importlib.util
import json
import struct
import urllib.request
import zlib
from collections import Counter
from pathlib import Path

DEFAULT_URL = "https://r2.houseofkublai.com/bo2/zone/all/base.ipak"
EXPECTED_BYTES = 2614362112
EXPECTED_INDEX_ENTRIES = 13366
EXPECTED_CANDIDATES = 43
EXPECTED_CF_SKIP = 9


def load_zjson(path: Path) -> dict:
    return json.loads(zlib.decompress(base64.b64decode(path.read_text().strip())))


def range_get(url: str, start: int, end: int) -> tuple[bytes, str]:
    req = urllib.request.Request(
        url,
        headers={"Range": f"bytes={start}-{end}", "User-Agent": "bo2-t6-assets-exact43/1"},
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        if response.status != 206:
            raise RuntimeError(f"range not honored: HTTP {response.status}")
        content_range = response.headers.get("Content-Range", "")
        data = response.read()
    if len(data) != end - start + 1:
        raise RuntimeError(f"range length mismatch: {content_range}")
    return data, content_range


def align(value: int, amount: int) -> int:
    return (value + amount - 1) // amount * amount


def lzo_decoder():
    libname = ctypes.util.find_library("lzo2")
    if not libname:
        raise RuntimeError("liblzo2 not found")
    fn = ctypes.CDLL(libname).lzo1x_decompress_safe
    fn.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p]
    fn.restype = ctypes.c_int
    return fn


def extract_entry(segment: bytes, absolute_start: int, entry: tuple[int, int, int, int], lzo) -> tuple[bytes, int, int, int]:
    data_hash, _name_hash, _relative_offset, raw_size = entry
    absolute = absolute_start
    absolute_end = absolute_start + raw_size
    output = bytearray()
    blocks = skips = skip_bytes = 0
    while absolute < absolute_end:
        absolute = align(absolute, 128)
        if absolute >= absolute_end:
            break
        local = absolute - absolute_start
        header = segment[local:local + 128]
        if len(header) != 128:
            raise ValueError("truncated IPAK block header")
        command_offset = struct.unpack_from("<I", header, 0)[0]
        file_offset = command_offset & 0xFFFFFF
        command_count = (command_offset >> 24) & 0xFF
        if command_count > 31:
            raise ValueError(f"IPAK block command count {command_count}")
        commands = []
        for index in range(command_count):
            word = struct.unpack_from("<I", header, 4 + 4 * index)[0]
            commands.append((word & 0xFFFFFF, (word >> 24) & 0xFF))
        if any(kind in (0, 1) for _, kind in commands) and file_offset != len(output):
            raise ValueError(f"IPAK output offset mismatch {file_offset} != {len(output)}")
        pos = local + 128
        for size, kind in commands:
            blob = segment[pos:pos + size]
            if len(blob) != size:
                raise ValueError("truncated IPAK command")
            if kind == 0:
                output.extend(blob)
            elif kind == 1:
                dst = ctypes.create_string_buffer(0x8000)
                dst_len = ctypes.c_size_t(0x8000)
                src = ctypes.create_string_buffer(blob)
                rc = lzo(src, len(blob), dst, ctypes.byref(dst_len), None)
                if rc:
                    raise ValueError(f"LZO error {rc}")
                output.extend(dst.raw[:dst_len.value])
            elif kind == 0xCF:
                # Retail T6 padding/skip command: consume stored bytes, emit none.
                skips += 1
                skip_bytes += size
            else:
                raise ValueError(f"unsupported IPAK command {kind:#x}")
            pos += size
        absolute = absolute_start + pos
        blocks += 1
        if blocks > 10000:
            raise ValueError("IPAK block runaway")
    result = bytes(output)
    crc29 = zlib.crc32(result) & 0x1FFFFFFF
    if crc29 != data_hash:
        raise ValueError(f"CRC29 {crc29:08x} != {data_hash:08x}")
    return result, blocks, skips, skip_bytes


def build(url: str, alias_bank_path: Path, texture_tool_path: Path, out_dir: Path) -> dict:
    bank = load_zjson(alias_bank_path)
    if bank.get("aliasCount") != 81 or bank.get("conflictCount") != 0:
        raise ValueError("unexpected alias-bank boundary")

    spec = importlib.util.spec_from_file_location("t6tex", texture_tool_path)
    t6 = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(t6)

    out_dir.mkdir(parents=True, exist_ok=True)
    head, _ = range_get(url, 0, 65535)
    magic, version, total, section_count = struct.unpack_from("<4sIII", head, 0)
    if magic != b"KAPI" or version != 0x50000:
        raise ValueError("invalid T6 IPAK")
    if total != EXPECTED_BYTES:
        raise ValueError(f"base.ipak bytes {total} != {EXPECTED_BYTES}")
    sections = [struct.unpack_from("<IIII", head, 16 + 16 * i) for i in range(section_count)]
    data_sections = [s for s in sections if s[0] == 2]
    index_sections = [s for s in sections if s[0] == 1]
    if len(data_sections) != 1 or len(index_sections) != 1:
        raise ValueError("missing unique IPAK data/index section")
    data_section = data_sections[0]
    _, index_offset, index_size, index_count = index_sections[0]
    if index_count != EXPECTED_INDEX_ENTRIES or index_count * 16 > index_size:
        raise ValueError(f"unexpected IPAK index boundary: {index_count}")
    index_bytes, _ = range_get(url, index_offset, index_offset + index_count * 16 - 1)
    by_name: dict[int, tuple[int, int, int, int]] = {}
    for i in range(index_count):
        entry = struct.unpack_from("<IIII", index_bytes, i * 16)
        if entry[1] in by_name:
            raise ValueError(f"duplicate IPAK nameHash {entry[1]:08x}")
        by_name[entry[1]] = entry

    lzo = lzo_decoder()
    rows = []
    stats = Counter()
    network_bytes = len(head) + len(index_bytes)
    for alias in bank["aliases"]:
        name_hash = int(alias["hash"])
        data_hash = int(alias["dataHash"])
        entry = by_name.get(name_hash)
        if entry is None or entry[0] != data_hash:
            continue
        row = {key: alias[key] for key in ("name", "hash", "dataHash", "semantic", "width", "height", "depth", "suffix", "slot")}
        row["nameHashHex"] = f"{name_hash:08x}"
        row["dataHashHex"] = f"{data_hash:08x}"
        try:
            start = data_section[1] + entry[2]
            end = start + entry[3] - 1
            segment, content_range = range_get(url, start, end)
            network_bytes += len(segment)
            iwi, blocks, skips, skipped_bytes = extract_entry(segment, start, entry, lzo)
            fmt, flags, width, height, depth, gamma, _sizes = t6.parse_iwi27(iwi)
            expected = (int(alias["width"]), int(alias["height"]), int(alias["depth"]))
            if (width, height, depth) != expected:
                raise ValueError(f"dimensions {(width, height, depth)} != {expected}")
            safe = f"{len(rows):03d}_{alias['name'].replace('/', '__').replace('~', '_tilde_')}"
            iwi_path = out_dir / f"{safe}.iwi"
            iwi_path.write_bytes(iwi)
            png, _meta = t6.iwi_top_png(iwi, normal_semantic=(int(alias["semantic"]) == 5))
            png_path = out_dir / f"{safe}.png"
            png_path.write_bytes(png)
            row.update({
                "status": "validated", "contentRange": content_range, "ipakEntry": list(entry),
                "blockCount": blocks, "skipCommandCount": skips, "skipBytes": skipped_bytes,
                "format": fmt, "flags": flags, "gamma": gamma,
                "iwiFile": iwi_path.name, "iwiBytes": len(iwi), "iwiSha256": hashlib.sha256(iwi).hexdigest(),
                "pngFile": png_path.name, "pngBytes": len(png), "pngSha256": hashlib.sha256(png).hexdigest(),
                "crc29Validated": True, "iwi27Validated": True, "dimensionsValidated": True,
            })
            stats["validated"] += 1
            if skips:
                stats["validatedWithCfSkip"] += 1
        except Exception as exc:
            row.update({"status": "rejected", "ipakEntry": list(entry), "reason": f"{type(exc).__name__}: {exc}"})
            stats["rejected"] += 1
        rows.append(row)

    report = {
        "format": "t6-base-ipak-exact-alias-extraction-cf-skip-v1",
        "sourceUrl": url, "sourceBytes": total, "indexEntryCount": index_count,
        "candidateCount": len(rows), "summary": dict(stats), "networkBytes": network_bytes,
        "rows": rows,
        "decoderRule": "command 0=raw, 1=LZO, 0xCF=skip/padding; all other command bytes fail closed",
    }
    report_path = out_dir / "BASE_IPAK_EXACT_ALIAS_CF_SKIP_V1.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if len(rows) != EXPECTED_CANDIDATES or stats["validated"] != EXPECTED_CANDIDATES or stats["rejected"]:
        raise ValueError(f"exact43 boundary failed: candidates={len(rows)} stats={dict(stats)}")
    if stats["validatedWithCfSkip"] != EXPECTED_CF_SKIP:
        raise ValueError(f"0xCF exact43 count {stats['validatedWithCfSkip']} != {EXPECTED_CF_SKIP}")
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--alias-bank", type=Path, required=True)
    ap.add_argument("--texture-tool", type=Path, default=Path("tools/t6_nuketown_ipak_partial_texture_export_v2.py"))
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    report = build(args.url, args.alias_bank, args.texture_tool, args.out_dir)
    print(json.dumps({"candidateCount": report["candidateCount"], "summary": report["summary"], "networkBytes": report["networkBytes"]}, indent=2))


if __name__ == "__main__":
    main()

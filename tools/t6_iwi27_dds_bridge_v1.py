#!/usr/bin/env python3
"""Losslessly wrap source-proven T6 PC IWI27 BC payloads as standard DDS.

This bridge is deliberately narrow.  It accepts only a staged-payload manifest
whose IWI bytes have already been exact-retail resolved, plus a green
``t6-iwi27-mip-layout-proof-v2`` over the same source payload population.

No pixel decompression or recompression occurs.  IWI stores the compressed mip
blocks smallest->largest; DDS stores them largest->smallest.  The bridge splits
IWI by the source-proven BC mip byte counts, reverses whole mip byte slices, and
prepends a standard 128-byte legacy DDS container header.

Observed/promoted formats:
  IWI 0x0B DXT1 -> DDS DXT1 / BC1
  IWI 0x0D DXT5 -> DDS DXT5 / BC3
  IWI 0x0E DXN  -> DDS ATI2 / BC5_UNORM

IWI 0x0C/DXT3 is intentionally not promoted by this v1 bridge because it was
not present in the exact 81-payload Nuketown proof corpus and the production
DDS decoder does not currently accept DXT3.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

import t6_iwi27_mip_layout_probe_v1 as probe
import t6_iwi27_mip_layout_proof_v2 as layout

FORMAT = "t6-iwi27-dds-bridge-v1"
STAGED_FORMAT = "t6-nuketown-shared-ipak-staged-payloads-v1"
LAYOUT_FORMAT = "t6-iwi27-mip-layout-proof-v2"
DDS_HEADER_BYTES = 128
DDS_FOURCC = {
    0x0B: b"DXT1",
    0x0D: b"DXT5",
    0x0E: b"ATI2",
}
DDS_FORMAT_NAMES = {
    0x0B: "DXT1/BC1",
    0x0D: "DXT5/BC3",
    0x0E: "ATI2/BC5_UNORM",
}


class BridgeError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _load_json(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    try:
        doc = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise BridgeError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise BridgeError(f"{path}: top level is not an object")
    return doc, raw


def _safe_alias_path(name: str) -> Path:
    if not name or "\0" in name or "\\" in name:
        raise BridgeError(f"unsafe/empty GfxImage name {name!r}")
    pure = PurePosixPath(name)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise BridgeError(f"unsafe GfxImage path {name!r}")
    return Path(*pure.parts).with_name(pure.name + ".dds")


def _dds_header(width: int, height: int, mip_count: int, top_bytes: int, fourcc: bytes) -> bytes:
    if len(fourcc) != 4:
        raise BridgeError(f"invalid DDS FOURCC {fourcc!r}")
    if width <= 0 or height <= 0 or mip_count <= 0 or top_bytes <= 0:
        raise BridgeError("invalid DDS dimensions/mip metadata")

    # DDS_HEADER begins immediately after the 4-byte magic.
    header = bytearray(124)
    DDSD_CAPS = 0x00000001
    DDSD_HEIGHT = 0x00000002
    DDSD_WIDTH = 0x00000004
    DDSD_PIXELFORMAT = 0x00001000
    DDSD_MIPMAPCOUNT = 0x00020000
    DDSD_LINEARSIZE = 0x00080000
    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_LINEARSIZE
    if mip_count > 1:
        flags |= DDSD_MIPMAPCOUNT

    struct.pack_into("<I", header, 0, 124)
    struct.pack_into("<I", header, 4, flags)
    struct.pack_into("<I", header, 8, height)
    struct.pack_into("<I", header, 12, width)
    struct.pack_into("<I", header, 16, top_bytes)
    struct.pack_into("<I", header, 20, 0)  # depth: 2D only
    struct.pack_into("<I", header, 24, mip_count)

    # DDS_PIXELFORMAT at DDS_HEADER offset 72.
    struct.pack_into("<I", header, 72, 32)
    struct.pack_into("<I", header, 76, 0x00000004)  # DDPF_FOURCC
    header[80:84] = fourcc

    DDSCAPS_COMPLEX = 0x00000008
    DDSCAPS_TEXTURE = 0x00001000
    DDSCAPS_MIPMAP = 0x00400000
    caps = DDSCAPS_TEXTURE
    if mip_count > 1:
        caps |= DDSCAPS_COMPLEX | DDSCAPS_MIPMAP
    struct.pack_into("<I", header, 104, caps)
    return b"DDS " + bytes(header)


def _split_iwi_mips(raw: bytes, *, fmt: int, width: int, height: int) -> tuple[list[bytes], list[int]]:
    if len(raw) < probe.HEADER_BYTES:
        raise BridgeError("truncated IWI")
    sizes = probe.expected_mips(width, height, probe.BLOCK_BYTES[fmt])
    payload = raw[probe.HEADER_BYTES:]
    if len(payload) != sum(sizes):
        raise BridgeError(
            f"IWI payload bytes {len(payload)} != complete mip bytes {sum(sizes)}"
        )

    # Physical IWI payload is smallest -> largest.  Split using the exact
    # reversed largest->smallest byte-size sequence, then reverse slices into
    # DDS's largest -> smallest order.
    physical_sizes = list(reversed(sizes))
    physical = []
    cursor = 0
    for n in physical_sizes:
        part = payload[cursor:cursor + n]
        if len(part) != n:
            raise BridgeError("truncated physical IWI mip slice")
        physical.append(part)
        cursor += n
    if cursor != len(payload):
        raise BridgeError("IWI mip splitter did not consume the exact payload")
    return list(reversed(physical)), sizes


def convert_iwi(raw: bytes) -> tuple[bytes, dict]:
    if len(raw) < probe.HEADER_BYTES or raw[:3] != b"IWi" or raw[3] != probe.IWI_VERSION:
        raise BridgeError("source is not T6 IWI27")
    fmt, flags = raw[4], raw[5]
    if fmt not in DDS_FOURCC:
        raise BridgeError(f"IWI27 format 0x{fmt:02x} is not promoted by DDS bridge v1")
    width, height, depth = struct.unpack_from("<3H", raw, 6)
    gamma = struct.unpack_from("<f", raw, 12)[0]
    if depth != 1:
        raise BridgeError(f"DDS bridge v1 is 2D-only; IWI depth={depth}")

    expected_words, sizes = layout.expected_size_words(width, height, fmt)
    actual_words = list(struct.unpack_from("<8I", raw, 32))
    if actual_words != expected_words:
        raise BridgeError(
            f"IWI size words disagree with proven v2 layout: {actual_words} != {expected_words}"
        )

    dds_mips, sizes2 = _split_iwi_mips(raw, fmt=fmt, width=width, height=height)
    if sizes2 != sizes:
        raise BridgeError("internal mip size disagreement")
    if [len(x) for x in dds_mips] != sizes:
        raise BridgeError("DDS mip order/size reconstruction failed")

    source_physical = raw[probe.HEADER_BYTES:]
    source_physical_parts = list(reversed(dds_mips))
    if b"".join(source_physical_parts) != source_physical:
        raise BridgeError("reconstructed IWI physical mip concatenation changed bytes")

    top_bytes = sizes[0]
    header = _dds_header(width, height, len(sizes), top_bytes, DDS_FOURCC[fmt])
    dds_payload = b"".join(dds_mips)
    dds = header + dds_payload
    if dds[DDS_HEADER_BYTES:DDS_HEADER_BYTES + top_bytes] != dds_mips[0]:
        raise BridgeError("DDS top mip placement failed")

    source_sha = sha256(raw)
    per_mip = []
    for level, (source_part, dds_part) in enumerate(zip(reversed(source_physical_parts), dds_mips)):
        # The two objects are intentionally the same level bytes reached from
        # opposite physical orders.  Keep both hashes as explicit evidence.
        source_hash = sha256(source_part)
        dds_hash = sha256(dds_part)
        if source_part != dds_part or source_hash != dds_hash:
            raise BridgeError(f"mip {level}: compressed bytes changed during reorder")
        per_mip.append({
            "level": level,
            "bytes": len(dds_part),
            "sourceCompressedSha256": source_hash,
            "ddsCompressedSha256": dds_hash,
            "byteIdentical": True,
        })

    return dds, {
        "sourceIwiSha256": source_sha,
        "sourceIwiBytes": len(raw),
        "formatCode": fmt,
        "iwiFormat": probe.FORMAT_NAMES[fmt],
        "ddsFormat": DDS_FORMAT_NAMES[fmt],
        "fourCC": DDS_FOURCC[fmt].decode("ascii"),
        "flags": flags,
        "gamma": gamma,
        "width": width,
        "height": height,
        "depth": depth,
        "mipCount": len(sizes),
        "mipBytesLargestToSmallest": sizes,
        "sourcePhysicalMipOrder": "smallest-to-largest",
        "ddsPhysicalMipOrder": "largest-to-smallest",
        "ddsHeaderBytes": DDS_HEADER_BYTES,
        "compressedMipBytesPreserved": True,
        "mips": per_mip,
        "ddsBytes": len(dds),
        "ddsSha256": sha256(dds),
    }


def build(staged_manifest_path: Path, payload_root: Path, layout_proof_path: Path, out_root: Path) -> dict:
    staged, staged_raw = _load_json(staged_manifest_path)
    proof_doc, proof_raw = _load_json(layout_proof_path)
    if staged.get("format") != STAGED_FORMAT:
        raise BridgeError(f"unexpected staged manifest format {staged.get('format')!r}")
    if proof_doc.get("format") != LAYOUT_FORMAT:
        raise BridgeError(f"unexpected mip layout proof format {proof_doc.get('format')!r}")

    ss = staged.get("summary") or {}
    ps = proof_doc.get("summary") or {}
    if not (
        int(ss.get("aliasCount", -1)) == 81
        and int(ss.get("resolvedAliasCount", -1)) == 81
        and int(ss.get("unresolvedAliasCount", -1)) == 0
        and int(ss.get("uniquePayloadCount", -1)) == 81
    ):
        raise BridgeError(f"staged source gate is not exact 81/81: {ss}")
    if not (
        int(ps.get("fileCount", -1)) == 81
        and int(ps.get("completeEightWordFitCount", -1)) == 81
        and int(ps.get("completeMipPayloadFitCount", -1)) == 81
        and int(ps.get("failureCount", -1)) == 0
        and ps.get("allTwoDimensional") is True
        and ps.get("serializedPayloadOrder") == "smallest-to-largest"
    ):
        raise BridgeError(f"mip layout proof is not green 81/81: {ps}")

    proof_by_sha = {row["sha256"]: row for row in proof_doc.get("rows") or []}
    if len(proof_by_sha) != 81:
        raise BridgeError(f"mip proof SHA population {len(proof_by_sha)} != 81")

    payload_rows = {row["sha256"]: row for row in staged.get("payloads") or []}
    if len(payload_rows) != 81:
        raise BridgeError(f"staged unique payload population {len(payload_rows)} != 81")

    aliases_by_name: dict[str, list[dict]] = defaultdict(list)
    for alias in staged.get("aliases") or []:
        if alias.get("status") != "resolved":
            raise BridgeError(f"unresolved staged alias reached DDS bridge: {alias}")
        aliases_by_name[str(alias["name"])].append(alias)

    # A single OAT image basename must never select byte-different retail image
    # payloads.  Multiple pointer aliases are allowed only when payload identity
    # is exactly the same.
    for name, aliases in aliases_by_name.items():
        shas = {str(a["payloadSha256"]) for a in aliases}
        if len(shas) != 1:
            raise BridgeError(f"image name {name!r} has conflicting payload SHAs: {sorted(shas)}")

    out_root.mkdir(parents=True, exist_ok=True)
    converted_by_sha: dict[str, tuple[bytes, dict]] = {}
    output_rows = []
    format_counts = Counter()
    alias_use_counts = Counter()

    for name in sorted(aliases_by_name):
        aliases = aliases_by_name[name]
        source_sha = str(aliases[0]["payloadSha256"])
        payload_row = payload_rows.get(source_sha)
        proof_row = proof_by_sha.get(source_sha)
        if payload_row is None or proof_row is None:
            raise BridgeError(f"{name!r}: source SHA {source_sha} missing from staged/proof population")
        source_rel = Path(str(payload_row["file"]))
        source_path = payload_root / source_rel.name
        if not source_path.is_file():
            # The staging manifest stores payloads/<sha>.iwi while callers often
            # pass the payloads directory itself.  Do not search any broader tree.
            raise BridgeError(f"{name!r}: exact staged IWI is missing: {source_path}")
        raw = source_path.read_bytes()
        if sha256(raw) != source_sha:
            raise BridgeError(f"{name!r}: staged IWI SHA drift")
        if source_sha not in converted_by_sha:
            dds, meta = convert_iwi(raw)
            if meta["ddsFormat"] != DDS_FORMAT_NAMES[int(proof_row["formatCode"])]:
                raise BridgeError(f"{name!r}: proof/converter format disagreement")
            converted_by_sha[source_sha] = (dds, meta)
        dds, meta = converted_by_sha[source_sha]

        rel = _safe_alias_path(name)
        out = out_root / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists() and out.read_bytes() != dds:
            raise BridgeError(f"{name!r}: existing DDS path contains different bytes")
        out.write_bytes(dds)
        format_counts[meta["ddsFormat"]] += 1
        alias_use_counts[source_sha] += len(aliases)
        output_rows.append({
            "image": name,
            "output": str(rel).replace("\\", "/"),
            "aliasIndices": sorted(int(a["aliasIndex"]) for a in aliases),
            "semantics": sorted({int(a["semantic"]) for a in aliases}),
            "samplerStates": sorted({int(a["samplerState"]) for a in aliases}),
            **meta,
        })

    converted_source_shas = set(converted_by_sha)
    if converted_source_shas != set(payload_rows):
        missing = sorted(set(payload_rows) - converted_source_shas)
        raise BridgeError(f"not every exact source payload was represented by a named DDS: {missing[:8]}")

    return {
        "format": FORMAT,
        "source": {
            "stagedManifest": {
                "path": str(staged_manifest_path),
                "bytes": len(staged_raw),
                "sha256": sha256(staged_raw),
            },
            "mipLayoutProof": {
                "path": str(layout_proof_path),
                "bytes": len(proof_raw),
                "sha256": sha256(proof_raw),
                "format": proof_doc.get("format"),
            },
        },
        "summary": {
            "sourceAliasCount": int(ss["aliasCount"]),
            "sourcePayloadCount": len(converted_by_sha),
            "outputImageNameCount": len(output_rows),
            "ddsFormatCountsByImageName": dict(sorted(format_counts.items())),
            "allCompressedMipBytesPreserved": all(row["compressedMipBytesPreserved"] for row in output_rows),
            "unresolvedCount": 0,
            "conflictCount": 0,
        },
        "outputs": output_rows,
        "proofBoundary": (
            "Exact staged IWI27 payloads + green full eight-word mip-layout proof. The bridge "
            "only synthesizes the DDS container header and reverses whole compressed mip "
            "slices from IWI smallest->largest to DDS largest->smallest. No BC block is "
            "decoded, recompressed, color-space transformed, normalized, or inferred."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged-manifest", type=Path, required=True)
    ap.add_argument("--payload-root", type=Path, required=True)
    ap.add_argument("--layout-proof", type=Path, required=True)
    ap.add_argument("--out-root", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.staged_manifest, args.payload_root, args.layout_proof, args.out_root)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    payload = _json_bytes(doc)
    args.manifest.write_bytes(payload)
    print(json.dumps({"manifest": str(args.manifest), "bytes": len(payload), "sha256": sha256(payload), **doc["summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

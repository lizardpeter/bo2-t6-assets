#!/usr/bin/env python3
"""Materialize exact T6 image payloads across multiple retail IPAKs.

Identity is fail-closed:
- image name is already proven upstream from retail GfxImage/Material serialization;
- IPAK nameHash is derived with T6's retail filename hash from that exact name;
- retained streamed dataHash must match the IPAK index row;
- the exact (nameHash,dataHash) pair must occur exactly once across repositories;
- reconstructed payload CRC29, IWI27 metadata, dimensions, and PNG semantics are
  validated by the proven v1 implementation.

Retail command 0xCF is source-closed as IPAK padding: its source span is consumed
but it emits no bytes into the reconstructed IWI. This is the same semantic used
by t6_ipak_http_range_v2.py and is required by current shared retail containers.

Whole-container SHA-256 is always recorded as provenance. Callers may also pin
one or more container hashes with --expect-ipak-sha256, but container packaging
is not itself an image identity: exact pair resolution + payload validation is.

This corrects the historical v4 manifest's misleading `nameHashHex` label. That
field is retained as upstream evidence but is not used as an IPAK filename hash.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import struct
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2_PATH = HERE / "t6_ipak_iwi_materialize_v2.py"
IPAK_COMMAND_UNCOMPRESSED = 0x00
IPAK_COMMAND_LZO = 0x01
IPAK_COMMAND_SKIP = 0xCF


def _load_v2():
    spec = importlib.util.spec_from_file_location("t6_ipak_iwi_materialize_v2", V2_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {V2_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


v2 = _load_v2()
base = v2.base
TextureError = base.TextureError


def r_hash_string(s: str) -> int:
    h = 0
    for c in s.encode("latin1"):
        h = ((33 * h) ^ (c | 0x20)) & 0xFFFFFFFF
    return h


def _rows_from_doc(doc):
    if isinstance(doc, list):
        return doc
    for key in ("exactBaseIpakKeys", "exactStreamKeyImages", "exactIpakKeys"):
        rows = doc.get(key) if isinstance(doc, dict) else None
        if isinstance(rows, list):
            return rows
    raise TextureError("target manifest has no exact texture row list")


def load_targets_v3(path: Path) -> list[dict]:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    out = []
    seen = set()
    for r in _rows_from_doc(doc):
        if not isinstance(r, dict):
            continue
        name = r.get("image") or r.get("name")
        if not isinstance(name, str) or not name:
            raise TextureError("target missing image/name")
        sp = r.get("streamedPart0") or {}
        raw_dh = sp.get("dataHash", sp.get("dataHashHex", r.get("dataHash", r.get("dataHashHex"))))
        dh = base.parse_u32(raw_dh) & 0x1FFFFFFF
        nh = r_hash_string(name)
        key = (nh, dh)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "image": name,
            "nameHash": nh,
            "dataHash": dh,
            "target": r,
            "upstreamHashField": r.get("nameHash", r.get("nameHashHex")),
        })
    if not out:
        raise TextureError("no exact texture targets")
    return out


def load_metadata_v3(paths: list[Path]) -> dict[str, dict]:
    candidates: dict[str, list[dict]] = {}

    def add(name, source, row, uses):
        if not isinstance(name, str) or not name:
            return
        sp = row.get("streamedPart0") or {}
        candidates.setdefault(name, []).append({
            "sourceManifest": str(source),
            "dataHash": sp.get("dataHash", sp.get("dataHashHex", row.get("dataHash", row.get("dataHashHex")))),
            "width": row.get("width"),
            "height": row.get("height"),
            "depth": row.get("depth"),
            "uses": uses or [],
        })

    for path in paths:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(doc, dict):
            for key in ("exactBaseIpakKeys", "exactStreamKeyImages", "exactIpakKeys"):
                rows = doc.get(key)
                if isinstance(rows, list):
                    for r in rows:
                        if isinstance(r, dict):
                            add(r.get("image") or r.get("name"), path, r, r.get("uses"))
            rows = doc.get("promotions")
            if isinstance(rows, list):
                for r in rows:
                    if not isinstance(r, dict):
                        continue
                    im = r.get("image") or {}
                    if isinstance(im, dict):
                        add(im.get("name"), path, im, r.get("uses"))

    out = {}
    for name, rows in candidates.items():
        merged = {"sourceManifests": sorted({r["sourceManifest"] for r in rows}), "uses": []}
        for field in ("dataHash", "width", "height", "depth"):
            vals = []
            for r in rows:
                val = r.get(field)
                if val is None:
                    continue
                val = (base.parse_u32(val) & 0x1FFFFFFF) if field == "dataHash" else int(val)
                vals.append(val)
            if vals and len(set(vals)) != 1:
                raise TextureError(f"{name}: conflicting metadata {field}: {sorted(set(vals))}")
            if vals:
                merged[field] = vals[0]
        for r in rows:
            for use in r.get("uses") or []:
                if use not in merged["uses"]:
                    merged["uses"].append(use)
        out[name] = merged
    return out


def extract_entry_v3(path: Path, row: dict, lzo) -> bytes:
    """v1 exact extraction plus retail 0xCF padding semantics."""
    pos = int(row["absoluteOffset"])
    end = pos + int(row["entrySpan"])
    out = bytearray()
    blocks = 0
    with path.open("rb") as f:
        while pos < end:
            pos = base.align(pos, base.IPAK_BLOCK)
            if pos >= end:
                break
            if pos + 128 > end:
                raise TextureError("IPAK entry has truncated block header")
            f.seek(pos)
            hdr = f.read(128)
            if len(hdr) != 128:
                raise TextureError("IPAK block header short read")
            command_word = struct.unpack_from("<I", hdr, 0)[0]
            file_off = command_word & 0xFFFFFF
            command_count = (command_word >> 24) & 0xFF
            if command_count > 31:
                raise TextureError(f"IPAK block command count {command_count} > 31")
            commands = []
            for i in range(command_count):
                word = struct.unpack_from("<I", hdr, 4 + 4 * i)[0]
                commands.append((word & 0xFFFFFF, (word >> 24) & 0xFF))
            if any(comp in (IPAK_COMMAND_UNCOMPRESSED, IPAK_COMMAND_LZO) for _, comp in commands) and file_off != len(out):
                raise TextureError(f"IPAK block output offset {file_off} != {len(out)}")
            p = pos + 128
            for span, comp in commands:
                if p + span > end:
                    raise TextureError("IPAK command crosses indexed entry span")
                f.seek(p)
                blob = f.read(span)
                if len(blob) != span:
                    raise TextureError("IPAK command short read")
                if comp == IPAK_COMMAND_UNCOMPRESSED:
                    out.extend(blob)
                elif comp == IPAK_COMMAND_LZO:
                    dst = ctypes.create_string_buffer(0x8000)
                    n = ctypes.c_size_t(0x8000)
                    src = ctypes.create_string_buffer(blob)
                    rc = lzo(src, len(blob), dst, ctypes.byref(n), None)
                    if rc != 0:
                        raise TextureError(f"LZO decompression error {rc}")
                    out.extend(dst.raw[:n.value])
                elif comp == IPAK_COMMAND_SKIP:
                    # Retail padding: consume the indexed source bytes but do not
                    # advance the reconstructed IWI output stream.
                    pass
                else:
                    raise TextureError(f"unsupported IPAK compression command {comp}")
                p += span
            pos = p
            blocks += 1
            if blocks > 10000:
                raise TextureError("IPAK block runaway")
    payload = bytes(out)
    crc = zlib.crc32(payload) & 0x1FFFFFFF
    if crc != int(row["dataHash"]):
        raise TextureError(f"IPAK CRC29 {crc:08x} != index dataHash {int(row['dataHash']):08x}")
    return payload


def parse_named_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        p = Path(value)
        return p.name, p
    name, raw = value.split("=", 1)
    if not name or not raw:
        raise argparse.ArgumentTypeError("expected NAME=PATH")
    return name, Path(raw)


def parse_named_value(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected NAME=VALUE")
    name, raw = value.split("=", 1)
    return name, raw


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ipak", action="append", required=True, help="NAME=PATH; repeat for each retail repository")
    ap.add_argument("--expect-ipak-sha256", action="append", default=[], help="NAME=SHA256; optional whole-container provenance pin")
    ap.add_argument("--targets", type=Path, required=True)
    ap.add_argument("--metadata", type=Path, action="append", default=[])
    ap.add_argument("--outdir", type=Path, required=True)
    a = ap.parse_args()

    expected = dict(parse_named_value(x) for x in a.expect_ipak_sha256)
    repositories = []
    for raw in a.ipak:
        name, path = parse_named_path(raw)
        if not path.is_file():
            raise SystemExit(f"IPAK not found: {path}")
        actual = base.sha256_file(path)
        if name in expected and actual.lower() != expected[name].lower():
            raise SystemExit(f"{name} SHA-256 mismatch: {actual}")
        parsed = base.parse_ipak(path)
        repositories.append({"name": name, "path": path, "sha256": actual, "ipak": parsed})

    targets = load_targets_v3(a.targets)
    metadata = load_metadata_v3(a.metadata)
    lzo = v2.load_portable_lzo()
    a.outdir.mkdir(parents=True, exist_ok=True)
    materialized = []
    unresolved = []

    for t in targets:
        key = (t["nameHash"], t["dataHash"])
        hits = []
        for repo in repositories:
            for row in repo["ipak"]["byExact"].get(key, []):
                hits.append((repo, row))
        if len(hits) != 1:
            unresolved.append({**t, "reason": "exact-key-not-found" if not hits else "ambiguous-exact-key", "matchCount": len(hits)})
            continue

        repo, row = hits[0]
        meta = metadata.get(t["image"], {})
        if "dataHash" in meta and meta["dataHash"] != t["dataHash"]:
            raise TextureError(f"{t['image']}: metadata dataHash mismatch")
        try:
            payload = extract_entry_v3(repo["path"], row, lzo)
            iwi_meta = base.parse_iwi27(payload)
            for field in ("width", "height", "depth"):
                if field in meta and meta[field] not in (None, 0) and int(meta[field]) != int(iwi_meta[field]):
                    raise TextureError(f"{t['image']}: retained {field} {meta[field]} != IWI {iwi_meta[field]}")
            # Metadata manifests and the exact target identity manifest are both
            # evidence. Never let a non-empty metadata use-list mask a proven
            # target semantic such as normalMap.
            uses = []
            for use in list(meta.get("uses") or []) + list(t["target"].get("uses") or []):
                if use not in uses:
                    uses.append(use)
            normal = any(
                (isinstance(x, str) and ("normalMap" in x or x.endswith(":normal")))
                or (isinstance(x, dict) and (x.get("semanticName") == "normalMap" or x.get("semanticRaw") == 5))
                for x in uses
            )
            png, png_meta = base.top_png(payload, normal)
        except Exception as exc:
            unresolved.append({**t, "repository": repo["name"], "reason": "payload-validation-failed", "error": str(exc)})
            continue

        stem = f"{base.safe_name(t['image'])}__nh_{t['nameHash']:08x}__dh_{t['dataHash']:08x}"
        iwi_name = stem + ".iwi"
        png_name = stem + ".png"
        (a.outdir / iwi_name).write_bytes(payload)
        (a.outdir / png_name).write_bytes(png)
        materialized.append({
            **t,
            "repository": repo["name"],
            "sourceIpakPath": str(repo["path"]),
            "index": row["index"],
            "entrySpan": row["entrySpan"],
            "iwiFile": iwi_name,
            "pngFile": png_name,
            "iwiSha256": base.sha256_bytes(payload),
            "pngSha256": base.sha256_bytes(png),
            "retainedMetadata": meta,
            "resolvedUses": uses,
            "iwi": png_meta,
            "crc29Validated": True,
            "exactKeyValidated": True,
            "ipakNameHashDerivedFromExactImageName": True,
        })

    source_ipaks = []
    for repo in repositories:
        source_ipaks.append({
            "name": repo["name"],
            "path": str(repo["path"]),
            "bytes": repo["path"].stat().st_size,
            "sha256": repo["sha256"],
            "sha256Expected": expected.get(repo["name"]),
            "sha256ExpectationMatched": (repo["sha256"].lower() == expected[repo["name"]].lower()) if repo["name"] in expected else None,
            "versionHex": f"0x{repo['ipak']['version']:x}",
        })
    counts = {repo["name"]: sum(1 for x in materialized if x["repository"] == repo["name"]) for repo in repositories}
    doc = {
        "format": "t6-ipak-iwi-materialization-v3",
        "authority": "exact retail image names + derived T6 IPAK filename hashes + retained streamed dataHash + unique cross-repository index pair + CRC29 + IWI27 + retained dimension validation",
        "sourceIpaks": source_ipaks,
        "targetManifest": {"path": str(a.targets), "sha256": base.sha256_file(a.targets)},
        "metadataManifests": [{"path": str(p), "sha256": base.sha256_file(p)} for p in a.metadata],
        "summary": {
            "requested": len(targets),
            "materialized": len(materialized),
            "unresolved": len(unresolved),
            "iwiFiles": len(materialized),
            "pngFiles": len(materialized),
            "repositories": counts,
        },
        "textures": materialized,
        "unresolved": unresolved,
        "proofBoundary": "Whole-container SHA-256 is provenance and may optionally be pinned by the caller. Asset identity is exact: no retained mislabeled nameHash field, filename fallback, dataHash-only fallback, cross-repository substitution, or unsupported-format substitution is accepted. The exact proven image name is hashed with the retail T6 filename hash and paired with the exact streamed dataHash; the pair must be unique across the supplied retail IPAKs and its reconstructed payload must pass CRC29/IWI validation. Retail command 0xCF is consumed as source padding only and emits no reconstructed bytes.",
    }
    (a.outdir / "manifest.json").write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    return 2 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())

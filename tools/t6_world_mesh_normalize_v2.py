#!/usr/bin/env python3
"""Retail-gated T6 world mesh normalizer v2.

V1 correctly normalizes a zero-error vertex proof, but the canonical format
specification also contains formula-known formats that may not yet have an
observed retail fixture. V2 adds the missing production gate: every
worldVertFormat used by the proof must be `exportEnabled` in an authoritative
`t6-world-vertex-format-registry-v1` document before any vd1 bytes are decoded.

The geometry implementation remains v1; this wrapper changes the trust model,
not the mesh math.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import t6_world_mesh_normalize_v1 as v1
from t6_zone_core import MaterialWorldVertexFormat, WORLD_VERTEX_FORMATS


NormalizeV2Error = v1.NormalizeError


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_registry_shape(registry: dict) -> None:
    if registry.get("format") != "t6-world-vertex-format-registry-v1":
        raise NormalizeV2Error(
            f"unsupported world vertex format registry {registry.get('format')!r}"
        )
    rows = registry.get("formats")
    if not isinstance(rows, dict) or set(rows) != {str(i) for i in range(9)}:
        raise NormalizeV2Error("world vertex registry must contain exactly formats 0..8")

    for fmt_enum, spec in WORLD_VERTEX_FORMATS.items():
        fmt = int(fmt_enum)
        row = rows[str(fmt)]
        family = row.get("sourceClosedFamily")
        if not isinstance(family, dict):
            raise NormalizeV2Error(f"registry format {fmt}: missing sourceClosedFamily")
        expected = {
            "uvCount": int(spec.uv_count),
            "normalCount": int(spec.normal_count),
            "vd1Stride": int(spec.vd1_stride),
            "vd1Fields": list(spec.vd1_fields),
        }
        if row.get("name") != fmt_enum.name:
            raise NormalizeV2Error(
                f"registry format {fmt}: name {row.get('name')!r} != {fmt_enum.name!r}"
            )
        for key, value in expected.items():
            if family.get(key) != value:
                raise NormalizeV2Error(
                    f"registry format {fmt}: {key}={family.get(key)!r} != canonical {value!r}"
                )
        contradictions = row.get("contradictoryRawStrides", [])
        if contradictions and row.get("exportEnabled"):
            raise NormalizeV2Error(
                f"registry format {fmt}: contradictory raw strides cannot be export-enabled"
            )


def validate_registry_for_proof(proof: dict, registry: dict) -> dict:
    _validate_registry_shape(registry)
    if proof.get("format") != "t6-world-vertex-proof-v1":
        raise NormalizeV2Error(f"unsupported vertex proof format {proof.get('format')!r}")
    if int(proof.get("badGroupCount", 0)) != 0:
        raise NormalizeV2Error(
            f"vertex proof contains {proof.get('badGroupCount')} bad groups"
        )

    groups = proof.get("groups")
    if not isinstance(groups, list):
        raise NormalizeV2Error("vertex proof has no groups list")
    observed = sorted({int(row["worldVertFormat"]) for row in groups})
    disabled: list[dict] = []
    for fmt in observed:
        try:
            MaterialWorldVertexFormat(fmt)
        except ValueError as exc:
            raise NormalizeV2Error(f"vertex proof uses invalid format {fmt}") from exc
        row = registry["formats"][str(fmt)]
        if not bool(row.get("exportEnabled")):
            disabled.append(
                {
                    "format": fmt,
                    "name": row.get("name"),
                    "status": row.get("status"),
                    "retailByteProven": bool(row.get("retailByteProven")),
                    "contradictoryRawStrides": list(row.get("contradictoryRawStrides", [])),
                }
            )

    if disabled:
        detail = ", ".join(
            f"{row['format']}:{row['name']}[{row['status']}]" for row in disabled
        )
        raise NormalizeV2Error(
            "vertex proof uses world formats not retail-approved for export: " + detail
        )

    return {
        "observedFormats": observed,
        "allObservedFormatsExportEnabled": True,
        "registryExportEnabledFormats": list(
            registry.get("coverage", {}).get("exportEnabledFormats", [])
        ),
        "registryAllFormatsExportEnabled": bool(
            registry.get("coverage", {}).get("allFormatsExportEnabled", False)
        ),
    }


def normalize(
    *,
    surfaces_doc: dict,
    vd0: bytes,
    vd1: bytes,
    index_bytes: bytes,
    proof: dict,
    registry: dict,
    source_meta: dict | None = None,
    registry_source: dict | None = None,
) -> dict:
    gate = validate_registry_for_proof(proof, registry)
    out = v1.normalize(
        surfaces_doc=surfaces_doc,
        vd0=vd0,
        vd1=vd1,
        index_bytes=index_bytes,
        proof=proof,
        source_meta=source_meta,
    )
    if out.get("format") != "t6-world-mesh-normalized-v1":
        raise NormalizeV2Error(f"unexpected v1 output {out.get('format')!r}")
    out["format"] = "t6-world-mesh-normalized-v2"
    out["worldVertexFormatGate"] = {
        **gate,
        "registry": registry_source or {
            "format": registry.get("format"),
            "source": "in-memory",
        },
        "policy": (
            "every worldVertFormat present in the retail vertex proof must be "
            "exportEnabled by t6-world-vertex-format-registry-v1 before vd1 decode"
        ),
    }
    return out


def _source(path: Path, data: bytes) -> dict:
    return {
        "file": path.name,
        "path": str(path),
        "bytes": len(data),
        "sha256": _sha256(data),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--surfaces", type=Path, required=True)
    ap.add_argument("--vd0", type=Path, required=True)
    ap.add_argument("--vd1", type=Path, required=True)
    ap.add_argument("--indices", type=Path, required=True)
    ap.add_argument("--vertex-proof", type=Path, required=True)
    ap.add_argument("--format-registry", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    surfaces_raw = args.surfaces.read_bytes()
    vd0 = args.vd0.read_bytes()
    vd1 = args.vd1.read_bytes()
    index_bytes = args.indices.read_bytes()
    proof_raw = args.vertex_proof.read_bytes()
    registry_raw = args.format_registry.read_bytes()

    surfaces_doc = json.loads(surfaces_raw.decode("utf-8"))
    proof = json.loads(proof_raw.decode("utf-8"))
    registry = json.loads(registry_raw.decode("utf-8"))
    source_meta = {
        "surfaces": _source(args.surfaces, surfaces_raw),
        "vd0": _source(args.vd0, vd0),
        "vd1": _source(args.vd1, vd1),
        "indices": _source(args.indices, index_bytes),
        "vertexProof": _source(args.vertex_proof, proof_raw),
    }
    doc = normalize(
        surfaces_doc=surfaces_doc,
        vd0=vd0,
        vd1=vd1,
        index_bytes=index_bytes,
        proof=proof,
        registry=registry,
        source_meta=source_meta,
        registry_source=_source(args.format_registry, registry_raw),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "map": doc.get("map"),
                "observedFormats": doc["worldVertexFormatGate"]["observedFormats"],
                "allObservedFormatsExportEnabled": doc["worldVertexFormatGate"][
                    "allObservedFormatsExportEnabled"
                ],
                "allNineFormatsExportEnabled": doc["worldVertexFormatGate"][
                    "registryAllFormatsExportEnabled"
                ],
                "stats": doc.get("stats"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Extract exact T6 DXBC stage input/output signatures.

The signature chunks are source metadata, not shader-behaviour inference. For
vertex shaders this module can additionally join OAT's exact MaterialTechnique
vertex-routing declarations to the DXBC input signature. That closes, for
example, DXBC TEXCOORD2 -> T6 ``code.tangent`` without guessing from values or
mesh layout.

Supported T6 retail payloads currently use the SM4/SM5 ``ISGN``/``OSGN``
24-byte element layout. Newer extended signature layouts deliberately fail
closed until their extra fields are implemented and covered.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from t6_dxbc_rdef_v1 import dxbc_chunks

FORMAT = "t6-dxbc-signature-v1"

COMPONENT_TYPES = {
    0: "unknown",
    1: "uint32",
    2: "sint32",
    3: "float32",
}

SYSTEM_VALUES = {
    0: "none",
    1: "position",
    2: "clip-distance",
    3: "cull-distance",
    4: "render-target-array-index",
    5: "viewport-array-index",
    6: "vertex-id",
    7: "primitive-id",
    8: "instance-id",
    9: "is-front-face",
    10: "sample-index",
    64: "target",
    65: "depth",
    66: "coverage",
    67: "depth-greater-equal",
    68: "depth-less-equal",
}


class DxbcSignatureError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cstr(blob: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(blob):
        raise DxbcSignatureError(f"signature string offset {offset} is outside payload")
    end = blob.find(b"\0", offset)
    if end < 0:
        raise DxbcSignatureError(f"signature string at offset {offset} is not NUL terminated")
    try:
        return blob[offset:end].decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise DxbcSignatureError(f"signature string at offset {offset} is not ASCII") from exc


def _components(mask: int) -> str:
    return "".join(ch for bit, ch in enumerate("xyzw") if mask & (1 << bit))


def parse_signature_payload(blob: bytes) -> list[dict[str, Any]]:
    if len(blob) < 8:
        raise DxbcSignatureError("signature payload is shorter than its header")
    count, table_offset = struct.unpack_from("<II", blob, 0)
    if table_offset < 8 or table_offset % 4:
        raise DxbcSignatureError(f"invalid signature table offset {table_offset}")
    end = table_offset + count * 24
    if end > len(blob):
        raise DxbcSignatureError(
            f"signature table count {count} at {table_offset} exceeds payload {len(blob)}"
        )

    rows: list[dict[str, Any]] = []
    for index in range(count):
        off = table_offset + index * 24
        name_off, semantic_index, system_value, component_type, register, mask_word = struct.unpack_from(
            "<6I", blob, off
        )
        mask = mask_word & 0xFF
        rw_mask = (mask_word >> 8) & 0xFF
        reserved = mask_word >> 16
        if mask & ~0xF or rw_mask & ~0xF:
            raise DxbcSignatureError(
                f"signature row {index} has invalid component masks 0x{mask:02X}/0x{rw_mask:02X}"
            )
        semantic = _cstr(blob, name_off)
        rows.append(
            {
                "index": index,
                "semantic": semantic,
                "semanticIndex": semantic_index,
                "semanticKey": f"{semantic.upper()}{semantic_index}",
                "systemValueCode": system_value,
                "systemValue": SYSTEM_VALUES.get(system_value),
                "componentTypeCode": component_type,
                "componentType": COMPONENT_TYPES.get(component_type),
                "register": register,
                "mask": f"0x{mask:02X}",
                "components": _components(mask),
                "readWriteMask": f"0x{rw_mask:02X}",
                "readWriteComponents": _components(rw_mask),
                "reserved": reserved,
            }
        )
    return rows


def _chunk(chunks: list[dict[str, Any]], fourcc: str) -> bytes:
    matches = [row["payload"] for row in chunks if row["fourcc"] == fourcc]
    if len(matches) != 1:
        raise DxbcSignatureError(f"expected exactly one {fourcc} signature chunk, got {len(matches)}")
    return matches[0]


def parse_dxbc_signatures(data: bytes) -> dict[str, Any]:
    chunks = dxbc_chunks(data)
    unsupported = [row["fourcc"] for row in chunks if row["fourcc"] in {"ISG1", "OSG1", "OSG5"}]
    if unsupported:
        raise DxbcSignatureError(
            "DXBC uses an unimplemented extended signature layout: " + ", ".join(unsupported)
        )
    return {
        "inputs": parse_signature_payload(_chunk(chunks, "ISGN")),
        "outputs": parse_signature_payload(_chunk(chunks, "OSGN")),
        "chunks": [
            {k: v for k, v in row.items() if k != "payload"}
            for row in chunks
            if row["fourcc"] in {"ISGN", "OSGN"}
        ],
    }


def _route_destination_for_semantic(semantic: str, semantic_index: int) -> str:
    name = semantic.upper()
    if name == "POSITION" and semantic_index == 0:
        return "position"
    if name == "NORMAL" and semantic_index == 0:
        return "normal"
    if name == "TANGENT" and semantic_index == 0:
        return "tangent"
    if name == "COLOR":
        return f"color[{semantic_index}]"
    if name == "TEXCOORD":
        return f"texcoord[{semantic_index}]"
    return f"{semantic.lower()}[{semantic_index}]"


def bind_vertex_routes(inputs: list[dict[str, Any]], routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Join exact OAT ``vertexRouting`` to non-system DXBC vertex inputs."""
    by_destination: dict[str, list[dict[str, Any]]] = {}
    for route in routes:
        destination = str(route.get("destination") or "")
        source = str(route.get("source") or "")
        if not destination or not source:
            raise DxbcSignatureError(f"malformed vertex route {route!r}")
        by_destination.setdefault(destination, []).append(route)

    out = []
    consumed: set[int] = set()
    for row in inputs:
        if row["systemValueCode"] != 0:
            out.append({**row, "t6RouteDestination": None, "t6Source": None})
            continue
        destination = _route_destination_for_semantic(row["semantic"], row["semanticIndex"])
        matches = by_destination.get(destination, [])
        if len(matches) != 1:
            raise DxbcSignatureError(
                f"DXBC input {row['semanticKey']} register {row['register']} maps to "
                f"T6 destination {destination!r}, found {len(matches)} exact OAT routes"
            )
        route = matches[0]
        consumed.add(id(route))
        out.append(
            {
                **row,
                "t6RouteDestination": destination,
                "t6Source": str(route["source"]),
            }
        )

    unused = [r for rows in by_destination.values() for r in rows if id(r) not in consumed]
    if unused:
        raise DxbcSignatureError(
            f"{len(unused)} OAT vertex route(s) were not consumed by DXBC signature: {unused!r}"
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dxbc", type=Path)
    parser.add_argument(
        "--vertex-routes-json",
        type=Path,
        help="JSON containing an OAT vertexRouting array or an object with vertexRouting",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    data = args.dxbc.read_bytes()
    parsed = parse_dxbc_signatures(data)
    if args.vertex_routes_json is not None:
        route_doc = json.loads(args.vertex_routes_json.read_text(encoding="utf-8"))
        routes = route_doc.get("vertexRouting") if isinstance(route_doc, dict) else route_doc
        if not isinstance(routes, list):
            raise SystemExit("--vertex-routes-json does not contain a vertexRouting array")
        parsed["inputs"] = bind_vertex_routes(parsed["inputs"], routes)

    out = {
        "format": FORMAT,
        "proofBoundary": (
            "Direct DXBC ISGN/OSGN signature metadata; optional T6 source semantics are joined only "
            "through exact OAT MaterialTechnique vertexRouting destination names. No value-pattern, "
            "mesh-layout, shader-arithmetic, or PBR inference."
        ),
        "source": {
            "path": args.dxbc.name,
            "bytes": len(data),
            "sha256": _sha256(data),
        },
        **parsed,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

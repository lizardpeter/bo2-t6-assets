#!/usr/bin/env python3
"""Recover exact OAT/RDEF VS constant bindings for Nuketown multiply decals.

The exact retained multiply-decal VS proof shows that pixel TEXCOORD0.z depends
on VS cb0 rows 26..31 plus the normal world transform, while SV_Position uses
cb0 rows 36..39.  This verifier joins those reflected byte ranges to the exact
selected OAT unlit/emissive pass and its constant.* assignments.  It does not
assign values to the accessors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

FORMAT = "t6-nuketown-special-multiply-decal-vs-bindings-v1"
TECHNIQUE_SET = "wpc_unlitdecalblend_multiply_35079164"
VS_SHA256 = "c3bd9eb7d12a444c63867be2e466ac00c495a5a7f64a8b2c9f73e2558a5e12e0"
PS_SHA256 = "e9820077a4df69228fd1626997270d7b31337f82eab6c26c1a14a33257424a0b"
FADE_CB = 0
FADE_START = 26 * 16
FADE_END = 32 * 16
VIEWPROJ_CB = 0
VIEWPROJ_START = 36 * 16
VIEWPROJ_END = 40 * 16
WORLD_CB = 3
WORLD_START = 0
WORLD_END = 4 * 16


class BindingError(RuntimeError):
    pass


def u32(b: bytes, off: int) -> int:
    if off < 0 or off + 4 > len(b):
        raise BindingError(f"u32 at {off} exceeds {len(b)} bytes")
    return struct.unpack_from("<I", b, off)[0]


def cstr(b: bytes, off: int) -> str:
    if off < 0 or off >= len(b):
        raise BindingError(f"string offset {off} exceeds {len(b)} bytes")
    end = b.find(b"\0", off)
    if end < 0:
        raise BindingError(f"string at {off} is unterminated")
    return b[off:end].decode("utf-8")


def dxbc_chunk(dxbc: bytes, wanted: bytes) -> bytes:
    if len(dxbc) < 32 or dxbc[:4] != b"DXBC":
        raise BindingError("payload is not DXBC")
    if u32(dxbc, 24) != len(dxbc):
        raise BindingError("DXBC declared size mismatch")
    count = u32(dxbc, 28)
    if 32 + 4 * count > len(dxbc):
        raise BindingError("DXBC chunk table is truncated")
    matches = []
    for off in struct.unpack_from("<" + "I" * count, dxbc, 32):
        if off + 8 > len(dxbc):
            raise BindingError("DXBC chunk header is truncated")
        size = u32(dxbc, off + 4)
        end = off + 8 + size
        if end > len(dxbc):
            raise BindingError("DXBC chunk payload is truncated")
        if dxbc[off : off + 4] == wanted:
            matches.append(dxbc[off + 8 : end])
    if len(matches) != 1:
        raise BindingError(f"DXBC {wanted!r} chunk count {len(matches)}, expected one")
    return matches[0]


def rdef_cbuffers(dxbc: bytes) -> list[dict[str, Any]]:
    r = dxbc_chunk(dxbc, b"RDEF")
    if len(r) < 32:
        raise BindingError("RDEF fixed header is truncated")
    cb_count, cb_off, res_count, res_off = struct.unpack_from("<4I", r, 0)
    if cb_off + cb_count * 24 > len(r) or res_off + res_count * 32 > len(r):
        raise BindingError("RDEF table exceeds payload")

    bound: dict[str, int] = {}
    for i in range(res_count):
        q = res_off + i * 32
        name = cstr(r, u32(r, q))
        input_type = u32(r, q + 4)
        bind_point = u32(r, q + 20)
        bind_count = u32(r, q + 24)
        if input_type != 0:
            continue
        if bind_count != 1:
            raise BindingError(f"RDEF CBUFFER {name!r} bindCount {bind_count}, expected one")
        if name in bound:
            raise BindingError(f"RDEF repeats CBUFFER resource {name!r}")
        bound[name] = bind_point

    out = []
    seen_bind = set()
    for i in range(cb_count):
        q = cb_off + i * 24
        name = cstr(r, u32(r, q))
        var_count = u32(r, q + 4)
        var_off = u32(r, q + 8)
        size = u32(r, q + 12)
        if name not in bound:
            raise BindingError(f"RDEF cbuffer {name!r} has no resource binding")
        bind = bound[name]
        if bind in seen_bind:
            raise BindingError(f"RDEF repeats bind point b{bind}")
        seen_bind.add(bind)
        if size == 0 or size % 16:
            raise BindingError(f"RDEF cbuffer {name!r} has invalid size {size}")
        if var_off + var_count * 24 > len(r):
            raise BindingError(f"RDEF variables for {name!r} exceed payload")
        variables = []
        occupied: list[tuple[int, int, str]] = []
        for j in range(var_count):
            v = var_off + j * 24
            vn = cstr(r, u32(r, v))
            start = u32(r, v + 4)
            n = u32(r, v + 8)
            end = start + n
            if n == 0 or end > size:
                raise BindingError(f"RDEF {name}.{vn} range {start}..{end} exceeds {size}")
            for old_start, old_end, old_name in occupied:
                if not (end <= old_start or start >= old_end):
                    raise BindingError(f"RDEF {name} variables {old_name!r}/{vn!r} overlap")
            occupied.append((start, end, vn))
            variables.append({"name": vn, "startOffset": start, "sizeBytes": n, "endOffset": end})
        out.append({"name": name, "bindPoint": bind, "sizeBytes": size, "variables": variables})
    out.sort(key=lambda x: x["bindPoint"])
    return out


def shader_decl(line: str, kind: str) -> str | None:
    text = line.strip()
    if not text.startswith(kind):
        return None
    rest = text[len(kind):]
    if not rest or not rest[0].isspace():
        return None
    a = rest.find('"')
    if a < 0:
        return None
    b = rest.find('"', a + 1)
    if b < 0 or rest[b + 1 :].strip():
        return None
    return rest[a + 1 : b]


def split_passes(text: str) -> list[list[str]]:
    depth = 0
    current: list[str] | None = None
    passes = []
    for ln, raw in enumerate(text.splitlines(), 1):
        t = raw.strip()
        if depth == 0 and (not t or t.startswith("//")):
            continue
        opens = raw.count("{")
        closes = raw.count("}")
        if depth == 0:
            if t != "{":
                raise BindingError(f"technique line {ln} expected pass opening brace, got {raw!r}")
            current = [raw]
        elif current is not None:
            current.append(raw)
        depth += opens - closes
        if depth < 0:
            raise BindingError(f"technique brace depth negative at line {ln}")
        if depth == 0 and current is not None:
            passes.append(current)
            current = None
    if depth or current is not None or not passes:
        raise BindingError("technique pass structure is incomplete")
    return passes


def constant_assignment(line: str) -> tuple[str, str] | None:
    t = line.strip()
    omitted = "// Omitted due to matching accessors:"
    if t.startswith(omitted):
        t = t[len(omitted):].strip()
    elif t.startswith("//"):
        return None
    if not t.endswith(";") or "=" not in t:
        return None
    lhs, rhs = t[:-1].split("=", 1)
    lhs, rhs = lhs.strip(), rhs.strip()
    if not rhs.startswith("constant."):
        return None
    src = rhs[len("constant."):]
    if not lhs or not src or any(ch.isspace() for ch in lhs + src):
        raise BindingError(f"malformed constant assignment {line!r}")
    return lhs, src


def vertex_assignments(pass_lines: list[str], vs_asset: str) -> dict[str, str]:
    hits = [i for i, line in enumerate(pass_lines) if shader_decl(line, "vertexShader") == vs_asset]
    if len(hits) != 1:
        raise BindingError(f"selected pass has {len(hits)} exact vertexShader {vs_asset!r} declarations")
    started = False
    depth = 0
    out: dict[str, str] = {}
    for raw in pass_lines[hits[0] + 1 :]:
        t = raw.strip()
        if not started:
            if not t:
                continue
            if t != "{":
                raise BindingError("vertexShader declaration is not followed by a block")
            started = True
            depth = 1
            continue
        if depth == 1:
            row = constant_assignment(t)
            if row:
                var, src = row
                if var in out and out[var] != src:
                    raise BindingError(f"vertex variable {var!r} has conflicting sources")
                out[var] = src
        depth += raw.count("{") - raw.count("}")
        if depth == 0:
            return out
        if depth < 0:
            raise BindingError("vertexShader block brace depth became negative")
    raise BindingError("vertexShader block is unterminated")


def selected_programs(census: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], Path, str]:
    groups = {str(g.get("groupKey")): g for g in census.get("shaderGroups", []) if isinstance(g, dict)}
    rows = [m for m in census.get("materials", []) if m.get("techniqueSet") == TECHNIQUE_SET]
    if len(rows) != 3:
        raise BindingError(f"multiply-decal Material count {len(rows)}, expected three")
    identities = set()
    selected: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for m in rows:
        local = {}
        for p in m.get("programs", []):
            typ = p.get("techniqueType")
            if typ not in ("unlit", "emissive"):
                continue
            g = groups.get(str(p.get("groupKey")))
            if g is None:
                raise BindingError("selected multiply-decal shader group is absent")
            local[typ] = (p, g)
            identities.add((typ, str(p.get("techniqueOwner")), str(p.get("technique")), str(p.get("groupKey"))))
        if set(local) != {"unlit", "emissive"}:
            raise BindingError(f"Material {m.get('material')!r} lacks exact unlit/emissive programs")
        for typ, pair in local.items():
            if typ in selected and selected[typ][0] != pair[0]:
                raise BindingError(f"multiply-decal Materials disagree on {typ} selected program")
            selected[typ] = pair
    u_prog, u_group = selected["unlit"]
    e_prog, e_group = selected["emissive"]
    if str(u_prog.get("techniqueOwner")) != str(e_prog.get("techniqueOwner")) or str(u_prog.get("technique")) != str(e_prog.get("technique")):
        raise BindingError("unlit/emissive selected Technique ownership differs")
    owner = Path(str(u_prog.get("techniqueOwner") or ""))
    technique = str(u_prog.get("technique") or "")
    if not str(owner) or not technique:
        raise BindingError("selected Technique owner/name is empty")
    return u_group, e_group, owner, technique


def stage(group: dict[str, Any], kind: str, expected_sha: str) -> dict[str, Any]:
    rows = [s for p in group.get("passes", []) for s in p.get("stages", []) if s.get("kind") == kind]
    if len(rows) != 1:
        raise BindingError(f"selected group has {len(rows)} {kind} stages")
    if str(rows[0].get("sha256") or "").lower() != expected_sha:
        raise BindingError(f"selected {kind} SHA differs from pinned exact shader")
    return rows[0]


def intersecting_variables(cbuffers: list[dict[str, Any]], bind: int, start: int, end: int, assignments: dict[str, str]) -> list[dict[str, Any]]:
    bs = [b for b in cbuffers if b["bindPoint"] == bind]
    if len(bs) != 1:
        raise BindingError(f"RDEF b{bind} cbuffer count {len(bs)}, expected one")
    rows = []
    covered = set()
    for v in bs[0]["variables"]:
        a, z = v["startOffset"], v["endOffset"]
        if z <= start or a >= end:
            continue
        src = assignments.get(v["name"])
        rows.append({
            "cbuffer": bs[0]["name"],
            "bindPoint": bind,
            "shaderVariable": v["name"],
            "startOffset": a,
            "sizeBytes": v["sizeBytes"],
            "endOffset": z,
            "sourceAccessor": src,
        })
        for byte in range(max(a, start), min(z, end)):
            covered.add(byte)
    if covered != set(range(start, end)):
        missing = sorted(set(range(start, end)) - covered)
        raise BindingError(f"RDEF b{bind} does not cover target byte range {start}..{end}; first missing {missing[:8]}")
    return rows


def build(census_path: Path) -> dict[str, Any]:
    census = json.loads(census_path.read_text(encoding="utf-8"))
    if census.get("format") != "t6-nuketown-special-material-census-v1":
        raise BindingError(f"unexpected special census format {census.get('format')!r}")
    ug, eg, owner, technique = selected_programs(census)
    uvs, ups = stage(ug, "vertexShader", VS_SHA256), stage(ug, "pixelShader", PS_SHA256)
    evs, eps = stage(eg, "vertexShader", VS_SHA256), stage(eg, "pixelShader", PS_SHA256)
    for a, b, label in ((uvs, evs, "VS"), (ups, eps, "PS")):
        if a.get("relativeFile") != b.get("relativeFile") or a.get("asset") != b.get("asset"):
            raise BindingError(f"unlit/emissive exact {label} identity differs")

    vs_path = owner / str(uvs.get("relativeFile") or "")
    dxbc = vs_path.read_bytes()
    if hashlib.sha256(dxbc).hexdigest() != VS_SHA256:
        raise BindingError(f"{vs_path}: exact VS SHA mismatch")
    cbuffers = rdef_cbuffers(dxbc)

    tech_path = owner / "techniques" / f"{technique}.tech"
    text = tech_path.read_text(encoding="utf-8")
    passes = split_passes(text)
    vs_asset = str(uvs.get("asset") or "")
    ps_asset = str(ups.get("asset") or "")
    matches = [p for p in passes if any(shader_decl(x, "vertexShader") == vs_asset for x in p) and any(shader_decl(x, "pixelShader") == ps_asset for x in p)]
    if len(matches) != 1:
        raise BindingError(f"{tech_path}: exact VS/PS pair appears in {len(matches)} passes, expected one")
    assignments = vertex_assignments(matches[0], vs_asset)

    fade = intersecting_variables(cbuffers, FADE_CB, FADE_START, FADE_END, assignments)
    world = intersecting_variables(cbuffers, WORLD_CB, WORLD_START, WORLD_END, assignments)
    view = intersecting_variables(cbuffers, VIEWPROJ_CB, VIEWPROJ_START, VIEWPROJ_END, assignments)
    unresolved = [r for r in fade + world + view if not r["sourceAccessor"]]
    if unresolved:
        raise BindingError(f"target VS ranges have unresolved OAT sources: {[r['shaderVariable'] for r in unresolved]}")

    return {
        "format": FORMAT,
        "producer": "tools/t6_nuketown_special_multiply_decal_vs_bindings_v1.py",
        "map": "mp_nuketown_2020",
        "techniqueSet": TECHNIQUE_SET,
        "technique": technique,
        "techniqueOwner": str(owner),
        "vertexShader": {"asset": vs_asset, "sha256": VS_SHA256, "relativeFile": uvs.get("relativeFile")},
        "pixelShader": {"asset": ps_asset, "sha256": PS_SHA256, "relativeFile": ups.get("relativeFile")},
        "fadeRange": {"bindPoint": FADE_CB, "startOffset": FADE_START, "endOffset": FADE_END, "variables": fade},
        "worldMatrixRange": {"bindPoint": WORLD_CB, "startOffset": WORLD_START, "endOffset": WORLD_END, "variables": world},
        "viewProjectionRange": {"bindPoint": VIEWPROJ_CB, "startOffset": VIEWPROJ_START, "endOffset": VIEWPROJ_END, "variables": view},
        "proofBoundary": (
            "Exact native-OAT-selected multiply-decal VS bytes are SHA-256 verified, reflected RDEF variable ranges are decoded directly, and the exact selected OAT pass is matched by the pinned VS/PS asset pair. The reported constant.* accessors come only from that pass's vertexShader block, including OAT matching-accessor omissions. This proves destination byte-range to engine-accessor identity; it does not invent or assign runtime values to those accessors."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--special-census", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    d = build(a.special_census)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"fadeRange": d["fadeRange"], "worldMatrixRange": d["worldMatrixRange"], "viewProjectionRange": d["viewProjectionRange"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

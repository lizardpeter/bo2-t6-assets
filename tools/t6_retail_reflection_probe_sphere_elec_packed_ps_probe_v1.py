#!/usr/bin/env python3
"""Exploratory retained-byte owner probe for the 24 Tomb sphere-electric reflection shaders.

This stage deliberately does *not* promote any new physical semantics by itself.
It reconstructs the missing ownership evidence for the 24 pixel shaders already
closed mathematically by T6_RETAIL_REFLECTION_PROBE_SHIFTED_TANGENT_BASIS_NORMAL_V1.

The probe avoids ephemeral target-position JSON. It:
  1. rediscovers direct Tomb pixel-shader objects whose retained name starts with
     ``pimp_shader_sw4_3d_zm_sphere_elec_``;
  2. builds a broad retained TechniqueSet/pass graph that records both direct and
     packed *pixel* shader nodes plus their paired vertex shader nodes;
  3. independently anchors packed PS pointers across identical retained pass keys;
  4. uses Tomb aliases whose anchored direct PS object is also physically present
     in Tomb as a calibration corpus for packed-offset <-> direct-object spacing;
  5. searches the Tomb packed-PS population for a unique ordered 24-member pointer
     bank matching the direct sphere-electric object bank within the observed
     calibration residual;
  6. reports the actual paired VS nodes for any uniquely resolved target owners.

Fail-closed rule: no target bank is reported resolved unless exactly one candidate
bank satisfies the calibration bound and every target has an owner occurrence.
This is an ownership probe, not yet the final vertex-semantic proof.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import statistics
import struct
from pathlib import Path

TARGET_MAP = "zm_tomb"
TARGET_PREFIX = "pimp_shader_sw4_3d_zm_sphere_elec_"
EXPECTED_TARGET_OBJECTS = 24
EXPECTED_STRUCTURAL_PS_ANCHORS = 76
EXPECTED_TOMB_DIRECT_CONTROLS = 10


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def jhash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class DSU:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        if self.p[x] != x:
            self.p[x] = self.find(self.p[x])
        return self.p[x]

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.p[b] = a


def normalize_scan_rows(raw):
    out = []
    for r in raw:
        if isinstance(r, tuple):
            out.append({"start": r[0], "fmt": r[1], "name": r[2]})
        else:
            out.append(r)
    return out


def shader_node(child, mapname, direct_blobs, direct_objects, stage):
    inline = child.get("inline")
    if inline and inline.get("prog") and "sha" in inline["prog"]:
        prog = inline["prog"]
        h = prog["sha"]
        blob = prog["blob"]
        old = direct_blobs[stage].setdefault(h, blob)
        if old != blob:
            raise ValueError(f"{stage}: direct SHA collision {h}")
        direct_objects[stage][(mapname, h)].add(inline["start"])
        return ("sha", h)
    if child.get("kind") == "packed":
        return ("ptr", mapname, child.get("block"), child.get("offset"))
    return None


def collect_broad_events(root: Path, base, broad):
    all_events = {}
    direct_blobs = {"ps": {}, "vs": {}}
    direct_objects = {"ps": collections.defaultdict(set), "vs": collections.defaultdict(set)}
    scan_rows = []

    for mapname, cfg in base.MAPS.items():
        path = root / cfg["rel"]
        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != base.SHAS[mapname]:
            raise ValueError(f"{mapname}: expanded SHA mismatch {actual}")
        blocks = base.front(data)
        rows = normalize_scan_rows(base.scan_sets(data, blocks, cfg["world"]))
        events = []
        rejected = 0
        for ti, row in enumerate(rows):
            try:
                end, ts = broad.parse_set_loose(base, data, row, blocks)
            except Exception:
                rejected += 1
                continue
            nxt = rows[ti + 1]["start"] if ti + 1 < len(rows) else cfg["world"]
            if end > nxt:
                rejected += 1
                continue
            for tr in ts["refs"]:
                tech = tr.get("tech")
                if not tech:
                    continue
                for pa in tech["passes"]:
                    ps_node = shader_node(
                        pa["c"]["ps"], mapname, direct_blobs, direct_objects, "ps"
                    )
                    vs_node = shader_node(
                        pa["c"]["vs"], mapname, direct_blobs, direct_objects, "vs"
                    )
                    events.append(
                        {
                            "event": len(events),
                            "ti": ti,
                            "ts": ts["name"],
                            "fmt": ts["fmt"],
                            "slot": tr["slot"],
                            "pass": pa["i"],
                            "ps": ps_node,
                            "vs": vs_node,
                        }
                    )
        all_events[mapname] = events
        scan_rows.append(
            {
                "map": mapname,
                "techniqueSetCandidateCount": len(rows),
                "rejectedCandidateCount": rejected,
                "parsedPassCount": len(events),
            }
        )
    return all_events, direct_blobs, direct_objects, scan_rows


def program_type(base, blob: bytes):
    w = base.words(blob)
    return (w[0] >> 16) & 0xFFFF


def scan_named_direct_ps_objects(data: bytes, blocks, base, prefix: str | None = None):
    needle = (prefix or "pimp_shader_").encode("ascii")
    out = []
    seen_starts = set()
    p = 0
    while True:
        q = data.find(needle, p)
        if q < 0:
            break
        p = q + 1
        st = q - 16
        if st < 0 or st in seen_starts:
            continue
        try:
            namep, runtime, progp, size = struct.unpack_from("<IIII", data, st)
            if runtime != 0:
                continue
            if base.dec(namep, blocks)[0] not in ("following", "insert"):
                continue
            name, name_end = base.cstr(data, q)
            if name_end <= q or (prefix is not None and not name.startswith(prefix)):
                continue
            end, obj = base.shader(data, st, blocks)
            if obj["name"] != name or not obj.get("prog") or "sha" not in obj["prog"]:
                continue
            prog = obj["prog"]
            blob = prog["blob"]
            if not blob.startswith(b"DXBC") or hashlib.sha256(blob).hexdigest() != prog["sha"]:
                continue
            if program_type(base, blob) != 0:
                continue
        except Exception:
            continue
        seen_starts.add(st)
        out.append(
            {
                "fixedStart": st,
                "name": name,
                "sha256": prog["sha"],
                "programStart": prog["start"],
                "programBytes": prog["size"],
                "end": end,
            }
        )
    out.sort(key=lambda x: x["fixedStart"])
    return out


def structural_aliases(events, stage: str):
    dsu = DSU()
    by_key = collections.defaultdict(set)
    for mapname, evs in events.items():
        for e in evs:
            node = e[stage]
            if node is None:
                continue
            key = (e["ts"], e["slot"], e["pass"], e["fmt"])
            by_key[key].add(node)
    for nodes in by_key.values():
        nodes = list(nodes)
        for n in nodes[1:]:
            dsu.union(nodes[0], n)

    comp_shas = collections.defaultdict(set)
    for n in list(dsu.p):
        if n[0] == "sha":
            comp_shas[dsu.find(n)].add(n[1])

    ptrs = {
        e[stage]
        for evs in events.values()
        for e in evs
        if e[stage] is not None and e[stage][0] == "ptr"
    }
    resolved = {}
    conflicts = []
    for p in sorted(ptrs):
        shas = comp_shas[dsu.find(p)]
        if len(shas) == 1:
            resolved[p] = next(iter(shas))
        elif len(shas) > 1:
            conflicts.append((p, sorted(shas)))
    if conflicts:
        raise ValueError(f"{stage}: structural alias conflicts {conflicts[:3]}")
    return resolved, ptrs, by_key


def choose_unique_object_position(rows, sha):
    pos = sorted({r["fixedStart"] for r in rows if r["sha256"] == sha})
    if len(pos) != 1:
        return None
    return pos[0]


def calibration_controls(events, structural_ps, tomb_direct_ps):
    tomb_ptrs = sorted(
        p for p in structural_ps if p[0] == "ptr" and p[1] == TARGET_MAP
    )
    controls = []
    for p in tomb_ptrs:
        sha = structural_ps[p]
        pos = choose_unique_object_position(tomb_direct_ps, sha)
        if pos is None:
            continue
        controls.append(
            {
                "block": p[2],
                "offset": p[3],
                "sha256": sha,
                "fixedStart": pos,
                "delta": pos - p[3],
            }
        )
    controls.sort(key=lambda x: (x["block"], x["offset"]))
    return controls


def pairwise_drift(rows):
    vals = []
    for i, a in enumerate(rows):
        for b in rows[i + 1 :]:
            if a["block"] != b["block"]:
                continue
            vals.append(
                abs(
                    (b["fixedStart"] - a["fixedStart"])
                    - (b["offset"] - a["offset"])
                )
            )
    return vals


def target_candidate_banks(target_objects, tomb_pointers, controls):
    if not target_objects:
        return [], {}
    by_block_controls = collections.defaultdict(list)
    for r in controls:
        by_block_controls[r["block"]].append(r)

    calibration = {}
    candidates = []
    target_pos = [r["fixedStart"] for r in target_objects]
    rel_pos = [x - target_pos[0] for x in target_pos]

    for block, cr in sorted(by_block_controls.items()):
        if len(cr) < 2:
            continue
        drifts = pairwise_drift(cr)
        max_drift = max(drifts) if drifts else 0
        deltas = [r["delta"] for r in cr]
        delta_span = max(deltas) - min(deltas)
        calibration[block] = {
            "controlCount": len(cr),
            "pairwiseCount": len(drifts),
            "maxPairwiseDifferentialDriftBytes": max_drift,
            "deltaMin": min(deltas),
            "deltaMax": max(deltas),
            "deltaSpanBytes": delta_span,
            "deltaMedian": statistics.median(deltas),
        }

        offs = sorted({p[3] for p in tomb_pointers if p[2] == block})
        for first in offs:
            assigned = [first]
            residuals = [0]
            ok = True
            for rel in rel_pos[1:]:
                predicted = first + rel
                near = [o for o in offs if abs(o - predicted) <= max_drift]
                if len(near) != 1:
                    ok = False
                    break
                o = near[0]
                if o in assigned:
                    ok = False
                    break
                assigned.append(o)
                residuals.append(abs((o - first) - rel))
            if not ok or assigned != sorted(assigned):
                continue
            candidates.append(
                {
                    "block": block,
                    "offsets": assigned,
                    "maxResidualBytes": max(residuals),
                    "residuals": residuals,
                }
            )
    uniq = {}
    for c in candidates:
        uniq[(c["block"], tuple(c["offsets"]))] = c
    return list(uniq.values()), calibration


def owner_rows(events, target_objects, bank):
    sha_by_ptr = {
        ("ptr", TARGET_MAP, bank["block"], off): target_objects[i]["sha256"]
        for i, off in enumerate(bank["offsets"])
    }
    rows = []
    for e in events[TARGET_MAP]:
        sha = sha_by_ptr.get(e["ps"])
        if sha is None:
            continue
        rows.append(
            {
                "pixelShaderSha256": sha,
                "pixelPointer": {"block": e["ps"][2], "offset": e["ps"][3]},
                "techniqueSet": e["ts"],
                "worldVertFormat": e["fmt"],
                "slot": e["slot"],
                "passIndex": e["pass"],
                "pairedVertexNode": list(e["vs"]) if e["vs"] is not None else None,
            }
        )
    rows.sort(
        key=lambda x: (
            x["pixelShaderSha256"],
            x["techniqueSet"] or "",
            x["slot"],
            x["passIndex"],
        )
    )
    return rows


def build(root: Path, base_path: Path, broad_path: Path):
    base = load(base_path, "base")
    broad = load(broad_path, "broad")
    events, direct_blobs, direct_objects, scan_rows = collect_broad_events(root, base, broad)

    structural_ps, all_ps_ptrs, _ = structural_aliases(events, "ps")
    if len(structural_ps) != EXPECTED_STRUCTURAL_PS_ANCHORS:
        raise ValueError(
            f"packed PS structural anchor count {len(structural_ps)} != {EXPECTED_STRUCTURAL_PS_ANCHORS}"
        )

    cfg = base.MAPS[TARGET_MAP]
    tomb = (root / cfg["rel"]).read_bytes()
    blocks = base.front(tomb)
    all_tomb_direct_ps = scan_named_direct_ps_objects(tomb, blocks, base)
    targets = [r for r in all_tomb_direct_ps if r["name"].startswith(TARGET_PREFIX)]
    if len(targets) != EXPECTED_TARGET_OBJECTS:
        raise ValueError(f"sphere-electric direct PS object count {len(targets)}")
    if len({r["sha256"] for r in targets}) != EXPECTED_TARGET_OBJECTS:
        raise ValueError("sphere-electric target SHA identities are not 24 unique objects")

    controls = calibration_controls(events, structural_ps, all_tomb_direct_ps)
    if len(controls) != EXPECTED_TOMB_DIRECT_CONTROLS:
        raise ValueError(
            f"Tomb direct packed-PS calibration controls {len(controls)} != {EXPECTED_TOMB_DIRECT_CONTROLS}"
        )

    tomb_ptrs = sorted(
        {
            e["ps"]
            for e in events[TARGET_MAP]
            if e["ps"] is not None and e["ps"][0] == "ptr"
        }
    )
    banks, calibration = target_candidate_banks(targets, tomb_ptrs, controls)

    resolved_bank = banks[0] if len(banks) == 1 else None
    owners = owner_rows(events, targets, resolved_bank) if resolved_bank else []
    owned_target_shas = {r["pixelShaderSha256"] for r in owners}
    if resolved_bank is not None and owned_target_shas != {r["sha256"] for r in targets}:
        raise ValueError(
            f"unique bank found but owner coverage incomplete {len(owned_target_shas)}/{len(targets)}"
        )

    paired_vs = collections.Counter(
        tuple(r["pairedVertexNode"]) if r["pairedVertexNode"] is not None else None
        for r in owners
    )
    target_rows = [
        {
            "fixedStart": r["fixedStart"],
            "name": r["name"],
            "sha256": r["sha256"],
            "programStart": r["programStart"],
            "programBytes": r["programBytes"],
        }
        for r in targets
    ]
    control_rows = [dict(r) for r in controls]
    candidate_rows = [
        {
            "block": c["block"],
            "offsets": c["offsets"],
            "maxResidualBytes": c["maxResidualBytes"],
        }
        for c in banks
    ]
    summary = {
        "retainedMapCount": len(base.MAPS),
        "structurallyAnchoredPackedPixelPointerCount": len(structural_ps),
        "tombDirectPixelShaderObjectCount": len(all_tomb_direct_ps),
        "tombDirectCalibrationControlCount": len(controls),
        "sphereElectricTargetObjectCount": len(targets),
        "tombPackedPixelPointerCount": len(tomb_ptrs),
        "candidateTargetBankCount": len(banks),
        "targetBankUniquelyResolved": len(banks) == 1,
        "resolvedOwnerOccurrenceCount": len(owners),
        "resolvedTargetShaderCount": len(owned_target_shas),
        "pairedVertexNodeIdentityCount": len(paired_vs) if owners else 0,
        "targetRowsSha256": jhash(target_rows),
        "controlRowsSha256": jhash(control_rows),
        "candidateRowsSha256": jhash(candidate_rows),
        "ownerRowsSha256": jhash(owners),
        "scanRowsSha256": jhash(scan_rows),
    }
    return {
        "format": "t6-retail-reflection-probe-sphere-elec-packed-ps-probe-v1",
        "producer": "tools/t6_retail_reflection_probe_sphere_elec_packed_ps_probe_v1.py",
        "target": {
            "map": TARGET_MAP,
            "shaderNamePrefix": TARGET_PREFIX,
            "mathematicalProof": "manifests/render/T6_RETAIL_REFLECTION_PROBE_SHIFTED_TANGENT_BASIS_NORMAL_V1.json",
        },
        "calibration": calibration,
        "controls": control_rows,
        "candidateBanks": candidate_rows,
        "resolvedBank": (
            {
                "block": resolved_bank["block"],
                "offsets": resolved_bank["offsets"],
                "maxResidualBytes": resolved_bank["maxResidualBytes"],
            }
            if resolved_bank
            else None
        ),
        "targetObjects": target_rows,
        "ownerRows": owners,
        "pairedVertexNodes": [
            {"node": list(k) if k is not None else None, "ownerOccurrenceCount": v}
            for k, v in sorted(paired_vs.items(), key=lambda kv: str(kv[0]))
        ],
        "summary": summary,
        "proofBoundary": (
            "Retained ownership exploration only. The 24 target pixel shaders are inherited from the already-committed "
            "shifted tangent-basis normal proof. Packed pixel pointers are structurally anchored only through exact retained "
            "cross-map pass identity. Tomb pointer/object spacing is calibrated only from aliases whose direct PS object is "
            "also physically present in Tomb. A target bank is marked resolved only when exactly one ordered 24-pointer bank "
            "fits the independently observed calibration residual and all 24 direct target SHAs occur as owners. Physical "
            "roles of the paired vertex interpolators remain unpromoted until those actual VS payloads are separately proved."
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/mnt/data/t6_xanim_corpus"))
    ap.add_argument(
        "--base-verifier",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_texcoord2_texcoord1_v1.py"),
    )
    ap.add_argument(
        "--broad-verifier",
        type=Path,
        default=Path("tools/t6_retail_reflection_probe_texcoord3_texcoord1_v1.py"),
    )
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    data = build(a.root, a.base_verifier, a.broad_verifier)
    a.out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(json.dumps(data["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

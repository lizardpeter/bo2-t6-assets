#!/usr/bin/env python3
"""Self-contained, no-private-repository Source 2 VPK asset census/recovery.

Uses only Python stdlib and Steam-downloaded original VPKs. Does not decrypt,
reconstruct or fabricate textures. Every extracted resource passes the base
VPK index's exact CRC. Material references are discovered from original
Workshop resource string tables; compressed/unsupported KV3 references are
reported as a limitation rather than claimed to be fully enumerated.
"""
import argparse
import binascii
import collections
import hashlib
import json
import os
import pathlib
import re
import struct
import sys

MAGIC = 0x55AA1234
MAX_READ = 96 * 1024 * 1024
MAX_ENTRY_SCAN = 35000
MAX_TOTAL_SCAN = 850 * 1024 * 1024

# Directly observed in the user's original importer logs and archived audits.
# Do not imply that this covers every unresolved CS2 source dependency.
SEEDS = {
    "3620635379": [
        "materials/tile/tile_mall_floor00_color_tga_51298798.vtex_c",
        "materials/tile/tile_mall_floor00_height-ssbump_normal_tga_1f6f8cbd.vtex_c",
        "materials/skybox/sky_furnace.vmat_c",
        "materials/skybox/sky_day01_01.vmat_c",
        "materials/skybox/sky_day01_01vmat.vmat_c",
    ],
    "3620630831": [
        "materials/de_dust/hr_dust/hr_dust_decal_mudbrick_wear_01_color_psd_4a3a0ad0.vtex_c",
        "materials/de_dust/hr_dust/hr_dust_decal_road_striping_color_psd_3c1a7134.vtex_c",
        "materials/skybox/sky_de_dust2vmat.vmat_c",
        "materials/skybox/sky_csgo_cloudy01.vmat_c",
    ],
}
RESOURCE_RX = re.compile(
    rb"(?:materials|models|maps)/[a-zA-Z0-9_.+/\-]{4,250}\."
    rb"(?:vmat|vtex|vmdl|vmesh)(?:_c)?\b", re.I
)

def compiled(value):
    name = value.replace("\\", "/").strip().lower()
    if name.endswith((".vmat", ".vtex", ".vmdl", ".vmesh")):
        name += "_c"
    if (not name or name.startswith("/") or ":" in name or
            any(p in ("", ".", "..") for p in name.split("/"))):
        return None
    if not name.endswith((".vmat_c", ".vtex_c", ".vmdl_c", ".vmesh_c")):
        return None
    return name

class Vpk:
    def __init__(self, path=None, payload=None):
        self.path = pathlib.Path(path) if path else None
        if payload is None:
            with self.path.open("rb") as f:
                header = f.read(28)
                if len(header) < 12:
                    raise ValueError("short VPK directory header")
                magic, version, size = struct.unpack_from("<III", header)
                if magic != MAGIC or version not in (1, 2):
                    raise ValueError("not a Valve VPK v1/v2 directory")
                header_size = 12 if version == 1 else 28
                if size > 512 * 1024 * 1024:
                    raise ValueError("VPK directory tree too large")
                f.seek(header_size)
                tree = f.read(size)
        else:
            header = payload[:28]
            if len(header) < 12:
                raise ValueError("short nested VPK header")
            magic, version, size = struct.unpack_from("<III", header)
            if magic != MAGIC or version not in (1, 2):
                raise ValueError("not nested VPK v1/v2")
            header_size = 12 if version == 1 else 28
            if size > 512 * 1024 * 1024:
                raise ValueError("nested VPK directory too large")
            tree = payload[header_size:header_size + size]
            self.payload = payload
        if len(tree) != size:
            raise ValueError("truncated VPK tree")
        self.data_start = header_size + size
        self.entries = {}
        pos = 0
        def word():
            nonlocal pos
            end = tree.find(b"\0", pos)
            if end < 0 or end - pos > 1024:
                raise ValueError("malformed VPK string tree")
            data = tree[pos:end].decode("utf-8", "replace")
            pos = end + 1
            return data
        for _ in range(1000):
            ext = word()
            if not ext:
                break
            for _ in range(50000):
                folder = word()
                if not folder:
                    break
                for _ in range(150000):
                    name = word()
                    if not name:
                        break
                    if pos + 18 > len(tree):
                        raise ValueError("truncated VPK entry")
                    crc, preload, idx, off, length, term = struct.unpack_from(
                        "<IHHIIH", tree, pos
                    )
                    pos += 18
                    if term != 0xFFFF or pos + preload > len(tree):
                        raise ValueError("invalid VPK entry delimiter")
                    pre = tree[pos:pos + preload]
                    pos += preload
                    full = (("" if folder == " " else folder + "/") +
                            name + "." + ext).lower()
                    self.entries[full] = (crc, pre, idx, off, length)
                    if len(self.entries) > 750000:
                        raise ValueError("unbounded VPK tree")
            else:
                raise ValueError("too many VPK folders")
        else:
            raise ValueError("too many VPK extensions")

    def segment(self, idx):
        if not self.path:
            raise ValueError("nested VPK references unavailable external segment")
        base = self.path.name
        if not base.endswith("_dir.vpk"):
            raise ValueError("non-directory VPK path")
        return self.path.with_name(base[:-8] + f"_{idx:03}.vpk")

    def read(self, name, max_bytes=MAX_READ):
        name = name.lower()
        crc, pre, idx, off, length = self.entries[name]
        if len(pre) + length > max_bytes:
            raise ValueError(f"source entry too large: {name}")
        if idx == 0x7FFF:
            offset = self.data_start + off
            if hasattr(self, "payload"):
                data = self.payload[offset:offset + length]
            else:
                with self.path.open("rb") as f:
                    f.seek(offset)
                    data = f.read(length)
        else:
            if hasattr(self, "payload"):
                raise ValueError(f"nested external archive {idx:03} not available")
            with self.segment(idx).open("rb") as f:
                f.seek(off)
                data = f.read(length)
        if len(data) != length:
            raise ValueError(f"original VPK entry truncated: {name}")
        result = pre + data
        actual = binascii.crc32(result) & 0xFFFFFFFF
        if actual != crc:
            raise ValueError(f"original VPK CRC mismatch {name}: {actual:08x} != {crc:08x}")
        return result

def scan_workshop(args):
    original = Vpk(args.workshop)
    targets = set(SEEDS[args.workshop_id])
    seen_present = set()
    source_packages = []
    diagnostics = []
    for path in original.entries:
        if path.endswith((".vmat_c", ".vtex_c", ".vmdl_c", ".vmesh_c")):
            seen_present.add(path)
            if path.endswith(".vmat_c"):
                targets.add(path)
    maps = [p for p in original.entries if p.startswith("maps/") and p.endswith(".vpk")]
    scanned_bytes = 0
    scanned_entries = 0
    for name in maps:
        try:
            bytes_ = original.read(name, max_bytes=4 * 1024 * 1024 * 1024)
            nested = Vpk(payload=bytes_)
            source_packages.append(name)
        except (OSError, ValueError) as e:
            diagnostics.append(f"{name}: {e}")
            continue
        for entry in nested.entries:
            if entry.endswith((".vmat_c", ".vtex_c", ".vmdl_c", ".vmesh_c")):
                seen_present.add(entry)
            if entry.endswith(".vmat_c"):
                targets.add(entry)
            if not entry.endswith((".vmat_c", ".vmesh_c", ".vmdl_c",
                                   ".vwrld_c", ".vwnod_c")):
                continue
            if scanned_entries >= MAX_ENTRY_SCAN or scanned_bytes > MAX_TOTAL_SCAN:
                diagnostics.append("WORKSHOP RESOURCE SCAN BUDGET REACHED: incomplete census")
                break
            try:
                data = nested.read(entry, max_bytes=12 * 1024 * 1024)
                scanned_bytes += len(data)
                scanned_entries += 1
                for matched in RESOURCE_RX.findall(data):
                    candidate = compiled(matched.decode("utf-8"))
                    if candidate:
                        targets.add(candidate)
            except (OSError, ValueError) as e:
                if len(diagnostics) < 200:
                    diagnostics.append(f"{entry}: {e}")
        del nested, bytes_
    plan = dict(
        workshop_id=args.workshop_id, original_workshop=str(args.workshop),
        nested_packages=source_packages, scanned_entries=scanned_entries,
        scanned_bytes=scanned_bytes,
        seeded_entries=SEEDS[args.workshop_id], targets=sorted(targets),
        available_from_workshop=sorted(seen_present),
        diagnostic=diagnostics,
        audit_limitations=[
            "Raw original Source2 resource-string discovery, not full KV3 decompilation.",
            "Compressed KV3-only and base-model-only material references may not be enumerated.",
            "A listed material may be present but unsupported by the Vulkan shader path.",
        ]
    )
    pathlib.Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.output).write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"Workshop {args.workshop_id}: {len(targets)} source candidate paths, "
          f"{scanned_entries} scanned resources, {len(source_packages)} maps")

def build_plan(args):
    base = Vpk(args.index)
    statuses = {}
    groups = collections.defaultdict(list)
    for filename in args.plans:
        plan = json.loads(pathlib.Path(filename).read_text(encoding="utf-8"))
        wid = plan["workshop_id"]
        present = set(plan["available_from_workshop"])
        for path in plan["targets"]:
            if path in present:
                statuses.setdefault(wid, {})[path] = "WORKSHOP"
            elif path in base.entries:
                idx = base.entries[path][2]
                statuses.setdefault(wid, {})[path] = (
                    "BASE_INLINE" if idx == 0x7FFF else f"pak01_{idx:03}.vpk"
                )
                groups[idx].append(f"{wid}|{path}")
            else:
                statuses.setdefault(wid, {})[path] = "NOT_IN_BASE_INDEX"
    # Put the directly observed visual defects first, then the archive chunks
    # that resolve the most uniquely referenced source material/texture files.
    def priority(item):
        idx, paths = item
        seeds = sum(1 for p in paths
                    if p.split("|",1)[1] in SEEDS.get(p.split("|",1)[0], []))
        return (-seeds, -len(paths), idx)
    ordered = [int(k) for k, _ in sorted(
        ((k,v) for k,v in groups.items() if k != 0x7FFF), key=priority
    )]
    data = {
        "base_index": args.index, "known_seed_files": SEEDS,
        "statuses": statuses,
        "archive_priority": ordered,
        "archive_resources": {f"pak01_{idx:03}.vpk": sorted(entries)
                              for idx, entries in groups.items() if idx != 0x7FFF},
        "not_in_base": {wid: sorted(k for k,v in m.items() if v == "NOT_IN_BASE_INDEX")
                        for wid,m in statuses.items()},
    }
    pathlib.Path(args.output).write_text(json.dumps(data,indent=2),encoding="utf-8")
    print(f"Base index: {len(base.entries)} resources, "
          f"{len(ordered)} physical segments for discovered targets")
    print("Priority segments:", ", ".join(f"pak01_{i:03}.vpk" for i in ordered[:30]))

def extend_plan(args):
    """Walk original VMAT RERL/RED2 texture dependencies recovered in stage 1.

    Unlike the initial Workshop-only scan, this follows hundreds of compiled
    base VMATs. Source2 compiled VMATs retain their exact .vtex paths in the
    RERL/RED2 resource blocks, even when DATA/KV3 is compressed. No guessed
    texture names, synthesized pixels or original game shaders are needed.
    """
    base = Vpk(args.index)
    report_path = pathlib.Path(args.plan)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    root = pathlib.Path(args.output)
    sources = {}
    for fname in args.workshop_plans:
        item = json.loads(pathlib.Path(fname).read_text(encoding="utf-8"))
        sources[item["workshop_id"]] = set(item["available_from_workshop"])
    new_by_map = collections.Counter()
    new_refs = collections.defaultdict(list)
    for wid, statuses in report["statuses"].items():
        folder = root / f"cs2-workshop-{wid}-vpk" / "cs2-base-resources"
        if not folder.is_dir():
            continue
        # A Source2 model can reference external VMESH as well as VMAT.
        # Original Christmas decoration dependencies must be discovered from
        # authored RERL/RED2 bytes, not guessed from "santa" filenames.
        for material_file in folder.rglob("*"):
            if not material_file.is_file() or not material_file.name.endswith(
                (".vmat_c", ".vmdl_c", ".vmesh_c")
            ):
                continue
            if material_file.stat().st_size > MAX_READ:
                continue
            data = material_file.read_bytes()
            for match in RESOURCE_RX.findall(data):
                candidate = compiled(match.decode("utf-8", "replace"))
                if not candidate or candidate in statuses:
                    continue
                if candidate in sources.get(wid,set()):
                    location = "WORKSHOP"
                elif candidate not in base.entries:
                    location = "NOT_IN_BASE_INDEX"
                else:
                    idx = base.entries[candidate][2]
                    location = ("BASE_INLINE" if idx == 0x7fff
                                else f"pak01_{idx:03}.vpk")
                statuses[candidate] = location
                new_by_map[wid] += 1
                new_refs[wid].append(candidate)
    archive_resources = collections.defaultdict(list)
    for wid, statuses in report["statuses"].items():
        for name, source in statuses.items():
            if source.startswith("pak01_"):
                archive_resources[source].append(f"{wid}|{name}")
    report["archive_resources"] = {
        archive: sorted(refs) for archive, refs in sorted(archive_resources.items())
    }
    def ranking(pair):
        name, refs = pair
        seed_count = sum(1 for encoded in refs
            if encoded.split("|",1)[1] in SEEDS.get(encoded.split("|",1)[0], []))
        return (-seed_count,-len(refs),name)
    report["archive_priority"] = [
        int(archive.removeprefix("pak01_").removesuffix(".vpk"))
        for archive,refs in sorted(archive_resources.items(),key=ranking)
    ]
    report["not_in_base"] = {
        wid: sorted(name for name,value in statuses.items()
                    if value == "NOT_IN_BASE_INDEX")
        for wid,statuses in report["statuses"].items()
    }
    report["original_vmat_texture_dependency_expansion"] = {
        "new_paths_per_map": dict(new_by_map),
        "new_reference_samples": {
            wid: sorted(refs)[:35] for wid,refs in new_refs.items()
        },
        "extraction_method": "Original VMAT/VMDL/VMESH RERL/RED2 resource strings",
        "limitation": "Only recovered original VMAT/VMDL/VMESH references are scanned; compressed KV3-only strings may remain",
    }
    report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(f"Original VMAT/VMDL/VMESH dependency expansion: {dict(new_by_map)} new source "
          f"paths, {len(report['archive_priority'])} total referenced VPK chunks")

def extract(args):
    report = json.loads(pathlib.Path(args.plan).read_text(encoding="utf-8"))
    base = Vpk(args.index)
    out = pathlib.Path(args.output)
    extracted = []
    issues = []
    for wid, entries in report["statuses"].items():
        for name, location in entries.items():
            if location == "WORKSHOP" or location == "NOT_IN_BASE_INDEX":
                continue
            if args.segment is not None:
                if location != f"pak01_{args.segment:03}.vpk":
                    continue
            elif location != "BASE_INLINE":
                continue
            filename = (out/f"cs2-workshop-{wid}-vpk"/"cs2-base-resources"/name)
            try:
                bytes_ = base.read(name)
                filename.parent.mkdir(parents=True, exist_ok=True)
                if not filename.is_file() or filename.read_bytes() != bytes_:
                    filename.write_bytes(bytes_)
                extracted.append({
                    "workshop": wid, "path": name, "size": len(bytes_),
                    "sha256": hashlib.sha256(bytes_).hexdigest(), "source": location
                })
            except (OSError, ValueError, KeyError) as e:
                issues.append(f"{wid}\t{name}\t{location}\t{e}")
    summary = out/"_CS2-SOURCE-AUDIT"
    summary.mkdir(parents=True, exist_ok=True)
    prefix = f"pak01_{args.segment:03}" if args.segment is not None else "inline"
    (summary/f"extracted-{prefix}.json").write_text(json.dumps(extracted,indent=2),encoding="utf-8")
    (summary/f"failed-{prefix}.tsv").write_text("\n".join(issues),encoding="utf-8")
    print(f"{prefix}: recovered {len(extracted)} exact original source resources, "
          f"{len(issues)} failures")

def main():
    p = argparse.ArgumentParser()
    subs = p.add_subparsers(dest="cmd", required=True)
    a = subs.add_parser("scan")
    a.add_argument("--workshop", required=True)
    a.add_argument("--workshop-id", required=True, choices=tuple(SEEDS))
    a.add_argument("--output", required=True)
    a.set_defaults(func=scan_workshop)
    a = subs.add_parser("plan")
    a.add_argument("--index", required=True)
    a.add_argument("--plans", required=True, nargs="+")
    a.add_argument("--output", required=True)
    a.set_defaults(func=build_plan)
    a = subs.add_parser("extend")
    a.add_argument("--index", required=True)
    a.add_argument("--plan", required=True)
    a.add_argument("--output", required=True)
    a.add_argument("--workshop-plans", required=True, nargs="+")
    a.set_defaults(func=extend_plan)
    a = subs.add_parser("extract")
    a.add_argument("--index", required=True)
    a.add_argument("--plan", required=True)
    a.add_argument("--output", required=True)
    a.add_argument("--segment", type=int)
    a.set_defaults(func=extract)
    args = p.parse_args()
    try:
        args.func(args)
    except (OSError, ValueError, KeyError, struct.error) as exc:
        print(f"Source2 recovery error: {exc}",file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

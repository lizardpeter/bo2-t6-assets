#!/usr/bin/env python3
"""Prove exact T6 Technique absence inside explicitly successful OAT dump roots.

This validator is intentionally scoped.  It proves only that a named Technique
and its exact byte identity are absent from the supplied physical OAT outputs.
It never promotes that scoped negative to global retail absence.

The caller must supply one dump return code for every root.  Any nonzero or
missing return code fails closed so a partial OAT output cannot become negative
evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FORMAT = "t6-oat-exact-technique-absence-v1"


class AbsenceError(RuntimeError):
    pass


def parse_label_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected LABEL=PATH")
    label, raw = value.split("=", 1)
    label = label.strip()
    raw = raw.strip()
    if not label or not raw:
        raise argparse.ArgumentTypeError("expected non-empty LABEL=PATH")
    return label, Path(raw).resolve()


def parse_label_rc(value: str) -> tuple[str, int]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected LABEL=RC")
    label, raw = value.split("=", 1)
    label = label.strip()
    raw = raw.strip()
    if not label or not raw:
        raise argparse.ArgumentTypeError("expected non-empty LABEL=RC")
    try:
        rc = int(raw, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid return code {raw!r}") from exc
    return label, rc


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build(
    roots: dict[str, Path],
    dump_rcs: dict[str, int],
    target_name: str,
    target_bytes: int,
    target_sha256: str,
) -> dict:
    if not roots:
        raise AbsenceError("at least one root is required")
    if set(roots) != set(dump_rcs):
        missing = sorted(set(roots) - set(dump_rcs))
        extra = sorted(set(dump_rcs) - set(roots))
        raise AbsenceError(f"dump return-code labels must exactly match roots; missing={missing} extra={extra}")
    failed = {label: rc for label, rc in dump_rcs.items() if rc != 0}
    if failed:
        raise AbsenceError(f"one or more supplied OAT dumps were not successful: {failed}")
    if not target_name or "/" in target_name or "\\" in target_name:
        raise AbsenceError("target name must be one Technique basename without path separators")
    if target_bytes < 0:
        raise AbsenceError("target byte count must be non-negative")
    target_sha256 = target_sha256.lower()
    if len(target_sha256) != 64 or any(c not in "0123456789abcdef" for c in target_sha256):
        raise AbsenceError("target SHA-256 must be 64 lowercase/uppercase hex characters")

    root_rows = []
    named_hits = []
    exact_payload_hits = []
    exact_named_identity_hits = []
    total_techniques = 0
    total_techsets = 0

    for label, root in sorted(roots.items()):
        if not root.is_dir():
            raise AbsenceError(f"root {label!r} does not exist or is not a directory: {root}")
        techniques_dir = root / "techniques"
        techsets_dir = root / "techsets"
        techniques = sorted(techniques_dir.glob("*.tech")) if techniques_dir.is_dir() else []
        techsets = sorted(techsets_dir.glob("*.techset")) if techsets_dir.is_dir() else []
        total_techniques += len(techniques)
        total_techsets += len(techsets)

        root_named = []
        root_payload = []
        for path in techniques:
            size = path.stat().st_size
            digest = _sha256(path)
            record = {
                "root": label,
                "relativeFile": path.relative_to(root).as_posix(),
                "bytes": size,
                "sha256": digest,
            }
            if path.name == f"{target_name}.tech":
                named_hits.append(record)
                root_named.append(record)
            if size == target_bytes and digest == target_sha256:
                exact_payload_hits.append(record)
                root_payload.append(record)
                if path.name == f"{target_name}.tech":
                    exact_named_identity_hits.append(record)

        root_rows.append({
            "label": label,
            "root": str(root),
            "dumpReturnCode": dump_rcs[label],
            "techniqueCount": len(techniques),
            "techniqueSetCount": len(techsets),
            "targetFilenameHitCount": len(root_named),
            "targetExactPayloadHitCount": len(root_payload),
        })

    exact_absent = not named_hits and not exact_payload_hits
    return {
        "format": FORMAT,
        "authoritativeWithinSuppliedSuccessfulRoots": True,
        "globalRetailAbsenceClaim": False,
        "target": {
            "name": target_name,
            "bytes": target_bytes,
            "sha256": target_sha256,
        },
        "summary": {
            "successfulRootCount": len(root_rows),
            "techniqueCount": total_techniques,
            "techniqueSetCount": total_techsets,
            "targetFilenameHitCount": len(named_hits),
            "targetExactPayloadHitCount": len(exact_payload_hits),
            "targetExactNamedIdentityHitCount": len(exact_named_identity_hits),
            "exactTechniqueAbsentWithinSuppliedRoots": exact_absent,
        },
        "roots": root_rows,
        "targetFilenameHits": named_hits,
        "targetExactPayloadHits": exact_payload_hits,
        "targetExactNamedIdentityHits": exact_named_identity_hits,
        "proofBoundary": (
            "Authoritative only for physical files emitted by the explicitly supplied OAT roots whose caller-supplied dump return codes are all zero. "
            "The scan checks both the exact target filename and every .tech payload for the exact byte count and SHA-256, so a byte-identical payload under another filename is retained as a hit. "
            "A negative is not a global retail absence claim and says nothing about uncensused FastFiles, executable-owned renderer globals, generated runtime assets, or OAT assets not emitted by the requested dump mode."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", action="append", required=True, metavar="LABEL=PATH")
    p.add_argument("--dump-rc", action="append", required=True, metavar="LABEL=RC")
    p.add_argument("--target-name", required=True)
    p.add_argument("--target-bytes", type=int, required=True)
    p.add_argument("--target-sha256", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()

    roots: dict[str, Path] = {}
    for value in a.root:
        label, path = parse_label_path(value)
        if label in roots and roots[label] != path:
            raise AbsenceError(f"conflicting paths supplied for root label {label!r}")
        roots[label] = path

    dump_rcs: dict[str, int] = {}
    for value in a.dump_rc:
        label, rc = parse_label_rc(value)
        if label in dump_rcs and dump_rcs[label] != rc:
            raise AbsenceError(f"conflicting return codes supplied for root label {label!r}")
        dump_rcs[label] = rc

    result = build(roots, dump_rcs, a.target_name, a.target_bytes, a.target_sha256)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Exact-retail static census for T6 multi-XModel DObj skeleton assembly.

This is a locator/census, not a semantic promotion. It is pinned to the exact
retail PC t6mp.exe and starts from the already-authoritative DObj skeleton
consumer/helper anchors retained by t6_retail_xanim_root_translation_proof_v1.
It emits bounded disassembly windows, exact helper xrefs, and nearby call/jump
edges so the producer of modelParent and aggregate bone bases can be proved in a
subsequent fail-closed verifier without transferring semantics from another
client build.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM

EXPECTED_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
EXPECTED_BYTES = 12_850_328
IMAGE_BASE = 0x00400000

HELPERS = {
    "rootNoParent": 0x008D6100,
    "rootWithParent": 0x008D6220,
    "nonRoot": 0x008D6B50,
}
CONSUMERS = {
    "consumerA": 0x00422A6F,
    "consumerB": 0x005C6948,
}
WINDOWS = {
    # Intentionally wider before than after: the unresolved value producers are
    # expected to precede the already-proven modelParent sentinel branches.
    "consumerA": (0x00422600, 0x00422E80),
    "consumerB": (0x005C6500, 0x005C6D80),
}


class ProofError(RuntimeError):
    pass


class PE:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        if len(self.data) != EXPECTED_BYTES:
            raise ProofError(f"retail byte count drift {len(self.data)} != {EXPECTED_BYTES}")
        digest = hashlib.sha256(self.data).hexdigest()
        if digest != EXPECTED_SHA256:
            raise ProofError(f"retail SHA drift {digest} != {EXPECTED_SHA256}")
        if self.data[:2] != b"MZ":
            raise ProofError("not MZ")
        pe = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[pe:pe + 4] != b"PE\0\0":
            raise ProofError("not PE")
        coff = pe + 4
        machine, nsects, _, _, _, opt_size, _ = struct.unpack_from("<HHIIIHH", self.data, coff)
        if machine != 0x14C:
            raise ProofError(f"not i386: 0x{machine:x}")
        opt = coff + 20
        if struct.unpack_from("<H", self.data, opt)[0] != 0x10B:
            raise ProofError("not PE32")
        image_base = struct.unpack_from("<I", self.data, opt + 28)[0]
        if image_base != IMAGE_BASE:
            raise ProofError(f"image base drift 0x{image_base:x}")
        sec = opt + opt_size
        self.sections: list[dict[str, Any]] = []
        for i in range(nsects):
            off = sec + i * 40
            name = self.data[off:off + 8].split(b"\0", 1)[0].decode("ascii", "replace")
            vsize, vaddr, raw_size, raw_off = struct.unpack_from("<IIII", self.data, off + 8)
            self.sections.append({
                "name": name,
                "va": IMAGE_BASE + vaddr,
                "size": max(vsize, raw_size),
                "rawSize": raw_size,
                "rawOffset": raw_off,
            })
        text = [s for s in self.sections if s["name"] == ".text"]
        if len(text) != 1:
            raise ProofError(f"expected one .text section, got {len(text)}")
        self.text = text[0]

    def off(self, va: int) -> int:
        for s in self.sections:
            if s["va"] <= va < s["va"] + s["size"]:
                delta = va - s["va"]
                if delta >= s["rawSize"]:
                    raise ProofError(f"VA 0x{va:x} not file-backed")
                return s["rawOffset"] + delta
        raise ProofError(f"unmapped VA 0x{va:x}")

    def bytes(self, va: int, size: int) -> bytes:
        off = self.off(va)
        return self.data[off:off + size]


class Disasm:
    def __init__(self):
        self.md = Cs(CS_ARCH_X86, CS_MODE_32)
        self.md.detail = True

    def decode(self, data: bytes, va: int):
        return list(self.md.disasm(data, va))


def insn_row(insn) -> dict[str, Any]:
    row: dict[str, Any] = {
        "va": f"0x{insn.address:08x}",
        "size": insn.size,
        "bytes": bytes(insn.bytes).hex(),
        "mnemonic": insn.mnemonic,
        "opStr": insn.op_str,
    }
    if insn.mnemonic in ("call", "jmp") or insn.mnemonic.startswith("j"):
        if insn.operands and insn.operands[0].type == X86_OP_IMM:
            row["target"] = f"0x{insn.operands[0].imm & 0xffffffff:08x}"
    return row


def disasm_window(pe: PE, ds: Disasm, start: int, end: int) -> list[dict[str, Any]]:
    if end <= start:
        raise ProofError("bad window")
    return [insn_row(i) for i in ds.decode(pe.bytes(start, end - start), start)]


def helper_xrefs(pe: PE, ds: Disasm) -> dict[str, list[dict[str, Any]]]:
    s = pe.text
    text = pe.data[s["rawOffset"]:s["rawOffset"] + s["rawSize"]]
    rows = ds.decode(text, s["va"])
    out: dict[str, list[dict[str, Any]]] = {k: [] for k in HELPERS}
    by_target = {v: k for k, v in HELPERS.items()}
    for insn in rows:
        if insn.mnemonic != "call" or not insn.operands or insn.operands[0].type != X86_OP_IMM:
            continue
        target = insn.operands[0].imm & 0xffffffff
        name = by_target.get(target)
        if name is not None:
            out[name].append(insn_row(insn))
    return out


def summarize_window(rows: list[dict[str, Any]], anchor: int) -> dict[str, Any]:
    calls = [r for r in rows if r["mnemonic"] == "call"]
    branches = [r for r in rows if r["mnemonic"].startswith("j")]
    ff = [r for r in rows if "0xff" in r["opStr"].lower() or "255" in r["opStr"].lower()]
    # XModel field references known from exact retail root proof. This is merely
    # a locator count; semantic use is not promoted here.
    xmodel_offsets = ["+ 4]", "+ 5]", "+ 0xc]", "+ 0x10]", "+ 0x14]"]
    likely_xmodel = [r for r in rows if any(tok in r["opStr"].lower() for tok in xmodel_offsets)]
    return {
        "instructionCount": len(rows),
        "anchorHex": f"0x{anchor:08x}",
        "callCount": len(calls),
        "branchCount": len(branches),
        "ffImmediateReferences": ff,
        "knownXModelOffsetReferences": likely_xmodel,
        "directCalls": calls,
    }


def write_text(path: Path, windows: dict[str, list[dict[str, Any]]], xrefs: dict[str, list[dict[str, Any]]]) -> None:
    lines: list[str] = []
    for name, rows in windows.items():
        start, end = WINDOWS[name]
        lines.append(f"=== {name} 0x{start:08x}..0x{end:08x} ===")
        for r in rows:
            tgt = f" -> {r['target']}" if "target" in r else ""
            lines.append(f"{r['va']}  {r['bytes']:<24} {r['mnemonic']:<8} {r['opStr']}{tgt}")
        lines.append("")
    lines.append("=== exact helper xrefs in .text ===")
    for name, rows in xrefs.items():
        lines.append(f"{name} {HELPERS[name]:#010x}: {len(rows)} call xrefs")
        for r in rows:
            lines.append(f"  {r['va']} {r['mnemonic']} {r['opStr']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--disasm-out", type=Path, required=True)
    args = ap.parse_args()

    pe = PE(args.exe)
    ds = Disasm()

    # Re-pin the already-authoritative sentinel bytes so this census cannot
    # accidentally drift to a different code path in a hash-collision fantasy
    # or a future edited script with the same filename.
    if pe.bytes(0x00422A6F, 6).hex() != "81faff000000":
        raise ProofError("consumer A sentinel drift")
    if pe.bytes(0x005C6948, 6).hex() != "81f9ff000000":
        raise ProofError("consumer B sentinel drift")

    windows = {name: disasm_window(pe, ds, *WINDOWS[name]) for name in WINDOWS}
    xrefs = helper_xrefs(pe, ds)
    if not xrefs["rootNoParent"] or not xrefs["rootWithParent"] or not xrefs["nonRoot"]:
        raise ProofError(f"missing exact helper xrefs: { {k: len(v) for k,v in xrefs.items()} }")

    summaries = {
        name: summarize_window(rows, CONSUMERS[name])
        for name, rows in windows.items()
    }
    doc = {
        "format": "t6-retail-dobj-multixmodel-census-v1",
        "retailExecutable": {
            "bytes": len(pe.data),
            "sha256": hashlib.sha256(pe.data).hexdigest(),
            "imageBaseHex": "0x00400000",
        },
        "authorityRoots": {
            "knownHelpers": {k: f"0x{v:08x}" for k, v in HELPERS.items()},
            "knownConsumers": {k: f"0x{v:08x}" for k, v in CONSUMERS.items()},
            "consumerSentinelsRepinned": True,
        },
        "helperXrefs": xrefs,
        "windows": {
            name: {
                "startHex": f"0x{WINDOWS[name][0]:08x}",
                "endHex": f"0x{WINDOWS[name][1]:08x}",
                "sha256": hashlib.sha256(pe.bytes(WINDOWS[name][0], WINDOWS[name][1] - WINDOWS[name][0])).hexdigest(),
                "summary": summaries[name],
            }
            for name in WINDOWS
        },
        "proofBoundary": {
            "exactRetailBytes": True,
            "dobjRootConsumerAnchorsRepinned": True,
            "multixmodelAssemblyClosed": False,
            "note": "Locator census only. No modelParent producer, model-order, duplicate-bone, or aggregate bone-base semantic is promoted until a subsequent verifier binds exact instructions and control/data flow.",
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.disasm_out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_text(args.disasm_out, windows, xrefs)
    print(json.dumps({
        "format": doc["format"],
        "helperXrefCounts": {k: len(v) for k, v in xrefs.items()},
        "consumerA": summaries["consumerA"],
        "consumerB": summaries["consumerB"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

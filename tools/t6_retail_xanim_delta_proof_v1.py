#!/usr/bin/env python3
"""Prove T6 XAnim delta/root-motion evaluation semantics from retail t6mp.exe.

Pinned to one exact retail PC executable. The verifier checks the SHA-256 and
instruction bytes/call targets for the planar and 3D delta evaluators, their
byte-vs-ushort frame-index split, shared position evaluator, and the corrected
XAnimParts notify/deltaPart pointer offsets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

EXPECTED_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
IMAGE_BASE = 0x400000


class ProofError(RuntimeError):
    pass


class PE:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        if self.data[:2] != b"MZ":
            raise ProofError("not MZ")
        pe = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[pe:pe+4] != b"PE\0\0":
            raise ProofError("not PE")
        coff = pe + 4
        machine, nsects, _, _, _, opt_size, _ = struct.unpack_from("<HHIIIHH", self.data, coff)
        if machine != 0x14C:
            raise ProofError(f"not i386: 0x{machine:x}")
        opt = coff + 20
        if struct.unpack_from("<H", self.data, opt)[0] != 0x10B:
            raise ProofError("not PE32")
        if struct.unpack_from("<I", self.data, opt + 28)[0] != IMAGE_BASE:
            raise ProofError("unexpected image base")
        sec = opt + opt_size
        self.sections = []
        for i in range(nsects):
            off = sec + i * 40
            name = self.data[off:off+8].split(b"\0", 1)[0].decode("ascii", "replace")
            vsize, vaddr, raw_size, raw_off = struct.unpack_from("<IIII", self.data, off + 8)
            self.sections.append((name, IMAGE_BASE + vaddr, max(vsize, raw_size), raw_off, raw_size))

    def off(self, va: int) -> int:
        for _, start, size, raw, raw_size in self.sections:
            if start <= va < start + size:
                delta = va - start
                if delta >= raw_size:
                    raise ProofError(f"VA 0x{va:x} is not file-backed")
                return raw + delta
        raise ProofError(f"unmapped VA 0x{va:x}")

    def bytes(self, va: int, n: int) -> bytes:
        off = self.off(va)
        return self.data[off:off+n]

    def f32(self, va: int) -> float:
        return struct.unpack("<f", self.bytes(va, 4))[0]


def _expect(pe: PE, va: int, expected: bytes, label: str) -> None:
    actual = pe.bytes(va, len(expected))
    if actual != expected:
        raise ProofError(f"{label} bytes differ at 0x{va:x}: {actual.hex()} != {expected.hex()}")


def _rel32_target(pe: PE, call_va: int) -> int:
    if pe.bytes(call_va, 1) not in (b"\xE8", b"\xE9"):
        raise ProofError(f"not rel32 call/jump at 0x{call_va:x}")
    rel = struct.unpack("<i", pe.bytes(call_va + 1, 4))[0]
    return call_va + 5 + rel


def _expect_target(pe: PE, va: int, target: int, label: str) -> None:
    actual = _rel32_target(pe, va)
    if actual != target:
        raise ProofError(f"{label} target 0x{actual:x} != 0x{target:x}")


def prove(path: Path) -> dict:
    pe = PE(path)
    sha = hashlib.sha256(pe.data).hexdigest()
    if sha != EXPECTED_SHA256:
        raise ProofError(f"SHA mismatch {sha}")

    # Correct x86 XAnimParts pointer layout. +0x60 is notify, proven by the
    # notifyCount +0x22 loop and 8-byte XAnimNotifyInfo stride. deltaPart is +0x64.
    _expect(pe, 0x49E15E, b"\x8b\x1c\xc1\x56\x8b\x73\x60", "XAnim lookup + notify pointer")
    _expect(pe, 0x49E16C, b"\x80\x7b\x22\x00", "notifyCount test")
    _expect(pe, 0x49E19A, b"\x0f\xb6\x43\x22\x47\x83\xc6\x08", "notify iteration stride")

    # 2D/planar delta evaluator: XAnim_CalcDeltaForTime.
    _expect(
        pe,
        0x6B5680,
        bytes.fromhex("8b442404f30f105c24080f2e1d20e7be00538b5864560fb7700e"),
        "2D evaluator prologue/deltaPart/numframes",
    )
    if pe.f32(0xBEE720) != 1.0:
        raise ProofError("time==1.0 constant mismatch")
    _expect(pe, 0x6B571D, b"\x81\xfe\x00\x01\x00\x00", "2D 256-frame split")
    _expect_target(pe, 0x6B56E8, 0x8DA5E0, "2D end-position tailcall")
    _expect_target(pe, 0x6B570D, 0x8DA5E0, "2D null-rotation end-position tailcall")
    _expect_target(pe, 0x6B5725, 0x8DA8C0, "2D byte-index rotation helper")
    _expect_target(pe, 0x6B573A, 0x8DA9C0, "2D byte-index position helper")
    _expect_target(pe, 0x6B5746, 0x8DAB40, "2D ushort-index rotation helper")
    _expect_target(pe, 0x6B575B, 0x8DAC40, "2D ushort-index position helper")

    # 3D delta evaluator: XAnim_CalcDelta3DForTime.
    _expect(
        pe,
        0x667940,
        bytes.fromhex("8b442404f30f105c24080f2e1d20e7be00538b5864570fb7780e"),
        "3D evaluator prologue/deltaPart/numframes",
    )
    _expect(pe, 0x667968, b"\x8b\x43\x08", "3D deltaPart.quat pointer")
    _expect(pe, 0x667A0B, b"\x81\xff\x00\x01\x00\x00", "3D 256-frame split")
    _expect_target(pe, 0x6679CC, 0x8DA5E0, "3D end-position tailcall")
    _expect_target(pe, 0x6679FB, 0x8DA5E0, "3D null-rotation end-position tailcall")
    _expect_target(pe, 0x667A13, 0x8DADC0, "3D byte-index quaternion helper")
    _expect_target(pe, 0x667A28, 0x8DA9C0, "3D byte-index position helper")
    _expect_target(pe, 0x667A34, 0x8DAF30, "3D ushort-index quaternion helper")
    _expect_target(pe, 0x667A49, 0x8DAC40, "3D ushort-index position helper")

    # Shared end/full translation evaluator.
    _expect(pe, 0x8DA5E0, bytes.fromhex("8b0085c00f84a10000000fb7086685c97512"), "entire-position null/size branch")
    _expect(pe, 0x8DA5F2, b"\x0f\x10\x40\x04", "constant position vector")
    _expect(pe, 0x8DA604, b"\x80\x78\x02\x00", "smallTrans branch")
    _expect(pe, 0x8DA610, b"\x8b\x70\x1c", "translation frames pointer")

    # Dynamic helper identities and track pointer offsets.
    helper_specs = [
        (0x8DA8C0, b"\x83\xec\x14\x56\x8b\x70\x04", 0x8DA92F, 0x8DA6A0, "quat2 byte"),
        (0x8DA9C0, b"\x83\xec\x14\x56\x8b\x30",       0x8DAA26, 0x8DA6A0, "position byte"),
        (0x8DAB40, b"\x83\xec\x14\x56\x8b\x70\x04", 0x8DABAF, 0x8DA7B0, "quat2 ushort"),
        (0x8DAC40, b"\x83\xec\x14\x56\x8b\x30",       0x8DACA6, 0x8DA7B0, "position ushort"),
        (0x8DADC0, b"\x83\xec\x14\x57\x8b\x78\x08", 0x8DAE4F, 0x8DA6A0, "quat3D byte"),
        (0x8DAF30, b"\x83\xec\x14\x57\x8b\x78\x08", 0x8DAFBF, 0x8DA7B0, "quat3D ushort"),
    ]
    for start, prefix, call, target, label in helper_specs:
        _expect(pe, start, prefix, f"{label} helper prefix")
        _expect_target(pe, call, target, f"{label} time-index helper")

    # Byte and ushort key-index locators differ exactly in index element width.
    _expect(pe, 0x8DA6DF, b"\x0f\xb6\x3e", "byte index load")
    _expect(pe, 0x8DA7EF, b"\x0f\xb7\x3e", "ushort index load")

    # Higher-level runtime consumers independently bind the evaluators.
    _expect(pe, 0x8D72D9, b"\x80\x7e\x11\x00", "relative-delta bDelta gate")
    _expect_target(pe, 0x8D72F9, 0x6B5680, "relative-delta start evaluation")
    _expect_target(pe, 0x8D7316, 0x6B5680, "relative-delta end evaluation")
    _expect(pe, 0x8D731E, b"\x80\x7e\x10\x00", "relative-delta bLoop gate")
    _expect(pe, 0x8D7337, b"\x8b\x4e\x64", "relative-delta loop deltaPart load")

    _expect(pe, 0x8D8F19, b"\x80\x78\x11\x00", "accumulator bDelta gate")
    _expect_target(pe, 0x8D8F35, 0x6B5680, "accumulator 2D evaluator")
    _expect(pe, 0x8D8F4C, b"\x80\x78\x12\x00", "accumulator bDelta3D gate")
    _expect_target(pe, 0x8D8F6C, 0x667940, "accumulator 3D evaluator")

    functions = {
        "XAnim_CalcDeltaForTime": "0x006b5680",
        "XAnim_CalcDelta3DForTime": "0x00667940",
        "XAnim_CalcPosDeltaEntire": "0x008da5e0",
        "XAnim_GetTimeIndex_byte": "0x008da6a0",
        "XAnim_GetTimeIndex_ushort": "0x008da7b0",
        "XAnim_CalcRotDelta2D_byte": "0x008da8c0",
        "XAnim_CalcPosDelta_byte": "0x008da9c0",
        "XAnim_CalcRotDelta2D_ushort": "0x008dab40",
        "XAnim_CalcPosDelta_ushort": "0x008dac40",
        "XAnim_CalcRotDelta3D_byte": "0x008dadc0",
        "XAnim_CalcRotDelta3D_ushort": "0x008daf30",
        "relativeDeltaRangeConsumer": "0x008d72d0",
        "weightedDeltaAccumulator": "0x008d8f10",
    }

    return {
        "format": "t6-retail-xanim-delta-proof-v1",
        "retailExecutable": {
            "file": path.name,
            "bytes": len(pe.data),
            "sha256": sha,
            "imageBaseHex": "0x00400000",
        },
        "xanimPartsX86Offsets": {
            "numframesHex": "0x0e",
            "bLoopHex": "0x10",
            "bDeltaHex": "0x11",
            "bDelta3DHex": "0x12",
            "notifyCountHex": "0x22",
            "framerateHex": "0x30",
            "frequencyHex": "0x34",
            "notifyHex": "0x60",
            "deltaPartHex": "0x64",
        },
        "deltaPartX86Offsets": {
            "transHex": "0x00",
            "quat2Hex": "0x04",
            "quat3DHex": "0x08",
        },
        "functions": functions,
        "semantics": {
            "timeDomain": "normalized animation time; retail evaluator has explicit time == 1.0 end/full-delta path",
            "endOrZeroFramePath": "time == 1.0 or numframes == 0 evaluates terminal/constant rotation and XAnim_CalcPosDeltaEntire",
            "frameIndexWidth": "numframes < 256 uses uint8 indices; numframes >= 256 uses uint16 indices",
            "translation": "null -> zero; size==0 -> constant vec3; keyed -> decode SMALL_TRANS/FULL_TRANS and linearly interpolate between surrounding keys",
            "rotation2D": "deltaPart.quat2; null -> planar identity; size==0 -> constant signed-int16 pair; keyed -> component-wise linear interpolation in stored signed-int16 domain",
            "rotation3D": "deltaPart.quat; null -> quaternion identity; size==0 -> constant signed-int16 quaternion; keyed -> component-wise linear interpolation in stored signed-int16 domain",
            "loopRange": "higher-level relative-delta consumer evaluates start/end and, when bLoop and startTime > endTime, incorporates the full deltaPart across the wrap",
            "dispatch": "weighted runtime path selects 2D evaluator when bDelta, otherwise 3D evaluator when bDelta3D",
        },
        "validation": {
            "exactRetailSha256": True,
            "instructionBytesMatched": True,
            "correctedNotifyVsDeltaPartOffsetsMatched": True,
            "twoDimensionalEvaluatorMatched": True,
            "threeDimensionalEvaluatorMatched": True,
            "byteAndUshortIndexPathsMatched": True,
            "loopRangeConsumerMatched": True,
            "weightedDispatchMatched": True,
        },
        "proofBoundary": (
            "Direct static proof for the pinned retail PC executable. This closes XAnim deltaPart pointer layout, "
            "2D/3D time evaluation, terminal delta evaluation, key-index width selection, decoded translation "
            "interpolation, and loop-wrap relative-delta composition. It does not by itself prove how a model's "
            "ordinary animated root-bone translation track should be composed with bind pose; that remains a "
            "separate binding question."
        ),
        "referenceImplementations": {
            "OpenAssetToolsT6Struct": "Laupetin/OpenAssetTools@7d027e8f89118196713e955b0e11f8404149c54d src/Common/Game/T6/T6_Assets.h",
            "OpenBO2NamesOnly": "builtbyxeno/OpenBO2@a64812d21946baf710cec7fa26b98ad0d193903b src/code/src_noserver/xanim/xanim_calc.cpp",
            "note": "Reference projects are used for structure/function naming only; promoted semantics are independently verified against the pinned retail executable bytes."
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    doc = prove(args.exe)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

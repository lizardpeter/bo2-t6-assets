#!/usr/bin/env python3
"""Fail-closed proof of the T6 PC dedicated-server sound parameter producer queues.

Closes only producer/control-side ownership that survives in the dedicated
server. The retail sample mixer consumer/DSP is deliberately out of scope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

FORMAT = "t6-pc-server-sound-param-queue-runtime-proof-v1"
EXE_BYTES = 13_711_872
EXE_SHA256 = "f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d"
MAP_BYTES = 9_213_148
MAP_SHA256 = "34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf"
IMAGE_BASE = 0x00400000

RANGES = {
    "SD_PreUpdate": (0x008B90E0, 0x008B94C0, "492e581a4db0b4c346b86b5455808b29789299450f7ea42e415e06630a747db5"),
    "SD_UpdateVoice": (0x008B9860, 0x008B98F0, "3809e0e45094a27dd616469ce5f50a1a5823807ab1bb8b9ca99d96328c33d1dd"),
    "SD_MixSetParam": (0x008B9C80, 0x008B9D10, "43b9ac292aaedd16e1adf3f5f4f05df82dd137a0d339203f5de3203a71a7f58d"),
    "SD_VoiceSetParam": (0x008BA560, 0x008BA610, "f741d01f4881b626f5aa14800ac7487edd8f5c0a17810690035fc4ece72b3e3a"),
}

SYMBOLS = {
    0x008B90E0: "SD_PreUpdate",
    0x008B9860: "SD_UpdateVoice",
    0x008B8A50: "SD_GetVoiceParam",
    0x008BA560: "SD_VoiceSetParam",
    0x008BA620: "SD_VoiceStart",
    0x008BA610: "SD_VoiceHasData",
    0x008BA6C0: "SD_VoiceStarted",
    0x008BA700: "SD_VoiceDone",
    0x008BA710: "SD_VoicePosition",
    0x008BA150: "SD_VoiceParamFree",
    0x008B9B70: "SD_MixParamAllocate",
    0x008B8450: "SD_GetMixParam",
    0x008B9C80: "SD_MixSetParam",
    0x008B9C30: "SD_MixParamFree",
    0x008BA010: "SD_StreamDevhost",
    0x008B02B0: "SND_StopVoice",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def parse_pe(raw: bytes):
    require(raw[:2] == b"MZ", "not MZ")
    pe = struct.unpack_from("<I", raw, 0x3C)[0]
    require(raw[pe:pe+4] == b"PE\0\0", "not PE")
    coff = pe + 4
    machine, nsects, _, _, _, opt_size, _ = struct.unpack_from("<HHIIIHH", raw, coff)
    require(machine == 0x14C, "not x86 PE")
    opt = coff + 20
    require(struct.unpack_from("<I", raw, opt + 28)[0] == IMAGE_BASE, "image base changed")
    sections = []
    st = opt + opt_size
    for i in range(nsects):
        o = st + i * 40
        _, rva, rs, ro = struct.unpack_from("<IIII", raw, o + 8)
        sections.append((IMAGE_BASE + rva, rs, ro))
    def off(va: int) -> int:
        for base, rs, ro in sections:
            if base <= va < base + rs:
                return ro + va - base
        raise RuntimeError(f"unbacked VA 0x{va:08X}")
    def at(va: int, n: int) -> bytes:
        o = off(va)
        return raw[o:o+n]
    return at


def call_target(at, va: int) -> int:
    b = at(va, 5)
    require(b[0] == 0xE8, f"expected CALL at 0x{va:08X}")
    rel = struct.unpack_from("<i", b, 1)[0]
    return (va + 5 + rel) & 0xFFFFFFFF


def map_lines_for_va(text: str, va: int) -> list[str]:
    token = f"{va:08x}"
    return [ln for ln in text.splitlines() if re.search(rf"(?i)(?<![0-9a-f]){token}(?![0-9a-f])", ln)]


def prove(exe: bytes, map_text: str) -> dict:
    map_raw = map_text.encode("ascii")
    require(len(exe) == EXE_BYTES and sha256(exe) == EXE_SHA256, "EXE identity mismatch")
    require(len(map_raw) == MAP_BYTES and sha256(map_raw) == MAP_SHA256, "MAP identity mismatch")
    at = parse_pe(exe)

    symbol_evidence = {}
    for va, name in SYMBOLS.items():
        lines = map_lines_for_va(map_text, va)
        require(lines and any(name in ln for ln in lines), f"missing exact MAP symbol {name} @ 0x{va:08X}")
        symbol_evidence[f"0x{va:08X}"] = lines[:4]

    range_evidence = {}
    for name, (start, end, digest) in RANGES.items():
        raw = at(start, end - start)
        actual = sha256(raw)
        require(actual == digest, f"{name} exact range hash changed: {actual}")
        range_evidence[name] = {
            "startVa": f"0x{start:08X}",
            "endExclusiveVa": f"0x{end:08X}",
            "bytes": end - start,
            "sha256": actual,
        }

    # SD_PreUpdate: exact high-level slot loop = 0x7700 bytes / 0x1C0 = 68 slots.
    require(at(0x008B90FB, 5) == bytes.fromhex("33f633ff90"), "PreUpdate loop initialization changed")
    require(at(0x008B9100, 8) == bytes.fromhex("833cb500a9e50700"), "PreUpdate active-slot table changed")
    require(at(0x008B910E, 7) == bytes.fromhex("8b1cb580780801"), "PreUpdate driver-voice table changed")
    require(call_target(at, 0x008B9116) == 0x008BA700, "PreUpdate no longer checks SD_VoiceDone")
    require(call_target(at, 0x008B9123) == 0x008B02B0, "PreUpdate no longer stops done SND voice")
    require(call_target(at, 0x008B9131) == 0x008BA6C0, "PreUpdate no longer checks SD_VoiceStarted")
    require(call_target(at, 0x008B9142) == 0x008BA610, "PreUpdate no longer checks SD_VoiceHasData")
    require(call_target(at, 0x008B91D6) == 0x008B8A50, "PreUpdate no longer builds voice param")
    require(call_target(at, 0x008B91DD) == 0x008BA620, "PreUpdate no longer starts driver voice")
    require(at(0x008B9214, 13) == bytes.fromhex("81c7c00100004681ff00770000"), "PreUpdate loop stride/span changed")
    require(call_target(at, 0x008B9227) == 0x008B9B70, "PreUpdate mix-param allocation changed")
    require(call_target(at, 0x008B922D) == 0x008B8450, "PreUpdate mix-param population changed")
    require(call_target(at, 0x008B9233) == 0x008B9C80, "PreUpdate mix-param publication changed")
    require(call_target(at, 0x008B9238) == 0x008BA010, "PreUpdate stream devhost tail changed")

    # SD_UpdateVoice: resolve driver voice, update 64-bit public position, then enqueue a new param iff started.
    require(at(0x008B9867, 8) == bytes.fromhex("833cb58078080100"), "UpdateVoice driver table assertion changed")
    require(call_target(at, 0x008B989C) == 0x008BA710, "UpdateVoice no longer reads driver position")
    require(at(0x008B98A3, 18) == bytes.fromhex("69c9c00100008981a833e5078991ac33e507"), "UpdateVoice high-level position publication changed")
    require(call_target(at, 0x008B98BD) == 0x008BA6C0, "UpdateVoice no longer checks started")
    require(call_target(at, 0x008B98CB) == 0x008B8A50, "UpdateVoice no longer builds replacement param")
    require(call_target(at, 0x008B98D9) == 0x008BA560, "UpdateVoice no longer queues replacement param")

    # SD_VoiceSetParam: param state==1; active voiceParam must exist; atomic replacement is on voiceNewParam.
    require(at(0x008BA582, 3) == bytes.fromhex("833b01"), "VoiceSetParam incoming state invariant changed")
    require(at(0x008BA5AB, 8) == bytes.fromhex("833cb5000be60000"), "VoiceSetParam active voiceParam invariant changed")
    require(at(0x008BA5D8, 7) == bytes.fromhex("8d3cb50009e600"), "VoiceSetParam pending voiceNewParam target changed")
    require(at(0x008BA5E0, 15) == bytes.fromhex("8b37565357ff15f8c1b8003bc675f1"), "VoiceSetParam atomic replacement loop changed")
    require(call_target(at, 0x008BA5F4) == 0x008BA150, "VoiceSetParam no longer frees superseded pending param")

    # Global mix-master params are a separate atomic pointer, not the per-voice queue.
    require(at(0x008B9C9D, 4) == bytes.fromhex("837f7001"), "MixSetParam incoming state invariant changed")
    require(at(0x008B9CD0, 19) == bytes.fromhex("8b350080070156576800800701ffd33bc675ed"), "MixSetParam atomic pointer replacement changed")
    require(call_target(at, 0x008B9CE8) == 0x008B9C30, "MixSetParam no longer frees superseded mix param")

    high_level_stride = 0x1C0
    high_level_span = 0x7700
    require(high_level_span % high_level_stride == 0, "high-level slot population is not integral")
    high_level_count = high_level_span // high_level_stride
    require(high_level_count == 68, "high-level slot population changed")

    return {
        "format": FORMAT,
        "authority": "exact SHA-pinned T6 PC dedicated-server EXE + linker MAP",
        "identity": {
            "exeBytes": len(exe), "exeSha256": sha256(exe),
            "mapBytes": len(map_raw), "mapSha256": sha256(map_raw),
        },
        "ranges": range_evidence,
        "highLevelVoicePopulation": {
            "slotCount": high_level_count,
            "slotStrideBytes": high_level_stride,
            "loopSpanBytes": high_level_span,
            "activeSlotTableBase": "0x07E5A900",
            "driverVoicePointerTableBase": "0x01087880",
            "positionWriteOffsetsWithinHighLevelSlot": ["0x1A8", "0x1AC"],
        },
        "producerQueue": {
            "preUpdateVa": "0x008B90E0",
            "updateVoiceVa": "0x008B9860",
            "voiceSetParamVa": "0x008BA560",
            "voiceParamActiveBase": "0x00E60B00",
            "voiceNewParamPendingBase": "0x00E60900",
            "incomingVoiceParamRequiredState": 1,
            "updateRule": "for a started driver voice, SD_UpdateVoice builds SD_GetVoiceParam(index) and SD_VoiceSetParam atomically replaces voiceNewParam[index]",
            "supersededPendingRule": "a replaced non-null voiceNewParam is immediately returned through SD_VoiceParamFree",
            "startRule": "SD_PreUpdate obtains SD_GetVoiceParam(index) and calls SD_VoiceStart only after the active/not-done/not-started/has-data path and remaining readiness gates pass",
        },
        "globalMixParam": {
            "mixSetParamVa": "0x008B9C80",
            "pendingPointerAddress": "0x01078000",
            "incomingStateOffset": "0x70",
            "incomingStateRequiredValue": 1,
            "supersededPointerFreeVa": "0x008B9C30",
            "separateFromPerVoiceQueue": true,
        },
        "mapSymbolEvidence": symbol_evidence,
        "proofBoundary": (
            "Closes producer/control-side parameter publication surviving in the dedicated server. "
            "It does not identify the stripped per-voice consumer/mixer DSP, resampling, pan law, bus mixing, "
            "speaker matrix, or retail-client address equivalence. Atomic import 0x00B8C1F8 is treated only by "
            "its compare-and-retry machine behavior here and is not overnamed."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", type=Path, required=True)
    ap.add_argument("--map", dest="map_path", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    with args.map_path.open("r", encoding="ascii", newline="") as f:
        map_text = f.read()
    result = prove(args.exe.read_bytes(), map_text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail-closed proof for the T6 PC-server decoder/source/voice handoff.

This deliberately stops before claiming mixer DSP or retail-client equivalence.
It proves the exact SHA-pinned dedicated-server path from the already-closed
physical format byte through decoder/source allocation and voice publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

FORMAT = "t6-pc-server-sound-voice-pcm-runtime-proof-v1"
EXPECTED_EXE_BYTES = 13_711_872
EXPECTED_EXE_SHA256 = "f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d"
EXPECTED_MAP_BYTES = 9_213_148
EXPECTED_MAP_SHA256 = "34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf"
IMAGE_BASE = 0x00400000

SYMBOLS = {
    0x008B9A10: "SD_DecoderAllocate",
    0x008B9B20: "SD_DecoderAllocate",
    0x008B9D10: "SD_SourceInitStream",
    0x008B9E20: "SD_StreamAllocate",
    0x008BA1C0: "SD_VoiceAllocate",
    0x008BA310: "SD_VoiceAllocateRam",
    0x008BA4D0: "SD_VoiceAllocateStream",
    0x008BA560: "SD_VoiceSetParam",
    0x008BA610: "SD_VoiceHasData",
    0x008BA620: "SD_VoiceStart",
    0x008BA6C0: "SD_VoiceStarted",
    0x008BA700: "SD_VoiceDone",
    0x008BA710: "SD_VoicePosition",
    0x008BA8B0: "SD_OutputForceWakeup",
}

VOICE_START_BYTES = 0x9F
VOICE_START_SHA256 = "6d65d5ddfe6b86078c815997c5063e14d92c8d2416be002ec434fe0d7f723053"


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def parse_pe(raw: bytes):
    require(raw[:2] == b"MZ", "EXE is not PE/MZ")
    pe = struct.unpack_from("<I", raw, 0x3C)[0]
    require(raw[pe : pe + 4] == b"PE\0\0", "missing PE signature")
    coff = pe + 4
    machine, nsects, _, _, _, opt_size, _ = struct.unpack_from("<HHIIIHH", raw, coff)
    require(machine == 0x14C, f"unexpected PE machine 0x{machine:x}")
    opt = coff + 20
    require(struct.unpack_from("<I", raw, opt + 28)[0] == IMAGE_BASE, "unexpected image base")
    sections = []
    st = opt + opt_size
    for i in range(nsects):
        o = st + i * 40
        name = raw[o : o + 8].split(b"\0", 1)[0].decode("ascii", "replace")
        vs, rva, rs, ro = struct.unpack_from("<IIII", raw, o + 8)
        sections.append((name, IMAGE_BASE + rva, vs, rs, ro))

    def va_off(va: int) -> int:
        for _, base, _, rs, ro in sections:
            if base <= va < base + rs:
                return ro + va - base
        raise RuntimeError(f"VA is not backed by raw PE bytes: 0x{va:08X}")

    def at(va: int, n: int) -> bytes:
        o = va_off(va)
        return raw[o : o + n]

    return at


def direct_call_target(at, va: int) -> int:
    b = at(va, 5)
    require(b[0] == 0xE8, f"expected near CALL at 0x{va:08X}, got {b.hex()}")
    rel = struct.unpack_from("<i", b, 1)[0]
    return (va + 5 + rel) & 0xFFFFFFFF


def map_lines_for_va(text: str, va: int) -> list[str]:
    tok = f"{va:08x}"
    return [ln for ln in text.splitlines() if re.search(rf"(?i)(?<![0-9a-f]){tok}(?![0-9a-f])", ln)]


def prove(exe: bytes, map_text: str) -> dict:
    require(len(exe) == EXPECTED_EXE_BYTES, f"EXE bytes changed: {len(exe)}")
    require(sha256(exe) == EXPECTED_EXE_SHA256, "EXE SHA-256 mismatch")
    map_raw = map_text.encode("ascii")
    require(len(map_raw) == EXPECTED_MAP_BYTES, f"MAP bytes changed: {len(map_raw)}")
    require(sha256(map_raw) == EXPECTED_MAP_SHA256, "MAP SHA-256 mismatch")
    at = parse_pe(exe)

    symbol_evidence = {}
    for va, name in SYMBOLS.items():
        lines = map_lines_for_va(map_text, va)
        require(lines, f"MAP has no exact line for 0x{va:08X}")
        require(any(name in ln for ln in lines), f"MAP 0x{va:08X} does not name {name}")
        symbol_evidence[f"0x{va:08X}"] = lines[:8]

    # Two-argument decoder wrapper: entry +0x13, accepted codes 0/8 only.
    require(at(0x008B9B23, 14) == bytes.fromhex("8b4d0c8a411384c074223c087417"), "decoder wrapper format dispatch changed")
    require(at(0x008B9B48, 5) == bytes.fromhex("b8643ede00"), "format-8 decoder-instance pool changed")
    require(at(0x008B9B4F, 5) == bytes.fromhex("b85430de00"), "format-0 decoder-instance pool changed")
    require(at(0x008B9B5A, 5) == bytes.fromhex("b864000000"), "decoder wrapper 0x64 immediate changed")
    require(direct_call_target(at, 0x008B9B5F) == 0x008B9A10, "decoder wrapper no longer calls generic SD_DecoderAllocate")
    require(at(0x008B9B64, 5) == bytes.fromhex("83c40c5dc3"), "decoder wrapper return boundary changed")

    # Stream source initialization: entry +0x11 must be 1 or 2; stream stored at source +0x18.
    require(at(0x008B9D14, 14) == bytes.fromhex("8b75108a46113c0174283c027424"), "source stream-class checks changed")
    require(direct_call_target(at, 0x008B9D57) == 0x008B9E20, "SD_SourceInitStream no longer calls SD_StreamAllocate")
    require(at(0x008B9D5C, 9) == bytes.fromhex("8b4d0883c414894118"), "source stream-pointer publication changed")
    require(at(0x008B9D69, 15) == bytes.fromhex("b80100000089412889412089412c"), "source stream-allocation failure flags changed")
    require(at(0x008B9D7A, 35) == bytes.fromhex("33d2c7412000000000385612c74128000000000f95c2c7412c000000005e8951245dc3"), "source stream success flags changed")

    # Voice pool allocation: 128 x 0x180 and output wakeup retry when exhausted.
    require(at(0x008BA1D2, 5) == bytes.fromhex("be0071e500"), "voice pool base changed")
    require(at(0x008BA1F6, 6) == bytes.fromhex("81c180010000"), "voice scan byte stride changed")
    require(at(0x008BA1FD, 6) == bytes.fromhex("81c680010000"), "voice pointer stride changed")
    require(at(0x008BA203, 6) == bytes.fromhex("81f900960000"), "voice pool span changed")
    require(direct_call_target(at, 0x008BA20B) == 0x008BA8B0, "voice exhaustion no longer wakes output")
    require(at(0x008BA213, 8) == bytes.fromhex("408945fc83f80472"), "voice wakeup retry counter changed")

    # Start publishes the exact voice-param pointer after both per-voice tables are empty.
    voice_start = at(0x008BA620, VOICE_START_BYTES)
    require(sha256(voice_start) == VOICE_START_SHA256, "SD_VoiceStart exact function bytes changed")
    require(at(0x008BA63E, 8) == bytes.fromhex("833cb50009e60000"), "voiceNewParam assertion table changed")
    require(at(0x008BA66B, 8) == bytes.fromhex("833cb5000be60000"), "voiceParam assertion table changed")
    for store_va in (0x008BA69B, 0x008BA6A8, 0x008BA6B5):
        b = at(store_va, 7)
        require(b[-4:] == bytes.fromhex("000be600"), f"voiceParam publication target changed at 0x{store_va:08X}")

    # Started == state 2 && voiceParam[index] != null.
    require(at(0x008BA6C3, 9) == bytes.fromhex("8b45088338027529"), "SD_VoiceStarted state check changed")
    require(at(0x008BA6E3, 8) == bytes.fromhex("833c85000be60000"), "SD_VoiceStarted voiceParam check changed")
    require(at(0x008BA6ED, 7) == bytes.fromhex("b8010000005dc3"), "SD_VoiceStarted true return changed")

    # HasData, Done, Position are fixed field accessors.
    require(at(0x008BA610, 16) == bytes.fromhex("558bec8b4d0833c03941080f95c05dc3"), "SD_VoiceHasData accessor changed")
    require(at(0x008BA700, 16) == bytes.fromhex("558bec8b4d0833c03941040f95c05dc3"), "SD_VoiceDone accessor changed")
    require(at(0x008BA710, 14) == bytes.fromhex("558bec8b4d088b41108b51145dc3"), "SD_VoicePosition accessor changed")

    return {
        "format": FORMAT,
        "authority": "exact SHA-pinned T6 PC dedicated-server EXE + linker MAP",
        "identity": {
            "exeBytes": len(exe),
            "exeSha256": sha256(exe),
            "mapBytes": len(map_raw),
            "mapSha256": sha256(map_raw),
        },
        "decoderHandoff": {
            "physicalFormatOffset": "SndAssetBankEntry+0x13",
            "acceptedPcFormats": [0, 8],
            "format0DecoderPoolBase": "0x00DE3054",
            "format8DecoderPoolBase": "0x00DE3E64",
            "genericDecoderAllocateVa": "0x008B9A10",
            "wrapperDecoderAllocateVa": "0x008B9B20",
        },
        "streamSource": {
            "sourceInitStreamVa": "0x008B9D10",
            "acceptedEntryByte11Values": [1, 2],
            "streamAllocateVa": "0x008B9E20",
            "sourceStreamPointerOffset": "0x18",
            "entryByte12CopiedAsBooleanToSourceOffset": "0x24",
        },
        "voiceRuntime": {
            "voicePoolBase": "0x00E57100",
            "voiceBytes": 0x180,
            "voiceCount": 128,
            "voicePoolSpanBytes": 0x9600,
            "voiceNewParamBase": "0x00E60900",
            "voiceParamBase": "0x00E60B00",
            "outputForceWakeupVa": "0x008BA8B0",
            "allocationWakeupRetryCount": 4,
            "startVa": "0x008BA620",
            "startBytes": VOICE_START_BYTES,
            "startSha256": VOICE_START_SHA256,
            "startedInvariant": "voice.state == 2 && voiceParam[voiceIndex] != null",
            "fields": {
                "state": "0x00",
                "done": "0x04",
                "hasData": "0x08",
                "positionI64": "0x10",
            },
        },
        "mapSymbolEvidence": symbol_evidence,
        "proofBoundary": (
            "This closes the exact dedicated-server decoder/source/voice handoff and voice state accessors. "
            "It does not yet claim the mixer DSP, sample-rate conversion, speaker matrix, XAudio2 submission "
            "semantics, normal dedicated-server output enablement, or retail t6mp.exe address equivalence."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--exe", type=Path, required=True)
    p.add_argument("--map", dest="map_path", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = prove(a.exe.read_bytes(), a.map_path.read_text("ascii"))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

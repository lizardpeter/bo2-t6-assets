#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

FORMAT = "t6-pc-server-sound-decoder-stream-runtime-proof-v1"
EXPECTED_EXE_BYTES = 13_711_872
EXPECTED_EXE_SHA256 = "f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d"
EXPECTED_MAP_BYTES = 9_213_148
EXPECTED_MAP_SHA256 = "34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf"
EXPECTED_IMAGE_BASE = 0x00400000

RANGES = {
    "SD_DecoderShutdown": (0x008B99F0, 0x008B9A10, "09e6ad9478f56465517ecbcdfe2e356fb68e85acd67c452ab4844806dc6af779"),
    "SD_DecoderAllocate_impl": (0x008B9A10, 0x008B9B20, "35ec6c52fb0105ff7f5d3a80e44047a7849b8fc50acab49dd7d7839c1efa6f0c"),
    "SD_DecoderAllocate_wrapper": (0x008B9B20, 0x008B9B70, "73b09271cd3713480eb43d4d3b7af23c95e0171b3ca8962da7513fa70553a4f2"),
    "SD_SourceInitStream": (0x008B9D10, 0x008B9DA0, "8a1c3ebfb4d69d2c3b88ed35f7b014bf7e0aa64bef1c2366a7fe1fe6549b2081"),
    "SD_StreamShutdown": (0x008B9DA0, 0x008B9DC0, "dd5a9abab4fb383a3f6dbb5e57a71f700bcbf72ba934fbd8e21b1bd28090898d"),
    "SD_StreamBufferPreload": (0x008B9DC0, 0x008B9E20, "393f1ede1bef4e54cb3bfe9b5dbde3e65494be996679f36dd421dcb3d676f7ea"),
    "SD_StreamAllocate": (0x008B9E20, 0x008BA010, "3732b14d49e8c65495226e32b0d5aa2147a5432bbb6243da1fb840530d1edff0"),
}

SYMBOLS = {
    "SD_DecoderShutdown": 0x008B99F0,
    "SD_DecoderAllocate_impl": 0x008B9A10,
    "SD_DecoderAllocate_wrapper": 0x008B9B20,
    "SD_SourceInitStream": 0x008B9D10,
    "SD_StreamShutdown": 0x008B9DA0,
    "SD_StreamBufferPreload": 0x008B9DC0,
    "SD_StreamAllocate": 0x008B9E20,
    "SD_OutputForceWakeup": 0x008BA8B0,
    "SND_HashName": 0x008C5E00,
}

class ProofError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PE:
    def __init__(self, path: Path):
        self.data = path.read_bytes()
        if len(self.data) != EXPECTED_EXE_BYTES or sha256(self.data) != EXPECTED_EXE_SHA256:
            raise ProofError("EXE identity mismatch")
        peoff = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[:2] != b"MZ" or self.data[peoff:peoff+4] != b"PE\0\0":
            raise ProofError("invalid PE")
        coff = peoff + 4
        machine, nsects, _, _, _, opt_size, _ = struct.unpack_from("<HHIIIHH", self.data, coff)
        if machine != 0x14C:
            raise ProofError("unexpected PE machine")
        opt = coff + 20
        self.image_base = struct.unpack_from("<I", self.data, opt + 28)[0]
        if self.image_base != EXPECTED_IMAGE_BASE:
            raise ProofError("unexpected image base")
        self.sections = []
        table = opt + opt_size
        for i in range(nsects):
            off = table + i * 40
            virtual_size, rva, raw_size, raw_offset = struct.unpack_from("<IIII", self.data, off + 8)
            self.sections.append((self.image_base + rva, virtual_size, raw_size, raw_offset))

    def va_to_offset(self, va: int) -> int:
        for base, _, raw_size, raw_offset in self.sections:
            if base <= va < base + raw_size:
                return raw_offset + va - base
        raise ProofError(f"unmapped VA 0x{va:08X}")

    def bytes_at(self, va: int, size: int) -> bytes:
        off = self.va_to_offset(va)
        out = self.data[off:off+size]
        if len(out) != size:
            raise ProofError(f"short read at 0x{va:08X}")
        return out

    def cstr(self, va: int, limit: int = 256) -> str:
        off = self.va_to_offset(va)
        raw = self.data[off:off+limit]
        raw = raw.split(b"\0", 1)[0]
        if not raw:
            raise ProofError(f"empty string at 0x{va:08X}")
        try:
            return raw.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ProofError(f"non-ASCII string at 0x{va:08X}") from exc


def validate_map(path: Path) -> None:
    raw = path.read_bytes()
    if len(raw) != EXPECTED_MAP_BYTES or sha256(raw) != EXPECTED_MAP_SHA256:
        raise ProofError("MAP identity mismatch")
    text = raw.decode("ascii", errors="strict")
    lower = text.lower()
    required = {
        0x008B99F0: "SD_DecoderShutdown",
        0x008B9A10: "SD_DecoderAllocate",
        0x008B9B20: "SD_DecoderAllocate",
        0x008B9D10: "SD_SourceInitStream",
        0x008B9DA0: "SD_StreamShutdown",
        0x008B9DC0: "SD_StreamBufferPreload",
        0x008B9E20: "SD_StreamAllocate",
        0x008BA8B0: "SD_OutputForceWakeup",
        0x008C5E00: "SND_HashName",
    }
    for va, name in required.items():
        if name not in text or f"{va:08x}" not in lower:
            raise ProofError(f"MAP does not bind {name} to 0x{va:08X}")


def require_bytes(pe: PE, va: int, hex_bytes: str) -> None:
    want = bytes.fromhex(hex_bytes)
    got = pe.bytes_at(va, len(want))
    if got != want:
        raise ProofError(f"instruction window changed at 0x{va:08X}: {got.hex()} != {want.hex()}")


def call_target(pe: PE, va: int) -> int:
    b = pe.bytes_at(va, 5)
    if b[0] != 0xE8:
        raise ProofError(f"0x{va:08X} is not a near CALL")
    return va + 5 + struct.unpack_from("<i", b, 1)[0]


def require_call(pe: PE, va: int, target: int) -> None:
    got = call_target(pe, va)
    if got != target:
        raise ProofError(f"call 0x{va:08X} -> 0x{got:08X}, expected 0x{target:08X}")


def require_string(pe: PE, va: int, expected: str) -> None:
    got = pe.cstr(va)
    if got != expected:
        raise ProofError(f"string changed at 0x{va:08X}: {got!r}")


def build(exe: Path, map_path: Path) -> dict:
    pe = PE(exe)
    validate_map(map_path)

    exact = {}
    for name, (start, end, expected_hash) in RANGES.items():
        got = sha256(pe.bytes_at(start, end - start))
        if got != expected_hash:
            raise ProofError(f"{name}: range SHA changed: {got}")
        exact[name] = {
            "startVa": f"0x{start:08X}",
            "endVaExclusive": f"0x{end:08X}",
            "bytes": end - start,
            "sha256": got,
        }

    # Decoder interface table geometry: Shutdown pointers use base 0xDE2514,
    # stride 0x2C, and stop exactly at 0xDE26F8 => 11 records.
    require_bytes(pe, 0x008B99F1, "be1425de00")
    require_bytes(pe, 0x008B99FE, "83c62c")
    require_bytes(pe, 0x008B9A01, "81fef826de00")

    # Physical entry byte +0x13 becomes decoder->format. Dispatch uses the
    # format-indexed pointer table at 0xDE2538 with the same 0x2C stride.
    require_bytes(pe, 0x008B9AB0, "0fb64713")
    require_bytes(pe, 0x008B9AB4, "894620")
    require_bytes(pe, 0x008B9AB7, "6bc02c")
    require_bytes(pe, 0x008B9ABA, "39883825de00")
    require_bytes(pe, 0x008B9AE4, "8b46206bc02c8b883825de00")
    require_bytes(pe, 0x008B9AF0, "5756ffd1")

    # Two-argument wrapper admits only physical formats 0 and 8 and selects
    # a 100-instance pool for each before entering the generic allocator.
    require_bytes(pe, 0x008B9B26, "8a411384c074223c087417")
    require_bytes(pe, 0x008B9B48, "b8643ede00")
    require_bytes(pe, 0x008B9B4F, "b85430de00")
    require_bytes(pe, 0x008B9B54, "50518b4d0851b864000000")
    require_call(pe, 0x008B9B5F, 0x008B9A10)

    # Stream source requires physical channelCount 1 or 2, calls
    # SD_StreamAllocate, stores the stream at source+0x18, and records
    # success/failure state explicitly.
    require_bytes(pe, 0x008B9D17, "8a46113c0174283c027424")
    require_call(pe, 0x008B9D57, 0x008B9E20)
    require_bytes(pe, 0x008B9D5C, "8b4d0883c41489411885c07511")
    require_bytes(pe, 0x008B9D69, "b80100000089412889412089412c")
    require_bytes(pe, 0x008B9D7A, "33d2c7412000000000385612c74128000000000f95c2c7412c00000000")
    require_bytes(pe, 0x008B9D98, "895124")

    # Preload table: 16 records * 0x14 = 0x140 bytes.
    require_bytes(pe, 0x008B9DA0, "68400100006a006808b1f107")
    require_bytes(pe, 0x008B9DC7, "83b808b1f10700")
    require_bytes(pe, 0x008B9DD0, "83c014413d4001000072ec")
    require_bytes(pe, 0x008B9DEA, "898808b1f107")
    require_bytes(pe, 0x008B9DF3, "899018b1f107")
    require_bytes(pe, 0x008B9DFC, "898810b1f107")
    require_bytes(pe, 0x008B9E05, "899014b1f107")
    require_bytes(pe, 0x008B9E0B, "89880cb1f107")

    # Stream pool: [0x07F1A420,0x07F1AC90), stride 0x6C => 20 streams.
    require_bytes(pe, 0x008B9E25, "be20a4f107")
    require_bytes(pe, 0x008B9E30, "833e00742183c66c81fe90acf1077cf0")
    require_bytes(pe, 0x008B9E40, "681820ca006a0e")

    # Stream field zero assertions and required filename/entry arguments.
    require_bytes(pe, 0x008B9E56, "837e4000")
    require_bytes(pe, 0x008B9E7F, "837e4800")
    require_bytes(pe, 0x008B9EA8, "837e4c00")
    require_bytes(pe, 0x008B9ED1, "837e5000")
    require_bytes(pe, 0x008B9EFA, "837e5400")
    require_bytes(pe, 0x008B9F25, "8b7d0885ff")
    require_bytes(pe, 0x008B9F4E, "8b5d0c85db")

    # Runtime filename hash must equal physical entry id at +0x00.
    require_call(pe, 0x008B9FAE, 0x008C5E00)
    require_bytes(pe, 0x008B9FB6, "3b03")

    # Exact stream initialization fields.
    require_bytes(pe, 0x008B9FDD, "8b45108b4d148b5518")
    require_bytes(pe, 0x008B9FE6, "894668897e04")
    require_bytes(pe, 0x008B9FEF, "895e64894658894644")
    require_bytes(pe, 0x008B9FF9, "c70601000000894e5c895660")

    # Source-level assertion / diagnostic strings anchor the semantics.
    require_string(pe, 0x00CA1D60, r"c:\t6\code\src\sound\sd_decode.cpp")
    require_string(pe, 0x00CA1D84, "(g_sd.decoderInterfaces[decoder->format].Create)")
    require_string(pe, 0x00CA1E0C, "sound no decoder for asset type %d\n")
    require_string(pe, 0x00CA1EA4, r"c:\t6\code\src\sound\sd_source.cpp")
    require_string(pe, 0x00CA1EC8, "((entry->channelCount == 1 || entry->channelCount == 2))")
    require_string(pe, 0x00CA1F20, r"c:\t6\code\src\sound\sd_stream.cpp")
    require_string(pe, 0x00CA1F44, "(SND_HashName(filename) == entry->id)")
    require_string(pe, 0x00CA1F80, "(stream->buffersSubmitted[1] == 0)")
    require_string(pe, 0x00CA1FA4, "(stream->buffersSubmitted[0] == 0)")
    require_string(pe, 0x00CA1FC8, "(stream->buffers[1] == 0)")
    require_string(pe, 0x00CA1FE4, "(stream->buffers[0] == 0)")
    require_string(pe, 0x00CA2000, "(stream->ioBuffer == 0)")
    require_string(pe, 0x00CA2018, "Out of streams. Someone is playing WAY to many streamed sounds in one frame\n")

    decoder_count = (0x00DE26F8 - 0x00DE2514) // 0x2C
    stream_count = (0x07F1AC90 - 0x07F1A420) // 0x6C
    preload_count = 0x140 // 0x14
    if decoder_count != 11 or stream_count != 20 or preload_count != 16:
        raise ProofError("derived runtime pool geometry changed")

    return {
        "format": FORMAT,
        "authority": "exact SHA-pinned PC dedicated-server build only",
        "source": {
            "exe": {"bytes": EXPECTED_EXE_BYTES, "sha256": EXPECTED_EXE_SHA256},
            "map": {"bytes": EXPECTED_MAP_BYTES, "sha256": EXPECTED_MAP_SHA256},
            "imageBase": "0x00400000",
            "generatedBy": "tools/t6_pc_server_sound_decoder_stream_runtime_proof_v1.py",
        },
        "exactFunctionRanges": exact,
        "decoderInterface": {
            "recordCount": decoder_count,
            "strideBytes": 44,
            "shutdownPointerBase": "0x00DE2514",
            "createPointerBase": "0x00DE2538",
            "createPointerDeltaFromShutdown": 36,
            "physicalFormatOffset": "SndAssetBankEntry+0x13",
            "dispatch": "decoder->format indexes the 0x2C-stride Create pointer table; source assertion names g_sd.decoderInterfaces[decoder->format].Create",
            "wrapperAcceptedFormats": [0, 8],
            "wrapperPools": {
                "format0": {"base": "0x00DE3054", "instances": 100},
                "format8": {"base": "0x00DE3E64", "instances": 100},
            },
        },
        "streamSource": {
            "requiredChannelCounts": [1, 2],
            "streamPointerOffset": "sd_source+0x18",
            "entryByte12ToSourceFlag": "entry+0x12 != 0 is stored at sd_source+0x24 on successful stream allocation",
            "allocationFailure": "sd_source+0x20,+0x28,+0x2C are set to 1",
            "allocationSuccess": "sd_source+0x20,+0x28,+0x2C are cleared to 0",
        },
        "streamRuntime": {
            "poolBase": "0x07F1A420",
            "poolEndExclusive": "0x07F1AC90",
            "poolStrideBytes": 108,
            "poolCount": stream_count,
            "preloadTableBase": "0x07F1B108",
            "preloadRecordStrideBytes": 20,
            "preloadRecordCount": preload_count,
            "filenameIntegrity": "SND_HashName(filename) must equal SndAssetBankEntry.id at +0x00",
            "initialState": "stream+0x00 = 1; stream+0x04 = filename; stream+0x64 = entry; stream+0x44 and +0x58 are cleared",
        },
        "closedFacts": {
            "physicalFormatSelection": "SndAssetBankEntry+0x13 is the runtime decoder format index",
            "decoderDispatch": "format-indexed g_sd.decoderInterfaces[].Create is called with sd_decoder* and physical entry",
            "serverDirectDecoderFormats": "the two-argument SD_DecoderAllocate wrapper accepts only formats 0 and 8",
            "streamChannelValidation": "stream sources require entry channelCount 1 or 2",
            "streamFilenameBinding": "runtime filename hash is asserted equal to physical entry id",
        },
        "proofBoundary": "This closes decoder-interface dispatch and stream object setup for the exact SHA-pinned PC dedicated-server build. Numeric decoder formats 0 and 8 are not assigned codec names here. Codec-specific Create/Decode semantics and retail t6mp.exe equivalence remain open.",
        "notYetEstablished": [
            "codec names for numeric physical formats 0 and 8",
            "exact Create/Decode function targets installed in decoder interface records 0 and 8",
            "codec-specific bitstream-to-PCM decode semantics",
            "retail t6mp.exe equivalence",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--exe", type=Path, required=True)
    p.add_argument("--map", type=Path, required=True)
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    try:
        obj = build(args.exe, args.map)
    except ProofError as exc:
        print(f"ERROR: {exc}")
        return 2
    text = json.dumps(obj, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

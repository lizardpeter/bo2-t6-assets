#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

FORMAT = "t6-pc-server-sound-assetid-runtime-proof-v1"
EXPECTED_EXE_BYTES = 13_711_872
EXPECTED_EXE_SHA256 = "f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d"
EXPECTED_MAP_BYTES = 9_213_148
EXPECTED_MAP_SHA256 = "34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf"
EXPECTED_IMAGE_BASE = 0x00400000

RANGES = {
    "SND_AssetBankFindEntry_physical": (0x008B4060, 0x008B4100, "4d58506f53dad05314ac5767df0bcfbc7103f8b9834b3003a33ab03f126176b4"),
    "SND_AssetBankFindEntry_runtime": (0x008B48A0, 0x008B495E, "d197d45e6e25fd7164837fd1ba9ce780f71fff8ebdd0ae042dcc94328b67ab2c"),
    "SND_AssetBankFindStreamed": (0x008B4960, 0x008B497B, "7bbd5e43740391b1ed04ceb9f6c9b3660853fed4c64c7780762a5936499f6c64"),
    "SND_AssetBankFindLoaded": (0x008B4980, 0x008B4A31, "bdca163e63805518d60b7c166cefda588c60d3e7aba5ab67838f261be86a6941"),
    "SD_StartAlias": (0x008B94C0, 0x008B9801, "4ed142af3829da86eecb8d5e2db32e53db64decf3651a03bbcfff3c30ff97738"),
    "SD_VoiceAllocateRam": (0x008BA310, 0x008BA4C1, "9a82ead78d8745ac6365ccebee0ee6e754e17d208e0b2fc3dd035357e4099d6c"),
    "SD_VoiceAllocateStream": (0x008BA4D0, 0x008BA559, "356f708d145dcf3b03424abbc5bf88cad925b6da254d2fe55c050df33edcc98f"),
    "SD_VoiceHasData": (0x008BA610, 0x008BA620, "4edbbea44f2180c146797f430e3ae02de67ac019daf6d847fc26162e0d89a247"),
}

SYMBOLS = {
    "SND_StopVoice": 0x008B02B0,
    "SND_SetVoiceStartInfo": 0x008B1A40,
    "SND_AssetBankFindEntry": 0x008B4060,
    "SND_AssetBankGetFrameRate": 0x008B4100,
    "SND_AssetBankGetChannelCount": 0x008B41B0,
    "SND_AssetBankGetLooping": 0x008B41C0,
    "SND_AssetBankGetFrameCount": 0x008B41D0,
    "SND_AssetBankGetLengthMs": 0x008B41E0,
    "SND_AssetBankFindStreamed": 0x008B4960,
    "SND_AssetBankFindLoaded": 0x008B4980,
    "SD_StartAlias": 0x008B94C0,
    "SD_VoiceAllocateRam": 0x008BA310,
    "SD_VoiceAllocateStream": 0x008BA4D0,
    "SD_VoiceHasData": 0x008BA610,
    "SD_VoiceStart": 0x008BA620,
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
        if self.data[:2] != b"MZ" or self.data[peoff:peoff + 4] != b"PE\0\0":
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
            _, rva, raw_size, raw_offset = struct.unpack_from("<IIII", self.data, off + 8)
            self.sections.append((self.image_base + rva, raw_size, raw_offset))

    def va_to_offset(self, va: int) -> int:
        for base, raw_size, raw_offset in self.sections:
            if base <= va < base + raw_size:
                return raw_offset + va - base
        raise ProofError(f"unmapped VA 0x{va:08X}")

    def bytes_at(self, va: int, size: int) -> bytes:
        off = self.va_to_offset(va)
        out = self.data[off:off + size]
        if len(out) != size:
            raise ProofError(f"short read at 0x{va:08X}")
        return out


def validate_map(path: Path) -> None:
    raw = path.read_bytes()
    if len(raw) != EXPECTED_MAP_BYTES or sha256(raw) != EXPECTED_MAP_SHA256:
        raise ProofError("MAP identity mismatch")
    text = raw.decode("ascii", errors="strict")
    lower = text.lower()
    for name, va in SYMBOLS.items():
        if name not in text or f"{va:08x}" not in lower:
            raise ProofError(f"MAP does not bind {name} to 0x{va:08X}")
    if "?SND_AssetBankFindEntry@@YA_NIPAPAUSndAssetBankEntry@@PAH_N@Z" not in text or "008b48a0" not in lower:
        raise ProofError("MAP does not bind runtime SND_AssetBankFindEntry overload to 0x008B48A0")


def require_bytes(pe: PE, va: int, hex_bytes: str) -> None:
    expected = bytes.fromhex(hex_bytes)
    if pe.bytes_at(va, len(expected)) != expected:
        raise ProofError(f"instruction window changed at 0x{va:08X}")


def call_target(pe: PE, va: int) -> int:
    data = pe.bytes_at(va, 5)
    if data[0] != 0xE8:
        raise ProofError(f"0x{va:08X} is not a near CALL")
    return va + 5 + struct.unpack_from("<i", data, 1)[0]


def require_call(pe: PE, va: int, target: int) -> None:
    actual = call_target(pe, va)
    if actual != target:
        raise ProofError(f"call 0x{va:08X} -> 0x{actual:08X}, expected 0x{target:08X}")


def build(exe: Path, map_path: Path) -> dict:
    pe = PE(exe)
    validate_map(map_path)

    exact_ranges = {}
    for name, (start, end, expected_sha) in RANGES.items():
        actual_sha = sha256(pe.bytes_at(start, end - start))
        if actual_sha != expected_sha:
            raise ProofError(f"{name}: function SHA changed: {actual_sha}")
        exact_ranges[name] = {
            "startVa": f"0x{start:08X}",
            "endVaExclusive": f"0x{end:08X}",
            "bytes": end - start,
            "sha256": actual_sha,
        }

    # Physical entry lookup: nonzero key, inclusive binary search, 20-byte entry stride,
    # dword id comparison at entry +0x00, exact entry pointer returned on equality.
    require_bytes(pe, 0x008B4063, "837d0800")
    require_bytes(pe, 0x008B408F, "8b7d1033db4f7850")
    require_bytes(pe, 0x008B4097, "8d043b992bc28bf0d1fe")
    require_bytes(pe, 0x008B40C9, "8b550c8b4d088d04b68b04823bc1")
    require_bytes(pe, 0x008B40D7, "73058d5e01eb05760e8d7eff")
    require_bytes(pe, 0x008B40EE, "8b45148d0cb65f8d148a5e8910b001")

    # Runtime streamed/primed bank census: 32 slots, descriptor selection, exact id handoff.
    require_bytes(pe, 0x008B48BF, "33ff8b879825f007")
    require_bytes(pe, 0x008B48CB, "807d14008d702075068db042090000")
    require_bytes(pe, 0x008B48DA, "80be2009000000")
    require_bytes(pe, 0x008B48E3, "8b462053508b860c0800008d0c808b45088d148d801deb075250")
    require_call(pe, 0x008B48FD, SYMBOLS["SND_AssetBankFindEntry"])
    require_bytes(pe, 0x008B4909, "83c70481ff8000000072ad")
    require_bytes(pe, 0x008B4933, "8b451085c074058b4e088908")

    # Streamed wrapper sets the overloaded FindEntry selector to true and forwards assetId unchanged.
    require_bytes(pe, 0x008B4963, "8b45108b4d0c8b55086a01505152")
    require_call(pe, 0x008B4971, 0x008B48A0)

    # Loaded bank census: 32 slots, exact id, offset sentinel, loaded-base reconstruction.
    require_bytes(pe, 0x008B499F, "33ff8bb79825f007")
    require_bytes(pe, 0x008B49AB, "8b867012000085c07421")
    require_bytes(pe, 0x008B49B5, "8b4d0853508b86741200005051")
    require_call(pe, 0x008B49C2, SYMBOLS["SND_AssetBankFindEntry"])
    require_bytes(pe, 0x008B49CE, "8b13837a08ff752a")
    require_bytes(pe, 0x008B49D6, "83c70481ff8000000072c0")
    require_bytes(pe, 0x008B4A00, "8b451085c0740b8b520803967c1200008910")

    # SD_StartAlias dispatch and the two direct physical-asset branches.
    require_bytes(pe, 0x008B9511, "83fe090f8723010000")
    require_bytes(pe, 0x008B951A, "8b4018c1e80f83e00383f802742783f8037422")
    require_bytes(pe, 0x008B9555, "8b48108d550c5251")
    require_call(pe, 0x008B955D, SYMBOLS["SND_AssetBankFindStreamed"])
    require_bytes(pe, 0x008B9600, "8b4dfc8b550c8b40146a006a00515250")
    require_call(pe, 0x008B9610, SYMBOLS["SD_VoiceAllocateStream"])
    require_bytes(pe, 0x008B9618, "8904b58078080185c0750e56")
    require_call(pe, 0x008B9624, SYMBOLS["SND_StopVoice"])
    require_call(pe, 0x008B9633, SYMBOLS["SND_SetVoiceStartInfo"])

    require_bytes(pe, 0x008B9647, "8b48105251")
    require_call(pe, 0x008B964C, SYMBOLS["SND_AssetBankFindLoaded"])
    require_call(pe, 0x008B9659, SYMBOLS["SND_StopVoice"])
    require_call(pe, 0x008B9672, SYMBOLS["SND_AssetBankGetLengthMs"])
    require_call(pe, 0x008B967F, SYMBOLS["SND_AssetBankGetFrameRate"])
    require_call(pe, 0x008B968C, SYMBOLS["SND_AssetBankGetChannelCount"])
    require_call(pe, 0x008B969F, SYMBOLS["SND_AssetBankGetFrameRate"])
    require_bytes(pe, 0x008B96A7, "3d80bb00007429")
    require_bytes(pe, 0x008B96D7, "8b178b450c8a5a185080e301")
    require_call(pe, 0x008B96E3, SYMBOLS["SND_AssetBankGetLooping"])
    require_bytes(pe, 0x008B96EB, "3ac37423")
    require_call(pe, 0x008B971F, SYMBOLS["SND_AssetBankGetFrameCount"])
    require_call(pe, 0x008B972C, SYMBOLS["SND_AssetBankGetFrameRate"])
    require_call(pe, 0x008B9739, SYMBOLS["SND_AssetBankGetChannelCount"])
    require_call(pe, 0x008B9746, SYMBOLS["SND_AssetBankGetLooping"])
    require_call(pe, 0x008B9758, SYMBOLS["SD_VoiceAllocateRam"])
    require_bytes(pe, 0x008B9760, "8904b58078080185c0750e56")
    require_call(pe, 0x008B976C, SYMBOLS["SND_StopVoice"])
    require_call(pe, 0x008B977B, SYMBOLS["SND_SetVoiceStartInfo"])
    require_call(pe, 0x008B9788, SYMBOLS["SD_VoiceHasData"])
    require_call(pe, 0x008B97D8, SYMBOLS["SD_VoiceStart"])

    # Lower driver allocators: exact acquisition, setup, failure and ready-state paths.
    require_call(pe, 0x008BA314, 0x008BA1C0)
    require_bytes(pe, 0x008BA31B, "85f60f84dd000000")
    require_call(pe, 0x008BA3E9, 0x008B9B20)
    require_bytes(pe, 0x008BA3F6, "85c0750bc7060300000033c0")
    require_bytes(pe, 0x008BA4AF, "c7460801000000c706020000008bc6")

    require_call(pe, 0x008BA4D4, 0x008BA1C0)
    require_bytes(pe, 0x008BA4DB, "85f675035e5dc3")
    require_call(pe, 0x008BA4FC, 0x008B9D10)
    require_bytes(pe, 0x008BA504, "837e4400742b")
    require_call(pe, 0x008BA537, 0x008B9B20)
    require_bytes(pe, 0x008BA53F, "89464c0fb65311")
    require_bytes(pe, 0x008BA54E, "c706020000008bc6")
    require_bytes(pe, 0x008BA610, "558bec8b4d0833c03941080f95c05dc3")

    return {
        "format": FORMAT,
        "authority": "exact SHA-pinned PC dedicated-server build only",
        "source": {
            "exe": {"bytes": EXPECTED_EXE_BYTES, "sha256": EXPECTED_EXE_SHA256},
            "map": {"bytes": EXPECTED_MAP_BYTES, "sha256": EXPECTED_MAP_SHA256},
            "imageBase": "0x00400000",
            "generatedBy": "tools/t6_pc_server_sound_assetid_runtime_proof_v1.py",
        },
        "exactFunctionRanges": exact_ranges,
        "closedFacts": {
            "serializedAssetIdOffset": "SndAlias+0x10",
            "physicalEntryLookupKey": "the exact 32-bit serialized assetId",
            "physicalEntryStrideBytes": 20,
            "physicalEntryIdOffset": "0x00",
            "physicalEntrySearch": "binary search over the sorted physical SndAssetBankEntry array",
            "physicalLookupNonzeroInvariant": "SND_AssetBankFindEntry asserts assetId != 0 before searching",
            "runtimeBankSlotCount": 32,
            "loadedOffsetSentinel": "SndAssetBankEntry+0x08 must not equal 0xFFFFFFFF",
            "loadedDataPointer": "entry+0x08 offset plus selected runtime bank loaded-data base at bank+0x127C",
            "loadedRequiredFrameRateHz": 48000,
            "loadedLoopingAgreement": "SND_AssetBankGetLooping(entry) must equal SndAlias.flags0 bit0",
            "streamVoiceAllocation": "SD_VoiceAllocateStream",
            "ramVoiceAllocation": "SD_VoiceAllocateRam",
            "allocationFailure": "SD_StartAlias calls SND_StopVoice and returns failure",
            "allocationSuccess": "returned sd_voice* is stored in the driver-voice array and SND_SetVoiceStartInfo is called",
            "ramHasDataGate": "SD_VoiceHasData returns sd_voice+0x08 != 0 before SD_VoiceStart",
        },
        "dispatch": {
            "streamPool": "voice index <= 9; exact code requires SndAlias.flags0 loadType bits15-16 to be SA_STREAMED(2) or SA_PRIMED(3), then calls SND_AssetBankFindStreamed with SndAlias+0x10",
            "ramPool": "voice index > 9; calls SND_AssetBankFindLoaded with SndAlias+0x10, validates physical metadata, then calls SD_VoiceAllocateRam",
            "secondaryBoundary": "SD_StartAlias has no Secondary-alias fallback. assetId==0 is not a Secondary sentinel here; physical SND_AssetBankFindEntry additionally asserts the requested id is nonzero.",
        },
        "physicalSearch": {
            "algorithm": "inclusive low/high binary search; midpoint=(low+high)/2; entry=base+midpoint*20; compare uint32 entry+0x00 with requested id; equality stores the exact entry pointer",
            "runtimeStreamed": "the overloaded SND_AssetBankFindEntry scans 32 bank slots under critical section 11, selects the streamed descriptor when selector=true, requires its valid byte, derives the physical entry table, and passes the exact id to physical SND_AssetBankFindEntry",
            "runtimeLoaded": "SND_AssetBankFindLoaded scans 32 bank slots under critical section 11, passes the exact id/table/count to physical SND_AssetBankFindEntry, rejects entry+0x08 == 0xFFFFFFFF, and optionally returns loadedBase+offset",
        },
        "loadedMetadata": {
            "frameRate": "SND_AssetBankGetFrameRate @ 0x008B4100",
            "channelCount": "SND_AssetBankGetChannelCount @ 0x008B41B0",
            "looping": "SND_AssetBankGetLooping @ 0x008B41C0",
            "frameCount": "SND_AssetBankGetFrameCount @ 0x008B41D0",
            "lengthMs": "SND_AssetBankGetLengthMs @ 0x008B41E0",
        },
        "driverAllocation": {
            "commonAcquire": "both allocators first call exact helper 0x008BA1C0 and return null if no sd_voice is obtained",
            "ram": "initializes RAM state, calls exact helper 0x008B9B20, marks state 3 and returns null if setup fails, otherwise sets data-ready +0x08=1 and state=2 before returning sd_voice*",
            "stream": "initializes stream state via exact helper 0x008B9D10; a nonzero +0x44 setup-failure state returns null; the success path calls exact helper 0x008B9B20, copies entry byte +0x11 to sd_voice+0x10C, sets state=2, and returns sd_voice*",
            "unnamedHelpers": "0x008BA1C0, 0x008B9B20, and 0x008B9D10 remain address-only until their MAP/PDB names and deeper semantics are independently closed.",
        },
        "proofBoundary": "Only exact SHA-pinned PC dedicated-server machine code and exact MAP symbol bindings are authoritative. This closes the assetId-to-bank-entry-to-driver-voice handoff for this build. It does not claim retail t6mp.exe equivalence or codec decode semantics.",
        "notYetEstablished": [
            "retail t6mp.exe equivalence",
            "full names/prototypes of driver helpers 0x008BA1C0, 0x008B9B20, and 0x008B9D10",
            "codec-specific sample decode below the sd_voice/backend setup layer",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", type=Path, required=True)
    ap.add_argument("--map", dest="map_path", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    try:
        obj = build(args.exe, args.map_path)
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

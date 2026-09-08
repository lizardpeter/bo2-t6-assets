#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

FORMAT = "t6-pc-server-sound-voice-limit-runtime-proof-v1"
EXPECTED_EXE_BYTES = 13_711_872
EXPECTED_EXE_SHA256 = "f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d"
EXPECTED_MAP_BYTES = 9_213_148
EXPECTED_MAP_SHA256 = "34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf"
EXPECTED_IMAGE_BASE = 0x00400000

RANGES = {
    "Snd_GetGlobalPriorityVolume": (0x008AC640, 0x008AC770, "a0edfb93192d6c4f14f0990773ebd8ceb0819d64b9e60b65dd7e90cf07dbdf1e"),
    "Snd_GetLowestPriority": (0x008AC770, 0x008AC8D0, "eed4a0828be56265c980507d7afa878464c23f872b59d5a816e05d2e9b4d1777"),
    "SND_GetPlayingInfo": (0x008ACF40, 0x008AD1B0, "909e2686c849f26ff2707bd6beb3cf59b5be8a84ffe10a5c38cbeff25f011602"),
    "SND_FindFreeVoice": (0x008B2570, 0x008B2680, "8b253b8d2c0ff7e2c4a9944d8c8854b413e163511db7aefc65d3b15303b20f15"),
    "SND_Limit": (0x008B2680, 0x008B2750, "f1b33defa4519809ce91c90937b1498f94eb72cc823e28cc5445f97834937a6e"),
    "SND_LimitVoice": (0x008B2750, 0x008B2850, "76acc81aad1550b1ed29c3bf75912615e1ce0a2e446560276f9a81fa1201d795"),
}

SYMBOLS = {
    "SND_StopVoice": 0x008B02B0,
    "Snd_GetGlobalPriorityVolume": 0x008AC640,
    "Snd_GetLowestPriority": 0x008AC770,
    "SND_GetPlayingInfo": 0x008ACF40,
    "SND_FindFreeVoice": 0x008B2570,
    "SND_Limit": 0x008B2680,
    "SND_LimitVoice": 0x008B2750,
    "SND_PlaySoundAlias": 0x008B2850,
    "Snd_GetGlobalPriority": 0x008C5FE0,
    "Dvar_GetInt": 0x00776850,
    "Dvar_GetFloat": 0x007769E0,
    "snd_playing_priority_boost": 0x0798749C,
    "snd_max_stream_voice": 0x07F1D4E0,
    "snd_max_ram_voice": 0x07F1D4F4,
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
        if self.data[:2] != b"MZ":
            raise ProofError("not an MZ executable")
        peoff = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[peoff:peoff + 4] != b"PE\0\0":
            raise ProofError("not a PE executable")
        coff = peoff + 4
        machine, nsects, _, _, _, opt_size, _ = struct.unpack_from("<HHIIIHH", self.data, coff)
        if machine != 0x14C:
            raise ProofError("unexpected PE machine")
        opt = coff + 20
        self.image_base = struct.unpack_from("<I", self.data, opt + 28)[0]
        if self.image_base != EXPECTED_IMAGE_BASE:
            raise ProofError("unexpected image base")
        self.sections = []
        section_table = opt + opt_size
        for i in range(nsects):
            off = section_table + i * 40
            name = self.data[off:off + 8].split(b"\0", 1)[0].decode("ascii", "replace")
            virtual_size, rva, raw_size, raw_offset = struct.unpack_from("<IIII", self.data, off + 8)
            self.sections.append((name, self.image_base + rva, virtual_size, raw_size, raw_offset))

    def va_to_offset(self, va: int) -> int:
        for _, base, _, raw_size, raw_offset in self.sections:
            if base <= va < base + raw_size:
                return raw_offset + va - base
        raise ProofError(f"unmapped VA 0x{va:08X}")

    def bytes_at(self, va: int, size: int) -> bytes:
        off = self.va_to_offset(va)
        data = self.data[off:off + size]
        if len(data) != size:
            raise ProofError(f"short read at 0x{va:08X}")
        return data


def validate_map(path: Path) -> None:
    raw = path.read_bytes()
    if len(raw) != EXPECTED_MAP_BYTES or sha256(raw) != EXPECTED_MAP_SHA256:
        raise ProofError("MAP identity mismatch")
    text = raw.decode("ascii", errors="strict")
    lower = text.lower()
    for name, va in SYMBOLS.items():
        if name not in text or f"{va:08x}" not in lower:
            raise ProofError(f"MAP does not bind {name} to 0x{va:08X}")


def call_target(pe: PE, call_va: int) -> int:
    data = pe.bytes_at(call_va, 5)
    if data[0] != 0xE8:
        raise ProofError(f"0x{call_va:08X} is not a near CALL")
    return call_va + 5 + struct.unpack_from("<i", data, 1)[0]


def require_call(pe: PE, call_va: int, target: int) -> None:
    actual = call_target(pe, call_va)
    if actual != target:
        raise ProofError(f"call 0x{call_va:08X} -> 0x{actual:08X}, expected 0x{target:08X}")


def require_bytes(pe: PE, va: int, hex_bytes: str) -> None:
    expected = bytes.fromhex(hex_bytes)
    if pe.bytes_at(va, len(expected)) != expected:
        raise ProofError(f"instruction window changed at 0x{va:08X}")


def build(exe: Path, map_path: Path) -> dict:
    pe = PE(exe)
    validate_map(map_path)

    exact_ranges = {}
    for name, (start, end, expected_sha) in RANGES.items():
        raw = pe.bytes_at(start, end - start)
        actual_sha = sha256(raw)
        if actual_sha != expected_sha:
            raise ProofError(f"{name}: function SHA changed: {actual_sha}")
        exact_ranges[name] = {
            "startVa": f"0x{start:08X}",
            "endVaExclusive": f"0x{end:08X}",
            "bytes": end - start,
            "sha256": actual_sha,
        }

    # SND_FindFreeVoice: loadType pool choice, exact priority helpers, exact steal action.
    require_bytes(pe, 0x008B259A, "8b4f1881e100800100")
    require_bytes(pe, 0x008B25A6, "81f900800000")
    require_bytes(pe, 0x008B25AE, "8b15e0d4f107")
    require_bytes(pe, 0x008B25B9, "a1f4d4f107")
    require_call(pe, 0x008B2584, SYMBOLS["Snd_GetGlobalPriorityVolume"])
    require_call(pe, 0x008B2592, SYMBOLS["Snd_GetGlobalPriority"])
    require_call(pe, 0x008B25C4, SYMBOLS["Dvar_GetInt"])
    require_call(pe, 0x008B2608, SYMBOLS["Snd_GetLowestPriority"])
    require_call(pe, 0x008B2613, SYMBOLS["Dvar_GetFloat"])
    require_call(pe, 0x008B2631, SYMBOLS["SND_StopVoice"])

    # SND_Limit: exact playing census and enum branches.
    require_call(pe, 0x008B26C1, SYMBOLS["SND_GetPlayingInfo"])
    require_bytes(pe, 0x008B26DE, "83fe02")
    require_bytes(pe, 0x008B26E3, "83fe01")
    require_bytes(pe, 0x008B26FF, "83fe03")
    require_call(pe, 0x008B26F0, SYMBOLS["SND_StopVoice"])
    require_call(pe, 0x008B2712, SYMBOLS["Dvar_GetFloat"])
    require_bytes(pe, 0x008B2722, "d880e432e507")
    require_call(pe, 0x008B2732, SYMBOLS["SND_StopVoice"])

    # SND_LimitVoice: exact voiceLimit and volumeGroup masks.
    require_bytes(pe, 0x008B277D, "8b4618c1e809a801")
    require_bytes(pe, 0x008B27CA, "8b5318c1ea09f6c201")
    require_bytes(pe, 0x008B27EF, "8b46188b155830e507c1e81183e01f")
    require_bytes(pe, 0x008B2819, "8b318b7618c1ee1183e61f3bf2")
    require_call(pe, 0x008B27D6, SYMBOLS["SND_StopVoice"])

    # SND_PlaySoundAlias binds the two serialized limit pairs to SND_Limit.
    require_bytes(pe, 0x008B2D3B, "0fb64f5d")
    require_bytes(pe, 0x008B2D50, "c1e819")
    require_bytes(pe, 0x008B2D54, "83e003")
    require_call(pe, 0x008B2D58, SYMBOLS["SND_Limit"])
    require_bytes(pe, 0x008B2D68, "0fb64f5e")
    require_bytes(pe, 0x008B2D80, "c1e81b")
    require_bytes(pe, 0x008B2D84, "83e003")
    require_call(pe, 0x008B2D88, SYMBOLS["SND_Limit"])
    require_call(pe, 0x008B2D9A, SYMBOLS["SND_LimitVoice"])

    return {
        "format": FORMAT,
        "authority": "exact PC dedicated-server build only",
        "source": {
            "exe": {"bytes": EXPECTED_EXE_BYTES, "sha256": EXPECTED_EXE_SHA256},
            "map": {"bytes": EXPECTED_MAP_BYTES, "sha256": EXPECTED_MAP_SHA256},
            "imageBase": "0x00400000",
        },
        "exactFunctionRanges": exact_ranges,
        "layout": {
            "SndAliasBytes": 96,
            "aliasIdOffset": "0x04",
            "flags0Offset": "0x18",
            "limitCountOffset": "0x5D",
            "entityLimitCountOffset": "0x5E",
            "flags0": {
                "voiceLimitBit": 9,
                "loadTypeBits": [15, 16],
                "volumeGroupBits": [17, 21],
                "limitTypeBits": [25, 26],
                "entityLimitTypeBits": [27, 28],
            },
            "SndLimitType": {
                "SND_LIMIT_NONE": 0,
                "SND_LIMIT_OLDEST": 1,
                "SND_LIMIT_REJECT": 2,
                "SND_LIMIT_PRIORITY": 3,
            },
            "SndAssetLoadType": {
                "SA_UNKNOWN": 0,
                "SA_LOADED": 1,
                "SA_STREAMED": 2,
                "SA_PRIMED": 3,
            },
            "sourceNaming": "Pinned OpenAssetTools T6_Assets.h @ 9dca965366541504b71fa8cfb7ac049cb9b717e1; runtime behavior is taken only from the exact server machine code.",
        },
        "findFreeVoice": {
            "incomingPriority": "Snd_GetGlobalPriority(alias, Snd_GetGlobalPriorityVolume(alias, startInfo+0x08, -1))",
            "poolSelection": {
                "SA_LOADED": "voice indices begin at 10; count = Dvar_GetInt(snd_max_ram_voice)",
                "allOtherLoadTypeValues": "voice indices begin at 0; count = Dvar_GetInt(snd_max_stream_voice)",
            },
            "freeSlot": "returns the first selected-pool index whose g_snd.voiceAliasHash slot is zero",
            "fullPool": "Snd_GetLowestPriority returns the lowest globalPriority and its channel over that pool",
            "stealRule": "steal only when incomingPriority > lowestExistingGlobalPriority + Dvar_GetFloat(snd_playing_priority_boost)",
            "stealAction": "SND_StopVoice(candidate); exact code asserts the candidate voiceAliasHash slot became zero; return candidate channel",
            "failure": "returns -1 when no free slot exists and the priority-steal gate is not satisfied",
        },
        "generalAndEntityLimits": {
            "callBindingFromSND_PlaySoundAlias": [
                "general limit: aliasId(+0x04), limitCount(+0x5D), flags0.limitType(bits25-26), useEnt=false, computed global priority",
                "entity limit: aliasId(+0x04), entityLimitCount(+0x5E), flags0.entityLimitType(bits27-28), useEnt=true, same SndEntHandle, computed global priority",
            ],
            "playingInfo": "SND_GetPlayingInfo(aliasHash,&count,&oldest,&least,&isMultiple,ent,useEnt) scans active matching alias hashes; when useEnt is true it applies the exact entity predicate. `oldest` is selected by the minimum exact voice +0x24 integer; `least` is selected by the minimum exact voice globalPriority at +0xE4.",
            "rules": {
                "NONE": "allow immediately; no playing-info census or eviction",
                "commonPreGate": "after SND_GetPlayingInfo, isMultiple==true rejects; count < limitCount allows",
                "REJECT": "at/over limit rejects",
                "OLDEST": "at/over limit stops the returned oldest channel when nonnegative, then allows; if no oldest channel is returned, allows",
                "PRIORITY": "at/over limit requires a nonnegative least-priority channel and incomingPriority > existing.globalPriority + snd_playing_priority_boost; on success stops that channel and allows, otherwise rejects",
            },
            "serverDvar": "snd_playing_priority_boost @ 0x0798749C",
        },
        "voiceLimitAndVolumeGroup": {
            "voiceLimit": "If incoming alias flags0.voiceLimit bit9 is set, SND_LimitVoice scans all 68 active voices with the same SndEntHandle; any existing alias whose voiceLimit bit9 is also set is stopped via SND_StopVoice before the new attempt continues.",
            "volumeGroup": "Incoming alias flags0.volumeGroup (bits17-21) is compared with exact g_snd+0x158. If unequal, this gate allows. If equal, any active voice whose alias has the same volumeGroup causes rejection; if none exists, it allows.",
            "unnamedGlobal": "The PDB/source member name for g_snd+0x158 is intentionally not assigned here; only its exact address/offset and comparison behavior are promoted.",
        },
        "closedFacts": {
            "generalAliasLimitTypesClosed": True,
            "entityAliasLimitTypesClosed": True,
            "oldestReplacementClosed": True,
            "priorityReplacementClosed": True,
            "ramVsStreamVoicePoolSelectionClosed": True,
            "voiceLimitEntityReplacementClosed": True,
            "specialVolumeGroupExclusivityClosed": True,
        },
        "notYetEstablished": [
            "PDB/source member name for g_snd+0x158",
            "PDB/source member name for SndVoice+0x24 although the exact oldest-selection offset is closed",
            "full semantic name of the SND_GetPlayingInfo isMultiple internal predicate beyond its exact machine-code predicate",
            "retail t6mp.exe equivalence",
        ],
        "proofBoundary": "Every runtime branch above is tied to exact SHA-pinned PC dedicated-server machine-code ranges and exact MAP symbols. T6 field/enum names are imported only where independently declared by pinned T6 asset/source layouts. Unnamed runtime members remain numeric. This does not authorize retail-client behavior.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--map", dest="map_path", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.exe.resolve(), args.map_path.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["closedFacts"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

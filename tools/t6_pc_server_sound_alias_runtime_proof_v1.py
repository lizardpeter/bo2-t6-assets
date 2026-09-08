#!/usr/bin/env python3
"""Fail-closed T6 PC dedicated-server SndAlias runtime proof v1.

This proof is authoritative only for the exact SHA-pinned CoDMPServer_PC build.
It binds linker-MAP identities to exact machine-byte slices for:

* SND_PickSoundAliasFromList variant selection;
* SND_CheckValidSecondary dependency validation;
* the selection/Secondary/assetId==0 path in SND_PlaySoundAlias;
* the selected-variant probability gate;
* successful direct-start -> runtime has-played state;
* the three SndAlias never-played-twice / has-played helpers.

It deliberately does not promote dedicated-server behavior to retail t6mp.exe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

FORMAT = "t6-pc-server-sound-alias-runtime-proof-v1"
EXPECTED_EXE_BYTES = 13_711_872
EXPECTED_EXE_SHA256 = "f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d"
EXPECTED_MAP_BYTES = 9_213_148
EXPECTED_MAP_SHA256 = "34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf"
EXPECTED_PDB_BYTES = 49_196_032
EXPECTED_PDB_SHA256 = "7874efc2c9992467a72dbf48cc6f66d8cfa3c9a701275e41df1f8483a3d971fc"
EXPECTED_IMAGE_BASE = 0x00400000

SYMBOLS = {
    "g_snd": 0x07E52F00,
    "SND_AliasGetNeverPlayedTwice": 0x008AA7B0,
    "SND_AliasSetNeverPlayedTwice": 0x008AA7F0,
    "SND_AliasHasPlayed": 0x008AA830,
    "RandWithSeed": 0x00760DD0,
    "random": 0x00760D80,
    "I_stricmp": 0x0078E2C0,
    "SND_PickSoundAliasFromList": 0x008ACC50,
    "SND_PickSoundAlias": 0x008ACE30,
    "SND_CheckValidSecondary": 0x008ACE80,
    "SND_FindFreeVoice": 0x008B2570,
    "SND_PlaySoundAlias": 0x008B2850,
    "SND_BankAliasLookupCache": 0x008B4ED0,
    "SND_FindAlias": 0x008B6720,
    "SND_FindContextIndex": 0x008BC750,
    "SND_SubtitleNotify": 0x008C2DD0,
    "SND_HashName": 0x008C5E00,
    "SD_StartAlias": 0x008B94C0,
}

# Exact machine-code slices used to promote the bounded semantics below.
RANGES = {
    "SND_PickSoundAliasFromList": (
        0x008ACC50, 0x008ACE26,
        "536aac394901153948e21ca9537ef761ac448c6c18edff71606d72d0c569458c",
    ),
    "SND_CheckValidSecondary": (
        0x008ACE80, 0x008ACF40,
        "10f79f80ccaffffb921c4cd42b91a8608f9f5185e1a52d91b7fe5d2d012f34e5",
    ),
    "SND_PlaySoundAlias_select_secondary_zero": (
        0x008B2979, 0x008B2A9D,
        "fccb01b12942e5f7a80a54cdcdccf0ab6fe5dd97b755c7e56afdb4ca477c134d",
    ),
    "SND_PlaySoundAlias_probability": (
        0x008B2CE4, 0x008B2D1F,
        "95e5426bd177a1655f88935e578419f66fec906419c432260f910f7610c3bea1",
    ),
    "SND_PlaySoundAlias_start_and_has_played": (
        0x008B2F9B, 0x008B3178,
        "ad0dd7ce8d3d91a002b4e78e3943aa3c8e6a4a36087fd4a83be28fd5389f01f4",
    ),
    "SND_AliasGetNeverPlayedTwice": (
        0x008AA7B0, 0x008AA7E6,
        "1e85569ece79e660c5b211583dccb5d095ccfced12406d64a8af184cb785e421",
    ),
    "SND_AliasSetNeverPlayedTwice": (
        0x008AA7F0, 0x008AA82F,
        "440337a8fc1e24993b44f3ef02307c25f66d847a2350b449c1d2fa12a7b23fee",
    ),
    "SND_AliasHasPlayed": (
        0x008AA830, 0x008AA868,
        "60d2842aadf3936d98aa52623ea3f51204cf788154240f16a1aadc70fe99b6f5",
    ),
}

PROBABILITY_SCALE_VA = 0x00B93F54
PROBABILITY_SCALE_RAW = bytes.fromhex("8180803b")
ZERO_FLOAT_VA = 0x00B8F5F0
ZERO_FLOAT_RAW = b"\x00\x00\x00\x00"


class ProofError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PE:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        if len(self.data) != EXPECTED_EXE_BYTES:
            raise ProofError(f"EXE byte count mismatch: {len(self.data)}")
        if sha256(self.data) != EXPECTED_EXE_SHA256:
            raise ProofError("EXE SHA-256 mismatch")
        if self.data[:2] != b"MZ":
            raise ProofError("not an MZ executable")
        peoff = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[peoff:peoff + 4] != b"PE\0\0":
            raise ProofError("not a PE executable")
        coff = peoff + 4
        machine, nsects, _, _, _, opt_size, _ = struct.unpack_from("<HHIIIHH", self.data, coff)
        if machine != 0x14C:
            raise ProofError(f"unexpected PE machine 0x{machine:x}")
        opt = coff + 20
        if struct.unpack_from("<H", self.data, opt)[0] != 0x10B:
            raise ProofError("expected PE32")
        self.image_base = struct.unpack_from("<I", self.data, opt + 28)[0]
        if self.image_base != EXPECTED_IMAGE_BASE:
            raise ProofError(f"unexpected image base 0x{self.image_base:x}")
        self.sections = []
        sec = opt + opt_size
        for i in range(nsects):
            off = sec + i * 40
            name = self.data[off:off + 8].split(b"\0", 1)[0].decode("ascii", "replace")
            vsize, rva, raw_size, raw_off = struct.unpack_from("<IIII", self.data, off + 8)
            self.sections.append({
                "name": name,
                "va": self.image_base + rva,
                "virtualSize": vsize,
                "rawSize": raw_size,
                "rawOffset": raw_off,
            })

    def va_to_offset(self, va: int) -> int:
        for s in self.sections:
            delta = va - int(s["va"])
            if 0 <= delta < int(s["rawSize"]):
                return int(s["rawOffset"]) + delta
        raise ProofError(f"VA 0x{va:08x} is not physically mapped")

    def bytes_at(self, va: int, size: int) -> bytes:
        off = self.va_to_offset(va)
        data = self.data[off:off + size]
        if len(data) != size:
            raise ProofError(f"short read at VA 0x{va:08x}")
        return data

    def section(self, name: str) -> dict:
        rows = [s for s in self.sections if s["name"] == name]
        if len(rows) != 1:
            raise ProofError(f"expected exactly one {name} section")
        return rows[0]


def validate_map(path: Path) -> dict[str, int]:
    raw = path.read_bytes()
    if len(raw) != EXPECTED_MAP_BYTES:
        raise ProofError(f"MAP byte count mismatch: {len(raw)}")
    if sha256(raw) != EXPECTED_MAP_SHA256:
        raise ProofError("MAP SHA-256 mismatch")
    text = raw.decode("ascii", errors="strict")
    out: dict[str, int] = {}
    for name, expected in SYMBOLS.items():
        # Public/data lines contain the absolute VA as an eight-hex-digit token.
        candidates = [line for line in text.splitlines() if name in line and f"{expected:08x}" in line.lower()]
        if not candidates:
            raise ProofError(f"MAP does not bind {name} to 0x{expected:08x}")
        out[name] = expected
    return out


def validate_pdb(path: Path | None) -> dict | None:
    if path is None:
        return None
    raw = path.read_bytes()
    if len(raw) != EXPECTED_PDB_BYTES:
        raise ProofError(f"PDB byte count mismatch: {len(raw)}")
    if sha256(raw) != EXPECTED_PDB_SHA256:
        raise ProofError("PDB SHA-256 mismatch")
    if not raw.startswith(b"Microsoft C/C++ MSF 7.00\r\n\x1aDS"):
        raise ProofError("unexpected PDB/MSF magic")
    return {"bytes": len(raw), "sha256": sha256(raw)}


def exact_ranges(pe: PE) -> list[dict]:
    rows = []
    for name, (start, end, expected) in RANGES.items():
        data = pe.bytes_at(start, end - start)
        actual = sha256(data)
        if actual != expected:
            raise ProofError(f"{name}: byte-range SHA mismatch {actual}")
        rows.append({
            "name": name,
            "startVaHex": f"0x{start:08X}",
            "endVaHexExclusive": f"0x{end:08X}",
            "bytes": len(data),
            "sha256": actual,
        })
    return rows


def direct_call_sites(pe: PE, target: int) -> list[int]:
    text = pe.section(".text")
    raw = pe.data[int(text["rawOffset"]):int(text["rawOffset"]) + int(text["rawSize"])]
    base = int(text["va"])
    result = []
    for i in range(0, len(raw) - 5):
        if raw[i] != 0xE8:
            continue
        rel = struct.unpack_from("<i", raw, i + 1)[0]
        call_va = base + i
        if call_va + 5 + rel == target:
            result.append(call_va)
    return result


def build(exe_path: Path, map_path: Path, pdb_path: Path | None) -> dict:
    pe = PE(exe_path)
    map_symbols = validate_map(map_path)
    pdb = validate_pdb(pdb_path)
    ranges = exact_ranges(pe)

    if pe.bytes_at(PROBABILITY_SCALE_VA, 4) != PROBABILITY_SCALE_RAW:
        raise ProofError("probability scale constant bytes changed")
    probability_scale = struct.unpack("<f", PROBABILITY_SCALE_RAW)[0]
    if pe.bytes_at(ZERO_FLOAT_VA, 4) != ZERO_FLOAT_RAW:
        raise ProofError("zero probability comparison constant changed")

    expected_xrefs = {
        "SND_AliasGetNeverPlayedTwice": [0x008B29B6],
        "SND_AliasHasPlayed": [0x008B29C3],
        "SND_AliasSetNeverPlayedTwice": [0x008B30A3, 0x008B3136, 0x008B315C],
        "SND_PickSoundAliasFromList": [0x008ACE6C, 0x008B2983],
        "SND_CheckValidSecondary": [0x008B29F8],
    }
    xrefs = {}
    for name, expected in expected_xrefs.items():
        actual = direct_call_sites(pe, SYMBOLS[name])
        if actual != expected:
            raise ProofError(f"{name}: xrefs changed: {[hex(x) for x in actual]}")
        xrefs[name] = [f"0x{x:08X}" for x in actual]

    # Every call to the mutating helper passes literal true (push 1) immediately before alias push/call.
    for va in expected_xrefs["SND_AliasSetNeverPlayedTwice"]:
        call_off = pe.va_to_offset(va)
        window = pe.data[call_off - 8:call_off]
        if b"\x6a\x01" not in window:
            raise ProofError(f"setter call at 0x{va:08x} does not have local push-true evidence")

    return {
        "format": FORMAT,
        "authority": "exact-pc-dedicated-server-build-only",
        "source": {
            "exe": {"bytes": EXPECTED_EXE_BYTES, "sha256": EXPECTED_EXE_SHA256},
            "map": {"bytes": EXPECTED_MAP_BYTES, "sha256": EXPECTED_MAP_SHA256},
            "pdb": pdb,
            "imageBaseHex": f"0x{pe.image_base:08X}",
        },
        "symbols": {name: f"0x{va:08X}" for name, va in map_symbols.items()},
        "exactByteRanges": ranges,
        "directCallSites": xrefs,
        "layoutInputs": {
            "SndAliasListBytes": 20,
            "SndAliasBytes": 96,
            "SndAliasListCountOffsetHex": "0x0C",
            "SndAliasListSequenceOffsetHex": "0x10",
            "SndAliasSecondaryNameOffsetHex": "0x0C",
            "SndAliasAssetIdOffsetHex": "0x10",
            "SndAliasFlags0OffsetHex": "0x18",
            "SndAliasFlags1OffsetHex": "0x1C",
            "SndAliasContextTypeOffsetHex": "0x24",
            "SndAliasContextValueOffsetHex": "0x28",
            "SndAliasProbabilityOffsetHex": "0x58",
        },
        "selector": {
            "function": "SND_PickSoundAliasFromList",
            "prototypeFromMap": "SndAlias* SND_PickSoundAliasFromList(const SndAliasList*, int, SndEntHandle)",
            "rules": [
                "null list or count==0 returns null",
                "serialized list count is asserted below 64 and locally capped at 64",
                "variants are walked at exact 0x60-byte SndAlias stride",
                "contextType==0 is accepted without a context comparison",
                "nonzero contextType is resolved through SND_FindContextIndex and can match entity-specific context state; contextValue==0 is also accepted; otherwise the global context value is compared",
                "if the first accepted candidate has flags0 bit31, selection uses RandWithSeed on a local seed derived from alias-list address plus objectId",
                "otherwise, if the DWORD at g_snd+0x288 is nonzero, RandWithSeed mutates that global seed and selection is modulo accepted-candidate count",
                "otherwise libc rand() is used; for more than two accepted candidates it retries an immediate repeat of aliasList.sequence, with at most 100 attempts",
                "the chosen accepted-candidate index is written to aliasList.sequence at +0x10",
                "probability and never-played-twice are not evaluated inside this selector",
            ],
            "entityContextHandleMaskHex": "0x0FFF",
            "entityContextIndexLimitHex": "0x0700",
            "globalSeedAddressHex": "0x07E53188",
            "globalSeedOffsetFromGSndHex": "0x288",
        },
        "neverPlayedTwice": {
            "authoringEnable": "flags1 bit0, returned by SND_AliasGetNeverPlayedTwice",
            "runtimeHasPlayed": "flags1 bit1, returned by SND_AliasHasPlayed",
            "mutator": "SND_AliasSetNeverPlayedTwice writes flags1 bit1 to the supplied boolean despite its historical/PDB name",
            "playGate": "after variant selection, if bit0 is set and bit1 is already set, SND_PlaySoundAlias returns failure before Secondary processing",
            "successfulDirectStart": "after SD_StartAlias succeeds, all new-start success returns in the proven slice call SND_AliasSetNeverPlayedTwice(alias,true)",
            "setterCallCountInText": 3,
            "setterFalseCallCountThroughHelper": 0,
        },
        "secondary": {
            "order": "selected variant -> never-played-twice gate -> selected variant secondaryName -> direct assetId check",
            "lookup": "selected secondaryName is hashed with SND_HashName and looked up with SND_BankAliasLookupCache",
            "missingImmediateTarget": "if lookup returns null, Secondary playback is skipped and the selected primary continues",
            "validation": [
                "SND_CheckValidSecondary compares flags0 bit0 on primary versus immediate secondary-list head and rejects a looping/non-looping mismatch",
                "it walks downstream secondaryName links through SND_FindAlias using list heads, case-insensitively rejecting a chain that resolves back to the primary alias name",
                "the validation walk is bounded to ten downstream steps",
            ],
            "validTarget": "the complete secondary alias list is recursively passed to SND_PlaySoundAlias before the primary direct assetId check",
            "recursiveReturn": "the secondary recursive playback result is not used as the primary function return value",
        },
        "zeroAssetId": {
            "directBehavior": "after optional Secondary recursion, selected alias assetId==0 does not start a direct physical sound",
            "subtitleBehavior": "if the selected zero-direct alias has a subtitle pointer, SND_SubtitleNotify is called with 5000 ms",
            "returnValue": -1,
            "hasPlayedBit": "the zero-direct path returns before the proven successful-direct-start bit1 setter calls",
        },
        "probability": {
            "field": "selected SndAlias byte at +0x58",
            "scaleRawHex": PROBABILITY_SCALE_RAW.hex(),
            "scaleFloat": probability_scale,
            "equation": "p = uint8(probability) * (1/255)",
            "rule": "if p>0, random() is called and playback is rejected only when random()>p; if p==0, this random rejection gate is bypassed",
            "selectionOrder": "probability is evaluated after variant selection and after the direct assetId==0 return path",
        },
        "unresolved": [
            "retail t6mp.exe equivalence is not established",
            "the high-level meaning/owner names of the entity-context table and g_snd+0x288 seed are not promoted beyond the exact accesses above",
            "SndAlias stop_on_play runtime semantics are not closed in v1",
            "all lower-level voice/driver semantics are outside this v1 proof unless explicitly stated above",
        ],
        "proofBoundary": "Every promoted rule above is bounded to exact MAP-named functions and exact machine-byte slices in the SHA-pinned PC dedicated-server executable. Historical T5 source was used only to locate candidate concepts and is not part of the authority chain. No server rule is promoted to the retail t6mp.exe client without an independent client proof.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", type=Path, required=True)
    ap.add_argument("--map", dest="map_path", type=Path, required=True)
    ap.add_argument("--pdb", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.exe.resolve(), args.map_path.resolve(), args.pdb.resolve() if args.pdb else None)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "authority": doc["authority"],
        "exactByteRangeCount": len(doc["exactByteRanges"]),
        "setterCallCountInText": doc["neverPlayedTwice"]["setterCallCountInText"],
        "probabilityScale": doc["probability"]["scaleFloat"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

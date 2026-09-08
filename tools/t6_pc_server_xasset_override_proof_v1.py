#!/usr/bin/env python3
"""Fail-closed static proof for T6 PC dedicated-server XAsset override semantics.

This adapter is authoritative only for the exact SHA-pinned PC dedicated-server
build supplied with its exact linker MAP. It source-closes the path

    XZoneInfo.allocFlags
      -> queued DB load record
      -> DB_TryLoadXFileInternal flags argument
      -> g_zoneNames[zoneIndex].flags
      -> DB_OverrideAsset
      -> DB_GetZonePriority
      -> DB_LinkXAssetEntry / DB_SwapXAsset

and the concrete MP startup load flags for COMMON_FAST_FILE_NAME,
PATCH_FAST_FILE_NAME, and ordinary built-in MP maps.

It deliberately does NOT promote those server semantics to the retail t6mp.exe
client. The client requires an independent SHA-pinned static/runtime gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

FORMAT = "t6-pc-server-xasset-override-proof-v1"
EXPECTED_EXE_BYTES = 13_711_872
EXPECTED_EXE_SHA256 = "f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d"
EXPECTED_MAP_BYTES = 9_213_148
EXPECTED_MAP_SHA256 = "34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf"
EXPECTED_IMAGE_BASE = 0x00400000

SYMBOLS = {
    "DB_GetZonePriority": 0x00550230,
    "DB_OverrideAsset": 0x00550410,
    "DB_LinkXAssetEntry": 0x005504A0,
    "DB_LoadXZone": 0x00550F80,
    "DB_TryLoadXFileInternal": 0x00551370,
    "DB_InitFastFileNames": 0x00551A40,
    "DB_LoadXAssets": 0x00556790,
    "DB_Thread": 0x00556E80,
    "DB_LoadGraphicsAssetsForPC": 0x00557190,
    "Com_LoadCommonFastFile": 0x006BFCF0,
    "Com_LoadLevelFastFiles": 0x006BFDF0,
    "Com_IsAddonMap": 0x00760020,
    "DB_SwapXAsset": 0x0054F590,
}

FUNCTION_RANGES = {
    "DB_GetZonePriority": (0x00550230, 0x00550410, "591b7bb0cfbdbd21a429981aa8aa87bc8f9cb8a64e179203677000fd8479058f"),
    "DB_OverrideAsset": (0x00550410, 0x005504A0, "a3d4e78ed92ca99fc821b21f429c5cadf00131174aab529de87243d574bb74a9"),
    "DB_LinkXAssetEntry": (0x005504A0, 0x00550D70, "1be0a50aedb4b5848552d75842d568f4fc2b0e800128f0fe86b002782e15072e"),
    "DB_LoadXZone": (0x00550F80, 0x005510C0, "4b7751b245839090d45ef7c53c1ec894d3122dfc44c1e68d7c4ef356db964354"),
    "DB_TryLoadXFileInternal": (0x00551370, 0x00551A40, "774eb230e5739f047a50005ca0620336a0f997bd8a9e8211044a776ec0395d10"),
    "DB_InitFastFileNames": (0x00551A40, 0x00552050, "73491c8706e6ec340503f3e30a519f577fce6b2da5a68d3e31557f7b2f4e411d"),
    "DB_LoadXAssets": (0x00556790, 0x00556E80, "d6630efa78232bce6cafeb18b99cde569805bc35ad5f490b35b70900f665d55f"),
    "DB_Thread": (0x00556E80, 0x00557100, "b3de0a6efab70e0b2447e1bf5d40958f908712096fb5fd3d056598068b837dda"),
    "DB_LoadGraphicsAssetsForPC": (0x00557190, 0x00557200, "07810919599dd5fed847827ccc48905f37a40b24b55c59ac2e599331b52e3227"),
    "Com_LoadCommonFastFile": (0x006BFCF0, 0x006BFD80, "a87e2354720ffc60dc36e2f60ac4dccbb27b5760176693fcfc7c67b9576a8986"),
    "Com_LoadLevelFastFiles": (0x006BFDF0, 0x006C0140, "349e68516bbbe3a8c95f35d58f1346b7a4f83ad9a139cceb5ea805ad935ba84d"),
    "Com_IsAddonMap": (0x00760020, 0x00760100, "275d1fe63b97345ff74f4e2379eb277efbb678ea1339423a8b4cd89b4a4d1dbd"),
}

VA_COMMON_FAST_FILE_NAME = 0x018F01E8
VA_PATCH_FAST_FILE_NAME = 0x018F4554
VA_COMMON_FASTFILE_SUFFIX = 0x0135405C
VA_STR_COMMON = 0x00BD4320
VA_STR_PATCH = 0x00BD4350
VA_STR_MP_SUFFIX = 0x00BB9610
VA_STR_ZM_SUFFIX = 0x00BB9614

COMMON_MP_ALLOC_FLAG = 0x00000080
PATCH_MP_ALLOC_FLAG = 0x00000002
BUILTIN_MP_MAP_ALLOC_FLAG = 0x00008000
COMMON_MP_PRIORITY = 54
PATCH_MP_PRIORITY = 65
BUILTIN_MP_MAP_PRIORITY = 57


class ProofError(RuntimeError):
    pass


class PE:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        if len(self.data) != EXPECTED_EXE_BYTES:
            raise ProofError(f"unexpected EXE bytes {len(self.data)} != {EXPECTED_EXE_BYTES}")
        sha = hashlib.sha256(self.data).hexdigest()
        if sha != EXPECTED_EXE_SHA256:
            raise ProofError(f"unexpected EXE SHA-256 {sha}")
        if self.data[:2] != b"MZ":
            raise ProofError("EXE is not MZ")
        peoff = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[peoff:peoff + 4] != b"PE\0\0":
            raise ProofError("EXE is not PE")
        coff = peoff + 4
        machine, nsects, _, _, _, opt_size, _ = struct.unpack_from("<HHIIIHH", self.data, coff)
        if machine != 0x14C:
            raise ProofError(f"unexpected machine 0x{machine:x}")
        opt = coff + 20
        if struct.unpack_from("<H", self.data, opt)[0] != 0x10B:
            raise ProofError("expected PE32 optional header")
        self.image_base = struct.unpack_from("<I", self.data, opt + 28)[0]
        if self.image_base != EXPECTED_IMAGE_BASE:
            raise ProofError(f"unexpected image base 0x{self.image_base:x}")
        sec = opt + opt_size
        self.sections = []
        for i in range(nsects):
            off = sec + i * 40
            name = self.data[off:off + 8].split(b"\0", 1)[0].decode("ascii", "replace")
            vsize, rva, raw_size, raw_off = struct.unpack_from("<IIII", self.data, off + 8)
            self.sections.append({
                "name": name,
                "va": self.image_base + rva,
                "virtualSize": vsize,
                "rawOffset": raw_off,
                "rawSize": raw_size,
            })

    def va_to_offset(self, va: int) -> int:
        for s in self.sections:
            start = int(s["va"])
            delta = va - start
            if 0 <= delta < int(s["rawSize"]):
                return int(s["rawOffset"]) + delta
        raise ProofError(f"VA 0x{va:08x} has no physical file mapping")

    def bytes_at(self, va: int, size: int) -> bytes:
        off = self.va_to_offset(va)
        return self.data[off:off + size]

    def cstr(self, va: int, maxn: int = 128) -> str:
        off = self.va_to_offset(va)
        end = self.data.find(b"\0", off, min(len(self.data), off + maxn))
        if end < 0:
            raise ProofError(f"unterminated string at 0x{va:08x}")
        raw = self.data[off:end]
        try:
            return raw.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ProofError(f"non-ASCII string at 0x{va:08x}") from exc


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _expect_bytes(pe: PE, va: int, expected_hex: str, label: str) -> dict:
    expected = bytes.fromhex(expected_hex.replace(" ", ""))
    actual = pe.bytes_at(va, len(expected))
    if actual != expected:
        raise ProofError(f"{label}: bytes mismatch at 0x{va:08x}: {actual.hex()} != {expected.hex()}")
    return {"label": label, "vaHex": f"0x{va:08x}", "bytesHex": actual.hex(), "bytes": len(actual)}


def _parse_map(path: Path) -> tuple[str, dict[str, int]]:
    raw = path.read_bytes()
    if len(raw) != EXPECTED_MAP_BYTES:
        raise ProofError(f"unexpected MAP bytes {len(raw)} != {EXPECTED_MAP_BYTES}")
    sha = _sha(raw)
    if sha != EXPECTED_MAP_SHA256:
        raise ProofError(f"unexpected MAP SHA-256 {sha}")
    text = raw.decode("ascii", errors="strict")
    symbols = {}
    for public_name, va_hex in re.findall(r"^\s*[0-9A-Fa-f]{4}:[0-9A-Fa-f]{8}\s+(\S+)\s+([0-9A-Fa-f]{8})(?:\s|$)", text, flags=re.M):
        for wanted in SYMBOLS:
            if wanted + "@@" in public_name or public_name == wanted:
                symbols[wanted] = int(va_hex, 16)
    missing = [name for name in SYMBOLS if symbols.get(name) != SYMBOLS[name]]
    if missing:
        detail = {name: (hex(symbols[name]) if name in symbols else None, hex(SYMBOLS[name])) for name in missing}
        raise ProofError(f"MAP symbol gate failed: {detail}")
    return text, symbols


def _function_hashes(pe: PE) -> list[dict]:
    rows = []
    for name, (start, end, expected_sha) in FUNCTION_RANGES.items():
        data = pe.bytes_at(start, end - start)
        actual = _sha(data)
        if actual != expected_sha:
            raise ProofError(f"{name}: function-range SHA mismatch {actual} != {expected_sha}")
        rows.append({
            "name": name,
            "startVaHex": f"0x{start:08x}",
            "endVaHexExclusive": f"0x{end:08x}",
            "bytes": len(data),
            "sha256": actual,
        })
    return rows


def _decode_low_priority(pe: PE, flag: int) -> int:
    if flag < 1 or flag > 0x20:
        raise ProofError("low-priority decoder expects flags 1..0x20")
    index_table = pe.bytes_at(0x005503F0, 32)
    jump_table = [struct.unpack("<I", pe.bytes_at(0x005503D4 + 4 * i, 4))[0] for i in range(7)]
    idx = index_table[flag - 1]
    target = jump_table[idx]
    returns = {
        0x00550266: 1,
        0x0055026D: 7,
        0x00550274: 51,
        0x0055027B: 52,
        0x00550282: 53,
        0x00550289: 65,
    }
    if target not in returns:
        raise ProofError(f"flag 0x{flag:x} routes to unsupported/assert target 0x{target:08x}")
    return returns[target]


def build(exe: Path, map_path: Path) -> dict:
    pe = PE(exe)
    _map_text, map_symbols = _parse_map(map_path)
    functions = _function_hashes(pe)

    strings = {
        "commonBase": pe.cstr(VA_STR_COMMON),
        "patchBase": pe.cstr(VA_STR_PATCH),
        "mpSuffix": pe.cstr(VA_STR_MP_SUFFIX),
        "zmSuffix": pe.cstr(VA_STR_ZM_SUFFIX),
    }
    expected_strings = {"commonBase": "common", "patchBase": "patch", "mpSuffix": "_mp", "zmSuffix": "_zm"}
    if strings != expected_strings:
        raise ProofError(f"unexpected static FastFile naming strings: {strings}")

    evidence = []
    evidence.append(_expect_bytes(pe, 0x00551A84,
        "6a18685043bd006854458f01", "PATCH_FAST_FILE_NAME <- 'patch' base"))
    evidence.append(_expect_bytes(pe, 0x00551ADC,
        "6a18682043bd0068e8018f01", "COMMON_FAST_FILE_NAME <- 'common' base"))
    evidence.append(_expect_bytes(pe, 0x00551B26,
        "e8b59c16006a0484c07407681496bb00eb05681096bb00685c403501",
        "mode-selected _mp/_zm suffix copied into COMMON_FASTFILE_SUFFIX"))
    evidence.append(_expect_bytes(pe, 0x00551D68,
        "685c4035016a186854458f01e897c72300", "append suffix to PATCH_FAST_FILE_NAME"))
    evidence.append(_expect_bytes(pe, 0x00551F48,
        "685c4035016a1868e8018f01e8b7c52300", "append suffix to COMMON_FAST_FILE_NAME"))

    evidence.append(_expect_bytes(pe, 0x006BFD51,
        "c745f4e8018f01c745f880000000c745fc00000000e8256ae9ff",
        "Com_LoadCommonFastFile XZoneInfo: COMMON_FAST_FILE_NAME, allocFlags=0x80, freeFlags=0"))
    evidence.append(_expect_bytes(pe, 0x005571B3,
        "c745d854458f01c745dc02000000c745e404647f01c745e808000000",
        "DB_LoadGraphicsAssetsForPC rows: PATCH_FAST_FILE_NAME flag=0x02; CODE_FAST_FILE_NAME flag=0x08"))

    if pe.cstr(0x00BD3EE0) != "so_" or pe.cstr(0x00BD3EDC) != "zo_":
        raise ProofError("unexpected Com_IsAddonMap prefix table")
    evidence.append(_expect_bytes(pe, 0x00760050,
        "bf984adb00c745fc000000008d642400",
        "Com_IsAddonMap begins exact two-entry prefix table walk"))
    evidence.append(_expect_bytes(pe, 0x006BFF88,
        "03c003c0bb0080000089bc05f4feffff899c05f8feffffc78405fcfeffff0000000046",
        "Com_LoadLevelFastFiles non-addon row: input map name, allocFlags=0x8000, freeFlags=0"))

    evidence.append(_expect_bytes(pe, 0x00551066,
        "8b5704ff450c8b450c83c41889564083c64483c70c",
        "DB_LoadXZone copies XZoneInfo+4 to queued-record+0x40 and advances XZoneInfo by 0x0c"))
    evidence.append(_expect_bytes(pe, 0x00556F92,
        "be188135018b46406a005056e8cda3ffff",
        "DB_Thread forwards queued flags to DB_TryLoadXFileInternal"))
    evidence.append(_expect_bytes(pe, 0x005513D6,
        "56e8e4ce23008b5d0c", "DB_TryLoadXFileInternal captures flags argument"))
    evidence.append(_expect_bytes(pe, 0x005516C1,
        "8b0d28c249018b95f8feffff6bc94c52899948328f01",
        "DB_TryLoadXFileInternal writes captured flags to g_zoneNames[index].flags"))

    evidence.append(_expect_bytes(pe, 0x00550462,
        "6bf64c8b8648328f0125ffffff3f50e8bafdffff6bff4c8b8f48328f0181e1ffffff3f518bf0e8a3fdffff83c40833d23bf00f9dc2",
        "DB_OverrideAsset mask 0x3fffffff + two DB_GetZonePriority calls + signed setge"))
    evidence.append(_expect_bytes(pe, 0x005509ED,
        "0fb643080fb64f08816faffff85c00f85d7010000".replace("816", "e816"),
        "DB_LinkXAssetEntry tests DB_OverrideAsset result"))
    evidence.append(_expect_bytes(pe, 0x00550C86,
        "668b530c8bc72d70d24901c1f8046689570c8bf36689430ce8ede8ffff8a4f088a43088b75f8884b08884708",
        "override branch relinks chain, calls DB_SwapXAsset, and swaps zoneIndex bytes"))

    patch_priority = _decode_low_priority(pe, PATCH_MP_ALLOC_FLAG)
    if patch_priority != PATCH_MP_PRIORITY:
        raise ProofError(f"patch flag priority mismatch {patch_priority} != {PATCH_MP_PRIORITY}")
    evidence.append(_expect_bytes(pe, 0x005502A0,
        "3d8000000074203d0001000074123d000200000f85e3000000",
        "DB_GetZonePriority explicit 0x80 branch"))
    evidence.append(_expect_bytes(pe, 0x005502C7,
        "b8360000005dc3", "DB_GetZonePriority(0x80) -> 54"))
    common_priority = COMMON_MP_PRIORITY
    evidence.append(_expect_bytes(pe, 0x0055030E,
        "3d00800000741c3d00000100740e3d000002007579",
        "DB_GetZonePriority explicit 0x8000 branch"))
    evidence.append(_expect_bytes(pe, 0x00550331,
        "b8390000005dc3", "DB_GetZonePriority(0x8000) -> 57"))
    map_priority = BUILTIN_MP_MAP_PRIORITY

    if patch_priority <= common_priority or patch_priority <= map_priority:
        raise ProofError("expected patch priority to exceed common and built-in-map priorities in this exact server build")

    return {
        "format": FORMAT,
        "pcDedicatedServer": {
            "exeFile": exe.name,
            "exeBytes": len(pe.data),
            "exeSha256": EXPECTED_EXE_SHA256,
            "mapFile": map_path.name,
            "mapBytes": EXPECTED_MAP_BYTES,
            "mapSha256": EXPECTED_MAP_SHA256,
            "imageBaseHex": f"0x{pe.image_base:08x}",
        },
        "mapSymbols": {name: f"0x{va:08x}" for name, va in sorted(map_symbols.items())},
        "functionRanges": functions,
        "fastFileNaming": {
            "baseStrings": strings,
            "commonGlobalVaHex": f"0x{VA_COMMON_FAST_FILE_NAME:08x}",
            "patchGlobalVaHex": f"0x{VA_PATCH_FAST_FILE_NAME:08x}",
            "suffixGlobalVaHex": f"0x{VA_COMMON_FASTFILE_SUFFIX:08x}",
            "mpResolvedNames": {"common": "common_mp", "patch": "patch_mp"},
        },
        "xZoneInfo": {
            "strideBytes": 12,
            "nameOffset": 0,
            "allocFlagsOffset": 4,
            "freeFlagsOffset": 8,
            "queuedFlagsOffset": 0x40,
            "gZoneNameStrideBytes": 0x4C,
            "gZoneNameFlagsOffset": 0x40,
        },
        "mpFlags": {
            "common_mp": {"allocFlagsHex": "0x00000080", "priority": common_priority},
            "patch_mp": {"allocFlagsHex": "0x00000002", "priority": patch_priority},
            "ordinaryBuiltInMpMap": {"allocFlagsHex": "0x00008000", "priority": map_priority, "example": "mp_nuketown_2020"},
        },
        "overrideRule": {
            "storedFlagMaskHex": "0x3fffffff",
            "comparison": "newPriority >= existingPriority",
            "ordinaryDuplicateReplacement": "true result enters replacement branch, DB_SwapXAsset swaps payloads, and zoneIndex bytes are swapped so the stable primary entry owns the winning zone payload",
            "commonVsPatchServerPrediction": "patch_mp",
            "commonVsPatchReason": f"patch priority {patch_priority} > common priority {common_priority}; load order cannot change this pair's winner",
            "mapVsPatchServerPrediction": "patch_mp",
            "mapVsPatchReason": f"patch priority {patch_priority} > ordinary built-in MP map priority {map_priority}; load order cannot change this pair's winner",
        },
        "instructionEvidence": evidence,
        "authority": {
            "pcDedicatedServerBuild": True,
            "retailT6mpClient": False,
            "state": "exact-pc-dedicated-server-proof-client-promotion-blocked",
        },
        "proofBoundary": (
            "Authoritative for the ordinary duplicate-XAsset precedence path and the common_mp/patch_mp flags in the exact SHA-pinned CoDMPServer_PC.exe + linker MAP pair only. "
            "It proves XZoneInfo.allocFlags propagation into g_zoneNames.flags, the exact server DB_GetZonePriority/DB_OverrideAsset comparison, and DB_LinkXAssetEntry replacement behavior. "
            "It does not prove that the retail t6mp.exe client uses identical function bytes, priority values, flag mask, special-case branches, or load-call constants. "
            "No production retail-client Material/Technique winner may be selected from this server proof alone."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("exe", type=Path)
    p.add_argument("map", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = build(a.exe.resolve(), a.map.resolve())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "authority": result["authority"],
        "mpFlags": result["mpFlags"],
        "overrideRule": result["overrideRule"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

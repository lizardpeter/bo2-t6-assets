#!/usr/bin/env python3
"""Promote exact T6 PC server Material_CreateLayered construction semantics.

The proof consumes the exact structural disassembly emitted by
`t6_pc_server_material_create_layered_probe_v1.py`, the SHA-pinned server PE,
the pinned T6 asset declarations from OpenAssetTools, and the already-frozen
layered table sort manifest.  Promotion is fail-closed on exact instruction
bytes and exact structure declarations.

This proves dedicated-server construction semantics only.  It does not claim
retail-client executable equivalence and it does not reconstruct historical
standalone Material serialization that is absent from a retail FastFile dump.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

EXE_SHA256 = "f67eb68a494b93b5b229985205bdc94e26fdfe677663410e2207c25f6f27a55d"
MAP_SHA256 = "34e16e517072031629307ffa0520d59f3c586539b943d081f60c59ee9ce1c3bf"
OAT_COMMIT = "9dca965366541504b71fa8cfb7ac049cb9b717e1"
CREATE_LAYERED_SHA256 = "505da556ae793f0a27a5e393dff0c9c1ff8f0be4a42c2935c5790c9c29535e42"
COMPARATOR_SHA256 = "89c3ef79d0956caceb677fd742d376f28895d8788fd9ad7c1e88a4535d840952"
IMAGE_BASE = 0x00400000
FORMAT = "t6-pc-server-layered-material-construction-v1"

# Exact machine-code anchors.  These are deliberately narrow enough to make a
# semantic change fail, while the parent structural probe separately freezes the
# complete 1696-byte body hash and exact instruction accounting.
EXPECTED = {
    # Precompute hash("colorTint", 0), count source rows, and add a default
    # constant when a layer does not contain the colorTint hash.
    0x00A4DA7D: "56",
    0x00A4DA80: "6800cbd100",
    0x00A4DABA: "e851ccfdff",
    0x00A4DAC2: "898590feffff",
    0x00A4DAEB: "8a4854",
    0x00A4DAEE: "008daffeffff",
    0x00A4DAF4: "0fb64855",
    0x00A4DAF8: "025855",
    0x00A4DB04: "8b4064",
    0x00A4DB16: "3938",
    0x00A4DB28: "fec3",

    # Generated Material name: base + '(' + source names joined by ':' + ')'.
    0x00A4DC54: "e87703d4ff",
    0x00A4DC5B: "68b447b900",
    0x00A4DC62: "e8a908d4ff",
    0x00A4DC7A: "8b11",
    0x00A4DC81: "e88a08d4ff",
    0x00A4DC91: "68c41fb900",
    0x00A4DC98: "e87308d4ff",
    0x00A4DCA7: "68ac47b900",
    0x00A4DCAE: "e85d08d4ff",

    # Layer count assertion and one-byte layer suffix digit.
    0x00A4DDA8: "85d2",
    0x00A4DDAC: "8d4230",
    0x00A4DDAF: "8885affeffff",
    0x00A4DDB7: "c685affeffff00",

    # 16-byte MaterialTextureDef copy, suffix into nameEnd, incremental hash.
    0x00A4DDF0: "f30f7e01",
    0x00A4DDFA: "660fd603",
    0x00A4DDFE: "f30f7e4108",
    0x00A4DE03: "660fd64308",
    0x00A4DE0C: "884305",
    0x00A4DE0F: "8b03",
    0x00A4DE13: "c1e105",
    0x00A4DE16: "03c8",
    0x00A4DE18: "0fbe85affeffff",
    0x00A4DE1F: "33c8",
    0x00A4DE21: "890b",

    # Mature flag is recomputed from texture semantic and an image-owned string.
    0x00A4DE23: "8b4b0c",
    0x00A4DE26: "8b4148",
    0x00A4DE35: "8a4307",
    0x00A4DE44: "3c01",
    0x00A4DE48: "84c0",
    0x00A4DE57: "e8e41c0600",
    0x00A4DE67: "0f95c0",
    0x00A4DE6C: "32c0",
    0x00A4DE7A: "884308",

    # 32-byte MaterialConstantDef copy and bounded 12-byte name suffixing.
    0x00A4DEE0: "f30f7e01",
    0x00A4DEE4: "660fd606",
    0x00A4DEE8: "f30f7e4108",
    0x00A4DEED: "660fd64608",
    0x00A4DEF2: "f30f7e4110",
    0x00A4DEF7: "660fd64610",
    0x00A4DEFC: "f30f7e4118",
    0x00A4DF01: "660fd64618",
    0x00A4DF10: "807c060400",
    0x00A4DF18: "83f80c",
    0x00A4DF25: "88540604",
    0x00A4DF2C: "83fa0c",
    0x00A4DF31: "c644060500",
    0x00A4DF36: "8b06",
    0x00A4DF3A: "c1e205",
    0x00A4DF3D: "03d0",
    0x00A4DF3F: "0fbe85affeffff",
    0x00A4DF46: "33d0",
    0x00A4DF48: "8916",
    0x00A4DF56: "3901",
    0x00A4DF5A: "c685aefeffff01",

    # Missing colorTint: copy literal name, hash, and exact colorWhite vec4.
    0x00A4DF86: "80bdaefeffff00",
    0x00A4DF93: "6a0c",
    0x00A4DF98: "6800cbd100",
    0x00A4DF9E: "e85d050600",
    0x00A4DFA9: "890e",
    0x00A4DFAB: "f30f1005507dc600",
    0x00A4DFB9: "f30f114610",
    0x00A4DFBE: "f30f1005547dc600",
    0x00A4DFC6: "f30f114614",
    0x00A4DFCB: "f30f1005587dc600",
    0x00A4DFD6: "f30f114618",
    0x00A4DFDB: "f30f10055c7dc600",
    0x00A4DFE3: "f30f11461c",
    0x00A4DFF0: "803c0300",
    0x00A4DFF7: "83f80c",
    0x00A4E001: "880c03",
    0x00A4E004: "83fa0c",
    0x00A4E009: "c644030100",
    0x00A4E00E: "8b06",
    0x00A4E012: "c1e205",
    0x00A4E015: "03d0",
    0x00A4E017: "0fbec1",
    0x00A4E01A: "33d0",
    0x00A4E01C: "8916",

    # Exact constructed-entry accounting before final qsort.
    0x00A4E03D: "2b5f60",
    0x00A4E040: "0fb64754",
    0x00A4E044: "c1fb04",
    0x00A4E070: "2b7764",
    0x00A4E073: "0fb64755",
    0x00A4E077: "c1fe05",

    # Final exact table sorts.
    0x00A4E0A3: "0fb64f54",
    0x00A4E0A7: "8b5760",
    0x00A4E0AA: "6830d6a400",
    0x00A4E0AF: "6a10",
    0x00A4E0B3: "e858ff0500",
    0x00A4E0B8: "0fb64755",
    0x00A4E0BC: "8b4f64",
    0x00A4E0BF: "6830d6a400",
    0x00A4E0C4: "6a20",
    0x00A4E0C8: "e843ff0500",
}


class ProofError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise ProofError(msg)


def pe_sections(exe: bytes) -> list[tuple[str, int, int, int]]:
    pe = struct.unpack_from("<I", exe, 0x3C)[0]
    require(exe[pe:pe+4] == b"PE\0\0", "not a PE image")
    coff = pe + 4
    nsec = struct.unpack_from("<H", exe, coff + 2)[0]
    opt_size = struct.unpack_from("<H", exe, coff + 16)[0]
    st = coff + 20 + opt_size
    out = []
    for i in range(nsec):
        o = st + i * 40
        name = exe[o:o+8].split(b"\0", 1)[0].decode("ascii", "replace")
        _vsize, rva, raw_size, raw_off = struct.unpack_from("<IIII", exe, o + 8)
        out.append((name, IMAGE_BASE + rva, raw_size, raw_off))
    return out


def read_va(exe: bytes, sections: list[tuple[str, int, int, int]], va: int, n: int) -> bytes:
    for _name, start, raw_size, raw_off in sections:
        if start <= va and va + n <= start + raw_size:
            p = raw_off + va - start
            return exe[p:p+n]
    raise ProofError(f"VA range not raw-backed: 0x{va:08X}+{n}")


def cstring_at(exe: bytes, sections: list[tuple[str, int, int, int]], va: int, max_n: int = 64) -> bytes:
    raw = read_va(exe, sections, va, max_n)
    z = raw.find(b"\0")
    require(z >= 0, f"unterminated raw-backed string at 0x{va:08X}")
    return raw[:z]


def normalize_struct_body(body: str) -> str:
    body = re.sub(r"//.*", "", body)
    return " ".join(body.split())


def find_struct(header: str, name: str) -> str:
    # T6_Assets.h has ordinary declarations for the two records used here.
    m = re.search(rf"struct(?:\s+type_align\([^)]*\))?\s+{re.escape(name)}\s*\{{(?P<body>.*?)\}};", header, re.S)
    require(m is not None, f"pinned OAT structure {name} not found")
    return normalize_struct_body(m.group("body"))


def validate_oat(header: str) -> dict:
    tex = find_struct(header, "MaterialTextureDef")
    con = find_struct(header, "MaterialConstantDef")
    tex_fields = [
        "unsigned int nameHash;",
        "char nameStart;",
        "char nameEnd;",
        "MaterialTextureDefSamplerState samplerState;",
        "unsigned char semantic;",
        "bool isMatureContent;",
        "char pad[3];",
        "GfxImage* image;",
    ]
    pos = -1
    for field in tex_fields:
        nxt = tex.find(field, pos + 1)
        require(nxt >= 0, f"MaterialTextureDef field changed/missing: {field}")
        require(nxt > pos, f"MaterialTextureDef field order changed: {field}")
        pos = nxt
    con_fields = ["unsigned int nameHash;", "char name[12];", "vec4_t literal;"]
    pos = -1
    for field in con_fields:
        nxt = con.find(field, pos + 1)
        require(nxt >= 0, f"MaterialConstantDef field changed/missing: {field}")
        require(nxt > pos, f"MaterialConstantDef field order changed: {field}")
        pos = nxt
    return {
        "openAssetToolsCommit": OAT_COMMIT,
        "materialTextureDef": {
            "sizeBytesObservedByConstructor": 16,
            "fieldOffsets": {
                "nameHash": 0,
                "nameStart": 4,
                "nameEnd": 5,
                "samplerState": 6,
                "semantic": 7,
                "isMatureContent": 8,
                "image": 12,
            },
            "pinnedDeclaration": tex,
        },
        "materialConstantDef": {
            "sizeBytesObservedByConstructor": 32,
            "fieldOffsets": {"nameHash": 0, "name": 4, "literal": 16},
            "nameBytes": 12,
            "pinnedDeclaration": con,
        },
    }


def validate_sort(sort_doc: dict) -> None:
    require(sort_doc.get("format") == "t6-pc-server-layered-material-sort-v1", "unexpected sort manifest format")
    auth = sort_doc.get("authority", {})
    require(auth.get("executableSha256") == EXE_SHA256, "sort executable authority changed")
    require(auth.get("mapSha256") == MAP_SHA256, "sort MAP authority changed")
    require(sort_doc.get("comparator", {}).get("sha256") == COMPARATOR_SHA256, "sort comparator changed")
    mc = sort_doc.get("materialCreateLayered", {})
    require(mc.get("sha256") == CREATE_LAYERED_SHA256, "sort constructor body changed")
    require(mc.get("textureSort", {}).get("elementSizeBytes") == 16, "texture sort element size changed")
    require(mc.get("constantSort", {}).get("elementSizeBytes") == 32, "constant sort element size changed")
    require(mc.get("textureSort", {}).get("qsortCallVa") == "0x00A4E0B3", "texture qsort call changed")
    require(mc.get("constantSort", {}).get("qsortCallVa") == "0x00A4E0C8", "constant qsort call changed")


def build(probe: dict, exe: bytes, header: str, sort_doc: dict) -> dict:
    require(sha256(exe) == EXE_SHA256, "server executable SHA-256 gate failed")
    require(probe.get("format") == "t6-pc-server-material-create-layered-probe-v1", "unexpected structural probe format")
    pa = probe.get("authority", {})
    require(pa.get("executableSha256") == EXE_SHA256, "structural probe executable authority changed")
    require(pa.get("mapSha256") == MAP_SHA256, "structural probe MAP authority changed")
    fn = probe.get("function", {})
    require(fn.get("startVa") == "0x00A4DA60", "constructor start changed")
    require(fn.get("endVaExclusive") == "0x00A4E100", "constructor end changed")
    require(fn.get("sizeBytes") == 1696, "constructor size changed")
    require(fn.get("sha256") == CREATE_LAYERED_SHA256, "constructor SHA changed")
    require(fn.get("instructionCount") == 494, "constructor instruction count changed")

    rows = probe.get("instructions")
    require(isinstance(rows, list), "structural instructions missing")
    by_va = {int(r["address"], 16): r for r in rows}
    require(len(by_va) == len(rows), "duplicate instruction addresses")
    for va, expected_hex in EXPECTED.items():
        row = by_va.get(va)
        require(row is not None, f"required instruction missing at 0x{va:08X}")
        require(row.get("bytes") == expected_hex, f"instruction bytes changed at 0x{va:08X}: {row.get('bytes')}")

    validate_sort(sort_doc)
    oat = validate_oat(header)
    sections = pe_sections(exe)

    literals = {
        "openParen": cstring_at(exe, sections, 0x00B947B4),
        "separator": cstring_at(exe, sections, 0x00B91FC4),
        "closeParen": cstring_at(exe, sections, 0x00B947AC),
        "colorTint": cstring_at(exe, sections, 0x00D1CB00),
    }
    expected_literals = {"openParen": b"(", "separator": b":", "closeParen": b")", "colorTint": b"colorTint"}
    require(literals == expected_literals, f"constructor literals changed: {literals!r}")

    white_raw = read_va(exe, sections, 0x00C67D50, 16)
    white = list(struct.unpack("<4f", white_raw))
    require(white_raw == bytes.fromhex("0000803f0000803f0000803f0000803f"), f"colorWhite bytes changed: {white_raw.hex()}")

    # Freeze the exact _mature bytes copied through two absolute dword loads.
    mature_raw = read_va(exe, sections, 0x00D1C9C4, 8)
    require(mature_raw == b"_mature\0", f"_mature literal bytes changed: {mature_raw!r}")

    return {
        "format": FORMAT,
        "authority": {
            "executable": "CoDMPServer_PC.exe",
            "executableSha256": EXE_SHA256,
            "map": "CoDMPServer_PC.map",
            "mapSha256": MAP_SHA256,
            "materialCreateLayeredVa": "0x00A4DA60",
            "materialCreateLayeredEndVaExclusive": "0x00A4E100",
            "materialCreateLayeredSha256": CREATE_LAYERED_SHA256,
            "materialCreateLayeredInstructionCount": 494,
            "openAssetToolsCommit": OAT_COMMIT,
            "openAssetToolsT6AssetsHeaderSha256": sha256(header.encode("utf-8")),
            "sortManifestFormat": sort_doc["format"],
            "sortComparatorSha256": COMPARATOR_SHA256,
        },
        "structures": oat,
        "generatedMaterialName": {
            "rule": "baseName + '(' + sourceMaterialName[0] + ':' + ... + sourceMaterialName[layerCount-1] + ')'",
            "openParenVa": "0x00B947B4",
            "separatorVa": "0x00B91FC4",
            "closeParenVa": "0x00B947AC",
            "delimiterBytes": {k: v.hex() for k, v in literals.items() if k != "colorTint"},
        },
        "layering": {
            "assertedLayerCountUpperBoundExclusive": 8,
            "layerZeroSuffixByte": 0,
            "nonzeroLayerSuffix": "single ASCII digit byte = layerIndex + 0x30",
            "supportedAssertedNonzeroLayerIndices": [1, 2, 3, 4, 5, 6, 7],
        },
        "textureConstruction": {
            "sourceCountFieldOffset": "0x54",
            "sourceTableFieldOffset": "0x60",
            "recordSizeBytes": 16,
            "copy": "all 16 bytes are copied before per-layer edits",
            "nonzeroLayerNameEdit": "overwrite MaterialTextureDef.nameEnd (+0x05) with the one-byte ASCII layer digit",
            "nonzeroLayerHashEdit": "nameHash = ((oldNameHash << 5) + oldNameHash) XOR sign_extend(layerDigitByte)",
            "hashInterpretationForIndices1To7": "exactly one additional T6 R_HashString/djb2_xor_nocase character for the ASCII layer digit",
            "matureFlagRecompute": {
                "imagePointerFieldOffset": "0x0C",
                "imageStringPointerObservedOffset": "0x48",
                "semanticFieldOffset": "0x07",
                "isMatureContentFieldOffset": "0x08",
                "semantic0Or1Result": False,
                "otherwise": "strstr(*(texture.image + 0x48), '_mature') != NULL",
                "imageOffsetFieldName": "UNRESOLVED_BY_THIS_PROOF",
            },
        },
        "constantConstruction": {
            "sourceCountFieldOffset": "0x55",
            "sourceTableFieldOffset": "0x64",
            "recordSizeBytes": 32,
            "copy": "all 32 bytes are copied before per-layer edits",
            "nameArrayBytes": 12,
            "nonzeroLayerNameEdit": (
                "scan name[12] for first NUL; if found, replace it with the layer digit and, when one byte remains, "
                "write a new NUL; if name[12] is full, no visible name byte is changed"
            ),
            "nonzeroLayerHashEdit": (
                "always nameHash = ((oldNameHash << 5) + oldNameHash) XOR sign_extend(layerDigitByte), even when name[12] is full"
            ),
            "colorTint": {
                "literal": "colorTint",
                "literalVa": "0x00D1CB00",
                "sourcePresenceTest": "source constant nameHash equals precomputed R_HashString('colorTint', 0)",
                "missingSourceBehavior": "append one MaterialConstantDef named colorTint with literal copied from global colorWhite",
                "colorWhiteVa": "0x00C67D50",
                "colorWhiteRawLe": white_raw.hex(),
                "colorWhiteVec4": white,
                "nonzeroLayerDefaultRow": "the injected colorTint row is then subjected to the same bounded name suffix and incremental nameHash edit",
            },
            "finalCountFormula": "sum(source.constantCount) + one for each source layer whose constant table contains no colorTint nameHash",
        },
        "finalization": {
            "textureEntryAccounting": "(newTexEntry - newMtl->textureTable) / 16 == newMtl->textureCount",
            "constantEntryAccounting": "(newConstEntry - newMtl->constantTable) / 32 == newMtl->constantCount",
            "textureSort": "qsort 16-byte records by unsigned uint32 nameHash at +0",
            "constantSort": "qsort 32-byte records by unsigned uint32 nameHash at +0",
            "comparatorVa": "0x00A4D630",
            "comparatorSha256": COMPARATOR_SHA256,
        },
        "summary": {
            "generatedNameConstructionClosed": True,
            "layerSuffixConstructionClosed": True,
            "textureRecordConstructionClosed": True,
            "constantRecordConstructionClosed": True,
            "defaultColorTintConstructionClosed": True,
            "finalTextureSortClosed": True,
            "finalConstantSortClosed": True,
            "historicalStandaloneSerializationRecovered": False,
            "retailClientExecutableEquivalenceClaimed": False,
        },
        "proofBoundary": (
            "Exact construction semantics of SHA-pinned T6 PC dedicated-server Material_CreateLayered are source-closed by the complete "
            "1696-byte body hash plus exact semantic instruction anchors, SHA-pinned PE literals/data, pinned T6 OpenAssetTools structure "
            "declarations, and the already-frozen final qsort proof. This is structural/runtime construction authority for the server. "
            "It does not claim the retail client executable is byte/behavior equivalent. For retail Nuketown, generated Material rows must "
            "still be independently reconciled against the exact retail FastFile/OAT dump before promotion. Missing standalone component "
            "Materials remain historically unresolved where their serialized source XAssets are absent; generated-runtime reconstruction is "
            "a separate, testable question."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", type=Path, required=True)
    ap.add_argument("--exe", type=Path, required=True)
    ap.add_argument("--oat-header", type=Path, required=True)
    ap.add_argument("--sort-manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ns = ap.parse_args()
    try:
        probe = json.loads(ns.probe.read_text(encoding="utf-8"))
        exe = ns.exe.read_bytes()
        header = ns.oat_header.read_text(encoding="utf-8")
        sort_doc = json.loads(ns.sort_manifest.read_text(encoding="utf-8"))
        result = build(probe, exe, header, sort_doc)
    except (OSError, ValueError, KeyError, struct.error, ProofError) as exc:
        raise SystemExit(f"FAIL-CLOSED: {exc}") from exc
    payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_bytes(payload)
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    print("RESULT_SHA256", sha256(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

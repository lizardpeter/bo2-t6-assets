#!/usr/bin/env python3
"""Census serialized T6 SndAliasList/SndAlias data in an expanded FastFile.

This is a compact reimplementation of the structural parser retained in the
user's August 2026 `bo2_fastfile_alias_cataloger.py`. It intentionally does not
assign high-level meanings to playback fields. It only:

* locates exact known physical SABS/SABL bank-base strings;
* validates the inline SndBank -> SndAliasList array shape;
* validates every SndAlias head entry has the owning SndAliasList ID;
* preserves all 96-byte SndAlias raw/numeric fields and inline strings;
* computes the same semantic-variant key used by the retained tool, excluding
  serialized pointers/source location while preserving assetId and playback
  values.

A candidate bank-name string is not accepted as a SndBank section unless all
structural gates pass. This tool does not resolve runtime alias selection or
claim that assetId==0 is missing audio.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from collections import Counter
from pathlib import Path

SND_ALIAS_LIST_SIZE = 20
SND_ALIAS_SIZE = 96

RAW_PLAYBACK_FIELDS = [
    "duck", "context_type", "context_value", "stop_on_play", "futz_patch",
    "flux_time", "start_delay", "reverb_send", "center_send", "vol_min",
    "vol_max", "pitch_min", "pitch_max", "dist_min", "dist_max",
    "dist_reverb_max", "envelop_min", "envelop_max", "envelop_percentage",
    "fade_in", "fade_out", "doppler_scale", "min_priority_threshold",
    "max_priority_threshold", "probability", "occlusion_level", "min_priority",
    "max_priority", "pan", "limit_count", "entity_limit_count", "duck_group",
]


def snd_hash_name(text: str) -> int:
    if not text:
        return 0
    result = 0x1505
    for c in text.lower().encode("latin1", errors="ignore"):
        result = (c + 0x1003F * result) & 0xFFFFFFFF
    return result or 1


def read_cstr(blob: bytes, pos: int, max_len: int = 4096) -> tuple[str, int]:
    if pos < 0 or pos >= len(blob):
        raise ValueError(f"C string start outside buffer: {pos}")
    end = blob.find(b"\0", pos, min(len(blob), pos + max_len))
    if end < 0:
        raise ValueError(f"unterminated C string at {pos}")
    return blob[pos:end].decode("utf-8", errors="replace"), end + 1


def parse_alias_struct(blob: bytes, off: int) -> dict:
    if off < 0 or off + SND_ALIAS_SIZE > len(blob):
        raise ValueError("SndAlias extends outside expanded FastFile")
    name_ptr, alias_id, subtitle_ptr, secondary_ptr, asset_id, file_ptr = struct.unpack_from("<6I", blob, off)
    flags0, flags1, duck, context_type, context_value, stop_on_play, futz_patch = struct.unpack_from("<7I", blob, off + 24)
    u16 = struct.unpack_from("<14H", blob, off + 52)
    s16 = struct.unpack_from("<3h", blob, off + 80)
    u8 = struct.unpack_from("<10B", blob, off + 86)
    return {
        "name_ptr": name_ptr,
        "id": alias_id,
        "subtitle_ptr": subtitle_ptr,
        "secondary_ptr": secondary_ptr,
        "asset_id": asset_id,
        "file_ptr": file_ptr,
        "flags0": flags0,
        "flags1": flags1,
        "duck": duck,
        "context_type": context_type,
        "context_value": context_value,
        "stop_on_play": stop_on_play,
        "futz_patch": futz_patch,
        "flux_time": u16[0],
        "start_delay": u16[1],
        "reverb_send": u16[2],
        "center_send": u16[3],
        "vol_min": u16[4],
        "vol_max": u16[5],
        "pitch_min": u16[6],
        "pitch_max": u16[7],
        "dist_min": u16[8],
        "dist_max": u16[9],
        "dist_reverb_max": u16[10],
        "envelop_min": u16[11],
        "envelop_max": u16[12],
        "envelop_percentage": u16[13],
        "fade_in": s16[0],
        "fade_out": s16[1],
        "doppler_scale": s16[2],
        "min_priority_threshold": u8[0],
        "max_priority_threshold": u8[1],
        "probability": u8[2],
        "occlusion_level": u8[3],
        "min_priority": u8[4],
        "max_priority": u8[5],
        "pan": u8[6],
        "limit_count": u8[7],
        "entity_limit_count": u8[8],
        "duck_group": u8[9],
    }


def parse_sndbank_alias_section(blob: bytes, bank_name: str, bank_name_offset: int):
    array_start = bank_name_offset + len(bank_name.encode("ascii")) + 1
    lists = []
    off = array_start
    while off + SND_ALIAS_LIST_SIZE <= len(blob):
        name_ptr, alias_id, head_ptr, count, sequence = struct.unpack_from("<5I", blob, off)
        if name_ptr == 0 or head_ptr != 0xFFFFFFFF or not (1 <= count <= 1000) or sequence > 1000:
            break
        lists.append({
            "name_ptr": name_ptr,
            "id": alias_id,
            "head_ptr": head_ptr,
            "count": count,
            "sequence": sequence,
        })
        off += SND_ALIAS_LIST_SIZE
    if not lists:
        return [], [], off, ["no_alias_lists"], {}

    cursor = off
    aliases = []
    learned_names: dict[int, str] = {}
    issues = []

    for list_index, entry in enumerate(lists):
        list_name = None
        if entry["name_ptr"] == 0xFFFFFFFF:
            try:
                list_name, cursor = read_cstr(blob, cursor)
            except Exception as exc:
                issues.append(f"list_{list_index}_name:{exc}")
                break
            calculated = snd_hash_name(list_name)
            if calculated != entry["id"]:
                issues.append(
                    f"list_{list_index}_name_hash_mismatch:{entry['id']:08x}!={calculated:08x}"
                )
                break
        else:
            list_name = learned_names.get(entry["id"])

        def head_matches(candidate: int) -> bool:
            if candidate < 0 or candidate + entry["count"] * SND_ALIAS_SIZE > len(blob):
                return False
            return all(
                struct.unpack_from("<I", blob, candidate + i * SND_ALIAS_SIZE + 4)[0] == entry["id"]
                for i in range(entry["count"])
            )

        head_start = cursor
        if not head_matches(head_start):
            aligned = None
            for pad in range(1, 16):
                if head_matches(cursor + pad):
                    aligned = cursor + pad
                    break
            if aligned is None:
                issues.append(f"list_{list_index}_alias_head_mismatch")
                break
            head_start = aligned
            cursor = aligned

        variants = [
            parse_alias_struct(blob, head_start + i * SND_ALIAS_SIZE)
            for i in range(entry["count"])
        ]
        cursor = head_start + entry["count"] * SND_ALIAS_SIZE

        for variant_index, alias in enumerate(variants):
            strings = {}
            for pointer_key, output_key in (
                ("name_ptr", "alias_name_inline"),
                ("subtitle_ptr", "subtitle_inline"),
                ("secondary_ptr", "secondary_name_inline"),
                ("file_ptr", "asset_file_name_inline"),
            ):
                ptr = alias[pointer_key]
                if ptr == 0xFFFFFFFF:
                    try:
                        value, cursor = read_cstr(blob, cursor)
                    except Exception as exc:
                        issues.append(f"list_{list_index}_variant_{variant_index}_{pointer_key}:{exc}")
                        value = ""
                    strings[output_key] = value
                elif ptr == 0:
                    strings[output_key] = ""
                else:
                    strings[output_key] = ""

            inline_alias_name = strings.get("alias_name_inline", "")
            if inline_alias_name and snd_hash_name(inline_alias_name) == entry["id"]:
                learned_names[entry["id"]] = inline_alias_name
                if not list_name:
                    list_name = inline_alias_name
            if list_name:
                learned_names[entry["id"]] = list_name

            alias.update(strings)
            alias["alias_list_name_inline"] = list_name or ""
            alias["alias_list_id"] = entry["id"]
            alias["variant_index"] = variant_index
            alias["variant_count"] = entry["count"]
            aliases.append(alias)

        if issues:
            break

    return lists, aliases, cursor, issues, learned_names


def semantic_tuple(alias: dict) -> tuple:
    return tuple(
        [
            int(alias["alias_list_id"]) & 0xFFFFFFFF,
            int(alias["asset_id"]) & 0xFFFFFFFF,
            int(alias["flags0"]) & 0xFFFFFFFF,
            int(alias["flags1"]) & 0xFFFFFFFF,
        ]
        + [alias[f] for f in RAW_PLAYBACK_FIELDS]
        + [alias.get("subtitle_inline", ""), alias.get("secondary_name_inline", "")]
    )


def semantic_digest(alias: dict) -> str:
    payload = json.dumps(semantic_tuple(alias), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compile_bank_regex(bank_bases: list[str]) -> re.Pattern[bytes]:
    if not bank_bases:
        raise ValueError("at least one exact bank base is required")
    alts = b"|".join(
        re.escape(x.encode("ascii")) for x in sorted(set(bank_bases), key=lambda x: (-len(x), x))
    )
    return re.compile(rb"(?<![A-Za-z0-9_])(" + alts + rb")\x00")


def census(blob: bytes, bank_bases: list[str], source: str = "") -> dict:
    pattern = compile_bank_regex(bank_bases)
    candidate_count = 0
    accepted_sections = []
    alias_id_counts: Counter[int] = Counter()
    asset_id_counts: Counter[int] = Counter()
    semantic_counts: Counter[str] = Counter()
    inline_names: dict[int, str] = {}
    zero_asset_occurrences = 0
    rejected = Counter()

    for match in pattern.finditer(blob):
        candidate_count += 1
        bank_name = match.group(1).decode("ascii")
        lists, aliases, end_cursor, issues, learned = parse_sndbank_alias_section(blob, bank_name, match.start(1))
        if not lists or not aliases or issues:
            if not lists:
                rejected["no_alias_lists"] += 1
            elif issues:
                rejected[issues[0].split(":", 1)[0]] += 1
            else:
                rejected["empty_aliases"] += 1
            continue

        for aid, name in learned.items():
            if name:
                existing = inline_names.get(aid)
                if existing is not None and existing != name:
                    raise ValueError(f"alias ID 0x{aid:08x} has conflicting validated inline names {existing!r} vs {name!r}")
                inline_names[aid] = name

        for alias in aliases:
            aid = int(alias["alias_list_id"]) & 0xFFFFFFFF
            asset = int(alias["asset_id"]) & 0xFFFFFFFF
            alias_id_counts[aid] += 1
            if asset:
                asset_id_counts[asset] += 1
            else:
                zero_asset_occurrences += 1
            semantic_counts[semantic_digest(alias)] += 1

        accepted_sections.append({
            "bankName": bank_name,
            "bankNameOffset": match.start(1),
            "aliasListCount": len(lists),
            "aliasOccurrenceCount": len(aliases),
            "endingCursor": end_cursor,
        })

    return {
        "format": "t6-sndalias-expanded-census-v1",
        "source": source,
        "expandedBytes": len(blob),
        "summary": {
            "candidateBankStringCount": candidate_count,
            "validatedSndBankSectionCount": len(accepted_sections),
            "aliasDefinitionOccurrenceCount": sum(alias_id_counts.values()),
            "uniqueAliasIdCount": len(alias_id_counts),
            "uniqueSemanticVariantCount": len(semantic_counts),
            "zeroAssetIdOccurrenceCount": zero_asset_occurrences,
            "nonzeroAssetIdOccurrenceCount": sum(asset_id_counts.values()),
            "uniqueNonzeroAssetIdCount": len(asset_id_counts),
            "validatedInlineAliasNameCount": len(inline_names),
            "rejectedCandidateCount": sum(rejected.values()),
        },
        "validatedSections": accepted_sections,
        "aliasIdCounts": {f"{k:08X}": v for k, v in sorted(alias_id_counts.items())},
        "assetIdCounts": {f"{k:08X}": v for k, v in sorted(asset_id_counts.items())},
        "semanticVariantCounts": dict(sorted(semantic_counts.items())),
        "validatedInlineAliasNames": {f"{k:08X}": v for k, v in sorted(inline_names.items())},
        "rejectedCandidateKinds": dict(sorted(rejected.items())),
        "proofBoundary": (
            "Structural census of an already source-closed expanded T6 FastFile. Exact known SABS/SABL bank-base strings only nominate candidate SndBank sections. "
            "A section is accepted only after SndAliasList array-shape and per-head alias-ID equality validation. Raw assetId/playback fields are preserved for counting and semantic grouping. "
            "assetId==0 is retained and is not classified as missing. No runtime sound-selection semantics or physical-bank match is inferred here."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("expanded", type=Path)
    p.add_argument("--bank-bases", type=Path, required=True, help="one exact bank base per line, e.g. mpl_common.all")
    p.add_argument("--source", default="")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    bases = [x.strip() for x in a.bank_bases.read_text(encoding="utf-8").splitlines() if x.strip()]
    blob = a.expanded.read_bytes()
    result = census(blob, bases, a.source)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Export exact T6 PC SABS/SABL payloads using source-closed format semantics.

Authority for the observed PC formats is pinned to:
  Laupetin/OpenAssetTools@9dca965366541504b71fa8cfb7ac049cb9b717e1
  src/Common/Game/T6/T6_Assets.h
  src/ObjWriting/Game/T6/Sound/SndBankDumperT6.cpp

Only the two formats observed in the complete 116-bank PC corpus are accepted:
  0x00 SND_ASSET_FORMAT_PCMS16 -> wrap exact signed 16-bit PCM bytes in WAV
  0x08 SND_ASSET_FORMAT_FLAC   -> preserve exact native FLAC bytes

Every other format fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from t6_audio_bank_id_manifest_v1 import BankError, parse_bank

SOURCE_COMMIT = "9dca965366541504b71fa8cfb7ac049cb9b717e1"
FORMAT_PCMS16 = 0x00
FORMAT_FLAC = 0x08


class ExportError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _wav_pcm16(payload: bytes, channels: int, sample_rate: int, sample_count: int) -> bytes:
    if channels not in (1, 2):
        raise ExportError(f"unsupported PC T6 PCM channel count: {channels}")
    if sample_rate <= 0:
        raise ExportError(f"invalid sample rate: {sample_rate}")
    expected = sample_count * channels * 2
    if len(payload) != expected:
        raise ExportError(
            f"PCMS16 payload length mismatch: {len(payload)} != "
            f"{sample_count} * {channels} * 2 = {expected}"
        )
    block_align = channels * 2
    byte_rate = sample_rate * block_align
    data_len = len(payload)
    if data_len > 0xFFFFFFFF - 36:
        raise ExportError("PCM payload too large for RIFF/WAVE")
    header = b"".join(
        (
            b"RIFF",
            struct.pack("<I", 36 + data_len),
            b"WAVE",
            b"fmt ",
            struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, 16),
            b"data",
            struct.pack("<I", data_len),
        )
    )
    if len(header) != 44:
        raise ExportError("internal WAV header size error")
    return header + payload


def select_entry(doc: dict, *, entry_index: int | None, identifier: int | None) -> dict:
    entries = doc["entries"]
    if (entry_index is None) == (identifier is None):
        raise ExportError("select exactly one of entry_index or identifier")
    if entry_index is not None:
        if not 0 <= entry_index < len(entries):
            raise ExportError(f"entry index outside bank: {entry_index}")
        return entries[entry_index]
    matches = [e for e in entries if int(e["identifierU32"]) == identifier]
    if not matches:
        raise ExportError(f"identifier 0x{identifier:08X} not present in bank")
    if len(matches) != 1:
        raise ExportError(f"identifier 0x{identifier:08X} occurs {len(matches)} times in bank")
    return matches[0]


def export_entry(bank: bytes, *, source: str = "", entry_index: int | None = None, identifier: int | None = None) -> tuple[bytes, str, dict]:
    try:
        doc = parse_bank(bank, source)
    except BankError as exc:
        raise ExportError(str(exc)) from exc
    entry = select_entry(doc, entry_index=entry_index, identifier=identifier)
    start = int(entry["dataOffset"])
    size = int(entry["dataBytes"])
    end = start + size
    if not (0 <= start <= end <= len(bank)):
        raise ExportError("selected payload range is outside bank")
    payload = bank[start:end]
    code = int(entry["formatCode"])
    if code == FORMAT_PCMS16:
        rate = entry["sampleRateHz"]
        if rate is None:
            raise ExportError(f"unsupported sample-rate flag {entry['sampleRateFlag']}")
        output = _wav_pcm16(payload, int(entry["channels"]), int(rate), int(entry["sampleCount"]))
        extension = ".wav"
        transformation = "RIFF/WAVE header added; PCM sample payload preserved byte-for-byte"
    elif code == FORMAT_FLAC:
        if payload[:4] != b"fLaC":
            raise ExportError(f"format 8 payload lacks native FLAC marker: {payload[:16].hex()}")
        output = payload
        extension = ".flac"
        transformation = "native FLAC payload preserved byte-for-byte"
    else:
        raise ExportError(f"unsupported/unclosed T6 PC physical format code 0x{code:02X}")
    proof = {
        "format": "t6-audio-payload-export-v1",
        "authority": {
            "sourceCommit": f"Laupetin/OpenAssetTools@{SOURCE_COMMIT}",
            "physicalFormatCode": code,
            "physicalFormatName": "SND_ASSET_FORMAT_PCMS16" if code == 0 else "SND_ASSET_FORMAT_FLAC",
        },
        "sourceBank": {
            "source": source,
            "bytes": len(bank),
            "sha256": sha256(bank),
        },
        "entry": entry,
        "output": {
            "extension": extension,
            "bytes": len(output),
            "sha256": sha256(output),
            "payloadSha256": sha256(payload),
            "transformation": transformation,
        },
        "proofBoundary": "Exact physical payload export for source-closed PC formats 0 (PCMS16) and 8 (FLAC). No resampling, remixing, normalization, inferred codec substitution, or unknown-format fallback is performed.",
    }
    return output, extension, proof


def _parse_identifier(text: str) -> int:
    t = text.strip()
    if t.lower().startswith("0x"):
        t = t[2:]
    if not t or len(t) > 8:
        raise argparse.ArgumentTypeError("identifier must be a 32-bit hexadecimal value")
    try:
        v = int(t, 16)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("identifier must be hexadecimal") from exc
    if not 0 <= v <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError("identifier outside uint32")
    return v


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("bank", type=Path)
    sel = p.add_mutually_exclusive_group(required=True)
    sel.add_argument("--entry-index", type=int)
    sel.add_argument("--identifier", type=_parse_identifier)
    p.add_argument("--out", type=Path, required=True, help="output path; expected extension is enforced")
    p.add_argument("--proof", type=Path)
    args = p.parse_args()
    try:
        bank = args.bank.read_bytes()
        output, extension, proof = export_entry(
            bank,
            source=str(args.bank),
            entry_index=args.entry_index,
            identifier=args.identifier,
        )
        if args.out.suffix.lower() != extension:
            raise ExportError(f"selected entry requires {extension} output, got {args.out.suffix or '<none>'}")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(output)
        if args.proof:
            args.proof.parent.mkdir(parents=True, exist_ok=True)
            args.proof.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(proof, indent=2, sort_keys=True))
        return 0
    except (ExportError, OSError) as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

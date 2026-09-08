#!/usr/bin/env python3
from __future__ import annotations

import hashlib

import t6_audio_duplicate_payload_hash_v1 as mod


def physical_fixture(bank_a: bytes, bank_b: bytes) -> dict:
    return {
        "format": "t6-audio-physical-id-manifest-v1",
        "summary": {"entryCount": 3, "uniqueIdentifierCount": 2},
        "identifierOccurrenceCounts": {"11111111": 2, "22222222": 1},
        "banks": [
            {"zipPath": "a.sabl", "bank": {"sha256": hashlib.sha256(bank_a).hexdigest(), "bytes": len(bank_a)}},
            {"zipPath": "b.sabl", "bank": {"sha256": hashlib.sha256(bank_b).hexdigest(), "bytes": len(bank_b)}},
        ],
        "entries": [
            {"bankPath":"a.sabl","entryIndex":0,"identifierHex":"11111111","dataOffset":1,"dataBytes":3,"dataEndOffset":4,"checksum128Hex":"AA","formatName":"FLAC","sampleCount":10,"sampleRateHz":48000,"channels":1,"loopRaw":0},
            {"bankPath":"a.sabl","entryIndex":1,"identifierHex":"22222222","dataOffset":4,"dataBytes":2,"dataEndOffset":6,"checksum128Hex":"BB","formatName":"PCMS16","sampleCount":2,"sampleRateHz":48000,"channels":1,"loopRaw":0},
            {"bankPath":"b.sabl","entryIndex":0,"identifierHex":"11111111","dataOffset":2,"dataBytes":3,"dataEndOffset":5,"checksum128Hex":"AA","formatName":"FLAC","sampleCount":10,"sampleRateHz":48000,"channels":1,"loopRaw":0},
        ],
    }


def main() -> int:
    a=b'XabcYZ'
    b=b'QQabcR'
    p=physical_fixture(a,b)
    oa=mod.hash_bank_payloads(p,"a.sabl",a)
    ob=mod.hash_bank_payloads(p,"b.sabl",b)
    result=mod.aggregate(p,[oa,ob],physical_sha256="fixture")
    s=result["summary"]
    assert s["duplicatedIdentifierCount"]==1
    assert s["duplicatedIdentifierOccurrenceCount"]==2
    assert s["payloadByteEqualDuplicatedIdentifierCount"]==1
    assert s["payloadByteDivergentDuplicatedIdentifierCount"]==0

    b2=b'QQabdR'
    p2=physical_fixture(a,b2)
    oa2=mod.hash_bank_payloads(p2,"a.sabl",a)
    ob2=mod.hash_bank_payloads(p2,"b.sabl",b2)
    result2=mod.aggregate(p2,[oa2,ob2])
    assert result2["summary"]["payloadByteDivergentDuplicatedIdentifierCount"]==1
    assert result2["summary"]["payloadByteEqualDuplicatedIdentifierCount"]==0

    try:
        mod.aggregate(p,[oa])
    except ValueError:
        pass
    else:
        raise AssertionError("missing duplicate occurrence must fail closed")

    bad=bytearray(a); bad[0]^=1
    try:
        mod.hash_bank_payloads(p,"a.sabl",bytes(bad))
    except ValueError:
        pass
    else:
        raise AssertionError("full-bank SHA mismatch must fail closed")

    print("PASS: duplicate payload proof hashes exact spans, detects divergence, and requires complete coverage")
    return 0

if __name__=="__main__":
    raise SystemExit(main())

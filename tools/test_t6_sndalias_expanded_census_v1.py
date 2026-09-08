#!/usr/bin/env python3
from __future__ import annotations

import struct

import t6_sndalias_expanded_census_v1 as mod


def alias_struct(alias_id: int, asset_id: int, *, probability: int = 255) -> bytes:
    head = struct.pack(
        '<6I',
        0,              # name_ptr: packed/reused; no inline string consumed here
        alias_id,
        0,              # subtitle_ptr
        0,              # secondary_ptr
        asset_id,
        0,              # file_ptr
    )
    raw32 = struct.pack(
        '<7I',
        0x00000001,     # flags0 raw
        0x00000000,     # flags1 raw
        11,             # duck
        12,             # context_type
        13,             # context_value
        14,             # stop_on_play
        15,             # futz_patch
    )
    raw16 = struct.pack('<14H', *range(101, 115))
    signed16 = struct.pack('<3h', -7, 8, -9)
    raw8 = struct.pack('<10B', 1, 2, probability, 4, 5, 6, 7, 8, 9, 10)
    blob = head + raw32 + raw16 + signed16 + raw8
    assert len(blob) == mod.SND_ALIAS_SIZE
    return blob


def valid_blob() -> tuple[bytes, str, int]:
    bank = 'fixture_bank.all'
    name = 'fixture_alias'
    aid = mod.snd_hash_name(name)
    prefix = b'noise-prefix\x00'
    # One SndAliasList with two variants. Its inline list name appears before
    # the inline head array exactly as the retained parser expects.
    list_row = struct.pack('<5I', 0xFFFFFFFF, aid, 0xFFFFFFFF, 2, 0)
    data = (
        prefix
        + bank.encode('ascii') + b'\x00'
        + list_row
        + name.encode('ascii') + b'\x00'
        + alias_struct(aid, 0x11223344, probability=200)
        + alias_struct(aid, 0, probability=201)
        + b'\x00tail-noise'
    )
    return data, bank, aid


def test_valid_section() -> None:
    blob, bank, aid = valid_blob()
    result = mod.census(blob, [bank], source='fixture.ff')
    s = result['summary']
    assert s['candidateBankStringCount'] == 1
    assert s['validatedSndBankSectionCount'] == 1
    assert s['aliasDefinitionOccurrenceCount'] == 2
    assert s['uniqueAliasIdCount'] == 1
    assert s['uniqueSemanticVariantCount'] == 2
    assert s['zeroAssetIdOccurrenceCount'] == 1
    assert s['nonzeroAssetIdOccurrenceCount'] == 1
    assert s['uniqueNonzeroAssetIdCount'] == 1
    assert s['validatedInlineAliasNameCount'] == 1
    assert s['rejectedCandidateCount'] == 0
    assert result['aliasIdCounts'][f'{aid:08X}'] == 2
    assert result['assetIdCounts']['11223344'] == 1
    assert result['validatedInlineAliasNames'][f'{aid:08X}'] == 'fixture_alias'
    assert len(result['semanticVariantCounts']) == 2


def test_wrong_head_id_rejected() -> None:
    bank = 'fixture_bad.all'
    name = 'fixture_bad_alias'
    aid = mod.snd_hash_name(name)
    wrong = aid ^ 0x01020304
    list_row = struct.pack('<5I', 0xFFFFFFFF, aid, 0xFFFFFFFF, 1, 0)
    blob = (
        bank.encode('ascii') + b'\x00'
        + list_row
        + name.encode('ascii') + b'\x00'
        + alias_struct(wrong, 0x55667788)
        + b'\x00' * 32
    )
    result = mod.census(blob, [bank], source='bad.ff')
    s = result['summary']
    assert s['candidateBankStringCount'] == 1
    assert s['validatedSndBankSectionCount'] == 0
    assert s['aliasDefinitionOccurrenceCount'] == 0
    assert s['rejectedCandidateCount'] == 1
    assert result['rejectedCandidateKinds'].get('list_0_alias_head_mismatch') == 1


def test_inline_list_hash_mismatch_rejected() -> None:
    bank = 'fixture_hash_bad.all'
    stored_id = mod.snd_hash_name('expected_alias')
    list_row = struct.pack('<5I', 0xFFFFFFFF, stored_id, 0xFFFFFFFF, 1, 0)
    blob = (
        bank.encode('ascii') + b'\x00'
        + list_row
        + b'different_alias\x00'
        + alias_struct(stored_id, 0x12345678)
    )
    result = mod.census(blob, [bank], source='hash-bad.ff')
    assert result['summary']['validatedSndBankSectionCount'] == 0
    assert result['summary']['rejectedCandidateCount'] == 1
    assert result['rejectedCandidateKinds'].get('list_0_name_hash_mismatch') == 1


def main() -> int:
    test_valid_section()
    test_wrong_head_id_rejected()
    test_inline_list_hash_mismatch_rejected()
    print('PASS: T6 SndAlias structural census accepts exact sections and rejects malformed candidates')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

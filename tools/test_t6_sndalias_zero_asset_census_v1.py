#!/usr/bin/env python3
from __future__ import annotations

import struct

import t6_sndalias_expanded_census_v1 as base
import t6_sndalias_zero_asset_census_v1 as mod


def alias_struct(alias_id: int, asset_id: int, probability: int) -> bytes:
    head = struct.pack('<6I', 0, alias_id, 0, 0, asset_id, 0)
    raw32 = struct.pack('<7I', 1, 0, 11, 12, 13, 14, 15)
    raw16 = struct.pack('<14H', *range(101, 115))
    signed16 = struct.pack('<3h', -7, 8, -9)
    raw8 = struct.pack('<10B', 1, 2, probability, 4, 5, 6, 7, 8, 9, 10)
    out = head + raw32 + raw16 + signed16 + raw8
    assert len(out) == base.SND_ALIAS_SIZE
    return out


def valid_blob() -> tuple[bytes, str, int, int]:
    bank = 'fixture_zero.all'
    mixed_name = 'mixed_alias'
    zero_name = 'zero_only_alias'
    mixed_id = base.snd_hash_name(mixed_name)
    zero_id = base.snd_hash_name(zero_name)
    list1 = struct.pack('<5I', 0xFFFFFFFF, mixed_id, 0xFFFFFFFF, 2, 0)
    list2 = struct.pack('<5I', 0xFFFFFFFF, zero_id, 0xFFFFFFFF, 1, 0)
    blob = (
        bank.encode('ascii') + b'\x00'
        + list1 + list2
        + mixed_name.encode('ascii') + b'\x00'
        + alias_struct(mixed_id, 0x11223344, 200)
        + alias_struct(mixed_id, 0, 201)
        + zero_name.encode('ascii') + b'\x00'
        + alias_struct(zero_id, 0, 202)
        + b'\x00tail'
    )
    return blob, bank, mixed_id, zero_id


def main() -> int:
    blob, bank, mixed_id, zero_id = valid_blob()
    result = mod.census_zero(blob, [bank], source='fixture.ff')
    s = result['summary']
    assert s['candidateBankStringCount'] == 1
    assert s['validatedSndBankSectionCount'] == 1
    assert s['aliasDefinitionOccurrenceCount'] == 3
    assert s['zeroAssetIdOccurrenceCount'] == 2
    assert s['nonzeroAssetIdOccurrenceCount'] == 1
    assert s['uniqueAliasIdCount'] == 2
    assert s['uniqueAliasIdsWithZeroAssetCount'] == 2
    assert s['zeroOnlyAliasIdCount'] == 1
    assert s['mixedZeroAndNonzeroAliasIdCount'] == 1
    assert s['uniqueZeroSemanticVariantCount'] == 2
    assert s['validatedInlineNameForZeroAliasIdCount'] == 2
    assert s['rejectedCandidateCount'] == 0
    assert result['aliasAssetClassCounts'][f'{mixed_id:08X}'] == {
        'zeroOccurrenceCount': 1, 'nonzeroOccurrenceCount': 1,
    }
    assert result['aliasAssetClassCounts'][f'{zero_id:08X}'] == {
        'zeroOccurrenceCount': 1, 'nonzeroOccurrenceCount': 0,
    }
    assert result['validatedInlineZeroAliasNames'][f'{mixed_id:08X}'] == 'mixed_alias'
    assert result['validatedInlineZeroAliasNames'][f'{zero_id:08X}'] == 'zero_only_alias'
    assert len(result['zeroRows']) == 2
    assert s['zeroPointerStateCounts']['file_ptr'] == {'null': 2}
    assert s['zeroRowsWithNonemptyInlineStrings']['assetFileName'] == 0

    # Reuse the base parser's key negative: a bank string is not an accepted
    # SndBank section when no structurally valid alias-list array follows it.
    bad = bank.encode('ascii') + b'\x00' + b'not-an-alias-array' + b'\x00' * 64
    rejected = mod.census_zero(bad, [bank], source='bad.ff')
    assert rejected['summary']['validatedSndBankSectionCount'] == 0
    assert rejected['summary']['zeroAssetIdOccurrenceCount'] == 0
    assert rejected['summary']['rejectedCandidateCount'] == 1
    assert rejected['rejectedCandidateKinds'] == {'no_alias_lists': 1}

    assert mod.pointer_state(0) == 'null'
    assert mod.pointer_state(0xFFFFFFFF) == 'inline_serialized'
    assert mod.pointer_state(0x12345678) == 'other_u32'

    print('PASS: zero-asset census separates zero-only/mixed families and preserves pointer state without semantics')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

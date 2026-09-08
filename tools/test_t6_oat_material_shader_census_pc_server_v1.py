#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import t6_oat_material_shader_census_pc_server_v1 as mod


def semantics() -> dict[str, dict]:
    return {
        str(Path('/tmp/map_out').resolve()): {
            'serverZoneClass': 'ordinaryBuiltInMpMap',
            'allocFlagsHex': '0x00008000',
            'priority': 57,
        },
        str(Path('/tmp/common_out').resolve()): {
            'serverZoneClass': 'common_mp',
            'allocFlagsHex': '0x00000080',
            'priority': 54,
        },
        str(Path('/tmp/code_post_out').resolve()): {
            'serverZoneClass': 'code_post_gfx_mp',
            'allocFlagsHex': '0x00000008',
            'priority': 52,
        },
        str(Path('/tmp/patch_out').resolve()): {
            'serverZoneClass': 'patch_mp',
            'allocFlagsHex': '0x00000002',
            'priority': 65,
        },
    }


def main() -> int:
    s = semantics()

    # Unique owners do not require a precedence decision and therefore may be
    # outside the mapped server classes.
    owner, rows = mod.choose_owner([Path('/tmp/unique_unmapped')], s)
    assert owner == Path('/tmp/unique_unmapped')
    assert rows == []

    for loser in ('/tmp/map_out', '/tmp/common_out', '/tmp/code_post_out'):
        owner, rows = mod.choose_owner([Path(loser), Path('/tmp/patch_out')], s)
        assert owner == Path('/tmp/patch_out')
        assert len(rows) == 2
        assert max(r['priority'] for r in rows) == 65

    # A duplicate owner outside the exact server mapping must fail rather than
    # falling back to root order or a guessed zone class.
    try:
        mod.choose_owner([Path('/tmp/map_out'), Path('/tmp/unmapped')], s)
    except mod.ServerProjectedCensusError:
        pass
    else:
        raise AssertionError('duplicate owner with unmapped server class must fail')

    # Equal priority duplicates require exact load-order proof and must fail.
    tied = dict(s)
    tied[str(Path('/tmp/tie').resolve())] = {
        'serverZoneClass': 'fixtureTie',
        'allocFlagsHex': '0x1234',
        'priority': 65,
    }
    try:
        mod.choose_owner([Path('/tmp/patch_out'), Path('/tmp/tie')], tied)
    except mod.ServerProjectedCensusError:
        pass
    else:
        raise AssertionError('priority tie must fail closed')

    print('PASS: server-projected census selects only exact unique server maxima and never guesses')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

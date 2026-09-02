#!/usr/bin/env python3
"""Regenerate and validate the exact remaining MP format-8 scan queue."""
from __future__ import annotations
import json
from pathlib import Path
import t6_world_format8_scan_queue_v1 as q


def main() -> int:
    root=Path(__file__).resolve().parents[1]
    targets=q.load(root/'manifests/world/T6_RETAIL_MP_WORLD_FORMAT_TARGETS_V1.json')
    baseline=q.load(root/'manifests/world/T6_WORLD_VERTEX_FORMAT_CENSUS_V1.json')
    fmt45=q.load(root/'manifests/world/T6_RETAIL_WORLD_FORMATS_45_PROOF_V1.json')
    registry=q.load(root/'manifests/world/T6_WORLD_VERTEX_FORMAT_REGISTRY_V1.json')
    absence=q.load(root/'manifests/world/T6_RETAIL_WORLD_FORMAT_8_RETAINED_ABSENCE_CENSUS_V1.json')
    got=q.build(targets,baseline,fmt45,registry,absence)
    expected=json.loads((root/'manifests/world/T6_RETAIL_MP_FORMAT8_SCAN_QUEUE_V1.json').read_text(encoding='utf-8'))
    assert got==expected
    assert got['targetMapCount']==31 and got['auditedMapCount']==3 and got['pendingMapCount']==28
    assert got['targetFormat']==8 and got['expectedVd1Stride']==20
    assert {x['zone'] for x in got['auditedMaps']}=={'mp_nuketown_2020','mp_raid','mp_hijacked'}
    assert len({x['zone'] for x in got['pendingMaps']})==28
    assert len({x['sha256'] for x in got['pendingMaps']})==28
    assert all(len(x['sha256'])==64 and x['bytes']>0 for x in got['pendingMaps'])
    print('PASS: T6 MP format 8 scan queue regression')
    return 0
if __name__=='__main__':raise SystemExit(main())

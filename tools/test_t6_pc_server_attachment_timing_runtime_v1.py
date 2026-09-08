#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path

from t6_pc_server_attachment_timing_runtime_v1 import SPECS, build


def emit(root: Path, spec: dict, *, wrong_scale: bool = False) -> None:
    scale = "BROKEN" if wrong_scale else spec["scale_field"]
    c = f'''/* canonical_id: {spec["cid"]}\n * requested_va: 0x{spec["va"]}\n * ghidra_name: {spec["name"]}\n */
int {spec["name"]}(Weapon param_1) {{
  X *pWVar1; int iVar2; float fVar3; WeaponAttachment *apWStack_10[3];
  pWVar1 = {spec["base_getter"]}(param_1);
  BG_GetWeaponAttachments(param_1,&apWStack_10);
  iVar2 = 0; fVar3 = __real_3f800000;
  do {{
    if (apWStack_10[iVar2] == (WeaponAttachment *)0x0) break;
    fVar3 = fVar3 * apWStack_10[iVar2]->{scale};
    iVar2 = iVar2 + 1;
  }} while (iVar2 < 3);
  return (int)((float)pWVar1->{spec["base_field"]} * fVar3);
}}
'''
    asm = f'''# canonical_id: {spec["cid"]}\n# entry_point: {spec["va"]}\n# ghidra_name: {spec["name"]}\n{spec["va"]}\t55\tPUSH EBP\n'''
    (root / f'{spec["cid"]}.c').write_text(c)
    (root / f'{spec["cid"]}.asm').write_text(asm)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for s in SPECS:
            emit(root, s)
        doc = build(root)
        assert doc['summary']['formulaCount'] == 7
        assert doc['summary']['retailClientPromotionBlocked'] is True
        assert doc['formulas'][0]['attachmentScaleField'] == 'fFireTimeScale'

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for i, s in enumerate(SPECS):
            emit(root, s, wrong_scale=(i == 0))
        try:
            build(root)
        except SystemExit as e:
            assert 'fFireTimeScale' in str(e)
        else:
            raise AssertionError('mutated timing scale did not fail closed')
    print('ok')


if __name__ == '__main__':
    main()

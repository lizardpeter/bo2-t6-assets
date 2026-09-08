#!/usr/bin/env python3
from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import t6_oat_alias_csv_target_census_v1 as mod


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); sb=root/'soundbank'; sb.mkdir()
        p=sb/'fixture.all.aliases.csv'
        with p.open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=['Name','FileSource','Secondary'])
            w.writeheader()
            w.writerow({'Name':'ordinary_alias','FileSource':'a.wav','Secondary':''})
            w.writerow({'Name':'Target_Alias','FileSource':'','Secondary':'other'})
        d=mod.scan(root,'fixture.ff',['target_alias','missing_alias'])
        assert d['summary']['nativeSoundBankCsvCount']==1
        assert d['summary']['nativeAliasRowCount']==2
        assert d['summary']['targetMatchCount']==1
        assert d['matches'][0]['target']=='target_alias'
        assert d['matches'][0]['nativeAliasName']=='Target_Alias'

        bad=sb/'bad.all.aliases.csv'
        bad.write_text('Secondary\nfoo\n',encoding='utf-8')
        try:
            mod.scan(root,'fixture.ff',['target_alias'])
        except ValueError:
            pass
        else:
            raise AssertionError('missing Name column must fail')

    print('PASS: native OAT alias target census matches exact Name values and rejects malformed CSVs')
    return 0

if __name__=='__main__':
    raise SystemExit(main())

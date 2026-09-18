#!/usr/bin/env python3
"""Regression for exact 31-map format-8 corpus aggregation."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import t6_world_format8_mp_corpus_v1 as mod


def row(i: int) -> dict:
    zone=f"mp_test_{i:02d}"
    return {
        "zone":zone,
        "path":f"zone/all/{zone}.ff",
        "bytes":1000+i,
        "sha256":f"{i+1:064x}"[-64:],
    }


def scan(target: dict, hit: bool=False) -> dict:
    hist={"1":2,"7":1}
    hits=[]
    if hit:
        hist["8"]=1
        hits=[{"start":1234,"name":"lit_sm_test"}]
    return {
        "format":mod.SCAN_FORMAT,
        "zone":target["zone"],
        "sourceFastfile":{
            "path":f"/tmp/{target['zone']}.ff",
            "bytes":target["bytes"],
            "sha256":target["sha256"],
        },
        "expanded":{
            "path":f"/tmp/{target['zone']}.expanded.bin",
            "bytes":2000,
            "sha256":"ab"*32,
        },
        "assetCount":42,
        "scanStartAfterXAssetTable":128,
        "strongInlineTechniqueSetCount":sum(hist.values()),
        "formatDistribution":hist,
        "format8StrongInlineHitCount":len(hits),
        "format8StrongInlineHits":hits,
    }


def must_fail(fn, needle: str) -> None:
    try:
        fn()
    except mod.CorpusError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected CorpusError containing {needle!r}")


def main() -> int:
    targets={"format":mod.TARGET_FORMAT,"maps":[row(i) for i in range(31)]}
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        for target in targets["maps"]:
            doc=scan(target, hit=target["zone"]=="mp_test_17")
            (root/f"{target['zone']}.json").write_text(json.dumps(doc)+"\n")

        out=mod.build(targets,root)
        assert out["targetMapCount"]==31
        assert out["scannedMapCount"]==31
        assert out["allTargetFastfileIdentitiesMatched"] is True
        assert out["format8StrongInlineHitCount"]==1
        assert out["strictInlineAbsenceAcrossAll31MpMaps"] is False
        assert out["format8StrongInlineHits"]==[
            {"zone":"mp_test_17","start":1234,"name":"lit_sm_test"}
        ]
        assert out["formatDistribution"]=={"1":62,"7":31,"8":1}

        missing=root/"mp_test_30.json"
        saved=missing.read_text()
        missing.unlink()
        must_fail(lambda:mod.build(targets,root),"scan universe mismatch")
        missing.write_text(saved)

        bad=json.loads((root/"mp_test_00.json").read_text())
        bad["sourceFastfile"]["sha256"]="00"*32
        (root/"mp_test_00.json").write_text(json.dumps(bad)+"\n")
        must_fail(lambda:mod.build(targets,root),"exact source mismatch")

    print("PASS t6_world_format8_mp_corpus_v1")
    return 0


if __name__=="__main__":
    raise SystemExit(main())

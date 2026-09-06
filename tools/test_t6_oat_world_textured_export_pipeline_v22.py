#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v22 as pipeline
from t6_glb_parse_v1 import parse_glb
from t6_world_gltf_export_v1 import glb_bytes


def _record(path: Path) -> dict:
    b = path.read_bytes()
    return {"file": path.name, "path": str(path), "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t6_v22_") as td:
        root=Path(td);out=root/"out";out.mkdir();raw=b"v21-source-bin"
        doc={"asset":{"version":"2.0"},"buffers":[{"byteLength":len(raw)}],"bufferViews":[],"extras":{"T6":{"lightmapArchive":{"format":"t6-world-lightmap-glb-archive-v3"}}}}
        old=out/"mp_nuketown_2020.world_oat_portable_textured_v21.glb";old.write_bytes(glb_bytes(doc,raw))
        manifest=out/"v21.json";manifest.write_text("{}\n",encoding="utf-8")
        original_run=pipeline.v21.run_oat_textured_pipeline;original_embed=pipeline.embed_lightmap_previews;calls=[]
        try:
            pipeline.v21.run_oat_textured_pipeline=lambda **kwargs:{"format":"t6-oat-world-textured-export-pipeline-manifest-v21","map":"mp_nuketown_2020","outputs":{"oatPortableTexturedGlb":_record(old)},"stats":{"v21":1},"validation":{"v21BinByteIdenticalToV20":True},"policies":{"v21Sentinel":"preserved"},"manifest":_record(manifest)}
            def fake_embed(gltf,source):
                calls.append(bytes(source));d=json.loads(json.dumps(gltf));payload=b"PNG!";start=len(source);d.setdefault("bufferViews",[]).append({"buffer":0,"byteOffset":start,"byteLength":len(payload)});d["buffers"][0]["byteLength"]=start+len(payload);d.setdefault("extras",{}).setdefault("T6",{})[pipeline.PREVIEW_ROOT if hasattr(pipeline,'PREVIEW_ROOT') else 'lightmapPreviewArchive']={"format":pipeline.LIGHTMAP_PREVIEW_FORMAT};stats={"uniquePreviewImageCount":1,"appendedPreviewBytes":len(payload),"sourceBinExactPrefix":True};return d,bytes(source)+payload,stats
            pipeline.embed_lightmap_previews=fake_embed
            result=pipeline.run_oat_textured_pipeline(map_name="mp_nuketown_2020",output_dir=out)
        finally:
            pipeline.v21.run_oat_textured_pipeline=original_run;pipeline.embed_lightmap_previews=original_embed
        assert len(calls)>=2 and all(x==raw for x in calls)
        assert result["format"]==pipeline.FORMAT
        assert result["validation"]["v21BinByteIdenticalToV20"] is True
        assert result["validation"]["v22CanonicalLightmapArchivePresent"] is True
        assert result["validation"]["v22V21BinExactPrefix"] is True
        assert result["validation"]["v22AppendedPreviewBytes"]==4
        assert result["validation"]["v22UniquePreviewImageCount"]==1
        assert result["policies"]["v21Sentinel"]=="preserved"
        final=Path(result["outputs"]["oatPortableTexturedGlb"]["path"]);assert final.name.endswith("_v22.glb")
        final_doc,final_raw=parse_glb(final.read_bytes());assert final_raw[:len(raw)]==raw and final_raw[len(raw):]==b"PNG!"
        assert final_doc["extras"]["T6"]["lightmapPreviewArchive"]["format"]==pipeline.LIGHTMAP_PREVIEW_FORMAT
        assert not old.exists() and not manifest.exists()
        persisted=json.loads(Path(result["manifest"]["path"]).read_text(encoding="utf-8"));assert persisted["format"]==pipeline.FORMAT

        # No canonical archive: v22 must preserve v21 instead of inventing one.
        old2=out/"mp_nuketown_2020.world_oat_portable_textured_v21.glb";doc2={"asset":{"version":"2.0"},"buffers":[{"byteLength":len(raw)}],"extras":{"T6":{}}};old2.write_bytes(glb_bytes(doc2,raw));m2=out/"v21b.json";m2.write_text("{}\n")
        try:
            pipeline.v21.run_oat_textured_pipeline=lambda **kwargs:{"format":"t6-oat-world-textured-export-pipeline-manifest-v21","outputs":{"oatPortableTexturedGlb":_record(old2)},"stats":{},"validation":{},"policies":{},"manifest":_record(m2)}
            pipeline.embed_lightmap_previews=lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError("preview decoder should not run"))
            result2=pipeline.run_oat_textured_pipeline(map_name="mp_nuketown_2020",output_dir=out)
        finally:
            pipeline.v21.run_oat_textured_pipeline=original_run;pipeline.embed_lightmap_previews=original_embed
        assert result2["validation"]["v22CanonicalLightmapArchivePresent"] is False
        assert result2["stats"]["lightmapPreviewArchive"] is None
        _, raw2=parse_glb(Path(result2["outputs"]["oatPortableTexturedGlb"]["path"]).read_bytes());assert raw2==raw
    print("PASS: production v22 lightmap preview staging orchestration");return 0
if __name__=="__main__":raise SystemExit(main())

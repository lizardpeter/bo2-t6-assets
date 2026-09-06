#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,tempfile
from pathlib import Path
import t6_oat_world_textured_export_pipeline_v23 as pipeline
from t6_glb_parse_v1 import parse_glb
from t6_world_gltf_export_v1 import glb_bytes

def rec(p):
 b=p.read_bytes();return {"file":p.name,"path":str(p),"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()}

def main():
 with tempfile.TemporaryDirectory(prefix="t6_v23_") as td:
  root=Path(td);out=root/"out";out.mkdir();raw=b"v22-bin"
  doc={"asset":{"version":"2.0"},"buffers":[{"byteLength":len(raw)}],"materials":[{"name":"*retail"}],"meshes":[],"extras":{"T6":{"lightmapPreviewArchive":{"format":"t6-world-lightmap-preview-archive-v1"}}}}
  old=out/"mp_nuketown_2020.world_oat_portable_textured_v22.glb";old.write_bytes(glb_bytes(doc,raw));m=out/"v22.json";m.write_text("{}\n")
  oldrun=pipeline.v22.run_oat_textured_pipeline;oldspec=pipeline.specialize;calls=[]
  try:
   pipeline.v22.run_oat_textured_pipeline=lambda **kwargs:{"format":"t6-oat-world-textured-export-pipeline-manifest-v22","outputs":{"oatPortableTexturedGlb":rec(old)},"stats":{"v22":1},"validation":{"v22V21BinExactPrefix":True},"policies":{"v22Sentinel":"preserved"},"manifest":rec(m)}
   def fake(gltf,source):
    calls.append(bytes(source));d=json.loads(json.dumps(gltf));variant={"name":"*retail__T6_LM0000_TC1","extras":{"T6":{"lightmapPreviewBindingV1":{"format":pipeline.SPECIALIZATION_FORMAT,"retailMaterialName":"*retail","variantMaterialName":"*retail__T6_LM0000_TC1","lightmapIndex":0,"lightmapTexCoord":1}}}};d["materials"].append(variant);d.setdefault("extras",{}).setdefault("T6",{})["lightmapMaterialSpecialization"]={"format":pipeline.SPECIALIZATION_FORMAT};stats={"specializedMaterialCount":1,"redirectedLightmappedPrimitiveCount":2,"missingPresentPreviewRoleUseCount":0,"binByteIdentical":True};return d,bytes(source),stats
   pipeline.specialize=fake
   result=pipeline.run_oat_textured_pipeline(map_name="mp_nuketown_2020",output_dir=out)
  finally:
   pipeline.v22.run_oat_textured_pipeline=oldrun;pipeline.specialize=oldspec
  assert len(calls)>=2 and all(x==raw for x in calls)
  assert result["format"]==pipeline.FORMAT
  assert result["validation"]["v22V21BinExactPrefix"] is True
  assert result["validation"]["v23LightmapPreviewPresent"] is True
  assert result["validation"]["v23BinByteIdenticalToV22"] is True
  assert result["validation"]["v23SpecializedMaterialCount"]==1
  assert result["validation"]["v23RedirectedLightmappedPrimitiveCount"]==2
  assert result["policies"]["v22Sentinel"]=="preserved"
  final=Path(result["outputs"]["oatPortableTexturedGlb"]["path"]);assert final.name.endswith("_v23.glb")
  final_doc,final_raw=parse_glb(final.read_bytes());assert final_raw==raw;assert len(final_doc["materials"])==2;assert final_doc["extras"]["T6"]["lightmapMaterialSpecialization"]["format"]==pipeline.SPECIALIZATION_FORMAT
  assert not old.exists() and not m.exists();persisted=json.loads(Path(result["manifest"]["path"]).read_text());assert persisted["format"]==pipeline.FORMAT

  old2=out/"mp_nuketown_2020.world_oat_portable_textured_v22.glb";doc2={"asset":{"version":"2.0"},"buffers":[{"byteLength":len(raw)}],"extras":{"T6":{}}};old2.write_bytes(glb_bytes(doc2,raw));m2=out/"v22b.json";m2.write_text("{}\n")
  try:
   pipeline.v22.run_oat_textured_pipeline=lambda **kwargs:{"format":"t6-oat-world-textured-export-pipeline-manifest-v22","outputs":{"oatPortableTexturedGlb":rec(old2)},"stats":{},"validation":{},"policies":{},"manifest":rec(m2)}
   pipeline.specialize=lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError("specialization should not run"))
   result2=pipeline.run_oat_textured_pipeline(map_name="mp_nuketown_2020",output_dir=out)
  finally:
   pipeline.v22.run_oat_textured_pipeline=oldrun;pipeline.specialize=oldspec
  assert result2["validation"]["v23LightmapPreviewPresent"] is False
  assert result2["stats"]["lightmapMaterialSpecialization"] is None
  _,r2=parse_glb(Path(result2["outputs"]["oatPortableTexturedGlb"]["path"]).read_bytes());assert r2==raw
 print("PASS: production v23 per-surface lightmap specialization orchestration");return 0
if __name__=="__main__":raise SystemExit(main())

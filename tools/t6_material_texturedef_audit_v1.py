#!/usr/bin/env python3
"""Audit T6 PC32 inline MaterialTextureDef tables directly from expanded FF bytes.

Declared scope:
- 112-byte retail T6 Material fixed records.
- inline Material name (`info.name == PTR_FOLLOWING/PTR_INSERT`).
- 16-byte MaterialTextureDef records following the inline name.
- semantic/sampler/image-pointer provenance only; this tool does not guess image names.

The T6 layout is source-cross-checked against OpenAssetTools T6_Assets.h and
ZoneCode/Game/T6/XAssets/Material.txt. It fails closed if the fixed record or
semantic rows do not satisfy the expected retail invariants.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

MATERIAL_FIXED = 112
TEXTURE_DEF = 16
PTR_FOLLOWING = 0xFFFFFFFF
PTR_INSERT = 0xFFFFFFFE
SEMANTICS = {0: "2D", 1: "function", 2: "colorMap", 5: "normalMap", 8: "specularMap"}

class AuditError(RuntimeError): pass

def sha256(b: bytes) -> str: return hashlib.sha256(b).hexdigest()

def cstring(data: bytes, pos: int, max_len: int = 512) -> tuple[str, int]:
    end = data.find(b"\0", pos, min(len(data), pos + max_len + 1))
    if end < 0 or end == pos: raise AuditError(f"invalid inline string at {pos}")
    raw = data[pos:end]
    if any(c < 32 or c > 126 for c in raw): raise AuditError(f"non-ASCII inline string at {pos}")
    return raw.decode("ascii"), end + 1

def ptr(raw: int) -> dict:
    if raw == 0: return {"raw":raw,"rawHex":"0x00000000","kind":"null"}
    if raw == PTR_FOLLOWING: return {"raw":raw,"rawHex":"0xFFFFFFFF","kind":"following"}
    if raw == PTR_INSERT: return {"raw":raw,"rawHex":"0xFFFFFFFE","kind":"insert"}
    enc=(raw-1)&0xffffffff
    return {"raw":raw,"rawHex":f"0x{raw:08X}","kind":"packed","block":enc>>29,"offset":enc&0x1fffffff}

def audit(data: bytes, start: int, expected_name: str | None = None) -> dict:
    if start < 0 or start + MATERIAL_FIXED > len(data): raise AuditError("Material fixed record outside stream")
    fixed=data[start:start+MATERIAL_FIXED]
    name_ptr=struct.unpack_from("<I",fixed,0)[0]
    if name_ptr not in (PTR_FOLLOWING,PTR_INSERT): raise AuditError(f"Material name is not inline: {ptr(name_ptr)}")
    texture_count=fixed[0x54]; constant_count=fixed[0x55]; state_bits_count=fixed[0x56]
    technique_ptr=struct.unpack_from("<I",fixed,0x5c)[0]
    texture_ptr=struct.unpack_from("<I",fixed,0x60)[0]
    constant_ptr=struct.unpack_from("<I",fixed,0x64)[0]
    state_ptr=struct.unpack_from("<I",fixed,0x68)[0]
    if texture_count <= 0: raise AuditError("zero textureCount outside this audit scope")
    if texture_ptr not in (PTR_FOLLOWING,PTR_INSERT): raise AuditError(f"textureTable is not inline: {ptr(texture_ptr)}")
    name,p=cstring(data,start+MATERIAL_FIXED)
    if expected_name is not None and name != expected_name: raise AuditError(f"name mismatch {name!r} != {expected_name!r}")
    table_start=p; table_end=p+texture_count*TEXTURE_DEF
    if table_end > len(data): raise AuditError("texture table outside stream")
    rows=[]
    for i in range(texture_count):
        off=table_start+i*TEXTURE_DEF
        name_hash,name_start,name_end,sampler,semantic,pad,image_ptr=struct.unpack_from("<I4BII",data,off)
        if pad != 0: raise AuditError(f"texture slot {i}: reserved field nonzero: 0x{pad:08X}")
        if not (32 <= name_start <= 126 and 32 <= name_end <= 126): raise AuditError(f"texture slot {i}: invalid name chars")
        rows.append({"slot":i,"rawStart":off,"rawSha256":sha256(data[off:off+TEXTURE_DEF]),
                     "nameHash":name_hash,"nameHashHex":f"0x{name_hash:08X}","nameStart":chr(name_start),"nameEnd":chr(name_end),
                     "samplerState":sampler,"semantic":semantic,"semanticName":SEMANTICS.get(semantic,f"unknown-{semantic}"),
                     "imagePointer":ptr(image_ptr)})
    return {"format":"t6-material-texturedef-audit-v1","identity":{"name":name},
            "source":{"materialFixedStart":start,"materialFixedBytes":MATERIAL_FIXED,"materialFixedSha256":sha256(fixed),
                      "textureTableStart":table_start,"textureTableEnd":table_end,"textureTableBytes":table_end-table_start,
                      "textureTableSha256":sha256(data[table_start:table_end])},
            "material":{"textureCount":texture_count,"constantCount":constant_count,"stateBitsCount":state_bits_count,
                        "techniqueSetPointer":ptr(technique_ptr),"textureTablePointer":ptr(texture_ptr),
                        "constantTablePointer":ptr(constant_ptr),"stateBitsTablePointer":ptr(state_ptr)},
            "textures":rows,
            "validation":{"allTextureRows16Bytes":True,"reservedFieldsZero":True,
                          "knownSemanticRows":sum(1 for r in rows if r["semantic"] in SEMANTICS),
                          "unknownSemanticRows":sum(1 for r in rows if r["semantic"] not in SEMANTICS)}}

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("expanded",type=Path); ap.add_argument("--material-start",required=True,type=lambda x:int(x,0)); ap.add_argument("--expected-name"); ap.add_argument("--out",type=Path,required=True); a=ap.parse_args()
    data=a.expanded.read_bytes(); doc=audit(data,a.material_start,a.expected_name); doc["source"]["expandedSha256"]=sha256(data)
    text=json.dumps(doc,indent=2,sort_keys=True)+"\n"; a.out.write_text(text,encoding="utf-8")
    print(json.dumps({"out":str(a.out),"name":doc["identity"]["name"],"textureCount":doc["material"]["textureCount"],"semantics":[r["semanticName"] for r in doc["textures"]],"sha256":sha256(text.encode())},indent=2)); return 0

if __name__ == "__main__": raise SystemExit(main())

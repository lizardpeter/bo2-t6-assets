#!/usr/bin/env python3
"""Census actual RMGE01 J3D/MAT3/TEX1 contracts from owner-hosted retail assets.

No game bytes are committed. The output is structural JSON used to prioritize
exact importer admission in Rust-test.
"""
from __future__ import annotations

import argparse, collections, concurrent.futures, hashlib, json, struct, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

BASE_DEFAULT = "https://r2.houseofkublai.com/super-mario-galaxy/DATA/files"
UA = "Mozilla/5.0 SMG-RMGE01-census/1"

def be16(b,o): return struct.unpack_from(">H",b,o)[0]
def be32(b,o): return struct.unpack_from(">I",b,o)[0]
def cstr(b,o):
    e=b.find(b"\0",o)
    if e<0: e=len(b)
    return b[o:e].decode("shift_jis","replace")

def rgba8(b,o):
    return list(b[o:o+4])

def f32(b,o):
    return struct.unpack_from(">f",b,o)[0]

def object_url(base,obj):
    return f"{base}/ObjectData/{urllib.parse.quote(obj, safe='')}.arc"

def yaz0(src: bytes) -> bytes:
    if src[:4] != b"Yaz0": return src
    n=be32(src,4); out=bytearray(); p=16; code=0; bits=0
    while len(out)<n:
        if bits==0: code=src[p]; p+=1; bits=8
        if code&0x80:
            out.append(src[p]); p+=1
        else:
            a,b=src[p],src[p+1]; p+=2
            dist=((a&15)<<8)|b; length=a>>4
            if length==0: length=src[p]+0x12; p+=1
            else: length+=2
            q=len(out)-dist-1
            for _ in range(length):
                if len(out)>=n: break
                out.append(out[q]); q+=1
        code=(code<<1)&0xff; bits-=1
    return bytes(out)

def fetch(url, retries=4):
    err=None
    for attempt in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA})
            with urllib.request.urlopen(req,timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise RuntimeError(f"download missing {url}: HTTP 404")
            err=e
        except Exception as e:
            err=e
        time.sleep(1.5*(attempt+1))
    raise RuntimeError(f"download failed {url}: {err}")

def rarc_files(src: bytes):
    b=yaz0(src)
    if b[:4]!=b"RARC": raise ValueError("not RARC")
    header_size=be32(b,0x08)
    data_rel=be32(b,0x0c)
    data_start=header_size+data_rel
    info=header_size
    node_count=be32(b,info+0x00)
    node_start=info+be32(b,info+0x04)
    entry_count=be32(b,info+0x08)
    entry_start=info+be32(b,info+0x0c)
    string_start=info+be32(b,info+0x14)
    out=[]
    for i in range(entry_count):
        o=entry_start+i*0x14
        flags_name=be32(b,o+4); flags=flags_name>>24; no=flags_name&0xffffff
        name=cstr(b,string_start+no)
        if flags&0x02: continue
        do=be32(b,o+8); size=be32(b,o+0x0c)
        payload=b[data_start+do:data_start+do+size]
        if flags&0x04 and payload[:4]==b"Yaz0": payload=yaz0(payload)
        out.append((name,payload))
    return out

def bcsv_hash(s):
    h=0
    for c in s.encode("ascii"): h=(h*0x1f+c)&0xffffffff
    return h

H_NAME=bcsv_hash("name"); H_ZONE=bcsv_hash("ZoneName")

def bcsv_rows(b: bytes):
    if len(b)<0x10: return []
    nr,nf,ro,rs=struct.unpack_from(">IIII",b,0)
    if nr>1_000_000 or nf==0 or nf>256 or rs==0:
        return []
    fields_end=0x10+nf*0x0c
    if fields_end>len(b) or ro<fields_end or ro+nr*rs>len(b):
        return []
    fields=[]
    for i in range(nf):
        o=0x10+i*0x0c
        h,mask,off=struct.unpack_from(">IIH",b,o)
        shift=b[o+0x0a]; ty=b[o+0x0b]
        fields.append((h,mask,off,shift,ty))
    st=ro+nr*rs
    rows=[]
    for r in range(nr):
        base=ro+r*rs; row={}
        for h,mask,off,shift,ty in fields:
            o=base+off
            try:
                if ty==0: v=(be32(b,o)&mask)>>shift
                elif ty==1:
                    raw=b[o:o+0x20].split(b"\0",1)[0]; v=raw.decode("shift_jis","replace")
                elif ty==2: v=struct.unpack_from(">f",b,o)[0]
                elif ty==4: v=(be16(b,o)&mask)>>shift
                elif ty==5: v=(b[o]&mask)>>shift
                elif ty==6: v=cstr(b,st+be32(b,o))
                else: continue
                row[h]=v
            except Exception: pass
        rows.append(row)
    return rows

def j3d_sections(b):
    if b[:4] not in (b"J3D1",b"J3D2"): raise ValueError("not J3D")
    n=be32(b,0x0c); o=0x20; out={}
    for _ in range(n):
        tag=b[o:o+4].decode("ascii","replace"); size=be32(b,o+4)
        out[tag]=b[o:o+size]; o+=size
    return out

def string_table(b,off):
    n=be16(b,off); out=[]
    for i in range(n): out.append(cstr(b,off+be16(b,off+4+i*4+2)))
    return out

def mat3_census(sec, model_name):
    count=be16(sec,8)
    ent=be32(sec,0x0c); rem=be32(sec,0x10); names=string_table(sec,be32(sec,0x14))
    indirect=be32(sec,0x18); cull=be32(sec,0x1c)
    mat_color=be32(sec,0x20); color_chan_num=be32(sec,0x24); color_chan=be32(sec,0x28); amb_color=be32(sec,0x2c)
    texgen_num=be32(sec,0x34); texcoord=be32(sec,0x38); texmtx=be32(sec,0x40); texno=be32(sec,0x48)
    tev_order=be32(sec,0x4c); tev_color=be32(sec,0x50); tev_kcolor=be32(sec,0x54)
    tev_stage_num=be32(sec,0x58); tev_stage=be32(sec,0x5c)
    tev_swap_mode=be32(sec,0x60); tev_swap_table=be32(sec,0x64)
    alpha_off=be32(sec,0x6c); blend_off=be32(sec,0x70)
    rows=[]
    for i in range(count):
        ri=be16(sec,rem+i*2); m=ent+0x14c*ri
        mode=sec[m]; cull_i=sec[m+1]; chan_num_i=sec[m+2]; texgen_num_i=sec[m+3]; tsn_i=sec[m+4]
        stage_count=sec[tev_stage_num+tsn_i] if tev_stage_num else None
        channel_count=sec[color_chan_num+chan_num_i] if color_chan_num else 0
        texgen_count=sec[texgen_num+texgen_num_i] if texgen_num else 0
        cull_mode=be32(sec,cull+cull_i*4) if cull else None

        material_colors=[]
        ambient_colors=[]
        for j in range(2):
            mi=be16(sec,m+0x08+j*2)
            ai=be16(sec,m+0x14+j*2)
            material_colors.append([255,255,255,255] if mi==0xffff or not mat_color else rgba8(sec,mat_color+mi*4))
            ambient_colors.append([255,255,255,255] if ai==0xffff or not amb_color else rgba8(sec,amb_color+ai*4))

        channels=[]
        for j in range(channel_count):
            pair={}
            for label,k in (("color",0),("alpha",1)):
                ci=be16(sec,m+0x0c+(j*2+k)*2)
                if ci==0xffff:
                    pair[label]=None
                else:
                    co=color_chan+ci*8
                    raw=list(sec[co:co+8])
                    if raw[0] not in (0,1):
                        raise ValueError(f"{model_name} material {i} channel enable {raw[0]} is not boolean")
                    pair[label]={
                        "index":ci,
                        "enable":raw[0],
                        "mat_src":raw[1],
                        "light_mask":raw[2],
                        "diff_fn":raw[3],
                        "attn_raw":raw[4],
                        "amb_src":raw[5],
                        "raw":raw,
                    }
            channels.append(pair)

        texgens=[]
        for j in range(texgen_count):
            ti=be16(sec,m+0x28+j*2)
            if ti==0xffff:
                texgens.append(None)
                continue
            to=texcoord+ti*4
            texgen={"index":ti,"type":sec[to],"source":sec[to+1],"matrix":sec[to+2],"raw":list(sec[to:to+4])}
            if texgen["raw"][3] != 0xff:
                raise ValueError(f"{model_name} material {i} texgen {j} pad is {texgen['raw'][3]:#x}")
            mi=be16(sec,m+0x48+j*2)
            if mi!=0xffff and texmtx:
                mo=texmtx+mi*0x64
                if be16(sec,mo+0x02) != 0xffff or be16(sec,mo+0x1a) != 0xffff:
                    raise ValueError(f"{model_name} material {i} tex matrix {mi} sentinel mismatch")
                texgen["tex_mtx"]={
                    "index":mi,
                    "projection":sec[mo],
                    "info":sec[mo+1],
                    "center":[f32(sec,mo+0x04),f32(sec,mo+0x08),f32(sec,mo+0x0c)],
                    "scale":[f32(sec,mo+0x10),f32(sec,mo+0x14)],
                    "rotation_s16":struct.unpack_from(">h",sec,mo+0x18)[0],
                    "translation":[f32(sec,mo+0x1c),f32(sec,mo+0x20)],
                }
            texgens.append(texgen)

        textures=[]
        for j in range(8):
            ti=be16(sec,m+0x84+j*2)
            textures.append(None if ti==0xffff else be16(sec,texno+ti*2))

        tev_konst_colors=[]
        for j in range(4):
            ki=be16(sec,m+0x94+j*2)
            tev_konst_colors.append([255,255,255,255] if ki==0xffff else rgba8(sec,tev_kcolor+ki*4))

        tev_color_registers=[]
        for j in range(4):
            ci=be16(sec,m+0xdc+j*2)
            if ci==0xffff:
                tev_color_registers.append([0,0,0,0])
            else:
                co=tev_color+ci*8
                tev_color_registers.append(list(struct.unpack_from(">hhhh",sec,co)))

        stages=[]
        for j in range(16):
            si=be16(sec,m+0xe4+j*2)
            if si==0xffff: continue
            s=tev_stage+si*0x14
            oi=be16(sec,m+0xbc+j*2)
            order=None
            if oi!=0xffff:
                oo=tev_order+oi*4; order=list(sec[oo:oo+4])
            smi=be16(sec,m+0x104+j*2)
            raster_swap=[0,1,2,3]; texture_swap=[0,1,2,3]
            if smi!=0xffff:
                so=tev_swap_mode+smi*4
                ras_sel=sec[so]; tex_sel=sec[so+1]
                if ras_sel>=4 or tex_sel>=4:
                    raise ValueError(f"{model_name} material {i} stage {j} swap selector out of range")
                for sel,label in ((ras_sel,"raster"),(tex_sel,"texture")):
                    sti=be16(sec,m+0x124+sel*2)
                    table=[0,1,2,3] if sti==0xffff else list(sec[tev_swap_table+sti*4:tev_swap_table+sti*4+4])
                    if any(ch>3 for ch in table):
                        raise ValueError(f"{model_name} material {i} stage {j} {label} swap {table} invalid")
                    if label=="raster": raster_swap=table
                    else: texture_swap=table
            stages.append({
                "slot":j,"stage_index":si,
                "color":list(sec[s+1:s+10]),
                "alpha":list(sec[s+0x0a:s+0x13]),
                "order":order,
                "konst_color":sec[m+0x9c+j],
                "konst_alpha":sec[m+0xac+j],
                "raster_swap":raster_swap,
                "texture_swap":texture_swap,
            })
        ai=be16(sec,m+0x146); bi=be16(sec,m+0x148)
        alpha=list(sec[alpha_off+ai*8:alpha_off+ai*8+8]) if alpha_off else None
        blend=list(sec[blend_off+bi*4:blend_off+bi*4+4]) if blend_off else None
        has_indirect=bool(indirect and indirect!=be32(sec,0x14) and sec[indirect+i*0x138]==1)
        rows.append({
            "model":model_name,"material_index":i,
            "material_name":names[i] if i<len(names) else f"material_{i}",
            "mode":mode,"cull":cull_mode,
            "light_channel_count":channel_count,
            "material_colors":material_colors,
            "ambient_colors":ambient_colors,
            "channels":channels,
            "texgen_count":texgen_count,
            "texgens":texgens,
            "tev_konst_colors":tev_konst_colors,
            "tev_color_registers":tev_color_registers,
            "stage_count_declared":stage_count,
            "texture_indices":textures,"has_indirect":has_indirect,
            "stages":stages,"alpha_compare":alpha,"blend":blend,
        })
    return rows

def tex1_census(sec):
    count=be16(sec,8); headers=be32(sec,0x0c); names=string_table(sec,be32(sec,0x10))
    rows=[]
    for i in range(count):
        h=headers+i*0x20
        rows.append({
            "index":i,"name":names[i] if i<len(names) else f"texture_{i}",
            "format":sec[h],"width":be16(sec,h+2),"height":be16(sec,h+4),
            "palette_format":sec[h+9],"palette_count":be16(sec,h+0x0a),
            "mip_count":sec[h+0x18],
        })
    return rows

def shp1_census(sec):
    count=be16(sec,8); init=be32(sec,0x0c); rem=be32(sec,0x10)
    vals=[]
    for i in range(count):
        ri=be16(sec,rem+i*2)
        vals.append(sec[init+ri*0x28])
    return vals

def canonical_signature(m):
    keep={k:m[k] for k in ("mode","cull","stage_count_declared","texture_indices","has_indirect","stages","alpha_compare","blend")}
    return json.dumps(keep,sort_keys=True,separators=(",",":"))

def ras_signature(m):
    keep={k:m[k] for k in ("light_channel_count","channels","texgen_count","texgens")}
    return json.dumps(keep,sort_keys=True,separators=(",",":"))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--base",default=BASE_DEFAULT)
    ap.add_argument("--galaxy",default="EggStarGalaxy")
    ap.add_argument("--max-objects",type=int,default=220)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    base=a.base.rstrip("/"); galaxy=a.galaxy

    scenario_url=f"{base}/StageData/{galaxy}/{galaxy}Scenario.arc"
    scenario=rarc_files(fetch(scenario_url))
    zone_rows=[]
    for name,payload in scenario:
        if name.lower()=="zonelist.bcsv": zone_rows=bcsv_rows(payload); break
    zones=[r.get(H_ZONE) for r in zone_rows if isinstance(r.get(H_ZONE),str)]
    if not zones: raise RuntimeError("ZoneList.bcsv yielded no zones")

    object_names=set(); zone_failures=[]
    for zone in zones:
        try: files=rarc_files(fetch(f"{base}/StageData/{zone}.arc"))
        except Exception as e:
            zone_failures.append({"zone":zone,"error":str(e)}); continue
        for name,payload in files:
            if name.lower()=="stageobjinfo": continue
            try: rows=bcsv_rows(payload)
            except Exception: continue
            if not rows: continue
            for row in rows:
                v=row.get(H_NAME)
                if isinstance(v,str) and v and len(v)<128: object_names.add(v)

    objects=sorted(object_names)[:a.max_objects]
    failures=[]; materials=[]; textures=[]; shape_types=[]; models=0

    def inspect_object(obj):
        try:
            arc=rarc_files(fetch(object_url(base,obj)))
        except Exception as e:
            return obj, None, {"object":obj,"stage":"download","error":str(e)}
        models_found=[(name,p) for name,p in arc if name.lower().endswith((".bdl",".bmd"))]
        if not models_found:
            return obj, None, None
        models_found.sort(key=lambda x:(x[0].rsplit(".",1)[0].lower()!=obj.lower(),x[0].lower()))
        name,b=models_found[0]
        try:
            secs=j3d_sections(b)
            if "MAT3" not in secs or "TEX1" not in secs or "SHP1" not in secs:
                raise ValueError(f"missing core sections {sorted(secs)}")
            mats=mat3_census(secs["MAT3"],obj)
            tex=tex1_census(secs["TEX1"])
            for t in tex: t["model"]=obj
            shapes=shp1_census(secs["SHP1"])
            return obj, (mats,tex,shapes), None
        except Exception as e:
            return obj, None, {"object":obj,"model_file":name,"stage":"j3d","error":str(e)}

    inspected=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        for item in pool.map(inspect_object, objects):
            inspected.append(item)
    # pool.map preserves input order, so structural output remains deterministic.
    for obj,payload,error in inspected:
        if error is not None:
            failures.append(error)
            continue
        if payload is None:
            continue
        mats,tex,shapes=payload
        materials.extend(mats); textures.extend(tex); shape_types.extend(shapes); models+=1

    sig=collections.Counter(canonical_signature(m) for m in materials)
    examples={}
    for m in materials:
        s=canonical_signature(m)
        examples.setdefault(s,[]).append(f"{m['model']}::{m['material_name']}")
    top=[]
    for s,n in sig.most_common(50):
        top.append({"count":n,"examples":examples[s][:12],"signature":json.loads(s)})
    fmt=collections.Counter(t["format"] for t in textures)
    shape=collections.Counter(shape_types)
    non_identity_raster_swaps=sum(1 for m in materials for s in m["stages"] if s["raster_swap"] != [0,1,2,3])
    non_identity_texture_swaps=sum(1 for m in materials for s in m["stages"] if s["texture_swap"] != [0,1,2,3])
    tex_matrices=sum(1 for m in materials for t in m["texgens"] if t and "tex_mtx" in t)
    signed_tev_register_materials=sum(1 for m in materials if any(any(v != 0 for v in reg) for reg in m["tev_color_registers"]))
    ras=collections.Counter(ras_signature(m) for m in materials)
    ras_examples={}
    for m in materials:
        s=ras_signature(m)
        ras_examples.setdefault(s,[]).append(f"{m['model']}::{m['material_name']}")
    top_ras=[
        {"count":n,"examples":ras_examples[s][:12],"signature":json.loads(s)}
        for s,n in ras.most_common(30)
    ]
    result={
        "source":{"galaxy":galaxy,"scenario_url":scenario_url,"base":base},
        "counts":{
            "zones":len(zones),"placement_object_names":len(object_names),
            "objects_attempted":len(objects),"models_parsed":models,
            "materials":len(materials),"textures":len(textures),"failures":len(failures),
            "tex_matrices":tex_matrices,
            "non_identity_raster_swaps":non_identity_raster_swaps,
            "non_identity_texture_swaps":non_identity_texture_swaps,
            "materials_with_nonzero_signed_tev_registers":signed_tev_register_materials,
        },
        "zones":zones,
        "zone_failures":zone_failures,
        "texture_format_counts":{f"0x{k:02x}":v for k,v in sorted(fmt.items())},
        "shape_matrix_type_counts":{str(k):v for k,v in sorted(shape.items())},
        "top_material_signatures":top,
        "top_raster_contracts":top_ras,
        "materials":materials,
        "failures":failures[:300],
        "provenance":{
            "script":"tools/smg_rmge01_j3d_material_census_v1.py",
            "policy":"retail files are fetched transiently; only structural census JSON is retained",
        },
    }
    raw=json.dumps(result,indent=2,sort_keys=True)+"\n"
    result["provenance"]["result_sha256"]=hashlib.sha256(raw.encode()).hexdigest()
    Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result["counts"],indent=2))
    print("texture formats",result["texture_format_counts"])
    print("shape matrix types",result["shape_matrix_type_counts"])
    for row in top_ras[:8]:
        print("RAS",row["count"],row["examples"][:3],json.dumps(row["signature"],sort_keys=True)[:900])
    for row in top[:10]:
        print("SIG",row["count"],row["examples"][:3],json.dumps(row["signature"],sort_keys=True)[:500])

if __name__=="__main__": main()

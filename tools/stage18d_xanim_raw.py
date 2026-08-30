#!/usr/bin/env python3
"""Stage 18D: direct T6 XAnimParts raw-stream parser and MP7 animation proof.

Authority: expanded retail T6 XFile bytes. No OpenAssetTools executable is used.
External struct/zone-code descriptions may be used only as layout corroboration.

Current proof scope:
- 104-byte PC32 XAnimParts fixed record
- inline XAnim name parsing
- boneCount[PART_TYPE_ALL] (boneCount[9]) as exact ScriptString-name count
- XAnimNotifyInfo decoding (8 bytes: uint16 ScriptString + padding + float time)
- exact serialized child order for names, notify, deltaPart, raw data arrays, indices
- byte ranges + SHA-256 for every directly walkable child buffer
- exact boundary validation where the next inline-name XAnim begins immediately
- detailed MP7 base-viewmodel animation manifest

Complex delta-track payloads are deliberately not guessed. Their 12-byte XAnimDeltaPart
header is recorded, but exact child walking stops unless all three delta child pointers
are null (or the top-level deltaPart pointer itself is null/packed). This preserves the
proof boundary while the delta subformats are recovered independently.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import re
import struct
from pathlib import Path
from typing import Any

PTR_FOLLOWING = 0xFFFFFFFF
PTR_INSERT = 0xFFFFFFFE
XANIM_SIZE_PC32 = 104
XANIM_NOTIFY_SIZE_PC32 = 8
PART_TYPE_ALL_INDEX = 9
PTR_FIELDS = ["names", "dataByte", "dataShort", "dataInt", "randomDataShort", "randomDataByte", "randomDataInt", "indices", "notify", "deltaPart"]


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("t6raw", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sha256_slice(data: bytes, start: int, end: int) -> str:
    return hashlib.sha256(memoryview(data)[start:end]).hexdigest()


def read_cstring(data: bytes, pos: int, maxlen: int = 256):
    end = data.find(b"\0", pos, min(len(data), pos + maxlen + 1))
    if end < 0 or end == pos:
        return None
    raw = data[pos:end]
    if any(c < 32 or c > 126 for c in raw):
        return None
    return raw.decode("ascii"), end + 1


def parse_fixed(data: bytes, start: int) -> dict[str, Any]:
    name_ptr = struct.unpack_from("<I", data, start)[0]
    counts = struct.unpack_from("<6H", data, start + 4)
    bone_count = list(data[start + 24:start + 34])
    ptr_values = struct.unpack_from("<10I", data, start + 64)
    framerate, frequency, primed_length, loop_entry_time = struct.unpack_from("<4f", data, start + 48)
    return {
        "raw_struct_offset": start,
        "raw_struct_size": XANIM_SIZE_PC32,
        "name_ptr": name_ptr,
        "dataByteCount": counts[0], "dataShortCount": counts[1], "dataIntCount": counts[2],
        "randomDataByteCount": counts[3], "randomDataIntCount": counts[4], "numframes": counts[5],
        "bLoop": data[start + 16], "bDelta": data[start + 17], "bDelta3D": data[start + 18], "bLeftHandGripIK": data[start + 19],
        "streamedFileSize": struct.unpack_from("<I", data, start + 20)[0],
        "boneCount": bone_count, "notifyCount": data[start + 34], "assetType": data[start + 35], "isDefault": data[start + 36],
        "padding_37_39": data[start + 37:start + 40].hex(),
        "randomDataShortCount": struct.unpack_from("<I", data, start + 40)[0],
        "indexCount": struct.unpack_from("<I", data, start + 44)[0],
        "framerate": framerate, "frequency": frequency, "primedLength": primed_length, "loopEntryTime": loop_entry_time,
        "pointers": dict(zip(PTR_FIELDS, ptr_values)),
    }


def valid_fixed(rec, data, block_sizes, rawmod):
    if rec["name_ptr"] != PTR_FOLLOWING or rec["padding_37_39"] != "000000": return False
    if any(v not in (0, 1) for v in (rec["bLoop"], rec["bDelta"], rec["bDelta3D"], rec["bLeftHandGripIK"], rec["isDefault"])): return False
    if rec["numframes"] > 8192 or rec["notifyCount"] > 128 or rec["assetType"] > 16: return False
    if rec["randomDataShortCount"] > 2_000_000 or rec["indexCount"] > 2_000_000: return False
    if any(not math.isfinite(rec[f]) or abs(rec[f]) > 100000 for f in ("framerate", "frequency", "primedLength", "loopEntryTime")): return False
    for value in rec["pointers"].values():
        if value in (0, PTR_FOLLOWING, PTR_INSERT): continue
        dec = rawmod.decode_zone_pointer(value, block_sizes)
        if dec.get("kind") != "packed" or not dec.get("valid_for_declared_block_size"): return False
    return True


def scan_inline_name_records(data, front, rawmod):
    block_sizes = [b["bytes"] for b in front["block_sizes"]]
    out, pos, needle = [], front["asset_body_stream_raw_offset"], b"\xff\xff\xff\xff"
    while True:
        st = data.find(needle, pos)
        if st < 0: break
        pos = st + 1
        if st + XANIM_SIZE_PC32 + 2 >= len(data): continue
        parsed_name = read_cstring(data, st + XANIM_SIZE_PC32, 160)
        if parsed_name is None or not re.fullmatch(r"[A-Za-z0-9_./+\-]{2,160}", parsed_name[0]): continue
        try: rec = parse_fixed(data, st)
        except (ValueError, struct.error): continue
        if valid_fixed(rec, data, block_sizes, rawmod):
            rec["name"] = parsed_name[0]; out.append(rec)
    by_offset = {r["raw_struct_offset"]: r for r in out}
    return [by_offset[k] for k in sorted(by_offset)]


def script_string_name(script_strings, sid):
    if 0 <= sid < len(script_strings) and isinstance(script_strings[sid], str): return script_strings[sid]
    return None


def segment(data, name, start, size):
    end = start + size
    return {"name": name, "raw_offset": start, "bytes": size, "raw_end_offset": end, "sha256": sha256_slice(data, start, end)}


def walk_direct_children(data, rec, script_strings, rawmod, block_sizes):
    start, pos = rec["raw_struct_offset"], rec["raw_struct_offset"] + XANIM_SIZE_PC32
    result = {"status": "exact", "segments": [], "bone_scriptstrings": [], "notifies": [], "delta": None}
    parsed = read_cstring(data, pos, 256)
    if parsed is None: return {"status": "invalid_inline_name"}
    nm, end = parsed; result["inline_name"] = nm; result["segments"].append(segment(data, "name", pos, end-pos)); pos = end
    ptrs = rec["pointers"]
    names_count = rec["boneCount"][PART_TYPE_ALL_INDEX]
    if ptrs["names"] == PTR_FOLLOWING:
        size = names_count * 2; s = segment(data, "names", pos, size); s["count"] = names_count; result["segments"].append(s)
        ids = list(struct.unpack_from(f"<{names_count}H", data, pos)) if names_count else []
        result["bone_scriptstrings"] = [{"index": i, "scriptstring_id": sid, "name": script_string_name(script_strings, sid)} for i, sid in enumerate(ids)]; pos += size
    if ptrs["notify"] == PTR_FOLLOWING:
        size = rec["notifyCount"] * XANIM_NOTIFY_SIZE_PC32; s = segment(data, "notify", pos, size); s["count"] = rec["notifyCount"]; result["segments"].append(s)
        for i in range(rec["notifyCount"]):
            off = pos + i*8; sid = struct.unpack_from("<H", data, off)[0]; time = struct.unpack_from("<f", data, off+4)[0]
            result["notifies"].append({"index": i, "scriptstring_id": sid, "name": script_string_name(script_strings, sid), "time": time})
        pos += size
    if ptrs["deltaPart"] == PTR_FOLLOWING:
        trans, quat2, quat = struct.unpack_from("<III", data, pos); dseg = segment(data, "deltaPart_fixed", pos, 12)
        dseg.update({"trans_raw": f"0x{trans:08X}", "quat2_raw": f"0x{quat2:08X}", "quat_raw": f"0x{quat:08X}"}); result["segments"].append(dseg)
        result["delta"] = {"raw_offset": pos, "trans": trans, "quat2": quat2, "quat": quat}; pos += 12
        if any(v == PTR_FOLLOWING for v in (trans, quat2, quat)):
            result["status"] = "complex_delta_deferred"; result["exact_walk_end_raw_offset"] = pos; return result
    arrays = [("dataByte", rec["dataByteCount"], 1), ("dataShort", rec["dataShortCount"], 2), ("dataInt", rec["dataIntCount"], 4),
              ("randomDataShort", rec["randomDataShortCount"], 2), ("randomDataByte", rec["randomDataByteCount"], 1), ("randomDataInt", rec["randomDataIntCount"], 4),
              ("indices", rec["indexCount"], 1 if rec["numframes"] < 256 else 2)]
    for field, count, unit in arrays:
        if ptrs[field] == PTR_FOLLOWING:
            size = count*unit; s = segment(data, field, pos, size); s.update({"count": count, "element_bytes": unit}); result["segments"].append(s); pos += size
    result["exact_walk_end_raw_offset"] = pos; result["exact_total_serialized_bytes_from_fixed_start"] = pos-start; result["exact_serialized_sha256"] = sha256_slice(data, start, pos)
    return result


def write_csv(path, rows):
    if not rows: path.write_text("", encoding="utf-8"); return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--stream",type=Path,required=True); ap.add_argument("--raw-parser",type=Path,required=True); ap.add_argument("--outdir",type=Path,required=True); ap.add_argument("--candidate-json",type=Path)
    args=ap.parse_args(); args.outdir.mkdir(parents=True,exist_ok=True); data=args.stream.read_bytes(); rawmod=load_module(args.raw_parser); front=rawmod.parse_front(data); block_sizes=[b["bytes"] for b in front["block_sizes"]]
    if args.candidate_json:
        old=json.loads(args.candidate_json.read_text()); candidates=[]
        for o in old:
            st=int(o["raw_struct_offset"]); rec=parse_fixed(data,st); nm=read_cstring(data,st+104,160); assert nm and valid_fixed(rec,data,block_sizes,rawmod); rec["name"]=nm[0]; candidates.append(rec)
        candidates.sort(key=lambda r:r["raw_struct_offset"]); candidate_source=str(args.candidate_json)
    else: candidates=scan_inline_name_records(data,front,rawmod); candidate_source="direct_scan"
    details=[]; summaries=[]; exact=complex_delta=direct_boundaries=overlaps=0
    for i,rec in enumerate(candidates):
        walk=walk_direct_children(data,rec,front["script_strings"],rawmod,block_sizes); nxt=candidates[i+1]["raw_struct_offset"] if i+1<len(candidates) else None; gap=None
        if walk.get("status")=="exact":
            exact+=1
            if nxt is not None:
                gap=nxt-walk["exact_walk_end_raw_offset"]; direct_boundaries += (gap==0); overlaps += (gap<0)
        elif walk.get("status")=="complex_delta_deferred": complex_delta+=1
        d={**rec,"walk":walk,"next_inline_xanim_raw_offset":nxt,"gap_from_exact_end_to_next_inline":gap}; details.append(d)
        summaries.append({"name":rec["name"],"raw_struct_offset":rec["raw_struct_offset"],"numframes":rec["numframes"],"framerate":rec["framerate"],"frequency":rec["frequency"],"loop":rec["bLoop"],"delta":rec["bDelta"],"left_hand_grip_ik":rec["bLeftHandGripIK"],"asset_type":rec["assetType"],"bone_track_name_count":rec["boneCount"][9],"notify_count":rec["notifyCount"],"walk_status":walk.get("status"),"exact_walk_end_raw_offset":walk.get("exact_walk_end_raw_offset"),"gap_to_next_inline_xanim":gap})
    mp7=[d for d in details if d["name"].startswith("viewmodel_mp7_")]; mp7_offsets={d["raw_struct_offset"] for d in mp7}; failures=[]; mp7_rows=[]
    for d in mp7:
        w=d["walk"]; gap=d.get("gap_from_exact_end_to_next_inline"); nxt=d.get("next_inline_xanim_raw_offset")
        if nxt in mp7_offsets and gap!=0: failures.append({"name":d["name"],"next_raw_offset":nxt,"gap":gap})
        mp7_rows.append({"name":d["name"],"raw_struct_offset":d["raw_struct_offset"],"numframes":d["numframes"],"framerate":d["framerate"],"frequency":d["frequency"],"loop":d["bLoop"],"delta":d["bDelta"],"bone_track_name_count":d["boneCount"][9],"notify_count":d["notifyCount"],"data_byte_count":d["dataByteCount"],"data_short_count":d["dataShortCount"],"data_int_count":d["dataIntCount"],"random_data_short_count":d["randomDataShortCount"],"random_data_byte_count":d["randomDataByteCount"],"index_count":d["indexCount"],"serialized_end_raw_offset":w.get("exact_walk_end_raw_offset"),"serialized_sha256":w.get("exact_serialized_sha256"),"gap_to_next_inline_xanim":gap})
    (args.outdir/"common_mp_xanim_inline_assets.json").write_text(json.dumps(details,indent=2)); write_csv(args.outdir/"common_mp_xanim_inline_assets.csv",summaries); (args.outdir/"mp7_base_xanim_raw.json").write_text(json.dumps(mp7,indent=2)); write_csv(args.outdir/"mp7_base_xanim_raw.csv",mp7_rows)
    reload=next((d for d in mp7 if d["name"]=="viewmodel_mp7_reload"),None)
    proof={"stage":"18D raw XAnimParts proof","authority":"raw expanded common_mp XFile; no OpenAssetTools executable","expanded_stream_sha256":hashlib.sha256(data).hexdigest(),"expanded_stream_bytes":len(data),"xanim_asset_count_from_raw_xasset_list":front["asset_type_counts"].get("XANIMPARTS",0),"inline_name_xanim_fixed_records":len(candidates),"candidate_source":candidate_source,"struct_sizes_pc32_raw_proven":{"XAnimParts":104,"XAnimNotifyInfo":8,"XAnimDeltaPart_fixed":12},"part_type_all_index":9,"part_type_all_semantics":"boneCount[9] is the exact ScriptString name count; summing boneCount[] is incorrect","directly_walkable_inline_records":exact,"complex_delta_records_deferred":complex_delta,"exact_end_equals_next_inline_start":direct_boundaries,"exact_walk_overlaps_next_inline_start":overlaps,"mp7_base_viewmodel_xanim_records":len(mp7),"mp7_all_walk_status_exact":all(d["walk"].get("status")=="exact" for d in mp7),"mp7_consecutive_boundary_failures":failures,"mp7_consecutive_boundaries_exact":not failures,"mp7_reload_canary":reload,"proof_boundary":{"not_yet_claimed":["all 4233 XAnimParts names (packed-name records remain)","complex XAnimDeltaPart trans/quat payload decoding","final quaternion/translation curve reconstruction for all animations"],"next":"recover packed-name XAnimParts identity and independently decode complex delta-track variable unions"}}
    (args.outdir/"xanim_raw_proof.json").write_text(json.dumps(proof,indent=2)); print(json.dumps({k:v for k,v in proof.items() if k!="mp7_reload_canary"},indent=2))
if __name__=="__main__": main()

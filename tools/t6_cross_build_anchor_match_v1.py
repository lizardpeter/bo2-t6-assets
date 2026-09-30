#!/usr/bin/env python3
"""Conservative T6 current-client <-> PC-server changed-byte anchor matcher v1.

This is a candidate generator, not an identity promoter.

It uses exact one-to-one byte-hash anchors already accepted in uregraph. Between
consecutive anchors, it considers only intervals where:
  * server and current-client address order are both monotonic;
  * endpoint server->client deltas are close;
  * the number of interior function starts is identical;
  * each ordinally paired interior start has a small relative-offset error.

Server aliases at the same VA are retained and flagged; no ambiguous alias set is
promoted automatically.
"""
from __future__ import annotations
import argparse,csv,gzip,json,math
from collections import defaultdict
from pathlib import Path

VA_CANDIDATES=("va","address","start_va","address_start","rva_va","primary_va","function_va")
NAME_CANDIDATES=("name","symbol","symbol_name","function_name","display_name","decorated_name")
OBJECT_CANDIDATES=("object","object_name","origin","module","compiland")
SIZE_CANDIDATES=("code_size","size","length","exact_size_bytes","procedure_size")

def parse_int(v):
    if v is None: return None
    s=str(v).strip()
    if not s: return None
    try: return int(s,0)
    except Exception:
        try:
            if all(c in "0123456789abcdefABCDEF" for c in s):
                return int(s,16)
        except Exception: pass
    return None

def choose_col(fields,candidates):
    lower={f.lower():f for f in fields}
    for c in candidates:
        if c in lower: return lower[c]
    return None

def discover_va_col(rows,fields):
    named=choose_col(fields,VA_CANDIDATES)
    if named: return named
    best=None; best_score=-1
    sample=rows[:min(len(rows),2000)]
    for f in fields:
        vals=[parse_int(r.get(f)) for r in sample]
        usable=[v for v in vals if v is not None]
        if not usable: continue
        in_image=sum(0x00400000 <= v <= 0x03000000 for v in usable)
        score=in_image/len(sample)
        if score>best_score:
            best_score=score; best=f
    if best is None or best_score<0.5:
        raise SystemExit(f"could not discover server VA column; fields={fields}")
    return best

def load_server(path):
    opener=gzip.open if path.suffix==".gz" else open
    with opener(path,"rt",encoding="utf-8-sig",newline="") as f:
        rd=csv.DictReader(f)
        rows=list(rd); fields=rd.fieldnames or []
    va_col=discover_va_col(rows,fields)
    name_col=choose_col(fields,NAME_CANDIDATES)
    obj_col=choose_col(fields,OBJECT_CANDIDATES)
    size_col=choose_col(fields,SIZE_CANDIDATES)
    groups=defaultdict(list)
    for r in rows:
        va=parse_int(r.get(va_col))
        if va is None: continue
        name=(r.get(name_col,"") if name_col else "").strip()
        obj=(r.get(obj_col,"") if obj_col else "").strip()
        size=parse_int(r.get(size_col)) if size_col else None
        groups[va].append({"name":name,"object":obj,"size":size})
    return groups,{"va_col":va_col,"name_col":name_col,"object_col":obj_col,"size_col":size_col,
                   "rows":len(rows),"unique_vas":len(groups),"fields":fields}

def load_client(path):
    with path.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f,dialect="excel-tab")
        rows=list(rd)
    byva={}
    for r in rows:
        va=parse_int(r.get("entry_va"))
        if va is not None: byva[va]=r
    return byva

def load_anchors(path):
    with path.open(encoding="utf-8",newline="") as f:
        rd=csv.DictReader(f,dialect="excel-tab")
        rows=list(rd)
    out=[]
    for r in rows:
        c=parse_int(r["current_va"]); s=parse_int(r["server_va"])
        if c is None or s is None: continue
        out.append({**r,"current_va_int":c,"server_va_int":s})
    out.sort(key=lambda x:x["current_va_int"])
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--client-catalog",type=Path,required=True)
    ap.add_argument("--server-functions",type=Path,required=True)
    ap.add_argument("--anchors",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--summary",type=Path,required=True)
    ap.add_argument("--max-anchor-delta-drift",type=int,default=32)
    ap.add_argument("--max-interior-offset-error",type=int,default=64)
    ap.add_argument("--max-functions-per-interval",type=int,default=128)
    a=ap.parse_args()

    client=load_client(a.client_catalog)
    server,server_schema=load_server(a.server_functions)
    anchors=load_anchors(a.anchors)
    client_vas=sorted(client)
    server_vas=sorted(server)
    anchor_client={x["current_va_int"] for x in anchors}
    anchor_server={x["server_va_int"] for x in anchors}

    candidates=[]; interval_stats=defaultdict(int)
    for left,right in zip(anchors,anchors[1:]):
        c1,c2=left["current_va_int"],right["current_va_int"]
        s1,s2=left["server_va_int"],right["server_va_int"]
        if c2<=c1 or s2<=s1:
            interval_stats["non_monotonic"]+=1; continue
        d1=c1-s1; d2=c2-s2
        if abs(d2-d1)>a.max_anchor_delta_drift:
            interval_stats["delta_drift"]+=1; continue
        cvs=[v for v in client_vas if c1<v<c2]
        svs=[v for v in server_vas if s1<v<s2]
        if len(cvs)!=len(svs):
            interval_stats["count_mismatch"]+=1; continue
        if len(cvs)>a.max_functions_per_interval:
            interval_stats["too_large"]+=1; continue
        interval_stats["eligible"]+=1
        for rank,(cv,sv) in enumerate(zip(cvs,svs),1):
            if cv in anchor_client or sv in anchor_server:
                continue
            rel_c=cv-c1; rel_s=sv-s1; err=rel_c-rel_s
            if abs(err)>a.max_interior_offset_error:
                continue
            aliases=server[sv]
            distinct_names=sorted({x["name"] for x in aliases if x["name"]})
            distinct_objects=sorted({x["object"] for x in aliases if x["object"]})
            sizes=sorted({x["size"] for x in aliases if x["size"] is not None})
            cr=client[cv]
            candidates.append({
                "current_va":f"0x{cv:08X}",
                "current_ghidra_name":cr.get("name",""),
                "current_instruction_count":cr.get("instruction_count",""),
                "current_call_reference_count":cr.get("call_reference_count",""),
                "current_body_address_count":cr.get("body_address_count",""),
                "server_va":f"0x{sv:08X}",
                "server_names":" | ".join(distinct_names),
                "server_objects":" | ".join(distinct_objects),
                "server_sizes":" | ".join(str(x) for x in sizes),
                "server_alias_count":len(distinct_names) if distinct_names else len(aliases),
                "left_current_anchor":f"0x{c1:08X}",
                "right_current_anchor":f"0x{c2:08X}",
                "left_server_anchor":f"0x{s1:08X}",
                "right_server_anchor":f"0x{s2:08X}",
                "anchor_delta_left":d1,
                "anchor_delta_right":d2,
                "ordinal_rank":rank,
                "interval_function_count":len(cvs),
                "relative_offset_error":err,
                "candidate_state":"candidate-anchor-ordinal-layout",
            })

    a.output.parent.mkdir(parents=True,exist_ok=True)
    fields=list(candidates[0].keys()) if candidates else [
      "current_va","current_ghidra_name","server_va","server_names","candidate_state"
    ]
    with a.output.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,dialect="excel-tab",lineterminator="\n")
        w.writeheader(); w.writerows(candidates)

    unique_alias=[x for x in candidates if int(x["server_alias_count"])==1]
    summary={
      "format":"t6-current-client-server-anchor-ordinal-candidates-v1",
      "proof_boundary":"Candidate generation only. Exact anchors are accepted evidence; interior ordinal/address-layout matches are not semantic identities until independently corroborated.",
      "anchor_count":len(anchors),
      "client_catalog_functions":len(client),
      "server_unique_function_starts":len(server),
      "server_schema":server_schema,
      "thresholds":{
        "max_anchor_delta_drift":a.max_anchor_delta_drift,
        "max_interior_offset_error":a.max_interior_offset_error,
        "max_functions_per_interval":a.max_functions_per_interval,
      },
      "interval_stats":dict(interval_stats),
      "candidate_rows":len(candidates),
      "single_name_candidate_rows":len(unique_alias),
      "ambiguous_alias_candidate_rows":len(candidates)-len(unique_alias),
    }
    a.summary.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=="__main__": main()

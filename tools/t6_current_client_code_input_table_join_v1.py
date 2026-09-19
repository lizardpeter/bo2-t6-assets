#!/usr/bin/env python3
"""Join pinned OAT T6 code input tables to exact 20-byte current-client rows.

Observed candidate row layout:
  +0x00 accessor char*
  +0x04 enum value
  +0x08 0
  +0x0c 0
  +0x10 0
Rows are promoted only when the accessor string is found exactly in a raw-backed
client section and an exact dword pointer to that string begins the 20-byte row.

This proves static table representation for the SHA-classified current client.
It does not prove runtime provider values, update scheduling, API calls, or
historical-retail equivalence.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path

CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-code-input-table-join-v1"
ROW_BYTES=20

class E(RuntimeError): pass
def req(c,m):
    if not c: raise E(m)

def parse_pe(raw:bytes):
    pe=struct.unpack_from("<I",raw,0x3c)[0];req(raw[pe:pe+4]==b"PE\0\0","bad PE")
    coff=pe+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;req(struct.unpack_from("<H",raw,opt)[0]==0x10b,"not PE32")
    ib=struct.unpack_from("<I",raw,opt+28)[0];so=opt+optsz;secs=[]
    for i in range(n):
        q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
        vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8)
        secs.append({"name":name,"va":ib+rva,"virtualSize":vs,"rawSize":rs,"rawOffset":ro})
    return ib,secs

def raw_to_va(sec,off): return sec["va"]+(off-sec["rawOffset"])

def exact_string_vas(raw,secs,text):
    needle=text.encode("utf-8")+b"\0";out=[]
    for s in secs:
        blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]]
        pos=0
        while True:
            i=blob.find(needle,pos)
            if i<0:break
            # exact C string boundary: preceding byte may be anything; the start is
            # authoritative because pointer consumers address this byte exactly.
            out.append({"va":raw_to_va(s,s["rawOffset"]+i),"section":s["name"],"rawOffset":s["rawOffset"]+i})
            pos=i+1
    return out

def row_occurrences(raw,secs,string_vas,enum_value):
    targets=set(x["va"] for x in string_vas);out=[]
    for s in secs:
        start=s["rawOffset"];end=start+s["rawSize"]
        for p in range(start,end-ROW_BYTES+1,4):
            ptr,val,z0,z1,z2=struct.unpack_from("<IIIII",raw,p)
            if ptr in targets and val==(enum_value&0xffffffff) and z0==z1==z2==0:
                out.append({"rowVa":raw_to_va(s,p),"rowRawOffset":p,"section":s["name"],
                            "accessorPointerVa":ptr,"enumValue":val,
                            "rawDwords":[f"0x{x:08x}" for x in (ptr,val,z0,z1,z2)]})
    return out

def join_table(raw,secs,doc,label):
    rows=doc.get("rows");req(isinstance(rows,list) and rows,f"{label}: missing rows")
    out=[];matched=0;unique=0
    for source_index,r in enumerate(rows):
        acc=str(r.get("accessor") or "");req(acc,f"{label}: empty accessor at {source_index}")
        enum=int(r["enumValue"])
        strings=exact_string_vas(raw,secs,acc)
        matches=row_occurrences(raw,secs,strings,enum)
        if matches:matched+=1
        if len(matches)==1:unique+=1
        out.append({
          "sourceIndex":source_index,"accessor":acc,"enumSymbol":r.get("enumSymbol"),"enumValue":enum,
          "updateFrequency":r.get("updateFrequency"),"stringOccurrences":strings,"rowMatches":matches,
          "status":"unique-exact-row" if len(matches)==1 else ("absent" if not matches else "ambiguous-multiple-rows")
        })
    unique_rows=[(x["sourceIndex"],x["rowMatches"][0]["rowVa"]) for x in out if len(x["rowMatches"])==1]
    source_order_monotonic=all(b[1]>a[1] for a,b in zip(unique_rows,unique_rows[1:]))
    contiguous_pairs=sum(1 for a,b in zip(unique_rows,unique_rows[1:]) if b[0]==a[0]+1 and b[1]-a[1]==ROW_BYTES)
    return {
      "sourceFormat":doc.get("format"),"sourceRowCount":len(rows),"matchedSourceRowCount":matched,
      "uniqueExactRowCount":unique,"ambiguousRowCount":sum(len(x["rowMatches"])>1 for x in out),
      "absentRowCount":sum(not x["rowMatches"] for x in out),
      "uniqueRowsSourceOrderMonotonicInClient":source_order_monotonic,
      "adjacentSourceRowsAlsoAdjacentClientRowCount":contiguous_pairs,
      "rows":out
    }

def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True)
    ap.add_argument("--samplers",type=Path,required=True);ap.add_argument("--constants",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();digest=hashlib.sha256(raw).hexdigest();req(digest==CLIENT_SHA,f"client SHA drift {digest}")
    ib,secs=parse_pe(raw);sam=json.loads(a.samplers.read_text());con=json.loads(a.constants.read_text())
    req(sam.get("format")=="t6-code-sampler-source-table-v1","sampler source format drift")
    req(con.get("format")=="t6-code-constant-source-table-v1","constant source format drift")
    sj=join_table(raw,secs,sam,"sampler");cj=join_table(raw,secs,con,"constant")
    required={
      "lightmapSamplerPrimary":4,"lightmapSamplerSecondary":5,"reflectionProbeSampler":26,
      "attenuationSampler":15,"dlightAttenuationSampler":16,
      "hdrControl0":123,"hdrControl1":124,
    }
    by={x["accessor"]:x for x in sj["rows"]+cj["rows"]}
    required_rows={}
    for acc,val in required.items():
        r=by.get(acc);req(r is not None,f"required pinned accessor absent from source tables: {acc}")
        req(int(r["enumValue"])==val,f"{acc}: pinned enum {r['enumValue']} != {val}")
        req(len(r["rowMatches"])==1,f"{acc}: exact client row count {len(r['rowMatches'])}")
        required_rows[acc]=r["rowMatches"][0]
    doc={
      "format":FORMAT,"authority":"SHA-classified current Plutonium client + pinned OAT T6 source tables",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":digest,"imageBaseHex":f"0x{ib:08x}"},
      "rowLayout":{"bytes":ROW_BYTES,"fields":[
        {"offset":0,"meaning":"exact accessor C-string pointer"},
        {"offset":4,"meaning":"exact enum numeric value"},
        {"offset":8,"meaning":"zero in promoted row"},
        {"offset":12,"meaning":"zero in promoted row"},
        {"offset":16,"meaning":"zero in promoted row"}]},
      "samplers":sj,"constants":cj,"requiredRendererRows":required_rows,
      "summary":{
        "samplerSourceRowCount":sj["sourceRowCount"],"samplerUniqueExactRowCount":sj["uniqueExactRowCount"],
        "samplerAbsentRowCount":sj["absentRowCount"],"samplerAmbiguousRowCount":sj["ambiguousRowCount"],
        "constantSourceRowCount":cj["sourceRowCount"],"constantUniqueExactRowCount":cj["uniqueExactRowCount"],
        "constantAbsentRowCount":cj["absentRowCount"],"constantAmbiguousRowCount":cj["ambiguousRowCount"],
        "requiredRendererRowCount":len(required_rows),
      },
      "proofBoundary":"Exact current-client static representation only. Rows are promoted only from exact accessor C-string bytes, exact pointer identity, exact pinned enum value, and exact 20-byte [ptr,enum,0,0,0] bytes. Source-order similarity is diagnostic only. No runtime code-value provider, resource upload mechanism, sampler-state behavior, or historical-retail equivalence is inferred."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()

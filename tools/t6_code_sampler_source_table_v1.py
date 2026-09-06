#!/usr/bin/env python3
"""Parse the pinned OpenAssetTools T6 code-sampler source table exactly.

Authoritative upstream inputs are the same pinned OAT T6 headers used by the
code-constant parser. This joins `commonCodeSamplerSources[]` accessors to the
`MaterialTextureSource` enum without hand-maintaining a second table.

It proves compiler/dumper sampler identity metadata only. Runtime resource
selection/content and D3D11 sampler behavior remain separate proofs.
"""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from typing import Any
import t6_code_constant_source_table_v1 as base

FORMAT='t6-code-sampler-source-table-v1'
class T6CodeSamplerTableError(RuntimeError):pass

def _enum(assets_text:str)->dict:
 try:body=base._balanced_body(base._strip_comments(assets_text),r'\benum\s+MaterialTextureSource(?:\s*:\s*[^\{]+)?\s*\{','MaterialTextureSource enum')
 except Exception as e:raise T6CodeSamplerTableError(str(e)) from e
 values={};rows=[];current=-1
 for raw in body.split(','):
  entry=raw.strip()
  if not entry:continue
  m=re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*)(?:\s*=\s*(.+))?',entry,flags=re.S)
  if not m:raise T6CodeSamplerTableError(f'unsupported MaterialTextureSource entry {entry!r}')
  name,expr=m.groups()
  try:value=current+1 if expr is None else base._eval_expr(expr.strip(),values)
  except Exception as e:raise T6CodeSamplerTableError(str(e)) from e
  values[name]=value;current=value;rows.append({'symbol':name,'value':value,'valueHex':f'0x{value:x}','explicitExpression':None if expr is None else expr.strip()})
 aliases={}
 for row in rows:aliases.setdefault(int(row['value']),[]).append(str(row['symbol']))
 if not rows:raise T6CodeSamplerTableError('MaterialTextureSource enum parsed zero rows')
 return {'rows':rows,'bySymbol':values,'aliasesByValue':{str(k):v for k,v in sorted(aliases.items())}}

def _rows(constants_text:str,enum_doc:dict)->list[dict]:
 try:body=base._balanced_body(base._strip_comments(constants_text),r'\bcommonCodeSamplerSources\s*\[\s*\]\s*\{','commonCodeSamplerSources')
 except Exception as e:raise T6CodeSamplerTableError(str(e)) from e
 by=enum_doc['bySymbol'];aliases=enum_doc['aliasesByValue'];out=[];seen_accessor=set();seen_symbol=set()
 for record in base._top_level_records(body):
  symbol=base._field(record,'value');araw=base._field(record,'accessor');fraw=base._field(record,'updateFrequency')
  if None in (symbol,araw,fraw):raise T6CodeSamplerTableError(f'incomplete commonCodeSamplerSources row: {record[:160]!r}')
  if symbol not in by:raise T6CodeSamplerTableError(f'code sampler row uses unknown enum symbol {symbol!r}')
  m=re.fullmatch(r'"([^"\\]*(?:\\.[^"\\]*)*)"',araw)
  if not m:raise T6CodeSamplerTableError(f'unsupported sampler accessor literal {araw!r}')
  accessor=bytes(m.group(1),'utf-8').decode('unicode_escape')
  fm=re.fullmatch(r'techset::CommonCodeSourceUpdateFrequency::([A-Z_]+)',fraw)
  if not fm:raise T6CodeSamplerTableError(f'unsupported updateFrequency {fraw!r}')
  if accessor in seen_accessor:raise T6CodeSamplerTableError(f'duplicate code-sampler accessor {accessor!r}')
  if symbol in seen_symbol:raise T6CodeSamplerTableError(f'duplicate code-sampler enum symbol row {symbol!r}')
  seen_accessor.add(accessor);seen_symbol.add(symbol);value=int(by[symbol])
  out.append({'accessor':accessor,'enumSymbol':symbol,'enumValue':value,'enumValueHex':f'0x{value:x}','enumAliases':list(aliases.get(str(value),[])),'updateFrequency':fm.group(1),'techFlags':base._field(record,'techFlags'),'customSamplerIndex':base._field(record,'customSamplerIndex')})
 if not out:raise T6CodeSamplerTableError('commonCodeSamplerSources parsed zero rows')
 return out

def build_from_text(constants_text:str,assets_text:str,*,verify_pinned_blobs:bool=False)->dict:
 cb=constants_text.encode('utf-8');ab=assets_text.encode('utf-8');cs=base.git_blob_sha(cb);ass=base.git_blob_sha(ab)
 if verify_pinned_blobs:
  if cs!=base.CONSTANTS_BLOB:raise T6CodeSamplerTableError(f'TechsetConstantsT6.h Git blob {cs} != pinned {base.CONSTANTS_BLOB}')
  if ass!=base.ASSETS_BLOB:raise T6CodeSamplerTableError(f'T6_Assets.h Git blob {ass} != pinned {base.ASSETS_BLOB}')
 enum_doc=_enum(assets_text);rows=_rows(constants_text,enum_doc)
 freqs={f:sum(1 for r in rows if r['updateFrequency']==f) for f in sorted({r['updateFrequency'] for r in rows})}
 return {'format':FORMAT,'source':{'openAssetToolsCommit':base.PINNED_OAT_COMMIT,'techsetConstants':{'path':str(base.CONSTANTS_REL),'gitBlobSha1':cs,'pinnedGitBlobSha1':base.CONSTANTS_BLOB,'bytes':len(cb)},'t6Assets':{'path':str(base.ASSETS_REL),'gitBlobSha1':ass,'pinnedGitBlobSha1':base.ASSETS_BLOB,'bytes':len(ab)},'pinnedBlobVerificationRequired':bool(verify_pinned_blobs)},'rows':rows,'summary':{'codeSamplerSourceCount':len(rows),'customSamplerSourceCount':sum(1 for r in rows if r['customSamplerIndex'] is not None),'techFlaggedSourceCount':sum(1 for r in rows if r['techFlags'] is not None),'updateFrequencyCounts':freqs,'materialTextureSourceEnumEntryCount':len(enum_doc['rows']),'uniqueAccessorCount':len({r['accessor'] for r in rows}),'rowsSha256':base._jhash(rows)},'enumAliasesByValue':enum_doc['aliasesByValue'],'proofBoundary':'Exact parser join of pinned OAT T6 commonCodeSamplerSources accessor metadata to the pinned MaterialTextureSource enum. This proves code-sampler identity/index/update-frequency/custom-sampler/tech-flag metadata only; runtime resource choice/content and D3D11 sampler behavior remain separate.'}

def build_from_root(oat_source_root:Path,*,verify_pinned_blobs:bool=True)->dict:
 root=Path(oat_source_root);cp=root/base.CONSTANTS_REL;ap=root/base.ASSETS_REL
 if not cp.is_file() or not ap.is_file():raise T6CodeSamplerTableError(f'OAT source root lacks pinned T6 headers: {cp}, {ap}')
 try:ct=cp.read_bytes().decode('utf-8');at=ap.read_bytes().decode('utf-8')
 except UnicodeDecodeError as e:raise T6CodeSamplerTableError('pinned OAT T6 headers are not UTF-8') from e
 return build_from_text(ct,at,verify_pinned_blobs=verify_pinned_blobs)

def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--oat-source-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--allow-unpinned-source',action='store_true');a=p.parse_args();d=build_from_root(a.oat_source_root,verify_pinned_blobs=not a.allow_unpinned_source);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())

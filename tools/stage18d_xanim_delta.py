#!/usr/bin/env python3
"""Stage 18D raw T6 XAnim delta-track parser.

Authority: expanded retail T6 common_mp XFile bytes.
No OpenAssetTools executable or exported animation file is consumed.

The external T6 struct/zone-code descriptions are layout corroboration only.
All serialized-size rules below are validated against raw byte boundaries.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,struct
from pathlib import Path
from typing import Any

FOLLOW=0xffffffff
INSERT=0xfffffffe
XANIM=104
NOTIFY=8


def sha(data:bytes,a:int,b:int)->str:
    return hashlib.sha256(memoryview(data)[a:b]).hexdigest()

def cstr_end(data:bytes,pos:int)->int:
    e=data.find(b'\0',pos,pos+512)
    if e<0: raise ValueError('unterminated inline name')
    return e+1

def seg(data:bytes,name:str,a:int,b:int,**extra):
    d={'name':name,'raw_offset':a,'raw_end_offset':b,'bytes':b-a,'sha256':sha(data,a,b)}
    d.update(extra);return d

def parse_fixed(data:bytes,st:int)->dict[str,Any]:
    cs=struct.unpack_from('<6H',data,st+4)
    rds,idx=struct.unpack_from('<II',data,st+40)
    ptr=struct.unpack_from('<10I',data,st+64)
    return {
      'name_ptr':struct.unpack_from('<I',data,st)[0],
      'dataByteCount':cs[0],'dataShortCount':cs[1],'dataIntCount':cs[2],
      'randomDataByteCount':cs[3],'randomDataIntCount':cs[4],'numframes':cs[5],
      'boneCount':list(data[st+24:st+34]),'notifyCount':data[st+34],
      'randomDataShortCount':rds,'indexCount':idx,
      'ptrs':dict(zip(['names','dataByte','dataShort','dataInt','randomDataShort','randomDataByte','randomDataInt','indices','notify','deltaPart'],ptr))
    }

def indices(data:bytes,pos:int,count:int,unit:int):
    if unit==1: return list(data[pos:pos+count])
    return list(struct.unpack_from(f'<{count}H',data,pos)) if count else []

def parse_trans(data:bytes,pos:int,numframes:int)->tuple[dict[str,Any],int]:
    start=pos; size=struct.unpack_from('<H',data,pos)[0]; small=data[pos+2]
    if small not in (0,1): raise ValueError(f'bad smallTrans {small}')
    out={'kind':'trans','raw_offset':start,'size':size,'smallTrans':small,'segments':[]}
    if size==0:
        end=pos+16
        frame0=list(struct.unpack_from('<3f',data,pos+4))
        out.update({'mode':'constant','frame0':frame0,'serialized_fixed_bytes':16})
        out['segments'].append(seg(data,'trans_constant',pos,end))
        return out,end
    count=size+1; unit=1 if numframes<256 else 2
    mins=list(struct.unpack_from('<3f',data,pos+4)); scale=list(struct.unpack_from('<3f',data,pos+16))
    frames_ptr=struct.unpack_from('<I',data,pos+28)[0]
    idx_a=pos+32; idx_b=idx_a+count*unit
    idx=indices(data,idx_a,count,unit)
    out.update({'mode':'keyed','mins':mins,'size_vec':scale,'frames_ptr_raw':f'0x{frames_ptr:08X}',
                'index_element_bytes':unit,'frame_indices':idx,'serialized_header_and_indices_bytes':idx_b-pos})
    out['segments'].append(seg(data,'trans_header_and_indices',pos,idx_b,index_count=count,index_element_bytes=unit))
    pos=idx_b
    if frames_ptr==FOLLOW:
        elem=3 if small else 6; fb=count*elem; end=pos+fb
        raw=[]
        if small:
            for i in range(count): raw.append(list(data[pos+i*3:pos+(i+1)*3]))
        else:
            for i in range(count): raw.append(list(struct.unpack_from('<3H',data,pos+i*6)))
        out['quantized_frames']=raw
        out['frame_component_storage_bits']=8 if small else 16
        out['segments'].append(seg(data,'trans_frames',pos,end,frame_count=count,element_bytes=elem))
        pos=end
    elif frames_ptr not in (0,INSERT):
        out['frames_external_or_packed']=True
    out['raw_end_offset']=pos
    return out,pos

def parse_quat2(data:bytes,pos:int,numframes:int)->tuple[dict[str,Any],int]:
    start=pos; size=struct.unpack_from('<H',data,pos)[0]
    out={'kind':'quat2','raw_offset':start,'size':size,'segments':[]}
    if size==0:
        end=pos+8; q=list(struct.unpack_from('<2h',data,pos+4))
        out.update({'mode':'constant','frame0_raw_int16':q,'serialized_fixed_bytes':8})
        out['segments'].append(seg(data,'quat2_constant',pos,end)); return out,end
    count=size+1; unit=1 if numframes<256 else 2
    frames_ptr=struct.unpack_from('<I',data,pos+4)[0]; idx_a=pos+8; idx_b=idx_a+count*unit
    idx=indices(data,idx_a,count,unit)
    out.update({'mode':'keyed','frames_ptr_raw':f'0x{frames_ptr:08X}','index_element_bytes':unit,
                'frame_indices':idx,'serialized_header_and_indices_bytes':idx_b-pos})
    out['segments'].append(seg(data,'quat2_header_and_indices',pos,idx_b,index_count=count,index_element_bytes=unit))
    pos=idx_b
    if frames_ptr==FOLLOW:
        fb=count*4; end=pos+fb
        out['quantized_frames_int16']=[list(struct.unpack_from('<2h',data,pos+i*4)) for i in range(count)]
        out['segments'].append(seg(data,'quat2_frames',pos,end,frame_count=count,element_bytes=4)); pos=end
    elif frames_ptr not in (0,INSERT): out['frames_external_or_packed']=True
    out['raw_end_offset']=pos; return out,pos

def parse_quat(data:bytes,pos:int,numframes:int)->tuple[dict[str,Any],int]:
    start=pos; size=struct.unpack_from('<H',data,pos)[0]
    out={'kind':'quat','raw_offset':start,'size':size,'segments':[]}
    if size==0:
        end=pos+12; q=list(struct.unpack_from('<4h',data,pos+4))
        out.update({'mode':'constant','frame0_raw_int16':q,'serialized_fixed_bytes':12})
        out['segments'].append(seg(data,'quat_constant',pos,end)); return out,end
    count=size+1; unit=1 if numframes<256 else 2
    frames_ptr=struct.unpack_from('<I',data,pos+4)[0]; idx_a=pos+8; idx_b=idx_a+count*unit
    idx=indices(data,idx_a,count,unit)
    out.update({'mode':'keyed','frames_ptr_raw':f'0x{frames_ptr:08X}','index_element_bytes':unit,
                'frame_indices':idx,'serialized_header_and_indices_bytes':idx_b-pos})
    out['segments'].append(seg(data,'quat_header_and_indices',pos,idx_b,index_count=count,index_element_bytes=unit))
    pos=idx_b
    if frames_ptr==FOLLOW:
        fb=count*8; end=pos+fb
        out['quantized_frames_int16']=[list(struct.unpack_from('<4h',data,pos+i*8)) for i in range(count)]
        out['segments'].append(seg(data,'quat_frames',pos,end,frame_count=count,element_bytes=8)); pos=end
    elif frames_ptr not in (0,INSERT): out['frames_external_or_packed']=True
    out['raw_end_offset']=pos; return out,pos

def parse_one(data:bytes,row:dict[str,str],next_inline:int|None)->dict[str,Any]:
    st=int(row['raw_struct_offset']); f=parse_fixed(data,st); pos=st+XANIM
    if f['name_ptr']==FOLLOW: pos=cstr_end(data,pos)
    if f['ptrs']['names']==FOLLOW: pos += f['boneCount'][9]*2
    if f['ptrs']['notify']==FOLLOW: pos += f['notifyCount']*NOTIFY
    delta_start=pos
    if f['ptrs']['deltaPart']!=FOLLOW: raise ValueError('target is not inline deltaPart')
    tr,q2,q=struct.unpack_from('<3I',data,pos); pos+=12
    out={'name':row['name'],'raw_struct_offset':st,'numframes':f['numframes'],'delta_fixed_raw_offset':delta_start,
         'delta_child_pointers':{'trans':f'0x{tr:08X}','quat2':f'0x{q2:08X}','quat':f'0x{q:08X}'},
         'segments':[seg(data,'deltaPart_fixed',delta_start,delta_start+12)],'tracks':{}}
    for key,p,fn in [('trans',tr,parse_trans),('quat2',q2,parse_quat2),('quat',q,parse_quat)]:
        if p==FOLLOW:
            track,pos=fn(data,pos,f['numframes']); out['tracks'][key]=track; out['segments']+=track['segments']
        elif p==0: out['tracks'][key]={'kind':key,'mode':'null'}
        else: out['tracks'][key]={'kind':key,'mode':'packed_or_insert','pointer_raw':f'0x{p:08X}'}
    arrays=[('dataByte',f['dataByteCount'],1,f['ptrs']['dataByte']),('dataShort',f['dataShortCount'],2,f['ptrs']['dataShort']),
            ('dataInt',f['dataIntCount'],4,f['ptrs']['dataInt']),('randomDataShort',f['randomDataShortCount'],2,f['ptrs']['randomDataShort']),
            ('randomDataByte',f['randomDataByteCount'],1,f['ptrs']['randomDataByte']),('randomDataInt',f['randomDataIntCount'],4,f['ptrs']['randomDataInt']),
            ('indices',f['indexCount'],1 if f['numframes']<256 else 2,f['ptrs']['indices'])]
    for name,count,unit,p in arrays:
        if p==FOLLOW:
            end=pos+count*unit; out['segments'].append(seg(data,name,pos,end,count=count,element_bytes=unit)); pos=end
    out['exact_walk_end_raw_offset']=pos; out['exact_serialized_sha256']=sha(data,st,pos)
    out['next_inline_xanim_raw_offset']=next_inline
    out['gap_to_next_inline_xanim']=None if next_inline is None else next_inline-pos
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--stream',type=Path,required=True); ap.add_argument('--inline-csv',type=Path,required=True); ap.add_argument('--outdir',type=Path,required=True)
    a=ap.parse_args(); a.outdir.mkdir(parents=True,exist_ok=True); data=a.stream.read_bytes(); rows=list(csv.DictReader(a.inline_csv.open()))
    targets=[r for r in rows if r['walk_status']=='complex_delta_deferred']; offsets=[int(r['raw_struct_offset']) for r in rows]
    byoff={int(r['raw_struct_offset']):i for i,r in enumerate(rows)}
    details=[]; failures=[]
    for r in targets:
        i=byoff[int(r['raw_struct_offset'])]; nxt=offsets[i+1] if i+1<len(offsets) else None
        try: details.append(parse_one(data,r,nxt))
        except Exception as e: failures.append({'name':r['name'],'raw_struct_offset':int(r['raw_struct_offset']),'error':repr(e)})
    gaps=[x['gap_to_next_inline_xanim'] for x in details if x['gap_to_next_inline_xanim'] is not None]
    exact=sum(g==0 for g in gaps); overlap=sum(g<0 for g in gaps); positive=sum(g>0 for g in gaps)
    track_counts={k:sum(x['tracks'][k]['mode'] not in ('null','packed_or_insert') for x in details) for k in ('trans','quat2','quat')}
    keyed={k:sum(x['tracks'][k].get('mode')=='keyed' for x in details) for k in ('trans','quat2','quat')}
    constant={k:sum(x['tracks'][k].get('mode')=='constant' for x in details) for k in ('trans','quat2','quat')}
    manifest={'stage':'18D raw XAnim delta proof','authority':'expanded retail common_mp XFile bytes','expanded_stream_sha256':hashlib.sha256(data).hexdigest(),
              'input_complex_delta_records':len(targets),'successfully_delta_walked':len(details),'failures':failures,
              'track_present_inline_counts':track_counts,'keyed_track_counts':keyed,'constant_track_counts':constant,
              'exact_end_equals_next_inline_start':exact,'positive_gap_to_next_inline':positive,'overlaps_next_inline':overlap,
              'serialized_rules_raw_validated':{
                 'XAnimDeltaPart_fixed_bytes':12,
                 'XAnimPartTrans_constant_bytes':16,
                 'XAnimPartTrans_keyed':'32 + (size+1)*indexWidth, then (size+1)*(3 or 6) frame bytes when frames pointer is FOLLOWING',
                 'XAnimDeltaPartQuat2_constant_bytes':8,
                 'XAnimDeltaPartQuat2_keyed':'8 + (size+1)*indexWidth, then (size+1)*4 frame bytes when frames pointer is FOLLOWING',
                 'XAnimDeltaPartQuat_constant_bytes':12,
                 'XAnimDeltaPartQuat_keyed':'8 + (size+1)*indexWidth, then (size+1)*8 frame bytes when frames pointer is FOLLOWING',
                 'indexWidth':'1 byte when numframes < 256, else 2 bytes'},
              'proof_boundary':{'proven':'raw frame indices and quantized translation/quat components plus exact serialized ranges/hashes',
                                'not_yet_claimed':'float-space dequantization formula or quaternion reconstruction until independently validated'}}
    (a.outdir/'xanim_delta_proof.json').write_text(json.dumps(manifest,indent=2)); (a.outdir/'xanim_delta_records.json').write_text(json.dumps(details,indent=2))
    with (a.outdir/'xanim_delta_summary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['name','raw_struct_offset','numframes','trans_mode','trans_size','quat2_mode','quat2_size','quat_mode','quat_size','exact_walk_end_raw_offset','gap_to_next_inline_xanim']);w.writeheader()
        for x in details:
            w.writerow({'name':x['name'],'raw_struct_offset':x['raw_struct_offset'],'numframes':x['numframes'],
                'trans_mode':x['tracks']['trans'].get('mode'),'trans_size':x['tracks']['trans'].get('size'),
                'quat2_mode':x['tracks']['quat2'].get('mode'),'quat2_size':x['tracks']['quat2'].get('size'),
                'quat_mode':x['tracks']['quat'].get('mode'),'quat_size':x['tracks']['quat'].get('size'),
                'exact_walk_end_raw_offset':x['exact_walk_end_raw_offset'],'gap_to_next_inline_xanim':x['gap_to_next_inline_xanim']})
    print(json.dumps(manifest,indent=2))
if __name__=='__main__': main()

#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import struct
from pathlib import Path

import numpy as np
from PIL import Image

HERE=Path(__file__).resolve().parent
BASE_PATH=HERE/'t6_nuketown_ipak_partial_texture_export_v2.py'
spec=importlib.util.spec_from_file_location('t6_texture_base_for_iwi27',BASE_PATH)
base=importlib.util.module_from_spec(spec); spec.loader.exec_module(base)

IWI_DXT1=0x0B
IWI_DXT3=0x0C
IWI_DXT5=0x0D
IWI_DXN=0x0E
DXGI_BY_IWI={IWI_DXT1:71,IWI_DXT3:74,IWI_DXT5:77,IWI_DXN:83}


def iwi_top_png(blob:bytes,normal_semantic:bool=False):
    fmt,flags,w,h,d,gamma,sizes=base.parse_iwi27(blob)
    dxgi=DXGI_BY_IWI.get(fmt)
    if dxgi is None:
        raise NotImplementedError(f'IWI format {fmt}')
    block_bytes=8 if fmt==IWI_DXT1 else 16
    top_bytes=((w+3)//4)*((h+3)//4)*block_bytes
    end=int(sizes[0]); start=end-top_bytes
    if start<64 or end>len(blob) or start>=end:
        raise ValueError(f'BCn top mip bounds {start}:{end}/{len(blob)}')
    comp=blob[start:end]

    hdr=bytearray(b'DDS ')
    hdr+=struct.pack('<I',124)
    hdr+=struct.pack('<I',0x00081007)
    hdr+=struct.pack('<IIIII',h,w,top_bytes,0,1)
    hdr+=b'\0'*(11*4)
    hdr+=struct.pack('<II4sIIIII',32,4,b'DX10',0,0,0,0,0)
    hdr+=struct.pack('<IIIII',0x1000,0,0,0,0)
    hdr+=struct.pack('<IIIII',dxgi,3,0,1,0)

    im=Image.open(io.BytesIO(bytes(hdr)+comp)); im.load()
    if fmt==IWI_DXN and normal_semantic:
        arr=np.asarray(im.convert('RGB'),dtype=np.uint8)
        x=arr[...,0].astype(np.float32)/127.5-1.0
        y=arr[...,1].astype(np.float32)/127.5-1.0
        z=np.sqrt(np.maximum(0.0,1.0-x*x-y*y))
        zz=np.clip(np.rint((z*0.5+0.5)*255.0),0,255).astype(np.uint8)
        a=np.full_like(zz,255,dtype=np.uint8)
        rgba=np.dstack((arr[...,0],arr[...,1],zz,a))
        im=Image.fromarray(rgba,'RGBA')
    else:
        im=im.convert('RGBA')
    out=io.BytesIO(); im.save(out,format='PNG',compress_level=1,optimize=False)
    return out.getvalue(),{
        'format':fmt,'flags':flags,'width':w,'height':h,'depth':d,'gamma':gamma,
        'iwiBytes':len(blob),'topMipOffset':start,'topMipBytes':top_bytes,
        'decoder':'Pillow-DDS-DX10-native','dxgiFormat':dxgi,
        'normalZReconstructed':bool(fmt==IWI_DXN and normal_semantic),
    }

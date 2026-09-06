#!/usr/bin/env python3
from __future__ import annotations

import json
import struct

import t6_xmodel_blender_static_bindpose_export_v2 as v2


def make_glb() -> bytes:
    doc={
      'asset':{'version':'2.0','generator':'test'},
      'scene':0,'scenes':[{'nodes':[0]}],
      'nodes':[{'mesh':0}],
      'meshes':[{'primitives':[{'attributes':{'POSITION':0,'COLOR_0':1},'indices':2,'mode':4}]}],
      'buffers':[{'byteLength':0}],
      'bufferViews':[],
      'accessors':[]
    }
    jb=json.dumps(doc,separators=(',',':')).encode();jb+=b' '*((-len(jb))%4)
    bb=b''
    total=12+8+len(jb)+8+len(bb)
    return struct.pack('<4sII',b'glTF',2,total)+struct.pack('<II',len(jb),0x4E4F534A)+jb+struct.pack('<II',len(bb),0x004E4942)+bb


def main() -> int:
    out=v2.demote_color0(make_glb())
    doc,_=v2._read_glb(out)
    attrs=doc['meshes'][0]['primitives'][0]['attributes']
    assert 'COLOR_0' not in attrs
    assert attrs['_T6_COLOR_RGBA']==1
    assert doc['nodes'][0]['extras']['t6VertexColorTransport'].startswith('_T6_COLOR_RGBA')
    print('PASS')
    return 0


if __name__=='__main__':
    raise SystemExit(main())

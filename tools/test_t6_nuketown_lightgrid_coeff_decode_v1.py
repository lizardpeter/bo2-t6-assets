#!/usr/bin/env python3
"""Deterministic math regression for t6_nuketown_lightgrid_coeff_decode_v1."""
import argparse, hashlib, importlib.util, struct
from pathlib import Path


def load(path):
    s=importlib.util.spec_from_file_location('coeffdecode',path)
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--tool',type=Path,default=Path(__file__).with_name('t6_nuketown_lightgrid_coeff_decode_v1.py')); a=ap.parse_args()
    m=load(a.tool)
    cases={0:'0xc1800000',32768:'0x39800000',65535:'0x41800000'}
    for rawv,bits in cases.items():
        c=m.decode_coeff_record(struct.pack('<27H',*([rawv]*27)))
        assert c.shape==(9,3)
        assert all(m.float_bits(x)==bits for x in c.reshape(-1)), (rawv,m.float_bits(c[0,0]))
    dirs=m.generate_grid_basis_dirs()
    assert dirs.shape==(56,3)
    assert hashlib.sha256(dirs.astype('<f4').tobytes()).hexdigest()=='9dd96f562853c9286e37d31cd4c328a9bb955159d9e704e640a8164463f23d32'
    assert m.vector_bits(dirs[0])==['0xbf13cd3a','0xbf13cd3a','0xbf13cd3a']
    assert m.vector_bits(dirs[-1])==['0x3f13cd3a','0x3f13cd3a','0x3f13cd3a']
    vals=[(i*2341+1234)%65536 for i in range(27)]
    coeff=m.decode_coeff_record(struct.pack('<27H',*vals))
    sh=m.pack_gfx_lighting_sh(coeff)
    assert m.vector_bits(sh)==['0x3f8a43f9','0x3f80003b','0x3f6b78f9','0x41ea026a','0xc12d33ad','0xc0ecaaec','0xc07ddcfd','0xc1c0098c','0xbf09908c','0x403914b8','0x40ca46cb','0x4152dfd2']
    rgb=m.eval_directional_color(coeff,dirs[0])
    assert m.vector_bits(rgb)==['0x3f92145c','0x3fb948cd','0x3fe07d41']
    assert all(float(x)>=0 for x in rgb)
    print('PASS: T6 light-grid coefficient decode/basis/SH-pack regression')

if __name__=='__main__': main()

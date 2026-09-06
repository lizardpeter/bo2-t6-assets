#!/usr/bin/env python3
from __future__ import annotations

import struct

import t6_dxbc_signature_v1 as sig


def signature_payload(rows):
    count = len(rows)
    table_end = 8 + 24 * count
    names = bytearray()
    entries = bytearray()
    offsets = {}
    for name, semantic_index, system_value, component_type, register, mask, rw in rows:
        if name not in offsets:
            offsets[name] = table_end + len(names)
            names.extend(name.encode('utf-8') + b'\0')
        entries.extend(struct.pack(
            '<6I', offsets[name], semantic_index, system_value,
            component_type, register, (rw << 8) | mask,
        ))
    return struct.pack('<II', count, 0) + bytes(entries) + bytes(names)


def dxbc(chunks):
    count = len(chunks)
    header_size = 32 + 4 * count
    offsets = []
    body = bytearray()
    for tag, payload in chunks:
        offsets.append(header_size + len(body))
        body.extend(tag + struct.pack('<I', len(payload)) + payload)
    total = header_size + len(body)
    return (
        b'DXBC' + b'\0' * 16 + struct.pack('<III', 1, total, count)
        + struct.pack('<' + 'I' * count, *offsets) + bytes(body)
    )


def expect_fail(blob, tag, phrase):
    try:
        sig.parse_signature(blob, tag)
    except sig.DxbcSignatureError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError(f'expected failure containing {phrase!r}')


def main():
    isgn = signature_payload([
        ('TEXCOORD', 1, 0, 3, 2, 0x7, 0x7),
        ('TEXCOORD', 3, 0, 3, 4, 0x7, 0x7),
        ('COLOR', 0, 0, 3, 6, 0xf, 0xf),
    ])
    osgn = signature_payload([
        ('SV_Target', 0, 0, 3, 0, 0xf, 0xf),
    ])
    blob = dxbc([(b'ISGN', isgn), (b'OSGN', osgn)])
    io = sig.parse_io_signatures(blob)
    assert io['format'] == 't6-dxbc-io-signatures-v1'
    assert io['input']['format'] == sig.FORMAT
    assert io['input']['entryCount'] == 3
    assert io['input']['registerMap'] == {'2': 'TEXCOORD1', '4': 'TEXCOORD3', '6': 'COLOR0'}
    assert io['output']['registerMap'] == {'0': 'SV_Target0'}
    first = io['input']['entries'][0]
    assert first['register'] == 2 and first['semanticName'] == 'TEXCOORD' and first['semanticIndex'] == 1
    assert first['mask'] == 7 and first['readWriteMask'] == 7

    duplicate = signature_payload([
        ('TEXCOORD', 1, 0, 3, 2, 7, 7),
        ('TEXCOORD', 2, 0, 3, 2, 7, 7),
    ])
    expect_fail(dxbc([(b'ISGN', duplicate), (b'OSGN', osgn)]), 'ISGN', 'multiple signature rows claim register 2')

    missing = dxbc([(b'OSGN', osgn)])
    expect_fail(missing, 'ISGN', 'expected exactly one chunk, found 0')

    doubled = dxbc([(b'ISGN', isgn), (b'ISGN', isgn), (b'OSGN', osgn)])
    expect_fail(doubled, 'ISGN', 'expected exactly one chunk, found 2')

    bad = bytearray(isgn)
    struct.pack_into('<I', bad, 8, 4)  # name offset inside entry table
    expect_fail(dxbc([(b'ISGN', bytes(bad)), (b'OSGN', osgn)]), 'ISGN', 'outside string region')

    malformed = bytearray(blob)
    struct.pack_into('<I', malformed, 24, len(blob) + 1)
    expect_fail(bytes(malformed), 'ISGN', 'DXBC size mismatch')

    try:
        sig.parse_signature(blob, 'PCSG')
    except sig.DxbcSignatureError as exc:
        assert 'unsupported SM4 signature tag' in str(exc)
    else:
        raise AssertionError('unsupported signature tag accepted')

    print('PASS: strict reusable DXBC ISGN/OSGN signature parser')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Prove T6 D3D11 rasterizer/depth-stencil state semantics from retail t6mp.exe.

This verifier is intentionally pinned to one exact retail PC executable. It
checks the SHA-256 and exact instruction bytes before promoting any renderer
semantics. The proof closes:

- T6 polygonOffset enum 0/1/2/shadowmap -> D3D11 DepthBias and
  SlopeScaledDepthBias behavior;
- exact retail registration defaults/ranges for sm_polygonOffsetBias and
  sm_polygonOffsetScale;
- D3D11 CreateRasterizerState / CreateDepthStencilState builder identities;
- ordinary material stencil read/write masks.

Shadowmap bias/scale are runtime DVARs. Their registration defaults are exact;
the current runtime values may be changed by the user/game and should remain
configurable in a faithful renderer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

EXPECTED_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
IMAGE_BASE = 0x400000


class ProofError(RuntimeError):
    pass


class PE:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        if self.data[:2] != b"MZ":
            raise ProofError("not MZ")
        pe = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[pe : pe + 4] != b"PE\0\0":
            raise ProofError("not PE")
        coff = pe + 4
        machine, nsects, _, _, _, opt_size, _ = struct.unpack_from(
            "<HHIIIHH", self.data, coff
        )
        if machine != 0x14C:
            raise ProofError(f"not i386: 0x{machine:x}")
        opt = coff + 20
        magic = struct.unpack_from("<H", self.data, opt)[0]
        if magic != 0x10B:
            raise ProofError(f"not PE32: 0x{magic:x}")
        image_base = struct.unpack_from("<I", self.data, opt + 28)[0]
        if image_base != IMAGE_BASE:
            raise ProofError(f"image base 0x{image_base:x}")
        sec = opt + opt_size
        self.sections = []
        for i in range(nsects):
            off = sec + i * 40
            name = self.data[off : off + 8].split(b"\0", 1)[0].decode(
                "ascii", "replace"
            )
            vsize, vaddr, raw_size, raw_off = struct.unpack_from(
                "<IIII", self.data, off + 8
            )
            self.sections.append(
                (name, IMAGE_BASE + vaddr, max(vsize, raw_size), raw_off, raw_size)
            )

    def off(self, va: int) -> int:
        for _, start, size, raw, raw_size in self.sections:
            if start <= va < start + size:
                delta = va - start
                if delta >= raw_size:
                    raise ProofError(f"VA 0x{va:x} is not file-backed")
                return raw + delta
        raise ProofError(f"unmapped VA 0x{va:x}")

    def bytes(self, va: int, n: int) -> bytes:
        return self.data[self.off(va) : self.off(va) + n]

    def u32(self, va: int) -> int:
        return struct.unpack("<I", self.bytes(va, 4))[0]

    def f32(self, va: int) -> float:
        return struct.unpack("<f", self.bytes(va, 4))[0]

    def cstr(self, va: int, maxn: int = 256) -> str:
        off = self.off(va)
        end = self.data.find(b"\0", off, off + maxn)
        if end < 0:
            raise ProofError(f"unterminated string at 0x{va:x}")
        return self.data[off:end].decode("ascii")


def _expect(pe: PE, va: int, expected: bytes, label: str) -> None:
    actual = pe.bytes(va, len(expected))
    if actual != expected:
        raise ProofError(
            f"{label} bytes differ at 0x{va:x}: {actual.hex()} != {expected.hex()}"
        )


def _rel32_target(pe: PE, call_va: int) -> int:
    if pe.bytes(call_va, 1) != b"\xE8":
        raise ProofError(f"not rel32 call at 0x{call_va:x}")
    rel = struct.unpack("<i", pe.bytes(call_va + 1, 4))[0]
    return call_va + 5 + rel


def prove(path: Path) -> dict:
    pe = PE(path)
    sha = hashlib.sha256(pe.data).hexdigest()
    if sha != EXPECTED_SHA256:
        raise ProofError(f"SHA mismatch {sha}")

    if pe.cstr(0xBD58F4) != "sm_polygonOffsetScale":
        raise ProofError("scale DVAR name mismatch")
    if pe.cstr(0xCEA500) != "sm_polygonOffsetBias":
        raise ProofError("bias DVAR name mismatch")

    # sm_polygonOffsetScale: Dvar_RegisterFloat(name, 2, 0, 8, ...)
    if pe.f32(0xBF607C) != 2.0 or pe.f32(0xBC7E78) != 8.0:
        raise ProofError("scale constants mismatch")
    _expect(pe, 0x520C22, b"\x0f\x57\xc0", "scale min=0")
    _expect(
        pe,
        0x520C2B,
        b"\xf3\x0f\x10\x05\x7c\x60\xbf\x00",
        "scale default load",
    )
    _expect(pe, 0x520C38, b"\x68\xf4\x58\xbd\x00", "scale name push")
    if _rel32_target(pe, 0x520C42) != 0x598590:
        raise ProofError("scale registration target mismatch")

    # sm_polygonOffsetBias: Dvar_RegisterInt(name, 8192, 0, 65536, ...)
    _expect(pe, 0x717B8A, b"\x68\xa0\x10\x00\x00", "bias flags push")
    _expect(pe, 0x717B8F, b"\x68\x00\x00\x01\x00", "bias max=65536")
    _expect(pe, 0x717B94, b"\x6a\x00", "bias min=0")
    _expect(pe, 0x717B96, b"\x68\x00\x20\x00\x00", "bias default=8192")
    _expect(pe, 0x717B9B, b"\x68\x00\xa5\xce\x00", "bias name push")
    if _rel32_target(pe, 0x717BA5) != 0x4771F0:
        raise ProofError("bias registration target mismatch")

    # Runtime DVAR getter forms.
    _expect(pe, 0x5AEB90, b"\x8b\x44\x24\x04\x85\xc0", "float getter prologue")
    _expect(pe, 0x5AEBA3, b"\xd9\x40\x18", "float getter current")
    _expect(pe, 0x6997D0, b"\x8b\x44\x24\x04\x85\xc0", "int getter prologue")
    _expect(pe, 0x69980D, b"\x8b\x40\x18\xc3", "int getter current value")

    # 0x770DA0 builds D3D11_RASTERIZER_DESC. polygonOffset is state-byte-1
    # bits 4-5 (mask 0x30). Mode 3 takes live DVARs.
    _expect(pe, 0x770DC7, b"\x83\xe1\x30", "polygon offset mask")
    _expect(pe, 0x770DF9, b"\x83\xf8\x30", "shadowmap mode compare")
    if _rel32_target(pe, 0x770E05) != 0x6997D0:
        raise ProofError("shadow bias getter target mismatch")
    if _rel32_target(pe, 0x770E13) != 0x5AEB90:
        raise ProofError("shadow scale getter target mismatch")
    _expect(pe, 0x770E1D, b"\xc1\xe8\x04", "fixed mode shift")
    _expect(pe, 0x770E24, b"\xc1\xe6\x08", "fixed depth-bias x256")
    if pe.f32(0xCE4D20) != -1.0:
        raise ProofError("fixed slope multiplier mismatch")
    if pe.u32(0xBD60B0) != 0x80000000:
        raise ProofError("sign mask mismatch")
    _expect(pe, 0x770E43, b"\xf7\xde", "final depth-bias sign negate")
    _expect(
        pe,
        0x770E4B,
        b"\x0f\x57\x05\xb0\x60\xbd\x00",
        "final slope sign toggle",
    )
    _expect(
        pe,
        0x770E52,
        b"\x89\x74\x24\x1c",
        "D3D11_RASTERIZER_DESC.DepthBias store",
    )
    _expect(
        pe,
        0x770E56,
        b"\xf3\x0f\x11\x44\x24\x24",
        "D3D11_RASTERIZER_DESC.SlopeScaledDepthBias store",
    )
    _expect(
        pe,
        0x770E72,
        b"\x8b\x41\x58",
        "ID3D11Device::CreateRasterizerState vtable slot",
    )

    # 0x770C50 builds the 52-byte D3D11_DEPTH_STENCIL_DESC.
    _expect(pe, 0x770C58, b"\x6a\x34", "depth-stencil desc memset size=52")
    _expect(pe, 0x770C9F, b"\xc6\x44\x24\x14\xff", "StencilReadMask=0xff")
    _expect(pe, 0x770C9B, b"\x8a\x54\x24\x40", "StencilWriteMask source argument")
    _expect(pe, 0x770CA4, b"\x88\x54\x24\x15", "StencilWriteMask store")
    _expect(
        pe,
        0x770D82,
        b"\x8b\x41\x54",
        "ID3D11Device::CreateDepthStencilState vtable slot",
    )
    _expect(pe, 0x731DC8, b"\x68\xff\x00\x00\x00", "ordinary material write mask=0xff")
    if _rel32_target(pe, 0x731DD1) != 0x770C50:
        raise ProofError("ordinary depth-stencil builder target mismatch")

    scale_default = pe.f32(0xBF607C)
    bias_default = 0x2000
    modes = []
    for enum, raw, name in (
        (0, 0x00, "offset0"),
        (1, 0x10, "offset1"),
        (2, 0x20, "offset2"),
        (3, 0x30, "offsetShadowmap"),
    ):
        if raw == 0x30:
            depth_bias = -bias_default
            slope = -scale_default
            dynamic = True
        else:
            n = raw >> 4
            depth_bias = n * 256
            slope = float(n)
            dynamic = False
        modes.append(
            {
                "enum": enum,
                "name": name,
                "stateBitsByte1MaskedHex": f"0x{raw:02x}",
                "depthBias": depth_bias,
                "slopeScaledDepthBias": slope,
                "depthBiasClamp": 0.0,
                "usesShadowmapDvars": dynamic,
            }
        )

    return {
        "format": "t6-retail-d3d11-state-proof-v1",
        "retailExecutable": {
            "file": path.name,
            "bytes": len(pe.data),
            "sha256": sha,
            "imageBaseHex": "0x00400000",
        },
        "rasterizerState": {
            "builderVaHex": "0x00770da0",
            "deviceVtableOffsetHex": "0x58",
            "api": "ID3D11Device::CreateRasterizerState",
            "polygonOffsetField": {
                "stateWord": "loadBits[1] / T6 state byte 1",
                "bitRange": "4-5",
                "maskHex": "0x30",
            },
            "shadowmapDvars": {
                "sm_polygonOffsetBias": {
                    "type": "int",
                    "default": bias_default,
                    "min": 0,
                    "max": 65536,
                    "runtimeUse": "DepthBias = -currentValue",
                },
                "sm_polygonOffsetScale": {
                    "type": "float",
                    "default": scale_default,
                    "min": 0.0,
                    "max": pe.f32(0xBC7E78),
                    "runtimeUse": "SlopeScaledDepthBias = -currentValue",
                },
            },
            "modes": modes,
        },
        "depthStencilState": {
            "builderVaHex": "0x00770c50",
            "descriptorBytes": 52,
            "deviceVtableOffsetHex": "0x54",
            "api": "ID3D11Device::CreateDepthStencilState",
            "stencilReadMask": 255,
            "stencilWriteMaskPolicy": (
                "builder second argument; ordinary material-state creation at 0x731dc8 passes 0xff"
            ),
            "ordinaryMaterialStencilWriteMask": 255,
            "dynamicPath": (
                "0x770ef0 can provide a runtime write mask and binds a separate stencil reference "
                "through OMSetDepthStencilState"
            ),
        },
        "validation": {
            "exactRetailSha256": True,
            "instructionBytesMatched": True,
            "dvarRegistrationMatched": True,
            "d3d11BuilderCallsMatched": True,
        },
        "proofBoundary": (
            "Direct static proof for the pinned retail PC executable. Shadowmap bias/scale remain "
            "runtime DVARs; the listed defaults are exact registration defaults, while current values "
            "can change during execution."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    doc = prove(args.exe)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

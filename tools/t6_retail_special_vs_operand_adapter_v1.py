#!/usr/bin/env python3
"""VS-only declaration adapter for the strict retained-special SM4 operand parser.

The established operand census intentionally knows the declaration signatures
observed in the retained pixel-shader population.  Vertex shaders introduce
additional declaration opcodes such as dcl_input.  The multiply-decal VS proof
does not need declaration operands to reconstruct executable dataflow: vertex
input/output identity is joined independently through DXBC ISGN/OSGN.

This adapter therefore treats dcl_* instructions as opaque declarations, but
only after validating their opcode identity, encoded DWORD length, program
bounds, and absence of an extended opcode token.  Every executable instruction
is still delegated unchanged to the existing fail-closed operand decoder.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_BASE_PATH = Path(__file__).with_name("t6_retail_special_shdr_operand_census_v1.py")
_spec = importlib.util.spec_from_file_location("t6_special_pixel_operand_base", _BASE_PATH)
_base = importlib.util.module_from_spec(_spec)
assert _spec.loader
_spec.loader.exec_module(_base)

OperandDecodeError = _base.OperandDecodeError


def parse_instruction(dw, i, opcodes):
    if i < 0 or i >= len(dw):
        raise OperandDecodeError(f"instruction DWORD {i} outside program")
    token = dw[i]
    opcode_id = token & 0x7FF
    if opcode_id >= len(opcodes):
        raise OperandDecodeError(f"unknown opcode id {opcode_id}")
    name = opcodes[opcode_id]

    if not name.startswith("dcl_"):
        return _base.parse_instruction(dw, i, opcodes)

    if token & 0x80000000:
        raise OperandDecodeError(
            f"extended opcode token unsupported for vertex declaration {name} at {i}"
        )
    length = (token >> 24) & 0x7F
    if length < 1:
        raise OperandDecodeError(f"zero-length vertex declaration {name} at {i}")
    if len(dw) < 2:
        raise OperandDecodeError("truncated SM4 program header")
    declared_length = int(dw[1])
    if declared_length > len(dw):
        raise OperandDecodeError(
            f"SM4 declared length {declared_length} exceeds payload DWORD count {len(dw)}"
        )
    if i + length > declared_length:
        raise OperandDecodeError(
            f"vertex declaration {name} at {i} overruns declared program length: {length} DWORDs"
        )

    return {
        "opcode": name,
        "lengthDwords": length,
        "operands": [],
        "extraDwords": [],
    }

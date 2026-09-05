#!/usr/bin/env python3
from __future__ import annotations

import math
import struct

import t6_retail_world_material_constants_v1 as constants


F = 0xFFFFFFFF


def _fixture() -> tuple[bytes, tuple[int, ...]]:
    # Minimal fully valid serialized T6 Material record for the established
    # state.material parser: 1 packed image pointer, 1 constant, 1 state.
    fixed = bytearray(104)
    struct.pack_into("<I", fixed, 4, 1)  # game flags-ish validated < 0x8000
    fixed[9] = 3
    fixed[40:76] = struct.pack("<36b", 0, *([-1] * 35))
    fixed[76] = 1  # textureCount
    fixed[77] = 1  # constantCount
    fixed[78] = 1  # stateCount
    fixed[81] = 0  # prepass/misc gate in existing parser
    # techniqueSet packed pointer; child tables follow inline as required.
    struct.pack_into("<IIIII", fixed, 84, 1, F, F, F, 0)

    name = b"*fixture\0"
    texture = bytearray(16)
    struct.pack_into("<I", texture, 12, 1)  # packed existing image, no inline child

    constant = bytearray(32)
    struct.pack_into("<I", constant, 0, 0x88BEFC31)
    constant[4:16] = b"alphaRevealP"
    struct.pack_into("<4f", constant, 16, 0.25, 2.0, 7.0, 9.0)

    state_bits = 1 << 14  # cullFace enum 1; all other decoded enums are valid zeroes
    gfx_state = struct.pack("<QIII", state_bits, 0, 0, 0)
    data = bytes(fixed) + name + bytes(texture) + bytes(constant) + gfx_state
    blocks = (4096,) * 8
    return data, blocks


def main() -> int:
    data, blocks = _fixture()
    rows = constants.parse_constants(data, 0, blocks)
    assert len(rows) == 1
    row = rows[0]
    assert row["fileOffset"] == 104 + len(b"*fixture\0") + 16
    assert row["nameHash"] == 0x88BEFC31
    assert row["nameHashHex"] == "0x88befc31"
    assert row["nameFragment"] == "alphaRevealP"
    assert row["nameFragmentHex"] == b"alphaRevealP".hex()
    assert row["literal"] == [0.25, 2.0, 7.0, 9.0]
    assert len(row["serializedSha256"]) == 64

    # The reader inherits whole-record validation: malformed/non-finite literals
    # are never archived as usable material constants.
    bad = bytearray(data)
    struct.pack_into("<f", bad, row["fileOffset"] + 16, math.nan)
    try:
        constants.parse_constants(bytes(bad), 0, blocks)
    except ValueError as exc:
        assert "constant value" in str(exc)
    else:
        raise AssertionError("non-finite serialized MaterialConstantDef was accepted")

    print("PASS: exact serialized T6 world Material constants v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

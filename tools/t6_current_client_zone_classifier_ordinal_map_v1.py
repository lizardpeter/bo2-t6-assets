#!/usr/bin/env python3
"""Evaluate the exact current-client zone-classifier ordinal function.

0x00493440 is independently byte-proven to receive classifiers after the
0x3fffffff mask and its return value controls 16-byte linked-record insertion
order. This tool evaluates the exact SHA-classified revision-5346 machine code,
including the indirect 1..32 selector/jump tables, for every single-bit value
surviving that mask plus zero and the exact constructed row values.

No historical-retail or source-symbol identity is inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

import t6_current_client_candidate_cfg_dataflow_probe_v1 as cfg

EXPECTED_SHA256 = "770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGET = 0x00493440
MASK = 0x3FFFFFFF
MAX_STEPS = 128

# Exact values already independently recovered in constructed current-client
# 12-byte zone rows. Labels remain descriptive evidence labels only.
CONSTRUCTED = {
    "patch_mp": 0x00000002,
    "code_post_gfx_mp": 0x00000008,
    "common_mp": 0x00000080,
    "ui_mp": 0x02000000,
    "patch_ui_mp": 0x08000000,
    "ffotd_mp": 0x20000000,
}


class EvalError(RuntimeError):
    pass


def read_u8(raw: bytes, sections, va: int) -> int:
    off = cfg.va_to_offset(sections, va)
    if off is None or off >= len(raw):
        raise EvalError(f"u8 VA not mapped: 0x{va:08x}")
    return raw[off]


def read_u32(raw: bytes, sections, va: int) -> int:
    off = cfg.va_to_offset(sections, va)
    if off is None or off + 4 > len(raw):
        raise EvalError(f"u32 VA not mapped: 0x{va:08x}")
    return struct.unpack_from("<I", raw, off)[0]


def s32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def decode_one(raw: bytes, sections, va: int):
    off = cfg.va_to_offset(sections, va)
    if off is None:
        raise EvalError(f"instruction VA not mapped: 0x{va:08x}")
    sec = cfg.section_for_va(sections, va)
    if not sec or not sec["executable"]:
        raise EvalError(f"instruction VA not executable: 0x{va:08x}")
    end = min(off + 15, sec["rawOffset"] + sec["rawSize"])
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    rows = list(md.disasm(raw[off:end], va, count=1))
    if len(rows) != 1:
        raise EvalError(f"cannot decode 0x{va:08x}")
    return rows[0]


def imm0(ins) -> int:
    if not ins.operands or ins.operands[0].type != X86_OP_IMM:
        raise EvalError(f"{ins.address:#x}: expected immediate target")
    return int(ins.operands[0].imm) & 0xFFFFFFFF


def evaluate(raw: bytes, sections, input_value: int) -> dict:
    eax = None
    cmp_left = None
    cmp_right = None
    pc = TARGET
    trace = []

    for _ in range(MAX_STEPS):
        ins = decode_one(raw, sections, pc)
        trace.append(
            {
                "address": f"0x{ins.address:08x}",
                "bytes": ins.bytes.hex(),
                "mnemonic": ins.mnemonic,
                "opStr": ins.op_str,
                "eaxBefore": None if eax is None else f"0x{eax & 0xffffffff:08x}",
            }
        )
        next_pc = ins.address + ins.size
        m = ins.mnemonic
        ops = ins.operands

        if ins.address == TARGET:
            # Exact entry instruction is mov eax,[esp+4]. The evaluator's
            # synthetic stack argument is the tested classifier value.
            if not (m == "mov" and len(ops) == 2 and ops[0].type == X86_OP_REG and ins.reg_name(ops[0].reg) == "eax" and ops[1].type == X86_OP_MEM):
                raise EvalError("entry instruction drift")
            eax = input_value & 0xFFFFFFFF

        elif m == "cmp":
            if len(ops) != 2 or ops[0].type != X86_OP_REG or ins.reg_name(ops[0].reg) != "eax" or ops[1].type != X86_OP_IMM:
                raise EvalError(f"{ins.address:#x}: unsupported cmp {ins.op_str}")
            if eax is None:
                raise EvalError("cmp before eax initialized")
            cmp_left = eax & 0xFFFFFFFF
            cmp_right = int(ops[1].imm) & 0xFFFFFFFF

        elif m == "dec":
            if len(ops) != 1 or ops[0].type != X86_OP_REG or ins.reg_name(ops[0].reg) != "eax":
                raise EvalError(f"{ins.address:#x}: unsupported dec")
            eax = (eax - 1) & 0xFFFFFFFF

        elif m == "mov":
            if len(ops) == 2 and ops[0].type == X86_OP_REG and ins.reg_name(ops[0].reg) == "eax" and ops[1].type == X86_OP_IMM:
                eax = int(ops[1].imm) & 0xFFFFFFFF
            else:
                raise EvalError(f"{ins.address:#x}: unsupported mov {ins.op_str}")

        elif m == "movzx":
            if not (len(ops) == 2 and ops[0].type == X86_OP_REG and ins.reg_name(ops[0].reg) == "eax" and ops[1].type == X86_OP_MEM):
                raise EvalError(f"{ins.address:#x}: unsupported movzx {ins.op_str}")
            mem = ops[1].mem
            if ins.reg_name(mem.base) != "eax" or mem.index != 0 or mem.scale != 1:
                raise EvalError(f"{ins.address:#x}: unexpected selector addressing")
            eax = read_u8(raw, sections, (eax + int(mem.disp)) & 0xFFFFFFFF)

        elif m == "xor":
            if not (len(ops) == 2 and all(op.type == X86_OP_REG and ins.reg_name(op.reg) == "eax" for op in ops)):
                raise EvalError(f"{ins.address:#x}: unsupported xor {ins.op_str}")
            eax = 0

        elif m in {"je", "jne", "jg", "ja"}:
            if cmp_left is None or cmp_right is None:
                raise EvalError(f"{ins.address:#x}: branch without cmp")
            eq = cmp_left == cmp_right
            take = {
                "je": eq,
                "jne": not eq,
                "jg": s32(cmp_left) > s32(cmp_right),
                "ja": cmp_left > cmp_right,
            }[m]
            if take:
                next_pc = imm0(ins)

        elif m == "jmp":
            if len(ops) != 1:
                raise EvalError(f"{ins.address:#x}: bad jmp")
            op = ops[0]
            if op.type == X86_OP_IMM:
                next_pc = int(op.imm) & 0xFFFFFFFF
            elif op.type == X86_OP_MEM:
                mem = op.mem
                if mem.base != 0 or ins.reg_name(mem.index) != "eax" or mem.scale != 4:
                    raise EvalError(f"{ins.address:#x}: unexpected jump-table addressing")
                next_pc = read_u32(raw, sections, int(mem.disp) + eax * 4)
            else:
                raise EvalError(f"{ins.address:#x}: unsupported jmp")

        elif m == "ret":
            if eax is None:
                raise EvalError("ret without eax")
            trace[-1]["eaxAfter"] = f"0x{eax & 0xffffffff:08x}"
            return {
                "input": input_value & 0xFFFFFFFF,
                "inputHex": f"0x{input_value & 0xffffffff:08x}",
                "ordinal": eax & 0xFFFFFFFF,
                "ordinalHex": f"0x{eax & 0xffffffff:08x}",
                "steps": len(trace),
                "terminalVa": f"0x{ins.address:08x}",
                "trace": trace,
            }

        else:
            raise EvalError(f"{ins.address:#x}: unsupported instruction {m} {ins.op_str}")

        trace[-1]["eaxAfter"] = None if eax is None else f"0x{eax & 0xffffffff:08x}"
        pc = next_pc

    raise EvalError(f"step limit for input 0x{input_value:08x}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--revision", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    raw = args.exe.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != EXPECTED_SHA256:
        raise SystemExit(f"unexpected current-client SHA-256 {sha}")
    image_base, sections = cfg.parse_pe(raw)

    values = [0] + [1 << bit for bit in range(30)]
    rows = [evaluate(raw, sections, value) for value in values]
    by_value = {row["input"]: row for row in rows}

    constructed = []
    for name, value in CONSTRUCTED.items():
        row = by_value.get(value)
        if row is None:
            row = evaluate(raw, sections, value)
        constructed.append(
            {
                "name": name,
                "classifier": value,
                "classifierHex": f"0x{value:08x}",
                "ordinal": row["ordinal"],
                "ordinalHex": row["ordinalHex"],
                "terminalVa": row["terminalVa"],
            }
        )

    # Fail closed on the exact machine-code anchors that make the indirect
    # low-value table part of this proof.
    selector = decode_one(raw, sections, 0x00493466)
    jump = decode_one(raw, sections, 0x0049346D)
    if selector.mnemonic != "movzx" or "0x4935c0" not in selector.op_str:
        raise SystemExit("selector-table instruction drift")
    if jump.mnemonic != "jmp" or "0x4935a4" not in jump.op_str:
        raise SystemExit("jump-table instruction drift")

    output = {
        "format": "t6-current-client-zone-classifier-ordinal-map-v1",
        "authority": "SHA-classified current Plutonium client only",
        "client": {
            "revision": args.revision,
            "bytes": len(raw),
            "sha256": sha,
            "imageBaseHex": f"0x{image_base:08x}",
        },
        "target": f"0x{TARGET:08x}",
        "inputMaskAppliedByCaller": f"0x{MASK:08x}",
        "singleBitAndZeroMap": [
            {
                "classifier": row["input"],
                "classifierHex": row["inputHex"],
                "ordinal": row["ordinal"],
                "ordinalHex": row["ordinalHex"],
                "steps": row["steps"],
                "terminalVa": row["terminalVa"],
            }
            for row in rows
        ],
        "constructedRowMap": constructed,
        "lowValueIndirectTables": {
            "selectorTableBase": "0x004935c0",
            "jumpTableBase": "0x004935a4",
            "selectorInstruction": cfg.insn_json(selector),
            "jumpInstruction": cfg.insn_json(jump),
        },
        "evaluationTraces": {row["inputHex"]: row["trace"] for row in rows},
        "summary": {
            "testedValueCount": len(rows),
            "nonzeroOrdinalCount": sum(row["ordinal"] != 0 for row in rows),
            "zeroOrdinalInputs": [row["inputHex"] for row in rows if row["ordinal"] == 0],
            "constructedRowCount": len(constructed),
        },
        "status": "exact_current_client_classifier_to_ordering_ordinal_map_no_historical_retail_promotion",
        "proofBoundary": (
            "The mapping is obtained by evaluating the exact SHA-classified current-client machine code at 0x00493440, "
            "including its embedded selector/jump tables. The result may be called a current-client ordering ordinal because "
            "independent current-client proof shows its return values control linked-record insertion order. It is not by itself "
            "a source-symbol proof, historical-retail equivalence proof, or authorization to select any historical-retail Technique winner."
        ),
    }
    payload = (json.dumps(output, indent=2, sort_keys=True) + "\n").encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    print(json.dumps({
        "proofBytes": len(payload),
        "proofSha256": hashlib.sha256(payload).hexdigest(),
        "summary": output["summary"],
        "constructedRowMap": constructed,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

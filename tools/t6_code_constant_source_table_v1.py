#!/usr/bin/env python3
"""Parse the pinned OpenAssetTools T6 code-constant source table exactly.

Authoritative upstream inputs (pinned):
- OpenAssetTools commit 2ca512abe7cb82d70a94d5ad7846043c3978862d
- src/ObjCommon/Game/T6/Techset/TechsetConstantsT6.h
  Git blob b57c90f901b992ce39f3c513c4b967003b2b2ea6
- src/Common/Game/T6/T6_Assets.h
  Git blob 4ed3d959bf98618d313b03d96f0530aefb26bbef

`TechsetConstantsT6.h` is the compiler/dumper accessor table used for `.tech`
`code.*` arguments. `T6_Assets.h` owns the `MaterialConstantSource` enum values.
This tool joins them without copying a hand-maintained enum table into this repo.

Rows preserve:
- exact accessor;
- exact MaterialConstantSource enum symbol and numeric value;
- arrayCount;
- updateFrequency;
- optional techFlags;
- optional transposedMatrix enum symbol/value.

No runtime value or physical meaning is inferred from an accessor name.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

FORMAT = "t6-code-constant-source-table-v1"
PINNED_OAT_COMMIT = "2ca512abe7cb82d70a94d5ad7846043c3978862d"
CONSTANTS_REL = Path("src/ObjCommon/Game/T6/Techset/TechsetConstantsT6.h")
ASSETS_REL = Path("src/Common/Game/T6/T6_Assets.h")
CONSTANTS_BLOB = "b57c90f901b992ce39f3c513c4b967003b2b2ea6"
ASSETS_BLOB = "4ed3d959bf98618d313b03d96f0530aefb26bbef"


class T6CodeConstantTableError(RuntimeError):
    pass


def _jhash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def _balanced_body(text: str, start_pattern: str, label: str) -> str:
    match = re.search(start_pattern, text, flags=re.M)
    if not match:
        raise T6CodeConstantTableError(f"could not locate {label}")
    open_index = text.find("{", match.start())
    if open_index < 0:
        raise T6CodeConstantTableError(f"{label} has no opening brace")
    depth = 0
    in_string = False
    escaped = False
    for i in range(open_index, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[open_index + 1:i]
            if depth < 0:
                break
    raise T6CodeConstantTableError(f"unterminated {label}")


def _eval_expr(expression: str, values: dict[str, int]) -> int:
    expression = expression.strip()
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise T6CodeConstantTableError(f"unsupported enum expression {expression!r}") from exc

    def eval_node(node) -> int:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return int(node.value)
        if isinstance(node, ast.Name):
            if node.id not in values:
                raise T6CodeConstantTableError(
                    f"enum expression {expression!r} references unknown symbol {node.id!r}"
                )
            return int(values[node.id])
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Invert)):
            value = eval_node(node.operand)
            if isinstance(node.op, ast.UAdd): return value
            if isinstance(node.op, ast.USub): return -value
            return ~value
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.LShift, ast.RShift, ast.BitOr, ast.BitAnd, ast.BitXor)
        ):
            a, b = eval_node(node.left), eval_node(node.right)
            if isinstance(node.op, ast.Add): return a + b
            if isinstance(node.op, ast.Sub): return a - b
            if isinstance(node.op, ast.LShift): return a << b
            if isinstance(node.op, ast.RShift): return a >> b
            if isinstance(node.op, ast.BitOr): return a | b
            if isinstance(node.op, ast.BitAnd): return a & b
            return a ^ b
        raise T6CodeConstantTableError(f"unsupported enum AST in {expression!r}: {ast.dump(node)}")
    return eval_node(tree.body)


def parse_material_constant_source_enum(assets_text: str) -> dict:
    body = _balanced_body(
        _strip_comments(assets_text),
        r"\benum\s+MaterialConstantSource(?:\s*:\s*[^\{]+)?\s*\{",
        "MaterialConstantSource enum",
    )
    values: dict[str, int] = {}
    rows = []
    current = -1
    # Enum entries do not contain nested commas/expressions in the pinned T6 file.
    for raw in body.split(","):
        entry = raw.strip()
        if not entry:
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)(?:\s*=\s*(.+))?", entry, flags=re.S)
        if not match:
            raise T6CodeConstantTableError(f"unsupported MaterialConstantSource entry {entry!r}")
        name, expression = match.groups()
        value = current + 1 if expression is None else _eval_expr(expression.strip(), values)
        values[name] = value
        current = value
        rows.append({
            "symbol": name,
            "value": value,
            "valueHex": f"0x{value:x}",
            "explicitExpression": None if expression is None else expression.strip(),
        })
    if not rows:
        raise T6CodeConstantTableError("MaterialConstantSource enum parsed zero entries")
    aliases: dict[int, list[str]] = {}
    for row in rows:
        aliases.setdefault(int(row["value"]), []).append(str(row["symbol"]))
    return {
        "rows": rows,
        "bySymbol": values,
        "aliasesByValue": {str(k): v for k, v in sorted(aliases.items())},
    }


def _top_level_records(body: str) -> list[str]:
    records = []
    depth = 0
    start = None
    in_string = False
    escaped = False
    for i, ch in enumerate(body):
        if in_string:
            if escaped: escaped = False
            elif ch == "\\": escaped = True
            elif ch == '"': in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            if depth == 0: start = i + 1
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                raise T6CodeConstantTableError("negative brace depth in commonCodeConstSources")
            if depth == 0:
                if start is None: raise T6CodeConstantTableError("record end without start")
                records.append(body[start:i])
                start = None
    if depth != 0:
        raise T6CodeConstantTableError("unterminated commonCodeConstSources record")
    return records


def _field(record: str, name: str) -> str | None:
    match = re.search(rf"\.{re.escape(name)}\s*=\s*([^,]+),", record)
    return None if not match else match.group(1).strip()


def parse_common_code_const_sources(constants_text: str, enum_doc: dict) -> list[dict]:
    body = _balanced_body(
        _strip_comments(constants_text),
        r"\bcommonCodeConstSources\s*\[\s*\]\s*\{",
        "commonCodeConstSources",
    )
    by_symbol = enum_doc["bySymbol"]
    aliases = enum_doc["aliasesByValue"]
    rows = []
    seen_accessor = set()
    seen_value_symbol = set()
    for record in _top_level_records(body):
        symbol = _field(record, "value")
        accessor_raw = _field(record, "accessor")
        array_raw = _field(record, "arrayCount")
        frequency_raw = _field(record, "updateFrequency")
        if None in (symbol, accessor_raw, array_raw, frequency_raw):
            raise T6CodeConstantTableError(f"incomplete commonCodeConstSources row: {record[:160]!r}")
        if symbol not in by_symbol:
            raise T6CodeConstantTableError(f"code source row uses unknown enum symbol {symbol!r}")
        accessor_match = re.fullmatch(r'"([^"\\]*(?:\\.[^"\\]*)*)"', accessor_raw)
        if not accessor_match:
            raise T6CodeConstantTableError(f"unsupported code accessor literal {accessor_raw!r}")
        accessor = bytes(accessor_match.group(1), "utf-8").decode("unicode_escape")
        try:
            array_count = int(array_raw, 0)
        except ValueError as exc:
            raise T6CodeConstantTableError(f"non-integer arrayCount {array_raw!r}") from exc
        freq_match = re.fullmatch(r"techset::CommonCodeSourceUpdateFrequency::([A-Z_]+)", frequency_raw)
        if not freq_match:
            raise T6CodeConstantTableError(f"unsupported updateFrequency {frequency_raw!r}")
        if accessor in seen_accessor:
            raise T6CodeConstantTableError(f"duplicate code-constant accessor {accessor!r}")
        if symbol in seen_value_symbol:
            raise T6CodeConstantTableError(f"duplicate code-constant enum symbol row {symbol!r}")
        seen_accessor.add(accessor); seen_value_symbol.add(symbol)
        value = int(by_symbol[symbol])
        transposed = _field(record, "transposedMatrix")
        if transposed is not None and transposed not in by_symbol:
            raise T6CodeConstantTableError(
                f"{accessor!r}: transposedMatrix references unknown enum {transposed!r}"
            )
        row = {
            "accessor": accessor,
            "enumSymbol": symbol,
            "enumValue": value,
            "enumValueHex": f"0x{value:x}",
            "enumAliases": list(aliases.get(str(value), [])),
            "arrayCount": array_count,
            "updateFrequency": freq_match.group(1),
            "techFlags": _field(record, "techFlags"),
            "transposedMatrixEnumSymbol": transposed,
            "transposedMatrixEnumValue": None if transposed is None else int(by_symbol[transposed]),
        }
        rows.append(row)
    if not rows:
        raise T6CodeConstantTableError("commonCodeConstSources parsed zero rows")
    return rows


def build_from_text(constants_text: str, assets_text: str, *, verify_pinned_blobs: bool = False) -> dict:
    constants_bytes = constants_text.encode("utf-8")
    assets_bytes = assets_text.encode("utf-8")
    constants_blob = git_blob_sha(constants_bytes)
    assets_blob = git_blob_sha(assets_bytes)
    if verify_pinned_blobs:
        if constants_blob != CONSTANTS_BLOB:
            raise T6CodeConstantTableError(
                f"TechsetConstantsT6.h Git blob {constants_blob} != pinned {CONSTANTS_BLOB}"
            )
        if assets_blob != ASSETS_BLOB:
            raise T6CodeConstantTableError(
                f"T6_Assets.h Git blob {assets_blob} != pinned {ASSETS_BLOB}"
            )
    enum_doc = parse_material_constant_source_enum(assets_text)
    rows = parse_common_code_const_sources(constants_text, enum_doc)
    by_accessor = {row["accessor"]: row for row in rows}
    return {
        "format": FORMAT,
        "source": {
            "openAssetToolsCommit": PINNED_OAT_COMMIT,
            "techsetConstants": {
                "path": str(CONSTANTS_REL),
                "gitBlobSha1": constants_blob,
                "pinnedGitBlobSha1": CONSTANTS_BLOB,
                "bytes": len(constants_bytes),
            },
            "t6Assets": {
                "path": str(ASSETS_REL),
                "gitBlobSha1": assets_blob,
                "pinnedGitBlobSha1": ASSETS_BLOB,
                "bytes": len(assets_bytes),
            },
            "pinnedBlobVerificationRequired": bool(verify_pinned_blobs),
        },
        "rows": rows,
        "summary": {
            "codeConstantSourceCount": len(rows),
            "arraySourceCount": sum(1 for row in rows if int(row["arrayCount"]) > 0),
            "matrixPairSourceCount": sum(1 for row in rows if row["transposedMatrixEnumSymbol"] is not None),
            "updateFrequencyCounts": {
                frequency: sum(1 for row in rows if row["updateFrequency"] == frequency)
                for frequency in sorted({row["updateFrequency"] for row in rows})
            },
            "materialConstantSourceEnumEntryCount": len(enum_doc["rows"]),
            "uniqueAccessorCount": len(by_accessor),
            "rowsSha256": _jhash(rows),
        },
        "enumAliasesByValue": enum_doc["aliasesByValue"],
        "proofBoundary": (
            "Exact parser join of pinned OpenAssetTools T6 commonCodeConstSources accessor metadata to the pinned "
            "MaterialConstantSource enum. This proves compiler/dumper code-source identity/index/array/update-frequency "
            "metadata only; it does not recover runtime values or assign physical semantics from accessor names."
        ),
    }


def build_from_root(oat_source_root: Path, *, verify_pinned_blobs: bool = True) -> dict:
    root = Path(oat_source_root)
    constants_path = root / CONSTANTS_REL
    assets_path = root / ASSETS_REL
    if not constants_path.is_file() or not assets_path.is_file():
        raise T6CodeConstantTableError(
            f"OAT source root lacks pinned T6 headers: {constants_path}, {assets_path}"
        )
    constants_bytes = constants_path.read_bytes(); assets_bytes = assets_path.read_bytes()
    try:
        constants_text = constants_bytes.decode("utf-8"); assets_text = assets_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise T6CodeConstantTableError("pinned OAT T6 headers are not UTF-8") from exc
    return build_from_text(constants_text, assets_text, verify_pinned_blobs=verify_pinned_blobs)


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument('--oat-source-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--allow-unpinned-source',action='store_true');a=p.parse_args();d=build_from_root(a.oat_source_root,verify_pinned_blobs=not a.allow_unpinned_source);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d['summary'],indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())

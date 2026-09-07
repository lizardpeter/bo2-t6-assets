#!/usr/bin/env python3
"""Build a fail-closed T6 TechniqueSet/pass/shader manifest from OAT dumps.

This parser does not infer T6 loader ownership or shader semantics.  It consumes
OpenAssetTools' native dump products *after* OAT has resolved the retail
Material -> MaterialTechniqueSet pointers and records the exact files and
bindings that OAT emitted.

Expected OAT layout (pinned OAT 9dca965...):
    techsets/<techset>.techset
    techniques/<technique>.tech
    shader_bin/vs_<vertex-shader>.cso
    shader_bin/ps_<pixel-shader>.cso

The input binding manifest is the JSON produced by
`t6_nuketown_car01_oat_material_binding_v2.yml` (or another manifest with the
same `targets[*].techniqueSet` contract).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


TECHSET_HEADER_RE = re.compile(r'^\s*"(?P<type>[^"]+)"\s*:\s*$')
TECHSET_VALUE_RE = re.compile(r'^\s*(?P<name>[^";][^;]*?)\s*;\s*$')
SHADER_RE = re.compile(
    r'^\s*(?P<kind>vertexShader|pixelShader)\s+'
    r'(?P<major>\d+)\.(?P<minor>\d+)\s+"(?P<name>[^"]+)"\s*$'
)
ASSIGN_RE = re.compile(r'^\s*(?P<dest>[^/=][^=]*?)\s*=\s*(?P<src>[^;]+)\s*;\s*$')
VERTEX_ROUTE_RE = re.compile(r'^\s*vertex\.(?P<dest>[^=\s]+)\s*=\s*code\.(?P<src>[^;\s]+)\s*;\s*$')
STATE_MAP_RE = re.compile(r'^\s*stateMap\s+"(?P<name>[^"]+)"\s*;')


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def file_record(path: Path, root: Path, *, include_text: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        'path': path.relative_to(root).as_posix(),
        'size': path.stat().st_size,
        'sha256': sha256_file(path),
    }
    if include_text:
        result['text'] = path.read_text(encoding='utf-8', errors='strict')
    return result


def parse_techset(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse OAT CommonTechsetDumper's exact line-oriented grammar.

    OAT can emit multiple quoted technique-type headers followed by one
    technique value when several technique slots share the same technique.
    """
    pending_types: list[str] = []
    bindings: list[dict[str, Any]] = []
    errors: list[str] = []

    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped:
            continue
        m = TECHSET_HEADER_RE.match(raw)
        if m:
            pending_types.append(m.group('type'))
            continue
        m = TECHSET_VALUE_RE.match(raw)
        if m:
            if not pending_types:
                errors.append(f'line {lineno}: technique value without type header: {raw!r}')
                continue
            name = m.group('name').strip()
            bindings.append({'technique': name, 'types': pending_types[:]})
            pending_types.clear()
            continue
        errors.append(f'line {lineno}: unrecognized techset syntax: {raw!r}')

    if pending_types:
        errors.append(f'technique type header(s) without value: {pending_types!r}')
    return bindings, errors


def split_top_level_passes(text: str) -> tuple[list[list[tuple[int, str]]], list[str]]:
    """Split a dumped .tech file into top-level MaterialTechnique passes."""
    depth = 0
    current: list[tuple[int, str]] | None = None
    passes: list[list[tuple[int, str]]] = []
    errors: list[str] = []

    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        # Debug comments can appear before a pass.
        if depth == 0 and (not stripped or stripped.startswith('//')):
            continue

        opens = raw.count('{')
        closes = raw.count('}')

        if depth == 0:
            if stripped != '{':
                errors.append(f'line {lineno}: expected top-level pass opening brace, got {raw!r}')
                continue
            current = [(lineno, raw)]
        elif current is not None:
            current.append((lineno, raw))

        depth += opens - closes
        if depth < 0:
            errors.append(f'line {lineno}: brace depth became negative')
            depth = 0
            current = None
            continue

        if depth == 0 and current is not None:
            passes.append(current)
            current = None

    if depth != 0 or current is not None:
        errors.append(f'unterminated pass at EOF (brace depth {depth})')
    return passes, errors


def parse_pass(lines: list[tuple[int, str]], root: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    shaders: list[dict[str, Any]] = []
    vertex_routes: list[dict[str, str]] = []
    state_maps: list[str] = []
    shader_stack: list[dict[str, Any]] = []
    depth = 0

    for lineno, raw in lines:
        stripped = raw.strip()

        sm = STATE_MAP_RE.match(raw)
        if sm:
            state_maps.append(sm.group('name'))

        vr = VERTEX_ROUTE_RE.match(raw)
        if vr:
            vertex_routes.append({'destination': vr.group('dest'), 'source': vr.group('src')})

        sh = SHADER_RE.match(raw)
        if sh:
            kind = sh.group('kind')
            name = sh.group('name')
            prefix = 'vs' if kind == 'vertexShader' else 'ps'
            bin_path = root / 'shader_bin' / f'{prefix}_{name}.cso'
            shader: dict[str, Any] = {
                'kind': kind,
                'name': name,
                'model': f"{sh.group('major')}.{sh.group('minor')}",
                'line': lineno,
                'arguments': [],
            }
            if bin_path.is_file():
                shader['binary'] = file_record(bin_path, root)
            else:
                shader['binary'] = None
                errors.append(f'line {lineno}: missing shader binary {bin_path.relative_to(root).as_posix()}')
            shaders.append(shader)
            # OAT emits the opening brace on the following line. Keep the
            # declaration alive until that block has actually opened and then
            # returned to the declaration depth. The v1 parser originally
            # popped here immediately because the declaration line itself does
            # not change brace depth, dropping every shader argument.
            shader_stack.append({
                'shader': shader,
                'declaration_depth': depth,
                'block_started': False,
            })

        assign = ASSIGN_RE.match(raw)
        if assign and shader_stack:
            src = assign.group('src').strip()
            # stateMap and vertex routing are not shader argument assignments.
            if not stripped.startswith('stateMap ') and not stripped.startswith('vertex.'):
                arg = {
                    'destination': assign.group('dest').strip(),
                    'source': src,
                    'line': lineno,
                }
                if src.startswith('material.'):
                    arg['sourceClass'] = 'material'
                    arg['materialProperty'] = src[len('material.'):]
                elif src.startswith('constant.'):
                    arg['sourceClass'] = 'constant'
                elif src.startswith('sampler.'):
                    arg['sourceClass'] = 'sampler'
                elif src.startswith('float4('):
                    arg['sourceClass'] = 'literal'
                else:
                    arg['sourceClass'] = 'other'
                shader_stack[-1]['shader']['arguments'].append(arg)

        depth += raw.count('{') - raw.count('}')
        for entry in shader_stack:
            if depth > entry['declaration_depth']:
                entry['block_started'] = True
        while (
            shader_stack
            and shader_stack[-1]['block_started']
            and depth <= shader_stack[-1]['declaration_depth']
        ):
            shader_stack.pop()

    if len(state_maps) != 1:
        errors.append(f'pass has {len(state_maps)} stateMap declarations (expected 1)')

    return {
        'stateMap': state_maps[0] if len(state_maps) == 1 else state_maps,
        'shaders': shaders,
        'vertexRouting': vertex_routes,
        'textLines': [{'line': n, 'text': s} for n, s in lines],
    }, errors


def build_manifest(root: Path, binding: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    target_rows = binding.get('targets')
    if not isinstance(target_rows, list):
        raise ValueError('binding manifest has no targets array')

    material_bindings: list[dict[str, str]] = []
    techset_names: list[str] = []
    for row in target_rows:
        if not isinstance(row, dict) or not row.get('resolved'):
            errors.append({'scope': 'material', 'error': 'unresolved target in binding manifest', 'row': row})
            continue
        material = row.get('material')
        techset = row.get('techniqueSet')
        if not isinstance(material, str) or not isinstance(techset, str) or not techset:
            errors.append({'scope': 'material', 'error': 'invalid material/techniqueSet binding', 'row': row})
            continue
        material_bindings.append({'material': material, 'techniqueSet': techset})
        if techset not in techset_names:
            techset_names.append(techset)

    techsets: list[dict[str, Any]] = []
    parsed_techniques: dict[str, dict[str, Any]] = {}

    for techset_name in techset_names:
        path = root / 'techsets' / f'{techset_name}.techset'
        if not path.is_file():
            errors.append({'scope': 'techset', 'name': techset_name, 'error': 'missing .techset file', 'path': path.relative_to(root).as_posix()})
            continue
        text = path.read_text(encoding='utf-8', errors='strict')
        type_bindings, parse_errors = parse_techset(text)
        for error in parse_errors:
            errors.append({'scope': 'techset', 'name': techset_name, 'error': error})

        row: dict[str, Any] = {
            'name': techset_name,
            'file': file_record(path, root, include_text=True),
            'techniqueTypeBindings': type_bindings,
        }
        techsets.append(row)

        for binding_row in type_bindings:
            technique_name = binding_row['technique']
            if technique_name in parsed_techniques:
                continue
            tpath = root / 'techniques' / f'{technique_name}.tech'
            if not tpath.is_file():
                errors.append({'scope': 'technique', 'name': technique_name, 'error': 'missing .tech file', 'path': tpath.relative_to(root).as_posix()})
                continue
            ttext = tpath.read_text(encoding='utf-8', errors='strict')
            raw_passes, split_errors = split_top_level_passes(ttext)
            for error in split_errors:
                errors.append({'scope': 'technique', 'name': technique_name, 'error': error})
            passes: list[dict[str, Any]] = []
            for pass_index, pass_lines in enumerate(raw_passes):
                pass_row, pass_errors = parse_pass(pass_lines, root)
                pass_row['index'] = pass_index
                passes.append(pass_row)
                for error in pass_errors:
                    errors.append({'scope': 'technique', 'name': technique_name, 'pass': pass_index, 'error': error})
            parsed_techniques[technique_name] = {
                'name': technique_name,
                'file': file_record(tpath, root, include_text=True),
                'passes': passes,
            }

    return {
        'format': 't6-oat-techset-binding-manifest-v1',
        'proofBoundary': (
            'Records only native OpenAssetTools dump products and their exact '
            'declared TechniqueSet/technique/pass/shader bindings; no shader-role '
            'or PBR semantic inference.'
        ),
        'sourceBindingManifest': {
            'format': binding.get('format'),
            'openAssetToolsCommit': binding.get('openAssetToolsCommit'),
            'fastFileSha256': binding.get('fastFileSha256'),
        },
        'materialBindings': material_bindings,
        'techsets': techsets,
        'techniques': [parsed_techniques[name] for name in sorted(parsed_techniques)],
        'errors': errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--oat-root', type=Path, required=True, help='OAT Unlinker output root containing techsets/, techniques/, shader_bin/')
    parser.add_argument('--binding-manifest', type=Path, required=True, help='Native OAT Material -> TechniqueSet binding JSON')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()

    root = args.oat_root.resolve()
    binding = json.loads(args.binding_manifest.read_text(encoding='utf-8'))
    manifest = build_manifest(root, binding)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    for row in manifest['materialBindings']:
        print(f"{row['material']} -> {row['techniqueSet']}")
    for row in manifest['techsets']:
        print(f"techset {row['name']}: {len(row['techniqueTypeBindings'])} unique technique file binding(s)")
    for row in manifest['techniques']:
        print(f"technique {row['name']}: {len(row['passes'])} pass(es)")
        for p in row['passes']:
            for shader in p['shaders']:
                binary = shader.get('binary')
                suffix = binary['sha256'] if binary else 'MISSING'
                print(f"  pass {p['index']} {shader['kind']} {shader['name']} {suffix}")

    if manifest['errors']:
        print(json.dumps(manifest['errors'], indent=2))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

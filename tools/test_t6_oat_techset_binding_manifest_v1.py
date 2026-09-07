#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name('t6_oat_techset_binding_manifest_v1.py')
spec = importlib.util.spec_from_file_location('t6_oat_techset_binding_manifest_v1', MODULE_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class OatTechsetBindingManifestTest(unittest.TestCase):
    def test_native_dump_graph_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'techsets').mkdir()
            (root / 'techniques').mkdir()
            (root / 'shader_bin').mkdir()

            (root / 'techsets' / 'mc_lit_test.techset').write_text(
                '"lit":\n'
                '"lit sun":\n'
                '    lit_test_main;\n\n'
                '"emissive":\n'
                '    lit_test_emissive;\n',
                encoding='utf-8',
            )
            (root / 'techniques' / 'lit_test_main.tech').write_text(
                '{\n'
                '    stateMap "passthrough"; // TODO\n'
                '    vertexShader 5.0 "vs_test"\n'
                '    {\n'
                '        worldViewProjection = constant.worldViewProjection;\n'
                '    }\n'
                '    pixelShader 5.0 "ps_test"\n'
                '    {\n'
                '        colorMap = material.colorMap;\n'
                '        specMap = material.#0x12345678;\n'
                '    }\n'
                '    vertex.position = code.position;\n'
                '}\n',
                encoding='utf-8',
            )
            (root / 'techniques' / 'lit_test_emissive.tech').write_text(
                '{\n'
                '    stateMap "passthrough"; // TODO\n'
                '    vertexShader 5.0 "vs_test"\n'
                '    {\n'
                '    }\n'
                '    pixelShader 5.0 "ps_emit"\n'
                '    {\n'
                '        emissiveMap = material.emissiveMap;\n'
                '    }\n'
                '}\n',
                encoding='utf-8',
            )
            (root / 'shader_bin' / 'vs_vs_test.cso').write_bytes(b'VS')
            (root / 'shader_bin' / 'ps_ps_test.cso').write_bytes(b'PS')
            (root / 'shader_bin' / 'ps_ps_emit.cso').write_bytes(b'PE')

            binding = {
                'format': 't6-nuketown-car01-oat-material-binding-v2',
                'openAssetToolsCommit': '9dca965',
                'fastFileSha256': 'abc',
                'targets': [
                    {
                        'resolved': True,
                        'material': 'mc/mtl_nt_2020_car_01_exterior',
                        'techniqueSet': 'mc_lit_test',
                    }
                ],
            }
            result = mod.build_manifest(root, binding)

            self.assertEqual([], result['errors'])
            self.assertEqual(
                [{'material': 'mc/mtl_nt_2020_car_01_exterior', 'techniqueSet': 'mc_lit_test'}],
                result['materialBindings'],
            )
            self.assertEqual(
                [
                    {'technique': 'lit_test_main', 'types': ['lit', 'lit sun']},
                    {'technique': 'lit_test_emissive', 'types': ['emissive']},
                ],
                result['techsets'][0]['techniqueTypeBindings'],
            )

            main = next(x for x in result['techniques'] if x['name'] == 'lit_test_main')
            self.assertEqual(1, len(main['passes']))
            shaders = main['passes'][0]['shaders']
            self.assertEqual(['vs_test', 'ps_test'], [x['name'] for x in shaders])
            self.assertEqual(['constant'], [x['sourceClass'] for x in shaders[0]['arguments']])
            self.assertEqual(
                ['colorMap', '#0x12345678'],
                [x['materialProperty'] for x in shaders[1]['arguments']],
            )
            self.assertEqual(
                [{'destination': 'position', 'source': 'position'}],
                main['passes'][0]['vertexRouting'],
            )
            self.assertEqual(64, len(shaders[0]['binary']['sha256']))

    def test_techset_parser_fails_closed_on_orphan_value(self) -> None:
        bindings, errors = mod.parse_techset('orphan;\n')
        self.assertEqual([], bindings)
        self.assertEqual(1, len(errors))


if __name__ == '__main__':
    unittest.main()

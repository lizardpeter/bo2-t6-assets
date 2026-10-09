#!/usr/bin/env python3
"""Synthetic semantic-boundary unit checks for Ghidra bulk C++ candidate slicer."""
import importlib.util
import pathlib
import tempfile
import unittest
from unittest import mock


SPEC=importlib.util.spec_from_file_location(
    "t6_bulk", pathlib.Path(__file__).resolve().parents[1]/"tools/t6_server_bulk_cpp_candidates_v1.py"
)
M=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class CandidateTest(unittest.TestCase):
    def parsed(self, proto, body):
        return M.parse_candidate(f"{proto}\n{{\n{body}\n}}\n",
                                 {"requested_va": "0x00519400", "function_id": "pc-server:00519400"})

    def test_identity(self):
        data, status = self.parsed("int __cdecl Identity(int param_1)",
                                   "return param_1;")
        self.assertEqual(status, "pure_scalar_candidate")
        self.assertIn("std::int32_t Identity(std::int32_t param_1)", data["cpp"])

    def test_boolean_mask(self):
        data, status = self.parsed("bool __cdecl Flag(uint param_1)",
                                   "return (param_1 & 4U) != 0;")
        self.assertEqual(status, "pure_scalar_candidate")
        self.assertIn("(param_1 & 4U) != 0", data["cpp"])

    def test_no_arithmetic_without_x86_review(self):
        for b in ["return param_1 + 1;", "return param_1 * 2;",
                  "return param_1 / 3;", "return param_1 << 2;"]:
            with self.subTest(b=b):
                self.assertEqual(self.parsed("int __cdecl F(int param_1)", b)[0], None)

    def test_no_false_full_cpp_recovery(self):
        samples=[
            ("bool __cdecl F(int param_1)", "return Dvar_GetInt(party_maxplayers);"),
            ("int __cdecl F(void)", "return g_leaned;"),
            ("bool __cdecl F(int *param_1)", "return param_1 == 0;"),
            ("bool __cdecl FUN_00519400(int param_1)", "return param_1 != 0;"),
            ("bool __cdecl F(int param_1)", "return param_1 != 0;\n g_global = 3;"),
            ("bool __cdecl F(int param_1)", "if (param_1) return true;\nreturn false;"),
        ]
        for sig,b in samples:
            with self.subTest(sig=sig,b=b):
                self.assertIsNone(self.parsed(sig,b)[0])

    def test_full_corpus_requires_every_shard(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                M.build(pathlib.Path(td), pathlib.Path(td)/"out")

    def test_full_synthetic_shard_partition_and_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp)
            for i in range(8):
                shard=root/f"t6-full-pc-ghidra-decompile-{i:02d}"
                (shard/"unreviewed").mkdir(parents=True)
                id_=f"urn:t6:func:{i:08x}"
                with (shard/"results.tsv").open("w") as f:
                    f.write("function_id\trequested_va\tdecompile_completed\n")
                    f.write(f"{id_}\t0x{i:08x}\ttrue\n")
                name="Duplicate" if i in (0,1) else f"GetPrimitive{i}"
                (shard/"unreviewed"/f"{i:08x}.c").write_text(
                    f"int __cdecl {name}(int param_1) \n{{\nreturn param_1;\n}}\n")
            report=M.build(root, root/"output")
            self.assertEqual(report["original_ghidra_function_rows"],8)
            self.assertEqual(report["pure_scalar_candidate"],8)
            self.assertEqual(report["candidate_count_after_deduplication"],6)
            cpp=(root/"output"/"pure_scalar_candidates.cpp").read_text()
            self.assertEqual(cpp.count("namespace bo2_pc_va_"),6)
            self.assertNotIn("Duplicate(",cpp)


if __name__=="__main__":
    unittest.main()

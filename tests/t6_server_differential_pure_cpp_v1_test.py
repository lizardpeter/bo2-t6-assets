import importlib.util
import pathlib
import unittest

p=pathlib.Path(__file__).resolve().parents[1]/"tools/t6_server_differential_pure_cpp_v1.py"
spec=importlib.util.spec_from_file_location("t6diff",p)
M=importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

class DiffTests(unittest.TestCase):
    def test_pure_scalar_src(self):
        c,reason=M.parse_source(
            "int __cdecl Identity(int param_1)\n{\nreturn param_1;\n}\n",
            "0x00401000")
        self.assertEqual(reason,"eligible_scalar_local")
        self.assertEqual(c["arguments"],[("int","param_1")])
        self.assertIn("return param_1;",M.cpp(c))

    def test_globals_calls_pointers_loops_are_never_trusted(self):
        bad=[
            "return g_timer;",
            "return Com_GetCurrentTime();",
            "return *param_1;",
            "return param_1->foo;",
            "while (param_1) { return 1; } return 0;",
            "return param_1 / 0;",
        ]
        for body in bad:
            with self.subTest(body=body):
                c,_=M.parse_source(
                    f"int __cdecl F(int param_1)\n{{\n{body}\n}}\n",
                    "0x00401000")
                self.assertIsNone(c)

    def test_exact_contiguous_original_code(self):
        asm=("00401000\t8b442404\tMOV EAX,dword ptr [ESP + 0x4]\n"
             "00401004\tc3\tRET\n")
        data,reason=M.raw_x86_from_asm(asm,"0x00401000")
        self.assertEqual(data,bytes.fromhex("8b442404c3"))
        self.assertEqual(reason,"contiguous_exact_original_x86")

    def test_missing_bytes_are_never_accepted(self):
        asm=("00401000\t8b442404\tMOV EAX,dword ptr [ESP + 0x4]\n"
             "00401005\tc3\tRET\n")
        self.assertIsNone(M.raw_x86_from_asm(asm,"0x00401000")[0])

    def test_retail_x86_unicorn_case(self):
        try:
            import unicorn
        except ImportError:
            self.skipTest("Install Unicorn for emulator equivalence test")
        code=bytes.fromhex("8b442404c3")
        for value in [0,1,0xffffffff,0x7fffffff,0x80000000]:
            self.assertEqual(M.emulator_eval(code,0x00401000,[value]),value)

if __name__=="__main__":
    unittest.main()

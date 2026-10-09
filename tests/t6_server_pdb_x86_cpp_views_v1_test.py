#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest
from collections import Counter

path=pathlib.Path(__file__).resolve().parents[1]/"tools/t6_server_pdb_x86_cpp_views_v1.py"
spec=importlib.util.spec_from_file_location("t6_pdb_views",path)
M=importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

def t(kind="struct",size=24,alignment=4):
    return {"path":"/CoDMPServer_PC.pdb/Test","cpp_name":"pdb_Test_AABB",
            "kind":kind,"length":str(size),"alignment":str(alignment)}

def f(offset,length,name,datatype):
    return {"offset":str(offset),"length":str(length),"field_name":name,
            "field_type_path":datatype,"ordinal":str(offset)}

class Tests(unittest.TestCase):
    def test_original_scalar_offsets(self):
        stats=Counter()
        v=M.emit_type(t(),[
            f(0,4,"first","/int"),f(8,4,"ptr","/SomeType *"),
            f(12,8,"alias","/char[8]"),f(20,4,"end","/uint")],stats)
        self.assertIsNotNone(v)
        cpp,fields,meta=v
        self.assertIn("std::int32_t first;",cpp)
        self.assertIn("std::uint8_t __pad_1[4]",cpp)
        self.assertIn("std::uint32_t ptr;",cpp)
        self.assertIn("char alias[8];",cpp)
        self.assertIn("sizeof(pdb_Test_AABB) == 24",cpp)
        self.assertIn("offsetof(pdb_Test_AABB, ptr) == 8",cpp)
        self.assertEqual(meta["typed"],4)
    def test_opaque_complex_field_preserves_size_and_offset(self):
        v=M.emit_type(t(size=20),[f(0,16,"complexField","/SomeNestedClass"),f(16,4,"score","/float")],Counter())
        self.assertIn("std::uint8_t complexField[16]",v[0])
        self.assertIn("float score",v[0])
        self.assertEqual(v[2]["opaque"],1)
    def test_union_no_deceptive_overlapping_members(self):
        v=M.emit_type(t(kind="union",size=8,alignment=4),
                 [f(0,8,"all","/double"),f(0,4,"first","/uint")],Counter())
        self.assertIn("__storage[8]",v[0])
        self.assertNotIn("double all",v[0])
        self.assertTrue(v[2]["overlapping"])
    def test_reject_corrupt_ghidra_offsets_not_silently_truncate(self):
        self.assertIsNone(M.emit_type(t(size=4),[f(3,4,"bad","/uint")],Counter()))
    def test_reject_bad_alignment(self):
        self.assertIsNone(M.emit_type(t(size=12,alignment=8),[],Counter()))
    def test_no_invalid_field_identifier(self):
        used=set()
        self.assertEqual(M.member_name("switch",0,used),"pdb_field_0")
        self.assertEqual(M.member_name("validName",1,used),"validName")
        self.assertEqual(M.member_name("validName",2,used),"validName_ordinal_2")
    def test_target_x86_pointer_not_native_host_pointer(self):
        self.assertEqual(M.cpp_scalar("/CoDMPServer_PC.pdb/WeaponDef *",4),
                         ("std::uint32_t","",4))
        self.assertIsNone(M.cpp_scalar("/CoDMPServer_PC.pdb/WeaponDef *",8))

if __name__=="__main__":
    unittest.main()

#!/usr/bin/env python3
"""Proof tests for exact original-x86-call-target-aware BO2 C++ wrappers."""
import importlib.util
import pathlib
import unittest
from collections import Counter

p=pathlib.Path(__file__).resolve().parents[1]/"tools/t6_server_scalar_wrappers_v1.py"
spec=importlib.util.spec_from_file_location("t6_wrappers",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def R(name,va,rtype,args,body,call=None):
    asm=(f"0x{va[2:]}\t90\tNOP\n" +
         (f"0x{va[2:]}\te8\tCALL {call}\n" if call else ""))
    return m.Record(name=name,entry=va,rtype=rtype,params=tuple(args),body=body,
                    id="test-"+va,asm=asm)

class WrapperTests(unittest.TestCase):
    def test_single_direct_named_call(self):
        child=R("Child","0x00400000","bool",[]," return true; ")
        parent=R("Parent","0x00400010","bool",[],
                 " bool bVar1;\n bVar1 = Child();\n return bVar1;\n ",
                 "0x00400000")
        cs=m.compile_wrappers([child,parent],Counter())
        self.assertEqual(len(cs),1)
        self.assertIn("bool Parent()",cs[0][2])
        self.assertIn("return Child();",cs[0][2])

    def test_no_fake_target_matches(self):
        child=R("Child","0x00400000","bool",[],"return false;")
        bad=R("Parent","0x00400010","bool",[],"return Child();","0x00400020")
        self.assertFalse(m.compile_wrappers([child,bad],Counter()))

    def test_param_forwarding_and_types(self):
        child=R("Child","0x00400000","int",[("int","param_1")],"return param_1;")
        parent=R("Parent","0x00400010","int",[("int","param_1")],
                 "return Child(param_1);","0x00400000")
        cs=m.compile_wrappers([child,parent],Counter())
        self.assertEqual(len(cs),1)
        self.assertIn("std::int32_t Parent(std::int32_t param_1)",cs[0][2])

    def test_type_change_rejected(self):
        child=R("Child","0x00400000","int",[("int","param_1")],"return param_1;")
        parent=R("Parent","0x00400010","bool",[("int","param_1")],
                 "return Child(param_1);","0x00400000")
        self.assertFalse(m.compile_wrappers([child,parent],Counter()))

if __name__=="__main__":
    unittest.main()

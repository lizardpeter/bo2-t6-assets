#!/usr/bin/env python3
"""Classify exact OAT `.tech` RHS namespaces without semantic guessing.

Current OAT technique dumping uses:
- material.<name> for material constants/samplers;
- constant.<accessor> for engine code constants;
- sampler.<accessor> for engine code samplers.

Older repository fixtures used code.<accessor>; that spelling remains recognized
as a legacy compatibility namespace but is not treated as evidence that current
OAT emits it.
"""
from __future__ import annotations

FORMAT='t6-tech-argument-source-identity-v2'

def source_identity(expression:str|None)->dict:
 if expression is None:return {'sourceClass':'unassigned','sourceNamespace':None,'sourceKind':None,'sourceExpression':None,'sourceName':None}
 expression=str(expression).strip()
 mapping=(('material','material','material'),('constant','code','constant'),('sampler','code','sampler'),('code','code','legacy_code'))
 for namespace,source_class,kind in mapping:
  token=namespace+'.'
  if expression.startswith(token) and len(expression)>len(token):
   return {'sourceClass':source_class,'sourceNamespace':namespace,'sourceKind':kind,'sourceExpression':expression,'sourceName':expression[len(token):]}
 return {'sourceClass':'other','sourceNamespace':None,'sourceKind':'other','sourceExpression':expression,'sourceName':None}

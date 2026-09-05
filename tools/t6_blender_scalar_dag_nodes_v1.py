#!/usr/bin/env python3
"""Compile a validated forensic T6 scalar DAG into Blender Math nodes.

This generalizes the already-used vN height node equations without changing the
historical height adapter.  Callers supply every leaf explicitly: input sockets,
cbuffer literal values and sample sockets.  Child order is preserved.

Blender is an authoring backend; graph/equation fidelity is preserved, while
bit-identical D3D11 floating-point rounding is not claimed.
"""
from __future__ import annotations
from typing import Any
from t6_generated_height_weight_dag_v1 import validate_forensic_dag
import t6_blender_height_dag_nodes_v1 as h

class BlenderScalarDagError(RuntimeError): pass

def compile_scalar_dag(nodes,links,dag:dict,*,label_prefix:str,input_sockets:dict[str,Any]|None=None,constant_values:dict[str,float]|None=None,sample_sockets:dict[tuple[str,str],Any]|None=None):
 try:validate_forensic_dag(dag)
 except Exception as exc:raise BlenderScalarDagError(f"invalid forensic DAG: {exc}") from exc
 inputs={} if input_sockets is None else input_sockets
 constants={} if constant_values is None else constant_values
 samples={} if sample_sockets is None else sample_sockets
 values=[];specs=dag["nodes"]
 for index,spec in enumerate(specs):
  kind=str(spec.get("kind") or "");label=f"{label_prefix} #{index} {kind}";args=[values[int(c)] for c in spec.get("args",[])]
  try:
   if kind=="input":
    name=str(spec.get("name") or "");out=inputs.get(name)
    if out is None:raise BlenderScalarDagError(f"{label}: unbound input {name!r}")
   elif kind=="cb":
    name=str(spec.get("name") or "")
    if name not in constants:raise BlenderScalarDagError(f"{label}: unbound constant {name!r}")
    out=h._value(nodes,float(constants[name]),label+f" = {name}")
   elif kind=="lit":out=h._value(nodes,float(spec["value"]),label)
   elif kind=="sample":
    key=(str(spec.get("resource") or ""),str(spec.get("channel") or ""));out=samples.get(key)
    if out is None:raise BlenderScalarDagError(f"{label}: no exact sample socket for {key!r}")
   elif kind=="add" and len(args)==2:out=h._binary(nodes,links,"ADD",args[0],args[1],label)
   elif kind=="mul" and len(args)==2:out=h._binary(nodes,links,"MULTIPLY",args[0],args[1],label)
   elif kind=="div" and len(args)==2:out=h._binary(nodes,links,"DIVIDE",args[0],args[1],label)
   elif kind=="min" and len(args)==2:out=h._binary(nodes,links,"MINIMUM",args[0],args[1],label)
   elif kind=="max" and len(args)==2:out=h._binary(nodes,links,"MAXIMUM",args[0],args[1],label)
   elif kind=="neg" and len(args)==1:out=h._neg(nodes,links,args[0],label)
   elif kind in ("sat","saturate") and len(args)==1:out=h._sat(nodes,links,args[0],label)
   elif kind=="abs" and len(args)==1:out=h._unary(nodes,links,"ABSOLUTE",args[0],label)
   elif kind=="exp" and len(args)==1:out=h._exp2(nodes,links,args[0],label)
   elif kind=="log" and len(args)==1:out=h._log2(nodes,links,args[0],label)
   elif kind=="rcp" and len(args)==1:out=h._rcp(nodes,links,args[0],label)
   elif kind=="sqrt" and len(args)==1:out=h._unary(nodes,links,"SQRT",args[0],label)
   elif kind=="rsq" and len(args)==1:out=h._unary(nodes,links,"INVERSE_SQRT",args[0],label)
   elif kind=="frc" and len(args)==1:out=h._unary(nodes,links,"FRACT",args[0],label)
   elif kind=="lt" and len(args)==2:out=h._binary(nodes,links,"LESS_THAN",args[0],args[1],label)
   elif kind=="ge" and len(args)==2:out=h._ge_finite(nodes,links,args[0],args[1],label)
   elif kind=="eq" and len(args)==2:out=h._eq_finite(nodes,links,args[0],args[1],label)
   elif kind=="ne" and len(args)==2:out=h._ne_finite(nodes,links,args[0],args[1],label)
   elif kind=="select" and len(args)==3:
    parents=[int(c) for c in spec.get("args",[])];condition_kind=str(specs[parents[0]].get("kind") or "")
    if condition_kind not in ("lt","ge","eq","ne"):raise BlenderScalarDagError(f"{label}: select condition {condition_kind!r} is not proven boolean")
    out=h._select_boolean(nodes,links,args[0],args[1],args[2],label)
   else:raise BlenderScalarDagError(f"{label}: unsupported node kind/arity {kind!r}/{len(args)}")
  except BlenderScalarDagError:raise
  except Exception as exc:raise BlenderScalarDagError(f"{label}: Blender node construction failed: {exc}") from exc
  values.append(out)
 return values[int(dag["root"])]

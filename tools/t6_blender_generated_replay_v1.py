#!/usr/bin/env python3
"""Compile a v51 generated final-output replay material into Blender.

Consumes `t6-generated-final-output-replay-contract-v1` directly. The contract
already separates exact static retail state from dynamic engine inputs; this
adapter preserves that boundary:

- retailMaterialConstant -> exact retained scalar value;
- t6CodeConstantDynamic -> caller-supplied exact dynamic constant callback;
- shader-native/non-cbuffer symbol -> caller-supplied exact symbol callback;
- retailMaterialTexture -> caller-supplied exact material-texture sampler;
- t6CodeSamplerDynamic -> caller-supplied exact engine sampler callback.

Materials with replay blockers are rejected. Dynamic inputs are never replaced
with defaults. The exact program DAG is lowered by the generated retail-output
backend and transported through Emission without a Principled/PBR fallback.
"""
from __future__ import annotations

import math
from typing import Any, Callable

import t6_blender_generated_retail_output_v1 as output_backend

FORMAT = "t6-blender-generated-replay-v1"
REPLAY_FORMAT = "t6-generated-final-output-replay-contract-v1"
BlenderGeneratedReplayError = output_backend.BlenderGeneratedRetailOutputError


def _unique(rows: list[dict], key: str, value: str, label: str) -> dict:
    matches = [row for row in rows if str(row.get(key) or "") == value]
    if len(matches) != 1:
        raise BlenderGeneratedReplayError(
            f"{label}: expected exactly one {key}={value!r}, found {len(matches)}"
        )
    return matches[0]


def _static_scalar(binding: dict) -> float:
    constant = binding.get("materialConstant")
    if not isinstance(constant, dict):
        raise BlenderGeneratedReplayError(
            f"{binding.get('symbol')}: retailMaterialConstant lacks materialConstant record"
        )
    if "scalarValue" not in constant:
        raise BlenderGeneratedReplayError(
            f"{binding.get('symbol')}: materialConstant lacks exact scalarValue"
        )
    value = float(constant["scalarValue"])
    if not math.isfinite(value):
        raise BlenderGeneratedReplayError(
            f"{binding.get('symbol')}: non-finite exact scalarValue {value!r}"
        )
    return value


def compile_material(
    material,
    replay_doc: dict,
    material_name: str,
    *,
    external_symbol_resolver: Callable[[str], Any],
    dynamic_constant_resolver: Callable[[dict], Any],
    material_texture_resolver: Callable[[dict, dict, list[Any]], Any],
    dynamic_sampler_resolver: Callable[[dict, dict, list[Any]], Any],
) -> dict:
    if replay_doc.get("format") != REPLAY_FORMAT:
        raise BlenderGeneratedReplayError(
            f"unexpected replay contract {replay_doc.get('format')!r}"
        )
    owner = _unique(replay_doc.get("materials", []), "material", material_name, "replay material")
    if not bool(owner.get("programIdentityComplete")):
        raise BlenderGeneratedReplayError(f"{material_name!r}: program identity is incomplete")
    if not bool(owner.get("replayIdentityComplete")) or int(owner.get("blockerCount", -1)) != 0:
        raise BlenderGeneratedReplayError(
            f"{material_name!r}: replay identity is not complete; blockerCount={owner.get('blockerCount')!r}"
        )

    shader_sha = str(owner.get("pixelShaderSha256") or "")
    program = _unique(
        replay_doc.get("programs", []),
        "pixelShaderSha256",
        shader_sha,
        f"{material_name} replay program",
    )
    if str(owner.get("techniqueSet") or "") not in [str(x) for x in program.get("techniqueSets", [])]:
        raise BlenderGeneratedReplayError(
            f"{material_name!r}: TechniqueSet is absent from its exact replay program"
        )

    cbuffer_by_symbol = {}
    for binding in owner.get("cbufferInputs", []):
        symbol = str(binding.get("symbol") or "")
        if not symbol or symbol in cbuffer_by_symbol:
            raise BlenderGeneratedReplayError(f"{material_name!r}: invalid/duplicate cbuffer input {symbol!r}")
        cbuffer_by_symbol[symbol] = binding

    texture_by_resource = {}
    for binding in owner.get("textureInputs", []):
        resource = str(binding.get("resource") or "")
        if not resource or resource in texture_by_resource:
            raise BlenderGeneratedReplayError(f"{material_name!r}: invalid/duplicate texture input {resource!r}")
        texture_by_resource[resource] = binding

    external_symbols = set(str(x) for x in program.get("externalNonCbufferSymbols", []))
    dynamic_constant_calls = 0
    external_symbol_calls = 0
    static_constant_calls = 0
    material_texture_calls = 0
    dynamic_sampler_calls = 0

    def symbol_resolver(name: str):
        nonlocal dynamic_constant_calls, external_symbol_calls, static_constant_calls
        binding = cbuffer_by_symbol.get(name)
        if binding is not None:
            kind = str(binding.get("bindingKind") or "")
            if kind == "retailMaterialConstant":
                if not bool(binding.get("staticValueResolved")):
                    raise BlenderGeneratedReplayError(f"{material_name}/{name}: static value is not resolved")
                static_constant_calls += 1
                return _static_scalar(binding)
            if kind == "t6CodeConstantDynamic":
                identity = binding.get("dynamicIdentity")
                if not isinstance(identity, dict):
                    raise BlenderGeneratedReplayError(f"{material_name}/{name}: dynamic code constant lacks identity")
                dynamic_constant_calls += 1
                return dynamic_constant_resolver(binding)
            raise BlenderGeneratedReplayError(
                f"{material_name}/{name}: unsupported replay cbuffer bindingKind {kind!r}"
            )
        if name not in external_symbols:
            raise BlenderGeneratedReplayError(
                f"{material_name}: symbolic DAG requested undeclared external symbol {name!r}"
            )
        external_symbol_calls += 1
        return external_symbol_resolver(name)

    def texture_resolver(node: dict, args: list[Any]):
        nonlocal material_texture_calls, dynamic_sampler_calls
        resource = str(node.get("resource") or "")
        binding = texture_by_resource.get(resource)
        if binding is None:
            raise BlenderGeneratedReplayError(
                f"{material_name}: textureSample node {node.get('id')} requested unbound resource {resource!r}"
            )
        node_id = int(node.get("id", -1))
        if node_id not in [int(x) for x in binding.get("sampleNodeIds", [])]:
            raise BlenderGeneratedReplayError(
                f"{material_name}/{resource}: sample node {node_id} absent from replay binding"
            )
        opcode = str(node.get("opcode") or "")
        if opcode not in [str(x) for x in binding.get("opcodes", [])]:
            raise BlenderGeneratedReplayError(
                f"{material_name}/{resource}: opcode {opcode!r} absent from replay binding"
            )
        channel = str(node.get("channel") or "")
        if channel not in [str(x) for x in binding.get("channels", [])]:
            raise BlenderGeneratedReplayError(
                f"{material_name}/{resource}: channel {channel!r} absent from replay binding"
            )
        kind = str(binding.get("bindingKind") or "")
        if kind == "retailMaterialTexture":
            if not bool(binding.get("runtimeResourceResolved")) or not isinstance(binding.get("resolvedTexture"), dict):
                raise BlenderGeneratedReplayError(f"{material_name}/{resource}: retail texture is not resolved")
            material_texture_calls += 1
            return material_texture_resolver(binding, node, args)
        if kind == "t6CodeSamplerDynamic":
            if not isinstance(binding.get("dynamicIdentity"), dict):
                raise BlenderGeneratedReplayError(f"{material_name}/{resource}: dynamic sampler lacks identity")
            dynamic_sampler_calls += 1
            return dynamic_sampler_resolver(binding, node, args)
        raise BlenderGeneratedReplayError(
            f"{material_name}/{resource}: unsupported replay texture bindingKind {kind!r}"
        )

    shader = {
        "sha256": shader_sha,
        "techniqueSets": list(program.get("techniqueSets", [])),
        "nodes": list(program.get("nodes", [])),
        "outputs": list(program.get("outputs", [])),
    }
    compiled = output_backend.compile_material_output(
        material,
        shader,
        symbol_resolver=symbol_resolver,
        texture_resolver=texture_resolver,
    )
    material["t6_replay_contract_backend"] = FORMAT
    material["t6_replay_material"] = material_name
    material["t6_replay_identity_complete"] = True
    material["t6_runtime_dynamic_inputs_required"] = bool(owner.get("runtimeDynamicInputsStillRequired"))

    return {
        "format": FORMAT,
        "material": material_name,
        "techniqueSet": owner.get("techniqueSet"),
        "pixelShaderSha256": shader_sha,
        "replayIdentityComplete": True,
        "runtimeDynamicInputsStillRequired": bool(owner.get("runtimeDynamicInputsStillRequired")),
        "leafResolverCalls": {
            "retailMaterialConstant": static_constant_calls,
            "t6CodeConstantDynamic": dynamic_constant_calls,
            "externalNonCbufferSymbol": external_symbol_calls,
            "retailMaterialTexture": material_texture_calls,
            "t6CodeSamplerDynamic": dynamic_sampler_calls,
        },
        "output": compiled,
        "proofBoundary": (
            "Direct v51 replay-contract dispatch only. Static material state is consumed only when marked resolved; dynamic engine constants/samplers and shader-native symbols require explicit callbacks. No default/fallback resource or value is introduced."
        ),
    }

#!/usr/bin/env python3
"""Resolve T6 Material texture dependencies through one asset-class-neutral path.

GfxWorld and XModel materials are intentionally indistinguishable to this module.
It consumes retained Material texture-table rows, resolves each referenced GfxImage
identity, and delegates streamed payload ownership to `t6_image_resolver_v1`.

The module does **not** guess image identities from filenames.  An inline/named image
must retain its GfxImage hash and streamed-part hash.  A packed pointer must be closed
by a separately proven pointer->GfxImage identity map.  Runtime/code images are
preserved explicitly rather than looked up in IPAKs.

This layer resolves dependencies; it does not decide how a Treyarch semantic should
be approximated into generic glTF PBR.  That decision belongs to the renderer adapter.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from t6_image_resolver_v1 import (
    T6ImageIdentity,
    T6ImageResolverError,
    T6StreamedImageResolver,
    serializable_resolution,
)


class T6MaterialImageResolverError(RuntimeError):
    pass


PointerKey = tuple[int, int]


@dataclass(frozen=True)
class T6ResolvedImageIdentity:
    identity: T6ImageIdentity
    provenance: str
    pointer: PointerKey | None = None


def _first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None:
            return value
    return None


def _pointer_key(image: dict[str, Any], texture: dict[str, Any]) -> PointerKey | None:
    pointer = image.get("pointer") or texture.get("imagePointer") or {}
    if not isinstance(pointer, dict) or pointer.get("kind") != "offset":
        return None
    block = pointer.get("block")
    offset = pointer.get("offset")
    if block is None or offset is None:
        return None
    return int(block), int(offset)


def _streamed_hash(image: dict[str, Any]) -> int | None:
    value = _first(
        image,
        "streamedPart0Hash29",
        "streamedDataHash29",
        "dataHash29",
    )
    if value is not None:
        return int(value)
    parts = image.get("streamedParts")
    if isinstance(parts, list) and parts:
        part = parts[0] or {}
        if isinstance(part, dict):
            value = _first(part, "dataHash29", "hash29", "hash")
            if value is not None:
                return int(value) & 0x1FFFFFFF
    return None


def _name_hash(image: dict[str, Any]) -> int | None:
    value = _first(image, "nameHash", "gfxImageHash", "hash")
    return None if value is None else int(value)


def _dimensions(image: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    return (
        None if image.get("width") is None else int(image["width"]),
        None if image.get("height") is None else int(image["height"]),
        None if image.get("depth") is None else int(image["depth"]),
    )


def _identity_from_retained_image(
    image: dict[str, Any],
    *,
    provenance: str,
    pointer: PointerKey | None = None,
) -> T6ResolvedImageIdentity:
    name = str(image.get("name") or image.get("image") or "")
    if not name:
        raise T6MaterialImageResolverError(f"{provenance}: GfxImage identity has no retained name")
    nh = _name_hash(image)
    if nh is None:
        raise T6MaterialImageResolverError(
            f"{provenance}: {name}: missing retained GfxImage hash; filename hashing is not proof"
        )
    dh = _streamed_hash(image)
    if dh is None:
        raise T6MaterialImageResolverError(
            f"{provenance}: {name}: missing retained streamed-part hash"
        )
    width, height, depth = _dimensions(image)
    return T6ResolvedImageIdentity(
        T6ImageIdentity(
            name=name,
            name_hash=nh,
            data_hash29=dh,
            width=width,
            height=height,
            depth=depth,
        ),
        provenance=provenance,
        pointer=pointer,
    )


def normalize_packed_identity_map(rows: Iterable[dict[str, Any]]) -> dict[PointerKey, dict[str, Any]]:
    """Normalize a retained pointer->GfxImage proof table and reject conflicts."""
    out: dict[PointerKey, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        pointer = row.get("pointer") or {}
        if isinstance(pointer, dict):
            block, offset = pointer.get("block"), pointer.get("offset")
        else:
            block, offset = row.get("block"), row.get("offset")
        if block is None or offset is None:
            raise T6MaterialImageResolverError(f"packed identity row {index}: missing block/offset")
        key = (int(block), int(offset))
        image = row.get("imageIdentity") or row.get("image") or row
        if not isinstance(image, dict):
            raise T6MaterialImageResolverError(f"packed identity row {index}: image identity is not dict")
        prior = out.get(key)
        if prior is not None and prior != image:
            raise T6MaterialImageResolverError(f"packed pointer {key}: conflicting GfxImage identities")
        out[key] = image
    return out


def resolve_texture_identity(
    texture: dict[str, Any],
    *,
    material_name: str,
    texture_index: int,
    packed_identities: dict[PointerKey, dict[str, Any]] | None = None,
    runtime_images: set[str] | None = None,
) -> dict[str, Any]:
    image = texture.get("image") or {}
    if not isinstance(image, dict):
        raise T6MaterialImageResolverError(
            f"{material_name} texture {texture_index}: image record is not dict"
        )
    context = f"{material_name} texture {texture_index}"
    runtime_images = runtime_images or set()

    if image.get("inline") and image.get("name"):
        name = str(image["name"])
        if name in runtime_images or image.get("streaming") is False or image.get("streamedPartCount") == 0:
            nh = _name_hash(image)
            return {
                "state": "non-streamed",
                "name": name,
                "nameHash": nh,
                "dimensions": list(_dimensions(image)),
                "identityProvenance": "inline-retained-gfximage",
                "runtimeCodeImage": name in runtime_images,
            }
        try:
            resolved = _identity_from_retained_image(image, provenance="inline-retained-gfximage")
        except T6MaterialImageResolverError as exc:
            return {
                "state": "identity-incomplete",
                "reason": str(exc),
                "name": name,
                "pointer": None,
            }
        return {
            "state": "streamed-identity",
            "identity": resolved,
            "identityProvenance": resolved.provenance,
        }

    key = _pointer_key(image, texture)
    if key is None:
        return {
            "state": "identity-unresolved",
            "reason": "texture has neither inline GfxImage identity nor retained offset pointer",
        }
    if packed_identities is None or key not in packed_identities:
        return {
            "state": "packed-pointer-unresolved",
            "pointer": list(key),
            "reason": "no separately proven pointer->GfxImage identity mapping",
        }
    retained = packed_identities[key]
    try:
        resolved = _identity_from_retained_image(
            retained,
            provenance="retained-packed-pointer-proof",
            pointer=key,
        )
    except T6MaterialImageResolverError as exc:
        return {
            "state": "identity-incomplete",
            "pointer": list(key),
            "reason": str(exc),
        }
    return {
        "state": "streamed-identity",
        "identity": resolved,
        "identityProvenance": resolved.provenance,
        "pointer": list(key),
    }


def _semantic(texture: dict[str, Any]) -> Any:
    value = texture.get("semantic")
    if value is not None:
        return value
    return texture.get("name")


def resolve_materials(
    materials: Iterable[dict[str, Any]],
    *,
    image_resolver: T6StreamedImageResolver,
    packed_identities: dict[PointerKey, dict[str, Any]] | None = None,
    runtime_images: set[str] | None = None,
    payload_probe=None,
    include_payloads: bool = False,
) -> dict[str, Any]:
    """Resolve every retained texture-table dependency for any T6 Material set."""
    material_rows = []
    image_cache: dict[tuple[str, int, int], dict[str, Any]] = {}
    stats = {
        "materialCount": 0,
        "textureDependencyCount": 0,
        "streamedIdentityCount": 0,
        "streamedResolvedDependencyCount": 0,
        "streamedUnresolvedDependencyCount": 0,
        "nonStreamedDependencyCount": 0,
        "packedPointerUnresolvedDependencyCount": 0,
        "identityIncompleteDependencyCount": 0,
        "otherUnresolvedDependencyCount": 0,
        "uniqueStreamedIdentityCount": 0,
        "uniqueResolvedStreamedIdentityCount": 0,
    }

    for material_index, material in enumerate(materials):
        stats["materialCount"] += 1
        name = str(material.get("name") or material.get("material") or "")
        if not name:
            raise T6MaterialImageResolverError(f"material {material_index}: missing exact identity")
        dependencies = []
        textures = material.get("textures", [])
        if not isinstance(textures, list):
            raise T6MaterialImageResolverError(f"{name}: textures is not list")
        for texture_index, texture in enumerate(textures):
            stats["textureDependencyCount"] += 1
            if not isinstance(texture, dict):
                raise T6MaterialImageResolverError(f"{name} texture {texture_index}: not dict")
            identity_state = resolve_texture_identity(
                texture,
                material_name=name,
                texture_index=texture_index,
                packed_identities=packed_identities,
                runtime_images=runtime_images,
            )
            row = {
                "textureIndex": texture_index,
                "semantic": _semantic(texture),
                "samplerState": texture.get("samplerState"),
            }
            state = identity_state["state"]
            if state == "streamed-identity":
                stats["streamedIdentityCount"] += 1
                ri: T6ResolvedImageIdentity = identity_state["identity"]
                identity = ri.identity
                key = (identity.name, identity.name_hash, identity.data_hash29)
                if key not in image_cache:
                    try:
                        result = image_resolver.resolve(identity, payload_probe=payload_probe)
                    except T6ImageResolverError as exc:
                        raise T6MaterialImageResolverError(
                            f"{name} texture {texture_index}: {exc}"
                        ) from exc
                    image_cache[key] = result
                result = image_cache[key]
                proof = serializable_resolution(result)
                if result.get("state") == "resolved":
                    stats["streamedResolvedDependencyCount"] += 1
                else:
                    stats["streamedUnresolvedDependencyCount"] += 1
                row.update({
                    "state": result.get("state"),
                    "image": identity.name,
                    "nameHash": identity.name_hash,
                    "dataHash29": identity.data_hash29,
                    "dimensions": identity.dimensions(),
                    "identityProvenance": ri.provenance,
                    "pointer": None if ri.pointer is None else list(ri.pointer),
                    "resolution": proof,
                })
                if include_payloads and result.get("state") == "resolved":
                    row["payload"] = result["payload"]
            elif state == "non-streamed":
                stats["nonStreamedDependencyCount"] += 1
                row.update(identity_state)
            elif state == "packed-pointer-unresolved":
                stats["packedPointerUnresolvedDependencyCount"] += 1
                row.update(identity_state)
            elif state == "identity-incomplete":
                stats["identityIncompleteDependencyCount"] += 1
                row.update(identity_state)
            else:
                stats["otherUnresolvedDependencyCount"] += 1
                row.update(identity_state)
            dependencies.append(row)
        material_rows.append({
            "materialIndex": material_index,
            "material": name,
            "dependencies": dependencies,
        })

    stats["uniqueStreamedIdentityCount"] = len(image_cache)
    stats["uniqueResolvedStreamedIdentityCount"] = sum(
        result.get("state") == "resolved" for result in image_cache.values()
    )
    return {
        "format": "t6-material-image-resolution-v1",
        "stats": stats,
        "materials": material_rows,
        "policy": {
            "assetClassNeutral": True,
            "filenameHashInference": False,
            "sameNameWrongDataFallback": False,
            "packedPointerRequiresSeparateProof": True,
            "streamedPayloadResolver": "t6_image_resolver_v1",
            "ipakCore": "t6_ipak_core",
            "semanticPolicy": (
                "all Material texture-table dependencies are preserved; this stage does not "
                "force non-PBR Treyarch semantics into generic glTF slots"
            ),
        },
    }

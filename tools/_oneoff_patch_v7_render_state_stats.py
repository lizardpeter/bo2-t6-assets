#!/usr/bin/env python3
from pathlib import Path

path = Path("tools/t6_oat_material_manifest_v7.py")
text = path.read_text()
needle = "    _attach_render_state(doc, material_root)\n    doc = _promote(doc)\n"
if text.count(needle) != 1:
    raise SystemExit(
        f"expected exactly one v7 render-state attachment call site, found {text.count(needle)}"
    )

replacement = '''    _attach_render_state(doc, material_root)

    # v6's historical helper calls its all-layer total
    # renderStateComponentLayerCount, even though ordinary records also carry a
    # one-layer self description. v7 separates those accounting domains without
    # changing any attached render-state data.
    render_state_layer_count = 0
    render_state_ordinary_layer_count = 0
    render_state_component_layer_count = 0
    render_state_recovered_component_layer_count = 0
    for material in doc["materials"]:
        is_compound = bool(material.get("compoundIdentityDecoded"))
        for layer in material.get("layers", []):
            if "renderState" not in layer:
                continue
            render_state_layer_count += 1
            if is_compound:
                if layer.get("standaloneOatMaterialAvailable") is False:
                    render_state_recovered_component_layer_count += 1
                else:
                    render_state_component_layer_count += 1
            else:
                render_state_ordinary_layer_count += 1

    stats = doc["stats"]
    inherited_all_layer_count = int(stats.get("renderStateComponentLayerCount", -1))
    if inherited_all_layer_count != render_state_layer_count:
        raise OatMaterialManifestError(
            "v6 render-state helper all-layer count disagrees with v7 record census: "
            f"helper={inherited_all_layer_count} census={render_state_layer_count}"
        )
    if int(stats.get("renderStateMaterialCount", -1)) != len(doc["materials"]):
        raise OatMaterialManifestError(
            "not every resolved v7 Material received exact top-level render state"
        )
    if render_state_ordinary_layer_count != int(stats["ordinaryMaterialCount"]):
        raise OatMaterialManifestError(
            "ordinary self-layer render-state census disagrees with ordinary Material count"
        )
    if render_state_component_layer_count != int(stats["componentStandaloneLayerOccurrenceCount"]):
        raise OatMaterialManifestError(
            "standalone compound-component render-state census disagrees with component occurrence count"
        )
    if render_state_recovered_component_layer_count != 0:
        raise OatMaterialManifestError(
            "a v3-recovered standalone-missing component unexpectedly received fabricated render state"
        )

    stats["renderStateLayerCount"] = render_state_layer_count
    stats["renderStateOrdinaryLayerCount"] = render_state_ordinary_layer_count
    stats["renderStateComponentLayerCount"] = render_state_component_layer_count
    stats["renderStateRecoveredComponentLayerCount"] = render_state_recovered_component_layer_count

    doc = _promote(doc)
'''

path.write_text(text.replace(needle, replacement))
print("patched", path)

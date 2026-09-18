# T6 current-client zone-xref data-flow result — 2026-09-18

## Authority boundary

This checkpoint records **comparative current-client discovery only**. It does not establish historical retail `t6mp.exe` behavior and does not select any of the 58 unresolved retail Technique winners. String proximity, nearby calls, masks, ordering, or similarity to the dedicated-server implementation are not retail proof.

## Exact client / CI identity

- Current Plutonium revision: `5346`
- `games/t6mp.exe` bytes: `13,263,640`
- SHA-1: `f101e28c3a18ce1ffe37a40d23cd04f7f57925d3`
- SHA-256: `770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf`
- Workflow: `T6 current client zone xref dataflow probe v1` (`361254456`)
- Run: `35332134272`
- Job: `105558636245`
- Artifact: `10542240096` (`T6_CURRENT_CLIENT_ZONE_XREF_DATAFLOW_PROBE_V1`)
- Artifact ZIP SHA-256: `87f9f681cf4b67f34e6021bac1f91ad09d21d14b4cf88aaa85b056fa81b736b4`
- Proof JSON SHA-256: `d3b5d7ac74b8963aad325431337bc20d70b9115dea71367704e605fa45f15307`

The workflow completed successfully and deleted the executable before artifact upload.

## Exact recovered discovery result

The probe recovered **13 exact executable string-reference anchors** across `common`, `patch`, `_mp`, and `mp_nuketown_2020`, and **137 nearby direct CALLs**.

Only **7 of the 137 call sites** led to a first-512-byte target window containing the stored-zone mask `0x3fffffff`. All seven are associated with `_mp` anchors; none of the sampled targets contained `0x17ffffff`.

The mask-bearing targets are:

- `0x005225f0` — reached from `_mp` xrefs at `0x0067b4d2` and `0x009735d7`; target window contains `and eax,0x3fffffff` at `0x0052269b` and `0x005226e0`.
- `0x006ad580` — reached from `_mp` xref `0x009735d7`; target window contains `and eax,0x3fffffff` at `0x006ad5aa`.
- `0x005fb2f0` — reached three times near `_mp` xref `0x009735d7`; target window contains `and eax,0x3fffffff` at `0x005fb326`.
- `0x00682340` — reached near `_mp` xref `0x009735d7`; target window contains `and edx,0x3fffffff` at `0x0068238b`.

These are **four unique byte-supported candidate target regions**, not named DB functions.

Separately, four direct-call targets recur near multiple distinct string classes:

- `0x00424f00` occurs near `common`, `patch`, and `_mp` anchors (38 sampled calls).
- `0x004c0830` occurs near `common`, `patch`, and `_mp` anchors (13 sampled calls).
- `0x00593820` occurs near `common` and `_mp` anchors (4 sampled calls).
- `0x0044dfc0` occurs near `common` and `_mp` anchors (2 sampled calls).

The first two are therefore useful shared-call-graph anchors, but recurrence alone does not establish zone semantics.

## What this changes

The previous exact-byte and semantic-priority probes both returned zero server-priority-ladder matches. This data-flow run now supplies a much narrower current-client search frontier: four mask-bearing callees plus the shared multi-string call targets above. Continuing broad scans of every `0x3fffffff` occurrence is no longer justified.

## Exact next experiment

Recover complete function boundaries and inbound/outbound direct-call edges for `0x005225f0`, `0x006ad580`, `0x005fb2f0`, and `0x00682340`, plus the shared anchors `0x00424f00` and `0x004c0830`. For each candidate, trace the value being masked backward to its memory load and forward through comparisons/table mutation. Specifically test whether a byte-supported path reaches duplicate-XAsset hash/link mutation or zone-allocation metadata. Do not name a function from constants or proximity.

If this current-client graph produces a coherent zone-flags → masked stored-zone value → duplicate-XAsset mutation path, use it only to guide historical-retail recovery/runtime instrumentation. The 58 historical-retail Technique conflicts remain fail-closed until genuine retail-client/runtime ownership evidence exists.

## Existing closure boundary preserved

The production texture denominator remains the exact identity-deduplicated 450 GfxImages with 75/450 exact DDS coverage. The unresolved shader-side ownership set remains 58 divergent child Techniques across nine TechniqueSets affecting 269 ordinary Materials.

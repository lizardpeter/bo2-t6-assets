# T6 current-client precedence hard gate — 2026-09-18

## Authority

This checkpoint is exact only for SHA-classified current Plutonium client revision 5346 (`t6mp.exe` SHA-256 `770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf`) plus the independently pinned retail FastFile/OAT five-root census. It does not promote current-client behavior to historical-retail authority.

## Closed current-client chain

The current client now independently supplies the same classifier-to-scalar mapping needed to make the remaining precedence question narrow rather than speculative. `proof/current_client/T6_CURRENT_CLIENT_ZONE_CLASSIFIER_ORDINAL_MAP_V1.json` byte-evaluates the exact routine at `0x00493440` and proves, among other constructed rows:

- `patch_mp`: classifier `0x00000002` -> scalar/ordinal `65` (`0x41`), terminal `0x00493497`;
- `code_post_gfx_mp`: classifier `0x00000008` -> `52` (`0x34`);
- `common_mp`: classifier `0x00000080` -> `54` (`0x36`);
- `ui_mp`: classifier `0x02000000` -> `61`;
- `patch_ui_mp`: classifier `0x08000000` -> `62`;
- `ffotd_mp`: classifier `0x20000000` -> `66`.

The current-client runtime path separately proves that live zone-associated state is masked with `0x3fffffff` and passed to `0x00493440`; the result is compared in the runtime path. This is no longer merely server correspondence or a signature hypothesis.

The dynamic map-family work also recovers current-client `0x8000` row construction reaching the same 12-byte row sink. This establishes the relevant map classifier family in the same client authority class, but does not by itself establish the historical retail Nuketown duplicate winner.

## Five-root conflict consequence — still fail closed

The exact five-root native census remains:

- 58 divergent parent-owned child Technique conflicts;
- 57 map-root vs `patch_mp`;
- 1 `common_mp` vs `patch_mp`;
- 269 ordinary Materials affected across nine TechniqueSets;
- zero missing parent owners;
- zero historical-retail winners selected.

Current-client `patch_mp=65` and `common_mp=54` are now independently byte-proven rather than imported from the server. However, a winner still must **not** be selected until the current-client duplicate-XAsset insertion/replacement path is tied to this scalar comparison with directionality proven (which side survives when the compared scalar is greater/equal/lower), and that evidence is then properly bounded against historical retail.

## Exact next experiment

Stop spending time on classifier/priority discovery: that mapping is closed in the current client. Trace from the runtime comparison around the persisted `T6_CURRENT_CLIENT_RUNTIME_ZONE_PRIORITY_PATH_V1.json` evidence into the branch that mutates or preserves the XAsset hash/table entry. Recover:

1. both compared asset/zone operands;
2. the exact call to `0x00493440` for each side or the equivalent cached scalar source;
3. comparison direction and branch predicate;
4. the concrete write/no-write that replaces, chains, or preserves the existing XAsset;
5. zone index/record provenance for both old and incoming asset.

Only that byte-closed mutation chain can convert current-client scalar ordering into current-client duplicate ownership. Historical-retail authority remains a separate promotion gate.

## Preserved production closure

Production GfxImage denominator remains 450 identity-deduplicated images with 75/450 exact DDS coverage. The shader blocker remains 58 divergent child Techniques across nine TechniqueSets affecting 269 ordinary Materials.

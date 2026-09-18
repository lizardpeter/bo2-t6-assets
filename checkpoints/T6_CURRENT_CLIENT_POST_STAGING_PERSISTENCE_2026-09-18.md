# T6 current-client post-staging persistence — 2026-09-18

## Authority boundary

Exact for SHA-classified Plutonium revision 5346 (`t6mp.exe` SHA-256 `770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf`) only. No historical-retail identity, source symbol, precedence rule, or Technique winner is promoted.

## CI / proof identity

The first callee-CFG run (`35353424947`, job `105626833771`) failed exactly in the reusable inbound scanner because Capstone SKIPDATA pseudo-instructions reject `insn.group()` with `CS_ERR_SKIPDATA`. The specialized scanner was repaired in commit `099f7822c25a08925af060fe99cfa7fb1b658b70` to exclude SKIPDATA pseudo-instructions from call classification.

The repaired workflow succeeded:

- workflow: `T6 current client zone staging callee CFG probe v1` (`361414996`)
- run: `35353513362`
- job: `105627136231`
- persisted proof: `proof/current_client/T6_CURRENT_CLIENT_ZONE_STAGING_CALLEE_CFG_PROBE_V1.json`
- proof SHA-256: `c4862e3767e00aa7a14dedadd7b25ae167f7eb6ea5a499fcc59bacdfcc520c63`
- proof commit: `d0662f7` (full SHA recoverable from main history)
- artifact: `10550238523`
- artifact ZIP SHA-256: `49f11e3df72c6770c3b157e70eedc73972d0d175e62ba39d1f31d827e1accd47`

## Exact post-staging consumer behavior

`0x007fddd0` has exactly one decoded inbound direct CALL in the current client: the already-proved staging tail call at `0x00418215`. Its bounded CFG closes 47 instructions / 10 basic blocks, four direct calls, one return, and one explicit tail jump outside the local span.

The call-site argument flow and callee prologue independently close the `(stagingBase,count)` interpretation:

- caller `0x0041820f`: `lea edx,[esp+0x6c]` -> staging base;
- caller `0x00418213`: pushes recovered count in `edi`;
- caller `0x00418214`: pushes staging base in `edx`;
- caller `0x00418215`: calls `0x007fddd0`;
- callee after two saved-register pushes loads `ebp,[esp+0x10]`, which is the second caller argument/count;
- after two more saved-register pushes it loads `edi,[esp+0x14]`, which is the first caller argument/staging base.

The consumer then performs an exact counted 12-byte input loop:

- `0x007fde00`: reads staged row `+0` (`mov eax,[edi]`);
- if non-null, `0x007fde06..0x007fde0d` passes constant `0x40`, the staged `+0` pointer, and destination `esi-0x40` to direct callee `0x00424f00`;
- `0x007fde12`: reads staged row `+4` (`mov ecx,[edi+4]`);
- `0x007fde18`: writes that exact `+4` value to `[esi]`;
- `0x007fde1b`: advances `esi` by `0x44` bytes;
- `0x007fde1e`: advances staged-row pointer `edi` by `0x0c` bytes;
- `0x007fde21`: decrements count in `ebp`;
- `0x007fde22`: loops to `0x007fde00`.

The persistent destination begins with `esi = 0x012eeed8`. Because the string-copy destination passed to `0x00424f00` is `esi-0x40`, each persistent element is exactly 68 (`0x44`) bytes consisting, at minimum, of a 64-byte region beginning at `esi-0x40` followed by the staged `+4` dword at `esi`. The loop advances the destination by exactly 68 bytes per staged row.

Critically, the decoded loop **does not read staged row `+8`**. Thus the current client now independently proves:

`input +4 -> local staged +4 -> persistent 68-byte record trailing dword`

while input `+8` is copied into local staging earlier but is not propagated by this post-staging persistence loop.

This is materially stronger than the previous classifier-only checkpoint. The `+4` field is now a byte-proven classifier/flags-like value that survives into persistent current-client zone metadata. It remains deliberately unnamed at source level; `allocFlags` is not imported from the dedicated-server symbols.

## Downstream exact edges

After the loop, if at least one non-null staged name was processed, the function stores the processed count (`ebx`) to absolute global `0x012c6f1c`, calls `0x005c7d20`, calls `0x00458cc0`, stores the same count to `0x014deacc`, then tail-jumps to `0x005b8bf0`. These are exact current-client edges but their source-level roles remain unresolved.

The earlier shared zone-string anchor `0x00424f00` is now independently reached as the three-argument helper used to populate each 64-byte persistent name region. Its earlier recurrence near `common`, `patch`, and `_mp` therefore has a concrete current-client data-flow relationship to persistent staged zone names, but it is still not assigned a source symbol from recurrence alone.

## Exact next hard gate

Trace the persistent record base and trailing classifier dword through `0x005c7d20`, `0x00458cc0`, and tail target `0x005b8bf0`. Search for reads of the exact persistent array geometry (`0x012eee98` name-base / `0x012eeed8` first trailing dword / `0x44` stride) and determine which downstream path writes per-zone runtime state or reaches duplicate-XAsset linking. Keep `+8` explicitly separate: current-client evidence now shows it is not propagated through this persistence loop.

## Existing production closure preserved

Production textures remain 450 identity-deduplicated GfxImages with 75/450 exact DDS coverage. Historical-retail shader ownership remains fail-closed: 58 divergent child Techniques across nine TechniqueSets affecting 269 ordinary Materials.

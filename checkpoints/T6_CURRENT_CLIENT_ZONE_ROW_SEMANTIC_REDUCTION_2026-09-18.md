# T6 current-client zone-row semantic reduction — 2026-09-18

## Authority boundary

This checkpoint is exact for the SHA-classified current Plutonium client revision 5346 only (`t6mp.exe` SHA-256 `770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf`). It does **not** establish historical-retail identity or select any Technique winner.

## Newly closed current-client facts

The shared sink at `0x004174b0` consumes the already-proved 12-byte input rows as follows:

- input `+0` is consumed as a pointer to a NUL-terminated byte string;
- input `+4` is consumed as an integer/bitmask classifier;
- all 12 bytes are copied into a local 12-byte staging record;
- input `+8` is copied verbatim into staging and remains semantically unnamed at this checkpoint.

Exact decisive instructions in the persisted staging proof include:

- `0x00417f60`: reload current input-row pointer from `[esp+0x14]`;
- `0x00417f64`: copy row `+0..+7` with `movq xmm0,[eax]`;
- `0x00417f68`: read row `+4` into `esi`;
- `0x00417f6b`: read row `+8` into `eax`;
- `0x00417f7d`: write row `+0..+7` to local staging `[ebp]`;
- `0x00417f82`: write row `+8` to local staging `[ebp+8]`;
- `0x00417fa3`: test the copied `+4` value (`esi`) against `0x0204908a`;
- `0x004180b7`: reload input row `+4`;
- `0x004180ba`: compare `+4` to `0x00008000`;
- `0x004180c3`: compare `+4` to `0x00000080`;
- `0x004180ca`: compare `+4` to `0x00001000`;
- `0x004180d6`: compare `+4` to `0x00040000`.

The tail proof additionally closes the iteration stride rather than merely inferring it from the source-side row construction:

- `0x004181b5`: `add dword ptr [esp+0x14],0xc` advances the input-row pointer by exactly 12 bytes;
- `0x004181ba`: `dec dword ptr [esp+0x20]` decrements the remaining-row count;
- `0x004181be`: `jne 0x00417f60` loops to the next 12-byte row.

Therefore the current client independently establishes a counted 12-byte row consumer. The `+4` field is no longer merely an opaque dword: it is a byte-proven load-classifier/bitmask field in this client. This checkpoint deliberately does **not** rename it `allocFlags`; that source-level name still requires a closed current-client propagation path or genuine historical-retail symbol/runtime evidence.

## Cross-build comparison kept quarantined

The exact PC dedicated-server build independently proves source-level `XZoneInfo` layout `name@+0`, `allocFlags@+4`, `freeFlags@+8` and uses the same 12-byte stride. It also independently proves server call-site values `common_mp=0x80`, `patch_mp=2`, and built-in map `=0x8000`. The current client has separately produced exact 12-byte rows with overlapping values. This is strong comparative evidence but is **not** used here to import the server field names or precedence rule into the client.

## Next hard gate

Trace the local staging records beginning at `[esp+0x6c]` after the counted copy/classification loop. Recover every read of staged `+4` and `+8`, then follow the staged values into direct callees/queue records. The immediate target is an exact current-client path:

`input row +4/+8 -> local staged row +4/+8 -> persistent/queued record field -> downstream zone state`

Only after that path is byte-closed should source-level semantic naming be considered. In parallel, search the current-client downstream path for duplicate-XAsset mutation/zone-index ownership; do not infer it from the server implementation.

## Existing production closure preserved

The exact production GfxImage denominator remains 450 identity-deduplicated images with 75/450 exact DDS coverage. The historical-retail shader ownership set remains fail-closed: 58 divergent child Techniques across nine TechniqueSets affecting 269 ordinary Materials.

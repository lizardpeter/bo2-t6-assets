# Xbox 360 Profile Mapping — ForumDecorum238

Canonical specimen: `E0000255AEF799DA`  
Source: Digital Corpora `nps-2014-xbox1 / DRIVE2_TIME_FINAL.E01`  
Deleted FATX path: `/Content/E0000255AEF799DA/FFFE07D1/00010000/E0000255AEF799DA`

## Recovery

- Deleted FATX first cluster: `21751`; file size: `278528` bytes.
- Initial contiguous recovery: **20/56** STFS logical blocks matched the intact active hash table.
- Missing blocks were carved from the XTAF data area by their original 4 KiB SHA-1 values.
- Final reconstructed STFS integrity: **56/56 (100%)**.
- Fully reconstructed package SHA-256: `7803e496467d36701191f617c306bfda6a0f9b79cad7c213bb668a664a34b3df`.
- All 13 embedded files extract without short reads.

## Confirmed identity

- Gamertag: `ForumDecorum238`
- Online XUID: `000900000A90717C`
- Account `LiveEnabled` flag set.
- Service provider: `PROD`
- Subscription tier: Silver
- Domain: `xbox.com`
- Kerberos realm: `PASSPORT.NET`
- Authentication/credential bytes are intentionally not recorded.

## Mapping coverage

1. **FATX deletion/recovery** — deleted directory chain and first cluster confirmed.
2. **STFS/XContent** — header, certificate, licenses, volume descriptor, hash table and file chains mapped.
3. **STFS recovery provenance** — every reconstructed logical block linked to its exact SHA-1 and raw-disk source.
4. **Account** — HMAC/RC4 verified; field offsets and Live-account semantics mapped with secrets redacted.
5. **GPD/XDBF** — all six GPDs parsed entry-by-entry; achievements, title history, settings, images, strings and sync records mapped.
6. **PEC** — valid header verified; container is empty in this profile snapshot.
7. **Ancillary** — `liveid.bin` inventoried as opaque credential-adjacent data; `cache/ph.dat` partially mapped.
8. **FFFE07D1.fit** — XDBF structure and four composite-ID records mapped; record semantics remain unresolved.

## Confirmed title/profile content

- Dashboard: 3 title-history entries.
- `425307D5` — Fallout 3: 58 achievements, 1200 possible GS, 0 earned.
- `4D5307E6` — Halo 3: 79 achievements, 1750 possible GS, 0 earned.
- `58480880` — Internet Explorer.
- `584D07D1` — Avatar Editor.
- Dashboard setting `Gamercard Titles Played = 3` agrees with the three title-history entries.
- Gamer zone: Recreation.
- Region: United States.
- Gamer name: Sam.

## Durable artifacts in this branch

- `MAPPING.md` — human-readable authoritative map.
- `STATUS.md` — this progress checkpoint.
- Next machine-readable additions: XDBF entry map, profile/block provenance map, and reusable parser.

## Next targets

1. Identify the `FFFE07D1.fit` record type and composite-ID bit fields from dashboard/XAM code.
2. Reverse `cache/ph.dat` beyond the `phc3` header, timestamp, and title-ID record.
3. Decode non-secret substructures in Avatar Info, Party Address/Info, Jump-In List, and title-specific binary settings.
4. Emit graph-ready cross-links between semantic records, STFS logical blocks, and raw-disk carve offsets.

## Confidence tags

- `confirmed-by-hash`: bytes match the original STFS SHA-1 recorded in the intact active hash table.
- `confirmed-by-structure`: parsed from validated container/database metadata.
- `reference-derived`: field semantics corroborated by public Free60/Xenia/Velocity implementations.
- `unresolved`: structure preserved but semantic meaning not yet demonstrated.

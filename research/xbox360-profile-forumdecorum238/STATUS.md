# Xbox 360 Profile Mapping — ForumDecorum238

Canonical specimen: `E0000255AEF799DA`  
SHA-256: `173ac5db4d03038d881f850015662aedf92682b146ea3434ddd5b0e5ce42cb33`  
Source: Digital Corpora `nps-2014-xbox1 / DRIVE2_TIME_FINAL.E01`  
Deleted FATX path: `/Content/E0000255AEF799DA/FFFE07D1/00010000/E0000255AEF799DA`

## Current recovery status

- STFS root hash / active L0 hash table: **valid**.
- STFS file table (logical block 1): **hash-valid**.
- Data-block integrity at the naive contiguous FATX locations: **20/56 (35.7%)**.
- Logical STFS blocks **0–19** are intact at those locations; **20–55** are not.
- The intact STFS active hash table preserves the original SHA-1 for every logical block, so missing blocks can be recovered deterministically by SHA-1 carving from the disk image.
- The corruption boundary is consistent with the deleted outer FATX file having been fragmented after its initial allocation run, rather than the STFS metadata itself being damaged.

## Confirmed Account identity

- Gamertag: `ForumDecorum238`
- Online XUID: `000900000A90717C`
- `LiveEnabled`: set (`reservedFlags & 0x20000000`)
- Service provider: `PROD`
- Subscription tier: Silver/Free
- Online domain: `xbox.com`
- Kerberos realm: `PASSPORT.NET`
- Authentication/secret material is intentionally not committed.

## STFS container facts

- Magic: `CON `
- Content type: `0x00010000` (Profile)
- Title ID: `FFFE07D1` (Xbox 360 Dashboard)
- Profile ID: `E0000255AEF799DA`
- Header size: `0x971A`
- Header padded/data start: `0xA000`
- STFS type: read/write CON (redundant hash tables)
- Root active index: `1`
- Active L0 hash table: `0xB000`
- Active L0 SHA-1 / root hash: `81aa87394a1b941ce9dd56fd9d80307096684666`
- File table: logical block `1`, one 4 KiB block
- Allocated logical blocks: `56`
- Unallocated logical blocks: `5`

## STFS file coverage

| File | Chain | Hash-valid now | State |
|---|---|---:|---|
| `/Account` | 6 | 1/1 | complete |
| `/FFFE07D1.gpd` | 22 → 32 → 34 → 5 → 4 → 23 | 2/6 | partial |
| `/FFFE07D1.fit` | 15 → 49 → 54 → 55 | 1/4 | partial |
| `/tile_64.png` | 11 | 1/1 | complete |
| `/tile_32.png` | 12 | 1/1 | complete |
| `/584D07D1.gpd` | 18 → 19 → 20 → 17 | 3/4 | partial |
| `/FFFE07DE.gpd` | 7 → 8 → 9 → 27 | 3/4 | partial |
| `/liveid.bin` | 3 | 1/1 | complete |
| `/PEC` | 44 | 0/1 | missing/corrupt |
| `/cache/ph.dat` | 2 | 1/1 | complete |
| `/58480880.gpd` | 24 → 25 → 28 → 13 | 1/4 | partial |
| `/4D5307E6.gpd` | 45 → 46 → 47 → 30 → 33 → 26 → 36 → 37 → 38 → 39 → 40 → 41 → 21 | 0/13 | missing/corrupt |
| `/425307D5.gpd` | 14 → 16 → 29 → 52 → 42 → 48 → 53 → 50 → 51 | 2/9 | partial |

## Integrity checkpoint

The package itself contains a valid active hash table even though the deleted outer FATX file was initially recovered as one contiguous run. Validation of all 56 logical blocks against that table shows:

- **20 logical blocks match their original SHA-1 exactly**
- **36 logical block positions do not**
- some mismatched positions contain zero blocks or data whose SHA-1 matches a different original STFS block, further supporting a fragmented deleted FATX chain rather than a fabricated/corrupt header

## Mapping layers

1. **FATX deletion/recovery layer** — confirmed deleted directory chain and first cluster.
2. **STFS/XContent header** — structure and primary metadata mapped.
3. **STFS hash/block layer** — active hash table and all logical file chains mapped.
4. **Account blob** — identity and Live-account semantics mapped; secrets redacted.
5. **GPD/XDBF layer** — in progress; only hash-valid source blocks are authoritative until reconstruction reaches 56/56.
6. **Cross-file graph** — pending full recovery.

## Work queue

1. SHA-1 carve `DRIVE2_TIME_FINAL.E01` for the missing logical STFS block hashes.
2. Rebuild the full STFS package and require **56/56** block-hash validation.
3. Re-extract all files from the rebuilt package.
4. Parse every GPD/XDBF namespace and record entry offset, ID, length, type, semantics, and source block provenance.
5. Map `FFFE07D1.fit`, `PEC`, and `liveid.bin` without exposing authentication secrets.
6. Add cross-file relationships for title IDs, title records, settings, achievements, images, sync records, and profile identity.

## Confidence tags

- `confirmed-by-hash`: bytes match the original STFS SHA-1 recorded in the intact active hash table.
- `confirmed-by-structure`: parsed from intact container/database metadata.
- `reference-derived`: semantic interpretation agrees with public implementations/specifications.
- `unknown`: not yet mapped or not yet recoverable from hash-valid bytes.

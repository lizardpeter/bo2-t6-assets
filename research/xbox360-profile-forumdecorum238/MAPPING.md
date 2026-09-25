# Xbox 360 Live Profile Map — ForumDecorum238

Specimen: `E0000255AEF799DA` (`ForumDecorum238`)  
Source: Digital Corpora `nps-2014-xbox1 / DRIVE2_TIME_FINAL.E01`  
Recovered from deleted FATX path `/Content/E0000255AEF799DA/FFFE07D1/00010000/E0000255AEF799DA`.

## Recovery integrity

The deleted FATX directory entry preserved first cluster `21751` and size `278528`, but its old FAT chain had been freed. A naive contiguous read preserved only 20 of 56 STFS logical blocks. The active STFS L0 hash table remained intact, so every missing 4096-byte logical block was recovered by exact SHA-1 matching.

- Initial valid logical STFS blocks: **20/56**
- Final reconstructed logical STFS blocks: **56/56**
- Fully reconstructed package SHA-256: `7803e496467d36701191f617c306bfda6a0f9b79cad7c213bb668a664a34b3df`
- XTAF cluster size: `0x4000` (16 KiB)
- XTAF data area absolute offset: `0x1347B9000`
- Deleted profile first-cluster contiguous start: `0x149B91000`

## Outer STFS / XContent

- Magic: `CON `
- Content type: `0x00010000` — Profile
- Metadata version: 2
- Title ID: `FFFE07D1` — Xbox 360 Dashboard
- Profile ID: `E0000255AEF799DA`
- Header size: `0x971A`; padded STFS region starts at `0xA000`
- Root active hash-table index: 1
- Active L0 hash table: `0xB000`
- Root hash / active L0 SHA-1: `81aa87394a1b941ce9dd56fd9d80307096684666`
- File-table logical block: 1
- Allocated logical blocks: 56; unallocated: 5
- Header SHA-1 at `0x32C` verifies over the signed metadata region.

### Embedded files

| Path | Size | STFS logical block chain |
|---|---:|---|
| `Account` | 404 | `6` |
| `FFFE07D1.gpd` | 24,559 | `22→32→34→5→4→23` |
| `FFFE07D1.fit` | 13,739 | `15→49→54→55` |
| `tile_64.png` | 2,234 | `11` |
| `tile_32.png` | 1,167 | `12` |
| `584D07D1.gpd` | 15,670 | `18→19→20→17` |
| `FFFE07DE.gpd` | 14,450 | `7→8→9→27` |
| `liveid.bin` | 658 | `3` |
| `PEC` | 4,096 | `44` |
| `cache/ph.dat` | 71 | `2` |
| `58480880.gpd` | 15,753 | `24→25→28→13` |
| `4D5307E6.gpd` | 52,340 | `45→46→47→30→33→26→36→37→38→39→40→41→21` |
| `425307D5.gpd` | 36,204 | `14→16→29→52→42→48→53→50→51` |

## Account

The 404-byte `Account` blob is HMAC/RC4 protected. Its stored HMAC verifies against the decrypted confounder+payload. Credential bytes are deliberately not recorded.

| Payload offset | Size | Field | Value / interpretation |
|---|---:|---|---|
| `0x00` | 4 | `reservedFlags` | `0x20000001`; `LiveEnabled` set |
| `0x04` | 4 | `liveFlags` | `0x00000000` |
| `0x08` | 32 | gamertag | `ForumDecorum238` (UTF-16BE) |
| `0x28` | 8 | XUID | `000900000A90717C`; online-XUID prefix |
| `0x30` | 4 | cached user flags | subscription tier 3 = Silver |
| `0x34` | 4 | service provider | `PROD` |
| `0x38` | 4 | passcode | not emitted; all-zero in specimen |
| `0x3C` | 20 | online domain | `xbox.com` |
| `0x50` | 24 | Kerberos realm | `PASSPORT.NET` |
| `0x68` | 16 | online key | present/nonzero; **redacted** |

## XDBF / GPD layout

All six `.gpd` files and `FFFE07D1.fit` are valid big-endian `XDBF` databases.

Common layout:

- `+0x00` magic `XDBF`
- `+0x04` version, u32 BE
- `+0x08` entry-table capacity, u32 BE
- `+0x0C` current entry count, u32 BE
- `+0x10` free-table capacity, u32 BE
- `+0x14` current free-entry count, u32 BE
- entry = 18 bytes: namespace u16, ID u64, data-relative offset u32, length u32
- free-space entry = 8 bytes: offset u32, length u32
- data base = `0x18 + entry_capacity*0x12 + free_capacity*0x08`, normally `0x3418`
- special IDs `0x100000000` and `0x200000000` are sync-list and sync-state records inside a namespace

Observed standard namespaces: 1 achievement, 2 image, 3 setting, 4 title history, 5 title string.

### Database inventory

| File | Semantic title | Entries | Main contents |
|---|---|---:|---|
| `FFFE07D1.gpd` | Xbox 360 Dashboard | 33 | profile settings, title history, dashboard image/string, sync |
| `FFFE07DE.gpd` | Xbox 360 Dashboard system DB | 5 | image/string + sync |
| `584D07D1.gpd` | Avatar Editor | 7 | image/string + title-specific setting + sync |
| `58480880.gpd` | Internet Explorer | 7 | image/string + title-specific setting + sync |
| `4D5307E6.gpd` | Halo 3 | 87 | 79 achievements, image, two title-specific settings, sync, string |
| `425307D5.gpd` | Fallout 3 | 63 | 58 achievements, image, sync, string |
| `FFFE07D1.fit` | unresolved FIT XDBF | 4 | four namespace-1 composite-ID records |

## Dashboard GPD — FFFE07D1.gpd

### Title history

| Title ID | Name | Achievements | Earned | GS | Earned GS | Last played UTC |
|---|---|---:|---:|---:|---:|---|
| `425307D5` | Fallout 3 | 58 | 0 | 1200 | 0 | 2013-03-14 05:34:17.295 |
| `4D5307E6` | Halo 3 | 79 | 0 | 1750 | 0 | 2013-02-15 21:46:53.309 |
| `58480880` | Internet Explorer | 0 | 0 | 0 | 0 | 2012-12-07 22:31:12.800 |

The profile setting `Gamercard Titles Played = 3` matches this table exactly.

### Confirmed settings

- `0x10040000` Permissions = `8`
- `0x10040004` Gamercard Zone = `1` (**Recreation**)
- `0x10040005` Gamercard Region = `103` (**United States**)
- `0x10040012` Gamercard Titles Played = `3`
- `0x1004003B` Messenger Signup State = `1`
- `0x1004003D` Save Windows Live Password flag = `1`
- `0x1004003E` Friends App Show Buddies = `1`
- `0x10040047` Tenure Level / Years on Live = `0`
- `0x10040048` Tenure Milestone = `0`
- `0x1004004B` Subscription Length (months) = `0`
- `0x1004004C` Subscription Payment Type = `0`
- `0x10040052` Beacons Social Network Sharing = `1`
- `0x4064000F` Gamercard Picture Key = `fffe07d10002000c0001000c`
- `0x41040040` Gamercard User Name = `Sam`
- `0x5004000B` Gamercard Reputation ≈ `58.7222862`
- `0x60620054` Gamercard Party Address — 98-byte binary value; bytes withheld
- `0x61000046` Gamercard Party Info — 55-byte binary; contains title ID `4D5307E6`; member identifiers withheld
- `0x61180050` unknown 280-byte binary profile setting
- `0x63E80044` Gamercard Avatar Info 1 — 1000-byte avatar structure; includes profile ID; raw represented by hash
- `0x63E80051` Jump-In List — 100-byte record containing user-facing text `I want to use this app with friends.`; identifiers withheld
- `0x70080049` Tenure Next Milestone Date / Profile Date Created — zero/null
- `0x7008004F` Last Xbox Live Sign-in — zero/null in this GPD snapshot

## Fallout 3 — 425307D5.gpd

- 58 achievement records, IDs 1–58
- 1200 possible gamerscore
- 0 earned/unlocked in this profile snapshot
- namespace-1 sync list contains 58 items
- sync state: next sync ID 59; last synced ID 1; `2013-03-14T05:34:23.193Z`
- valid title PNG SHA-256: `9bb8a4f39364a09bba87c8933631304aec49319691193eade44322edc60cca63`
- every achievement record includes mapped entry offset, length, image ID, gamerscore, flags, name and descriptions

## Halo 3 — 4D5307E6.gpd

- 79 achievement records; IDs extend through 92 because some IDs are absent
- 1750 possible gamerscore
- 0 earned/unlocked in this profile snapshot
- namespace-1 sync list contains 79 items
- sync state: next sync ID 80; last synced ID 7; `2013-02-15T21:48:28.603Z`
- two title-specific binary settings, `0x63E83FFF` and `0x63E83FFE`
- valid title PNG SHA-256: `75dde967d48de440a24def27ce35429aef2a4a15d2c08d382b26d1daf3a32f79`

## Avatar Editor and Internet Explorer

Both small GPDs have a title PNG, title string, one title-specific binary setting, and namespace sync state. Neither contains achievement definitions.

- `584D07D1` → Avatar Editor
- `58480880` → Internet Explorer

## FFFE07D1.fit

Valid `XDBF` v1 with four namespace-1 records and composite 64-bit IDs:

- `FFFE07D101010008` — 95 bytes
- `FFFE07D101010009` — 116 bytes
- `FFFE07D10101000A` — 96 bytes
- `FFFE07D10201000A` — 96 bytes

The payloads share a structured fixed-field prefix but do **not** match normal achievement payload semantics despite namespace 1. They remain unresolved pending dashboard/XAM identification.

## PEC

`PEC` is a valid Profile Embedded Content header/STFS structure, but empty:

- length exactly `0x1000`
- header SHA-1 at `0x228` verifies over `0x23C..0xFFF`
- same profile and console IDs as the outer profile
- volume descriptor at `0x244`
- zero file-table blocks
- zero allocated/unallocated content blocks

Thus this snapshot has no avatar-item GPDs relocated into PEC.

## Other files

- `liveid.bin` — 658 bytes, SHA-256 `9426a63ddbd8400b53a773dbb223feddd47d20e069f9679651227f2ef4d227ce`. Treated as opaque credential-adjacent Xbox Live data; token/secret bytes are intentionally not decoded or published.
- `cache/ph.dat` — 71 bytes; magic `phc3`; contains title ID `58480880` at offset `0x20` and a FILETIME-like value at `0x0C` corresponding to `2012-11-25T01:45:50.036Z`. Legacy X360 tooling calls it an unknown profile/achievement-history cache.
- `tile_32.png`, `tile_64.png` — valid profile tiles.

## Confidence

- **confirmed-by-hash** — bytes match original STFS SHA-1.
- **confirmed-by-structure** — parsed from validated metadata.
- **reference-derived** — semantics corroborated by Free60/Xenia/Velocity.
- **unresolved** — byte structure preserved, semantics not yet demonstrated.

## Next targets

1. Identify `FFFE07D1.fit` record semantics and composite-ID fields.
2. Reverse `cache/ph.dat` after its `phc3` header, timestamp and title ID.
3. Decode non-secret Avatar/Party/Jump-In/title-specific binary substructures.
4. Map XDBF free-space allocator and sync mutation behavior.
5. Cross-link semantic records to STFS blocks and original raw-disk carve offsets for graph ingestion.

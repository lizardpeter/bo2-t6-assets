# Source Containers

Optional retail/source container files used to reproduce extraction results belong here and must be stored through Git LFS.

Examples include:

- `.ff` fastfiles
- `.ipak` image packages
- `.sabs` / `.sabl` audio containers
- expanded/decrypted `.bin` streams

Recommended provenance layout:

```text
source-containers/
  common_mp/
  common_patch_mp/
  patch_mp/
  localization/
  dlc/
```

For every source file, record SHA-256, byte size, original filename, extraction/decryption method, and relationship to later patch layers in `manifests/`.

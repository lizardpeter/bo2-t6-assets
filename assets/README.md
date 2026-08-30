# Decoded / Exported Assets

This tree holds verified BO2/T6 asset exports. Large binary payloads are stored with Git LFS according to the repository `.gitattributes` rules.

Planned organization:

```text
assets/
  weapons/
  viewhands/
  characters/
  attachments/
  equipment/
  scorestreaks/
  vehicles/
  models/
  animations/
  materials/
  textures/
  fx/
  audio/
  maps/
```

Keep the original internal asset name and source-layer provenance in the corresponding manifest. Do not silently merge `common_mp`, `common_patch_mp`, and `patch_mp` assets.

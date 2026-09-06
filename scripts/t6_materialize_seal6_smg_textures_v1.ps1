param(
    [string]$BaseIpak = "",
    [string]$Python = "python",
    [string]$OutDir = "retail_output\seal6_smg_textures"
)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Targets = Join-Path $RepoRoot "manifests\nonmap\retail\seal6_smg_exact_base_ipak_keys_v4.json"
$MetadataV3 = Join-Path $RepoRoot "manifests\nonmap\retail\seal6_smg_texture_keys_v3.json"
$ImportMetadata = Join-Path $RepoRoot "manifests\nonmap\retail\seal6_smg_import_image_resolution_v2.json"
$Tool = Join-Path $RepoRoot "tools\t6_ipak_iwi_materialize_v1.py"
if (-not $BaseIpak) {
    if ($env:T6_GAME_ROOT) {
        $BaseIpak = Join-Path $env:T6_GAME_ROOT "zone\all\base.ipak"
    } else {
        $BaseIpak = Join-Path $env:USERPROFILE "Downloads\Plutonium\pluto_t6_full_game\zone\all\base.ipak"
    }
}
if (-not (Test-Path -LiteralPath $BaseIpak)) { throw "base.ipak not found: $BaseIpak" }
$ExpectedSha = "6c3e68f856f0eafb54aef193b96464b313617f11653f75d1d3fa03f01125fa02"
& $Python $Tool --ipak $BaseIpak --targets $Targets --metadata $MetadataV3 --metadata $ImportMetadata --outdir $OutDir --expect-ipak-sha256 $ExpectedSha
if ($LASTEXITCODE -ne 0) { throw "SEAL6 texture materialization failed with exit code $LASTEXITCODE" }
Write-Host "Verified SEAL6 IWI + PNG textures written to $OutDir"

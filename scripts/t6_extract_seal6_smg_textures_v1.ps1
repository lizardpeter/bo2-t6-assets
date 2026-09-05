param(
    [string]$BaseIpak = "",
    [string]$Python = "python",
    [string]$OutDir = "retail_output\seal6_smg_base_ipak_entries"
)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Manifest = Join-Path $RepoRoot "manifests\nonmap\retail\seal6_smg_texture_keys_v3.json"
$Extractor = Join-Path $RepoRoot "tools\t6_ipak_exact_key_extract_v1.py"
if (-not $BaseIpak) {
    if ($env:T6_GAME_ROOT) {
        $BaseIpak = Join-Path $env:T6_GAME_ROOT "zone\all\base.ipak"
    } else {
        $BaseIpak = Join-Path $env:USERPROFILE "Downloads\Plutonium\pluto_t6_full_game\zone\all\base.ipak"
    }
}
if (-not (Test-Path -LiteralPath $BaseIpak)) { throw "base.ipak not found: $BaseIpak" }
$ExpectedSha = "6c3e68f856f0eafb54aef193b96464b313617f11653f75d1d3fa03f01125fa02"
& $Python $Extractor --ipak $BaseIpak --targets $Manifest --outdir $OutDir --repository base.ipak --expect-ipak-sha256 $ExpectedSha --zip
if ($LASTEXITCODE -ne 0) { throw "Exact-key extraction failed with exit code $LASTEXITCODE" }
Write-Host "Exact SEAL6 base.ipak entries written to $OutDir and $OutDir.zip"

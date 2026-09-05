param(
    [Parameter(Mandatory=$true)][string]$MeshJson,
    [Parameter(Mandatory=$true)][string]$SkeletonJson,
    [string[]]$XAnimJson = @(),
    [string]$XAnimDir = "",
    [string]$BaseIpak = "",
    [string]$Python = "python",
    [string]$OutDir = "retail_output\seal6_smg_textured_animated_lod0"
)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Retail = Join-Path $RepoRoot "manifests\nonmap\retail"
$Tools = Join-Path $RepoRoot "tools"

function Require-File([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label not found: $Path" }
    return (Resolve-Path -LiteralPath $Path).Path
}
function Run-Python([string[]]$Args) {
    & $Python @Args
    if ($LASTEXITCODE -ne 0) { throw "Python stage failed ($LASTEXITCODE): $($Args -join ' ')" }
}

$MeshJson = Require-File $MeshJson "normalized mesh"
$SkeletonJson = Require-File $SkeletonJson "normalized skeleton"

if (-not $BaseIpak) {
    if ($env:T6_GAME_ROOT) {
        $BaseIpak = Join-Path $env:T6_GAME_ROOT "zone\all\base.ipak"
    } else {
        $BaseIpak = Join-Path $env:USERPROFILE "Downloads\Plutonium\pluto_t6_full_game\zone\all\base.ipak"
    }
}
$BaseIpak = Require-File $BaseIpak "retail base.ipak"
$ExpectedBaseIpakSha = "6c3e68f856f0eafb54aef193b96464b313617f11653f75d1d3fa03f01125fa02"
$ActualBaseIpakSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $BaseIpak).Hash.ToLowerInvariant()
if ($ActualBaseIpakSha -ne $ExpectedBaseIpakSha) {
    throw "base.ipak SHA-256 mismatch: $ActualBaseIpakSha (expected $ExpectedBaseIpakSha)"
}

if ($XAnimJson.Count -eq 0) {
    if (-not $XAnimDir) { throw "Provide -XAnimJson or -XAnimDir containing the six normalized retail benchmark XAnims." }
    $Names = @(
        "pb_stand_alert",
        "pb_stand_ads",
        "pb_smg_sprint",
        "pb_combatrun_forward_loop",
        "pb_standjump_takeoff",
        "pt_stand_shoot_auto"
    )
    foreach ($Name in $Names) {
        $Candidate = Join-Path $XAnimDir "$Name.normalized.json"
        $XAnimJson += (Require-File $Candidate "normalized XAnim $Name")
    }
} else {
    $Resolved = @()
    foreach ($P in $XAnimJson) { $Resolved += (Require-File $P "normalized XAnim") }
    $XAnimJson = $Resolved
}
if ($XAnimJson.Count -ne 6) { throw "This benchmark wrapper requires exactly six normalized XAnims; got $($XAnimJson.Count)." }

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$OutDir = (Resolve-Path -LiteralPath $OutDir).Path
$AnimatedGlb = Join-Path $OutDir "seal6_smg_lod0_animated.glb"
$AnimatedProof = Join-Path $OutDir "seal6_smg_lod0_animated.proof.json"
$BindingPlan = Join-Path $OutDir "seal6_smg_lod0_material_binding_plan.json"
$TextureDir = Join-Path $OutDir "textures"
$TexturedGlb = Join-Path $OutDir "seal6_smg_lod0_textured_animated.glb"
$TextureApplyProof = Join-Path $OutDir "seal6_smg_lod0_textured_animated.proof.json"
$BuildSummary = Join-Path $OutDir "build_summary.json"

$SurfaceProof = Require-File (Join-Path $Retail "seal6_smg_material_handle_alias_proof_v1.json") "surface material proof"
$Materials = Require-File (Join-Path $Retail "seal6_smg_texture_keys_v2.json") "material texture manifest"
$ExactKeys = Require-File (Join-Path $Retail "seal6_smg_exact_base_ipak_keys_v4.json") "exact IPAK keys"
$HeaderAlias = Require-File (Join-Path $Retail "seal6_smg_image_alias_header_proof_v1.json") "image header alias proof"
$ImageRun = Require-File (Join-Path $Retail "seal6_common_packed_image_name_proof_v1.json") "image run proof"
$MaterialAlias = Require-File (Join-Path $Retail "seal6_faction_material_alias_proof_v1.json") "material virtual image alias proof"
$Imports = Require-File (Join-Path $Retail "seal6_smg_import_image_resolution_v2.json") "import image resolution"
$Shared = Require-File (Join-Path $Retail "seal6_shared_radiant_alias_proof_v1.json") "shared radiant alias proof"
$TextureMeta = Require-File (Join-Path $Retail "seal6_smg_texture_keys_v3.json") "texture metadata manifest"

$MultiExporter = Require-File (Join-Path $Tools "t6_xanim_skinned_gltf_multianim_export_v1.py") "multi-animation exporter"
$Binder = Require-File (Join-Path $Tools "t6_character_material_binding_plan_v1.py") "material binding compiler"
$Materializer = Require-File (Join-Path $Tools "t6_ipak_iwi_materialize_v1.py") "IPAK/IWI materializer"
$TextureApplier = Require-File (Join-Path $Tools "t6_gltf_apply_materialized_textures_v1.py") "GLB texture applier"

$AnimArgs = @($MultiExporter, $MeshJson, $SkeletonJson, $SurfaceProof, $AnimatedGlb, "--lod", "0", "--manifest", $AnimatedProof)
foreach ($P in $XAnimJson) { $AnimArgs += @("--xanim", $P) }
Run-Python $AnimArgs

Run-Python @(
    $Binder,
    "--materials", $Materials,
    "--surface-proof", $SurfaceProof,
    "--mesh", $MeshJson,
    "--exact-keys", $ExactKeys,
    "--header-alias-proof", $HeaderAlias,
    "--image-run-proof", $ImageRun,
    "--material-alias-proof", $MaterialAlias,
    "--import-resolution", $Imports,
    "--shared-identity-proof", $Shared,
    "--lod", "0",
    "--out", $BindingPlan
)

New-Item -ItemType Directory -Force -Path $TextureDir | Out-Null
Run-Python @(
    $Materializer,
    "--ipak", $BaseIpak,
    "--targets", $ExactKeys,
    "--metadata", $TextureMeta,
    "--metadata", $Imports,
    "--outdir", $TextureDir,
    "--expect-ipak-sha256", $ExpectedBaseIpakSha
)
$MaterializedManifest = Require-File (Join-Path $TextureDir "manifest.json") "materialized texture proof"

Run-Python @(
    $TextureApplier,
    "--glb", $AnimatedGlb,
    "--binding-plan", $BindingPlan,
    "--materialized-manifest", $MaterializedManifest,
    "--out", $TexturedGlb,
    "--manifest", $TextureApplyProof
)

$Animated = Get-Content -Raw -LiteralPath $AnimatedProof | ConvertFrom-Json
$Binding = Get-Content -Raw -LiteralPath $BindingPlan | ConvertFrom-Json
$Materialized = Get-Content -Raw -LiteralPath $MaterializedManifest | ConvertFrom-Json
$Applied = Get-Content -Raw -LiteralPath $TextureApplyProof | ConvertFrom-Json
if (-not $Binding.summary.nativeIdentityClosure) { throw "Native MaterialTextureDef identity closure failed." }
if (-not $Binding.summary.visualPbrTextureClosure) { throw "LOD0 visual texture binding closure failed." }
if ($Materialized.summary.unresolved -ne 0 -or $Materialized.summary.materialized -ne 42) { throw "Expected 42/42 exact base.ipak textures; got $($Materialized.summary.materialized) materialized and $($Materialized.summary.unresolved) unresolved." }
if ($Applied.summary.boundMaterials -ne 12 -or $Applied.summary.baseColorBindings -ne 12 -or $Applied.summary.normalBindings -ne 12) { throw "Textured LOD0 material binding count mismatch." }
if ($Animated.vertices -ne 13490 -or $Animated.triangles -ne 14968 -or $Animated.joints -ne 102 -or $Animated.animations.Count -ne 6) { throw "Animated SEAL6 benchmark geometry/rig/animation count mismatch." }

$Summary = [ordered]@{
    format = "t6-seal6-smg-textured-animated-lod0-build-v1"
    authority = "retail T6 XModel/XAnim/Material/GfxImage + exact retail base.ipak stream keys"
    baseIpak = [ordered]@{ path = $BaseIpak; sha256 = $ActualBaseIpakSha }
    animated = [ordered]@{ path = $AnimatedGlb; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $AnimatedGlb).Hash.ToLowerInvariant(); vertices = $Animated.vertices; triangles = $Animated.triangles; joints = $Animated.joints; animations = $Animated.animations.Count }
    materialBinding = $Binding.summary
    materializedTextures = $Materialized.summary
    textureApply = $Applied.summary
    texturedGlb = [ordered]@{ path = $TexturedGlb; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $TexturedGlb).Hash.ToLowerInvariant(); bytes = (Get-Item -LiteralPath $TexturedGlb).Length }
    gates = [ordered]@{ exactRetailBaseIpak = $true; nativeMaterialIdentityClosed = $true; exact42TexturePayloadsMaterialized = $true; lod0BaseColorNormalBindingsClosed = $true; sixRetailAnimationsPresent = $true }
    proofBoundary = "This is the retail-proven LOD0 six-animation benchmark. It does not yet claim all four XModel LODs, every retail third-person behavior animation, MP7 first-person/world integration, FX/audio, or complete-player gate closure."
}
$Summary | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 -LiteralPath $BuildSummary
Write-Host "Built retail SEAL6 LOD0 textured + animated benchmark: $TexturedGlb"
Write-Host "Proof: $BuildSummary"

param(
    [Parameter(Mandatory=$true)][string]$MeshJson,
    [Parameter(Mandatory=$true)][string]$SkeletonJson,
    [string[]]$XAnimJson = @(),
    [string]$XAnimDir = "",
    [string]$BaseIpak = "",
    [string]$MpIpak = "",
    [string]$Python = "python",
    [string]$OutDir = "retail_output\seal6_smg_textured_animated_all_lods_v3",
    [string]$PackagePath = "",
    [switch]$NoPortableDependencyBootstrap
)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Retail = Join-Path $RepoRoot "manifests\nonmap\retail"
$Tools = Join-Path $RepoRoot "tools"
$Requirements = Join-Path $RepoRoot "requirements-t6-textures.txt"

$ExpectedBaseIpakSha256 = "6c3e68f846fd8ae7bc0bc1adfbeff642d5c8e3ecfc4bd9be3a880f452144fa02"
$ExpectedMpIpakSha256 = "f97404b9bf5a4410ecd298e62a5cdbb3f9d5630b226d885310033842930632a5"
$ExpectedReferenceGlbSha256 = "c83d2f14d121dc4e6ffad0a11ff6f1517c7e7274ba480cbd528ee45543290008"

function Require-File([string]$Path,[string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label not found: $Path" }
    return (Resolve-Path -LiteralPath $Path).Path
}
function Run-With([string]$Exe,[string[]]$ArgList) {
    & $Exe @ArgList | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Stage failed ($LASTEXITCODE): $Exe $($ArgList -join ' ')" }
}
function Test-TexturePython([string]$Exe) {
    & $Exe -c "import imagecodecs, PIL; assert imagecodecs.LZO.available" *> $null
    return ($LASTEXITCODE -eq 0)
}
function Resolve-TexturePython() {
    if (Test-TexturePython $Python) { return $Python }
    if ($NoPortableDependencyBootstrap) {
        throw "Python lacks imagecodecs LZO/Pillow and -NoPortableDependencyBootstrap was supplied. Install requirements-t6-textures.txt."
    }
    $cacheBase = if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA "bo2-t6-assets" } elseif ($env:TEMP) { Join-Path $env:TEMP "bo2-t6-assets" } else { Join-Path $HOME ".cache\bo2-t6-assets" }
    $venv = Join-Path $cacheBase "t6-textures-py-2026.8.16"
    $venvPython = if ($IsWindows) { Join-Path $venv "Scripts\python.exe" } else { Join-Path $venv "bin\python" }
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        New-Item -ItemType Directory -Force -Path $cacheBase | Out-Null
        Write-Host "Creating isolated T6 texture Python environment: $venv"
        Run-With $Python @("-m","venv",$venv)
    }
    if (-not (Test-TexturePython $venvPython)) {
        Write-Host "Installing pinned portable texture dependencies into isolated environment..."
        Run-With $venvPython @("-m","pip","install","--disable-pip-version-check","-r",$Requirements)
    }
    if (-not (Test-TexturePython $venvPython)) { throw "Portable texture Python environment does not provide imagecodecs LZO + Pillow." }
    return $venvPython
}
function Get-Sha256([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}
function Get-JsonProperty([object]$Object,[string]$Name) {
    $p = $Object.PSObject.Properties[$Name]
    if ($null -eq $p) { return $null }
    return $p.Value
}

$MeshJson = Require-File $MeshJson "normalized mesh"
$SkeletonJson = Require-File $SkeletonJson "normalized skeleton"
$Requirements = Require-File $Requirements "portable texture requirements"

if (-not $BaseIpak) {
    if ($env:T6_GAME_ROOT) { $BaseIpak = Join-Path $env:T6_GAME_ROOT "zone\all\base.ipak" }
    else { $BaseIpak = Join-Path $env:USERPROFILE "Downloads\Plutonium\pluto_t6_full_game\zone\all\base.ipak" }
}
if (-not $MpIpak) {
    if ($env:T6_GAME_ROOT) { $MpIpak = Join-Path $env:T6_GAME_ROOT "zone\all\mp.ipak" }
    else { $MpIpak = Join-Path $env:USERPROFILE "Downloads\Plutonium\pluto_t6_full_game\zone\all\mp.ipak" }
}
$BaseIpak = Require-File $BaseIpak "retail base.ipak"
$MpIpak = Require-File $MpIpak "retail mp.ipak"
$ActualBaseSha = Get-Sha256 $BaseIpak
$ActualMpSha = Get-Sha256 $MpIpak
if ($ActualBaseSha -ne $ExpectedBaseIpakSha256) { throw "base.ipak SHA-256 mismatch: $ActualBaseSha" }
if ($ActualMpSha -ne $ExpectedMpIpakSha256) { throw "mp.ipak SHA-256 mismatch: $ActualMpSha" }

$ExpectedAnimations = @(
    @{name="pb_stand_alert";frames=383},
    @{name="pb_stand_ads";frames=90},
    @{name="pb_smg_sprint";frames=46},
    @{name="pb_combatrun_forward_loop";frames=50},
    @{name="pb_standjump_takeoff";frames=27},
    @{name="pt_stand_shoot_auto";frames=18}
)
if ($XAnimJson.Count -eq 0) {
    if (-not $XAnimDir) { throw "Provide -XAnimJson or -XAnimDir." }
    foreach ($a in $ExpectedAnimations) {
        $XAnimJson += (Require-File (Join-Path $XAnimDir "$($a.name).normalized.json") "normalized XAnim $($a.name)")
    }
} else {
    $resolved = @()
    foreach ($p in $XAnimJson) { $resolved += (Require-File $p "normalized XAnim") }
    $XAnimJson = $resolved
}
if ($XAnimJson.Count -ne 6) { throw "Expected exactly six benchmark XAnims; got $($XAnimJson.Count)" }

# Validate clip identity/rate/frame domain before producing any output.
$SeenAnimations = @{}
foreach ($p in $XAnimJson) {
    $x = Get-Content -Raw -LiteralPath $p | ConvertFrom-Json
    if ($x.format -ne "t6-xanim-normalized-v1") { throw "Unsupported normalized XAnim format in $p" }
    $name = [string]$x.name
    if ($SeenAnimations.ContainsKey($name)) { throw "Duplicate normalized XAnim: $name" }
    $SeenAnimations[$name] = $x
}
foreach ($a in $ExpectedAnimations) {
    if (-not $SeenAnimations.ContainsKey($a.name)) { throw "Missing exact benchmark XAnim $($a.name)" }
    $x = $SeenAnimations[$a.name]
    $frames = if ($null -ne $x.numframes) { [int]$x.numframes } elseif ($null -ne $x.numFrames) { [int]$x.numFrames } else { -1 }
    $fps = if ($null -ne $x.framerate) { [double]$x.framerate } elseif ($null -ne $x.frameRate) { [double]$x.frameRate } else { -1 }
    if ($frames -ne [int]$a.frames) { throw "$($a.name) frame mismatch: $frames" }
    if ([math]::Abs($fps - 30.0) -gt 0.000001) { throw "$($a.name) framerate mismatch: $fps" }
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$OutDir = (Resolve-Path -LiteralPath $OutDir).Path

$ExportSurfaceProof = Require-File (Join-Path $Retail "seal6_smg_material_handle_alias_proof_v1.json") "export surface proof"
$BindingSurfaceProof = Require-File (Join-Path $Retail "seal6_smg_surface_material_assignments_v1.json") "binding surface assignments"
$Materials = Require-File (Join-Path $Retail "seal6_smg_texture_keys_v2.json") "material manifest"
$ExactKeys = Require-File (Join-Path $Retail "seal6_smg_exact_base_ipak_keys_v4.json") "exact stream keys"
$TextureTargets = Require-File (Join-Path $Retail "seal6_smg_texture_keys_v4.json") "42-image identity target set"
$ResolutionContract = Require-File (Join-Path $Retail "seal6_smg_multi_ipak_resolution_contract_v1.json") "multi-IPAK resolution contract"
$HeaderAlias = Require-File (Join-Path $Retail "seal6_smg_image_alias_header_proof_v1.json") "header alias proof"
$ImageRun = Require-File (Join-Path $Retail "seal6_common_packed_image_name_proof_v1.json") "image run proof"
$MaterialAlias = Require-File (Join-Path $Retail "seal6_faction_material_alias_proof_v1.json") "material image alias proof"
$Imports = Require-File (Join-Path $Retail "seal6_smg_import_image_resolution_v2.json") "import resolution"
$Shared = Require-File (Join-Path $Retail "seal6_shared_radiant_alias_proof_v1.json") "shared radiant proof"
$TextureMeta = Require-File (Join-Path $Retail "seal6_smg_texture_keys_v3.json") "texture metadata"
$GoldenProof = Require-File (Join-Path $Retail "seal6_smg_golden_asset_proof_v1.json") "SEAL6 golden proof"
$Multi = Require-File (Join-Path $Tools "t6_xanim_skinned_gltf_multianim_export_v1.py") "multi-animation exporter"
$Binder = Require-File (Join-Path $Tools "t6_character_material_binding_plan_v2.py") "material binder v2"
$Materializer = Require-File (Join-Path $Tools "t6_ipak_iwi_materialize_v3.py") "multi-IPAK materializer v3"
$Apply = Require-File (Join-Path $Tools "t6_gltf_apply_materialized_textures_v1.py") "GLB texture applier"
$ProofValidator = Require-File (Join-Path $Tools "t6_asset_proof_manifest_v1.py") "asset proof validator"

$Contract = Get-Content -Raw -LiteralPath $ResolutionContract | ConvertFrom-Json
if ($Contract.summary.requestedTextures -ne 42 -or $Contract.summary.expectedMaterializedTextures -ne 42) { throw "SEAL6 multi-IPAK contract target count mismatch" }
if ((Get-JsonProperty $Contract.summary.expectedRepositoryCounts "base.ipak") -ne 40) { throw "SEAL6 contract base.ipak count mismatch" }
if ((Get-JsonProperty $Contract.summary.expectedRepositoryCounts "mp.ipak") -ne 2) { throw "SEAL6 contract mp.ipak count mismatch" }
if ($Contract.repositories.'base.ipak'.sha256 -ne $ExpectedBaseIpakSha256) { throw "SEAL6 contract base.ipak SHA mismatch" }
if ($Contract.repositories.'mp.ipak'.sha256 -ne $ExpectedMpIpakSha256) { throw "SEAL6 contract mp.ipak SHA mismatch" }
Run-With $Python @($ProofValidator,$GoldenProof)

$TexturePython = Resolve-TexturePython
Write-Host "Texture Python: $TexturePython"
$TextureDir = Join-Path $OutDir "textures"
New-Item -ItemType Directory -Force -Path $TextureDir | Out-Null
Run-With $TexturePython @(
    $Materializer,
    "--ipak","base.ipak=$BaseIpak",
    "--ipak","mp.ipak=$MpIpak",
    "--expect-ipak-sha256","base.ipak=$ExpectedBaseIpakSha256",
    "--expect-ipak-sha256","mp.ipak=$ExpectedMpIpakSha256",
    "--targets",$TextureTargets,
    "--metadata",$TextureMeta,
    "--metadata",$Imports,
    "--outdir",$TextureDir
)
$TextureProof = Require-File (Join-Path $TextureDir "manifest.json") "texture materialization proof"
$Tex = Get-Content -Raw -LiteralPath $TextureProof | ConvertFrom-Json
$BaseResolved = Get-JsonProperty $Tex.summary.repositories "base.ipak"
$MpResolved = Get-JsonProperty $Tex.summary.repositories "mp.ipak"
if ($Tex.format -ne "t6-ipak-iwi-materialization-v3") { throw "Expected v3 materialization proof" }
if ($Tex.summary.requested -ne 42 -or $Tex.summary.materialized -ne 42 -or $Tex.summary.unresolved -ne 0) { throw "Expected 42/42 exact retail texture payloads." }
if ($BaseResolved -ne 40 -or $MpResolved -ne 2) { throw "Expected exact repository split base.ipak=40 mp.ipak=2; got base.ipak=$BaseResolved mp.ipak=$MpResolved" }

$ExpectedLods = @(
    @{lod=0;surfs=14;verts=13490;tris=14968;mats=12},
    @{lod=1;surfs=10;verts=4474;tris=3916;mats=10},
    @{lod=2;surfs=9;verts=2076;tris=1671;mats=9},
    @{lod=3;surfs=9;verts=1148;tris=728;mats=9}
)
$LodResults = @()
foreach ($e in $ExpectedLods) {
    $lod = $e.lod
    $adir = Join-Path $OutDir "lod$lod"
    New-Item -ItemType Directory -Force -Path $adir | Out-Null
    $animated = Join-Path $adir "seal6_smg_lod${lod}_animated.glb"
    $animProof = Join-Path $adir "animated.proof.json"
    $plan = Join-Path $adir "material_binding_plan.json"
    $textured = Join-Path $adir "seal6_smg_lod${lod}_textured_animated.glb"
    $applyProof = Join-Path $adir "textured.proof.json"

    $aa = @($Multi,$MeshJson,$SkeletonJson,$ExportSurfaceProof,$animated,"--lod","$lod","--manifest",$animProof)
    foreach ($p in $XAnimJson) { $aa += @("--xanim",$p) }
    Run-With $Python $aa

    Run-With $Python @($Binder,"--materials",$Materials,"--surface-proof",$BindingSurfaceProof,"--mesh",$MeshJson,"--exact-keys",$ExactKeys,"--header-alias-proof",$HeaderAlias,"--image-run-proof",$ImageRun,"--material-alias-proof",$MaterialAlias,"--import-resolution",$Imports,"--shared-identity-proof",$Shared,"--lod","$lod","--out",$plan)
    Run-With $TexturePython @($Apply,"--glb",$animated,"--binding-plan",$plan,"--materialized-manifest",$TextureProof,"--out",$textured,"--manifest",$applyProof)

    $A = Get-Content -Raw -LiteralPath $animProof | ConvertFrom-Json
    $B = Get-Content -Raw -LiteralPath $plan | ConvertFrom-Json
    $P = Get-Content -Raw -LiteralPath $applyProof | ConvertFrom-Json
    if ($A.vertices -ne $e.verts -or $A.triangles -ne $e.tris -or $A.joints -ne 102 -or $A.animations.Count -ne 6) { throw "LOD$lod animated benchmark mismatch" }
    if ($B.summary.lodSurfaces -ne $e.surfs -or $B.summary.lodUniqueMaterials -ne $e.mats -or -not $B.summary.nativeIdentityClosure -or -not $B.summary.visualPbrTextureClosure) { throw "LOD$lod material closure mismatch" }
    if ($P.summary.boundMaterials -ne $e.mats -or $P.summary.baseColorBindings -ne $e.mats -or $P.summary.normalBindings -ne $e.mats) { throw "LOD$lod textured material binding mismatch" }

    $LodResults += [ordered]@{
        lod=$lod; surfaces=$e.surfs; vertices=$A.vertices; triangles=$A.triangles; joints=$A.joints; materials=$e.mats; animations=$A.animations.Count
        texturedGlb=$textured; texturedGlbSha256=Get-Sha256 $textured; texturedGlbBytes=(Get-Item -LiteralPath $textured).Length
        nativeMaterialIdentityClosure=$B.summary.nativeIdentityClosure; visualPbrTextureClosure=$B.summary.visualPbrTextureClosure
    }
}

$Summary = [ordered]@{
    format="t6-seal6-smg-textured-animated-all-lods-build-v3"
    authority="retail T6 all serialized XModel LODs + retail common_mp animations + exact surface/material/image identities + exact unique cross-repository base.ipak/mp.ipak payload resolution"
    sourceIpaks=[ordered]@{
        "base.ipak"=[ordered]@{path=$BaseIpak;sha256=$ActualBaseSha;resolvedTextures=40}
        "mp.ipak"=[ordered]@{path=$MpIpak;sha256=$ActualMpSha;resolvedTextures=2}
    }
    resolutionContract=[ordered]@{path=$ResolutionContract;sha256=Get-Sha256 $ResolutionContract}
    textureMaterialization=[ordered]@{path=$TextureProof;sha256=Get-Sha256 $TextureProof;summary=$Tex.summary}
    surfaceAssignments=[ordered]@{path=$BindingSurfaceProof;sha256=Get-Sha256 $BindingSurfaceProof;rows=42}
    goldenFixture=[ordered]@{path=$GoldenProof;sha256=Get-Sha256 $GoldenProof;referenceGlbSha256=$ExpectedReferenceGlbSha256}
    portableTextureBackend=[ordered]@{python=$TexturePython;requirements=$Requirements;systemLzoDllRequired=$false}
    lods=$LodResults
    aggregate=[ordered]@{serializedLods=4;serializedSurfaces=42;verticesAcrossSerializedSurfaces=21188;trianglesAcrossSerializedSurfaces=21283;joints=102;benchmarkAnimations=6;exactTexturePayloads=42;baseIpakTextures=40;mpIpakTextures=2;allLodsTextured=$true;allLodsAnimated=$true;allSurfaceMaterialsExact=$true}
    proofBoundary="All four serialized body LODs are rebuilt from the supplied normalized retail model/animation inputs and closed for geometry, skin, exact surface materials, 42 CRC/IWI-validated retail texture payloads uniquely resolved across base.ipak + mp.ipak, and the six-animation benchmark. Full third-person behavior-family closure, first-person weapon/world integration, FX/audio, and the final complete-player gate remain separate."
}
$Build = Join-Path $OutDir "build_summary.json"
$Summary | ConvertTo-Json -Depth 14 | Set-Content -Encoding UTF8 -LiteralPath $Build

$ProvenanceDir = Join-Path $OutDir "provenance"
New-Item -ItemType Directory -Force -Path $ProvenanceDir | Out-Null
foreach ($p in @($ResolutionContract,$GoldenProof,$BindingSurfaceProof,$ExportSurfaceProof,$Materials,$ExactKeys,$TextureTargets,$TextureMeta,$HeaderAlias,$ImageRun,$MaterialAlias,$Imports,$Shared)) {
    Copy-Item -LiteralPath $p -Destination (Join-Path $ProvenanceDir (Split-Path -Leaf $p)) -Force
}
Copy-Item -LiteralPath $Materializer -Destination (Join-Path $ProvenanceDir (Split-Path -Leaf $Materializer)) -Force
Copy-Item -LiteralPath $Build -Destination (Join-Path $ProvenanceDir "build_summary.json") -Force

if (-not $PackagePath) { $PackagePath = Join-Path (Split-Path -Parent $OutDir) "SEAL6_FULL_RETAIL_BLENDER.zip" }
$PackageParent = Split-Path -Parent $PackagePath
if ($PackageParent) { New-Item -ItemType Directory -Force -Path $PackageParent | Out-Null }
if (Test-Path -LiteralPath $PackagePath) { Remove-Item -LiteralPath $PackagePath -Force }
Compress-Archive -Path (Join-Path $OutDir "*") -DestinationPath $PackagePath -CompressionLevel Optimal
$PackagePath = (Resolve-Path -LiteralPath $PackagePath).Path
$PackageSha = Get-Sha256 $PackagePath
$PackageBytes = (Get-Item -LiteralPath $PackagePath).Length

$PackageManifest = [ordered]@{
    format="t6-seal6-full-retail-blender-package-v1"
    package=$PackagePath
    bytes=$PackageBytes
    sha256=$PackageSha
    buildSummary=$Build
    exactRetailTextureSplit=[ordered]@{"base.ipak"=40;"mp.ipak"=2}
    lods=4
    surfaces=42
    joints=102
    animations=6
    proofBoundary=$Summary.proofBoundary
}
$PackageManifestPath = "$PackagePath.manifest.json"
$PackageManifest | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 -LiteralPath $PackageManifestPath

Write-Host "Built all four retail SEAL6 body LODs: $OutDir"
Write-Host "Build proof: $Build"
Write-Host "Package: $PackagePath"
Write-Host "Package SHA-256: $PackageSha"

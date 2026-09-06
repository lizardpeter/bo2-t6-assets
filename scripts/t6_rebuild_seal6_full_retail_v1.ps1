param(
    [Parameter(Mandatory=$true)][string]$FactionSealsFastfile,
    [Parameter(Mandatory=$true)][string]$CommonMpFastfile,
    [Parameter(Mandatory=$true)][string]$BaseIpak,
    [Parameter(Mandatory=$true)][string]$MpIpak,
    [string]$Python = "python",
    [string]$OutRoot = "retail_output\seal6_full_retail_rebuild_v1",
    [string]$PackagePath = ""
)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Tools = Join-Path $RepoRoot "tools"
$Builder = Join-Path $PSScriptRoot "t6_build_seal6_smg_textured_animated_all_lods_v3.ps1"

$FactionRawBytes = 3095232
$FactionRawSha256 = "1a0754a5183eca3b1169610ad61b369768617340d000ef730a0d5c7b9ea97c88"
$FactionExpandedBytes = 11393922
$FactionExpandedSha256 = "21a11090990417faefa8c39282f499c7bdb87a7acf62f00082aa9b3811cced30"
$CommonExpandedBytes = 206493911
$CommonExpandedSha256 = "fbd91d0ede8e27bcaaf7af9638a7118050f27519524be36e9234f980bd6170ce"
$TargetName = "c_usa_mp_seal6_smg_fb"
$TargetAssetStart = "0x45CCF1"
$TargetXAssetIndex = 213

$ExpectedAnimations = @(
    @{name="pb_stand_alert";start=662933;frames=383;sha="5b939762cc76bb79674c2fc0d6ffd4c9460acd555ad2368aeaf45b52d80ad8b3"},
    @{name="pb_stand_ads";start=655915;frames=90;sha="6900419e6ea5cd43fa3cd2c9384e1862cff2c73e86e5df7db8ea4f41ef961c2c"},
    @{name="pb_smg_sprint";start=5203838;frames=46;sha="4824cc8f8fbda4c303dafd783034a1dc7e56d81dcbaffbaea88fafbf6bef7ac6"},
    @{name="pb_combatrun_forward_loop";start=5670677;frames=50;sha="091a8ff01a0e0a66fc19632fec483207ae565764c8f7c268208ab2facb92dd36"},
    @{name="pb_standjump_takeoff";start=10693310;frames=27;sha="53efd36cd2caa35613b255d7dfd29a185347a82f65f72eff5b567396734340b0"},
    @{name="pt_stand_shoot_auto";start=7851319;frames=18;sha="ee1d1b126359187212f7b249a38cb06a73b9cce2afcbad09d1d235f1ece2a08e"}
)

function Require-File([string]$Path,[string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label not found: $Path" }
    return (Resolve-Path -LiteralPath $Path).Path
}
function Get-Sha256([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}
function Run-With([string]$Exe,[string[]]$ArgList) {
    & $Exe @ArgList | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Stage failed ($LASTEXITCODE): $Exe $($ArgList -join ' ')" }
}
function Assert-FileIdentity([string]$Path,[long]$Bytes,[string]$Sha,[string]$Label) {
    $actualBytes = (Get-Item -LiteralPath $Path).Length
    if ($actualBytes -ne $Bytes) { throw "$Label byte-size mismatch: $actualBytes != $Bytes" }
    $actualSha = Get-Sha256 $Path
    if ($actualSha -ne $Sha) { throw "$Label SHA-256 mismatch: $actualSha != $Sha" }
}

$FactionSealsFastfile = Require-File $FactionSealsFastfile "retail faction_seals_mp.ff"
$CommonMpFastfile = Require-File $CommonMpFastfile "retail common_mp.ff"
$BaseIpak = Require-File $BaseIpak "retail base.ipak"
$MpIpak = Require-File $MpIpak "retail mp.ipak"
$Builder = Require-File $Builder "SEAL6 all-LOD v3 builder"
$FastfileTool = Require-File (Join-Path $Tools "bo2_t6_fastfile.py") "T6 FastFile decryptor"
$SkeletonTool = Require-File (Join-Path $Tools "t6_xmodel_skeleton_normalize_v3.py") "XModel skeleton normalizer v3"
$MeshTool = Require-File (Join-Path $Tools "t6_xmodel_mesh_normalize_v4.py") "XModel mesh normalizer v4"
$XAnimTool = Require-File (Join-Path $Tools "t6_xanim_normalize_v1.py") "XAnim normalizer"

# faction_seals_mp has one retained authoritative raw identity. common_mp is
# intentionally keyed by exact expanded identity because retained provenance
# contains two raw-container identities from different source packages; only the
# expanded animation source used by the benchmark is promoted here.
Assert-FileIdentity $FactionSealsFastfile $FactionRawBytes $FactionRawSha256 "faction_seals_mp.ff"
$CommonRawBytes = (Get-Item -LiteralPath $CommonMpFastfile).Length
$CommonRawSha256 = Get-Sha256 $CommonMpFastfile

New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null
$OutRoot = (Resolve-Path -LiteralPath $OutRoot).Path
$ExpandedDir = Join-Path $OutRoot "expanded"
$NormalizedDir = Join-Path $OutRoot "normalized"
$AnimDir = Join-Path $NormalizedDir "animations"
New-Item -ItemType Directory -Force -Path $ExpandedDir,$NormalizedDir,$AnimDir | Out-Null

$FactionExpanded = Join-Path $ExpandedDir "faction_seals_mp.ff.expanded"
$CommonExpanded = Join-Path $ExpandedDir "common_mp.ff.expanded"
$FactionAudit = Join-Path $ExpandedDir "faction_seals_mp.fastfile_audit.json"
$CommonAudit = Join-Path $ExpandedDir "common_mp.fastfile_audit.json"
Run-With $Python @($FastfileTool,"decrypt",$FactionSealsFastfile,"--output",$FactionExpanded,"--audit",$FactionAudit)
Run-With $Python @($FastfileTool,"decrypt",$CommonMpFastfile,"--output",$CommonExpanded,"--audit",$CommonAudit)
Assert-FileIdentity $FactionExpanded $FactionExpandedBytes $FactionExpandedSha256 "expanded faction_seals_mp"
Assert-FileIdentity $CommonExpanded $CommonExpandedBytes $CommonExpandedSha256 "expanded common_mp animation source"

$SkeletonJson = Join-Path $NormalizedDir "c_usa_mp_seal6_smg_fb.skeleton.v3.json"
$MeshJson = Join-Path $NormalizedDir "c_usa_mp_seal6_smg_fb.mesh.v4.json"
Run-With $Python @($SkeletonTool,$FactionExpanded,"--asset-start",$TargetAssetStart,"--xasset-index","$TargetXAssetIndex","--name",$TargetName,"--out",$SkeletonJson)
Run-With $Python @($MeshTool,$FactionExpanded,"--asset-start",$TargetAssetStart,"--skeleton",$SkeletonJson,"--out",$MeshJson)

$Skel = Get-Content -Raw -LiteralPath $SkeletonJson | ConvertFrom-Json
$Mesh = Get-Content -Raw -LiteralPath $MeshJson | ConvertFrom-Json
if ($Skel.identity.name -ne $TargetName -or $Skel.skeleton.numBones -ne 102) { throw "SEAL6 skeleton identity/cardinality mismatch" }
if ($Skel.skeletonSource.topLevelSurfsAliasProven -ne $true) { throw "SEAL6 packed top-level surface alias was not proven by skeleton v3" }
if ($Mesh.identity.name -ne $TargetName -or $Mesh.xmodel.numLods -ne 4 -or $Mesh.surfaces.Count -ne 42) { throw "SEAL6 mesh identity/LOD/surface mismatch" }
if ($Mesh.summary.vertices -ne 21188 -or $Mesh.summary.triangles -ne 21283) { throw "SEAL6 all-LOD mesh totals mismatch" }
if ($Mesh.reuseProof.mode -ne "exact-packed-top-level-XModel.surfs-alias") { throw "SEAL6 mesh v4 did not retain exact top-level surface alias proof" }

$XAnimPaths = @()
$XAnimProof = @()
foreach ($a in $ExpectedAnimations) {
    $out = Join-Path $AnimDir "$($a.name).normalized.json"
    Run-With $Python @($XAnimTool,$CommonExpanded,"--asset-start","$($a.start)","--out",$out)
    $x = Get-Content -Raw -LiteralPath $out | ConvertFrom-Json
    if ($x.format -ne "t6-xanim-normalized-v1") { throw "$($a.name) normalized format mismatch" }
    if ($x.name -ne $a.name) { throw "XAnim identity mismatch at $($a.start): $($x.name) != $($a.name)" }
    if ($x.header.numframes -ne $a.frames) { throw "$($a.name) frame mismatch: $($x.header.numframes)" }
    if ([math]::Abs([double]$x.header.framerate - 30.0) -gt 0.000001) { throw "$($a.name) framerate mismatch: $($x.header.framerate)" }
    if ($x.assetSerializedSha256 -ne $a.sha) { throw "$($a.name) serialized source SHA mismatch: $($x.assetSerializedSha256)" }
    if ($x.allFlatPoolsExhausted -ne $true) { throw "$($a.name) did not exhaust every FlatXAnimReader pool" }
    $XAnimPaths += $out
    $XAnimProof += [ordered]@{name=$x.name;assetFixedStart=$x.assetFixedStart;assetSerializedEnd=$x.assetSerializedEnd;assetSerializedSha256=$x.assetSerializedSha256;numframes=$x.header.numframes;framerate=$x.header.framerate;normalizedPath=$out;normalizedSha256=(Get-Sha256 $out)}
}

$BuildDir = Join-Path $OutRoot "build"
if (-not $PackagePath) { $PackagePath = Join-Path $OutRoot "SEAL6_FULL_RETAIL_BLENDER.zip" }
& $Builder -MeshJson $MeshJson -SkeletonJson $SkeletonJson -XAnimJson $XAnimPaths -BaseIpak $BaseIpak -MpIpak $MpIpak -Python $Python -OutDir $BuildDir -PackagePath $PackagePath
if ($LASTEXITCODE -ne 0) { throw "SEAL6 v3 package builder failed with code $LASTEXITCODE" }
$PackagePath = Require-File $PackagePath "SEAL6 full retail package"
$BuildSummary = Require-File (Join-Path $BuildDir "build_summary.json") "SEAL6 build summary"

$Repro = [ordered]@{
    format="t6-seal6-full-retail-rebuild-v1"
    asset=$TargetName
    policy=[ordered]@{sourceDerivedOnly=$true;noFallbackGeometry=$true;noFallbackSkeleton=$true;noFallbackAnimation=$true;noFallbackMaterialsOrTextures=$true;commonMpPromotedByExpandedIdentity=$true}
    source=[ordered]@{
        faction_seals_mp=[ordered]@{path=$FactionSealsFastfile;bytes=$FactionRawBytes;sha256=$FactionRawSha256;expandedPath=$FactionExpanded;expandedBytes=$FactionExpandedBytes;expandedSha256=$FactionExpandedSha256}
        common_mp=[ordered]@{path=$CommonMpFastfile;bytes=$CommonRawBytes;sha256=$CommonRawSha256;expandedPath=$CommonExpanded;expandedBytes=$CommonExpandedBytes;expandedSha256=$CommonExpandedSha256}
        base_ipak=[ordered]@{path=$BaseIpak;sha256=(Get-Sha256 $BaseIpak)}
        mp_ipak=[ordered]@{path=$MpIpak;sha256=(Get-Sha256 $MpIpak)}
    }
    xmodel=[ordered]@{assetStartHex=$TargetAssetStart;xassetIndex=$TargetXAssetIndex;skeletonPath=$SkeletonJson;skeletonSha256=(Get-Sha256 $SkeletonJson);meshPath=$MeshJson;meshSha256=(Get-Sha256 $MeshJson);joints=102;lods=4;surfaces=42;vertices=21188;triangles=21283}
    animations=$XAnimProof
    buildSummary=[ordered]@{path=$BuildSummary;sha256=(Get-Sha256 $BuildSummary)}
    package=[ordered]@{path=$PackagePath;bytes=(Get-Item -LiteralPath $PackagePath).Length;sha256=(Get-Sha256 $PackagePath);sidecar="$PackagePath.manifest.json"}
    proofBoundary="This is the one-command source-derived SEAL6 rebuild path from two retail FastFiles plus base.ipak/mp.ipak. It requires the exact faction source identity, exact retained common_mp expanded animation identity, exact XModel alias proof, six exact XAnim serialized payloads, and the v3 42/42 cross-IPAK materialization gate before packaging."
}
$ReproPath = Join-Path $OutRoot "rebuild_provenance.json"
$Repro | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 -LiteralPath $ReproPath
Write-Host "SEAL6 raw-retail rebuild complete: $PackagePath"
Write-Host "Rebuild provenance: $ReproPath"

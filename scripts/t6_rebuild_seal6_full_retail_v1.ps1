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
$Builder = Join-Path $PSScriptRoot "t6_build_seal6_smg_textured_animated_all_lods_v4.ps1"

# Raw FastFile wrappers can differ across source packages while decrypting to the
# same authoritative expanded XFile. Promotion therefore pins the exact
# expanded byte stream. The observed raw identity is still recorded in the
# provenance and the retail mirror's current raw size is checked as a guardrail.
$FactionObservedRawBytes = 3095232
$FactionExpandedBytes = 6245916
$FactionExpandedSha256 = "21a11090990417faefa8c39282f499c7bdb87a7acf62f00082aa9b3811cced30"
$CommonObservedRawBytes = 40307072
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
function Assert-RawSize([string]$Path,[long]$Bytes,[string]$Label) {
    $actualBytes = (Get-Item -LiteralPath $Path).Length
    if ($actualBytes -ne $Bytes) { throw "$Label raw byte-size mismatch: $actualBytes != $Bytes" }
}

$FactionSealsFastfile = Require-File $FactionSealsFastfile "retail faction_seals_mp.ff"
$CommonMpFastfile = Require-File $CommonMpFastfile "retail common_mp.ff"
$BaseIpak = Require-File $BaseIpak "retail base.ipak"
$MpIpak = Require-File $MpIpak "retail mp.ipak"
$Builder = Require-File $Builder "SEAL6 all-LOD v4 builder"
$FastfileTool = Require-File (Join-Path $Tools "bo2_t6_fastfile.py") "T6 FastFile decryptor"
$SkeletonTool = Require-File (Join-Path $Tools "t6_xmodel_skeleton_normalize_v3.py") "XModel skeleton normalizer v3"
# The retained SEAL6 golden fixture names mesh-normalize-v1 as its exact decoder,
# and fresh retail replay independently reports skeletonSource.mode=inline_owned.
# Mesh v4 is intentionally not used here: it is only for packed top-level surfs aliases.
$MeshTool = Require-File (Join-Path $Tools "t6_xmodel_mesh_normalize_v1.py") "inline XModel mesh normalizer v1"
$XAnimTool = Require-File (Join-Path $Tools "t6_xanim_normalize_v1.py") "XAnim normalizer"

Assert-RawSize $FactionSealsFastfile $FactionObservedRawBytes "faction_seals_mp.ff"
Assert-RawSize $CommonMpFastfile $CommonObservedRawBytes "common_mp.ff"
$FactionRawBytes = (Get-Item -LiteralPath $FactionSealsFastfile).Length
$FactionRawSha256 = Get-Sha256 $FactionSealsFastfile
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
$MeshJson = Join-Path $NormalizedDir "c_usa_mp_seal6_smg_fb.mesh.v1.json"
Run-With $Python @($SkeletonTool,$FactionExpanded,"--asset-start",$TargetAssetStart,"--xasset-index","$TargetXAssetIndex","--name",$TargetName,"--out",$SkeletonJson)
Run-With $Python @($MeshTool,$FactionExpanded,"--asset-start",$TargetAssetStart,"--out",$MeshJson)

$Skel = Get-Content -Raw -LiteralPath $SkeletonJson | ConvertFrom-Json
$Mesh = Get-Content -Raw -LiteralPath $MeshJson | ConvertFrom-Json
if ($Skel.identity.name -ne $TargetName -or $Skel.skeleton.numBones -ne 102) { throw "SEAL6 skeleton identity/cardinality mismatch" }
if ($Skel.skeletonSource.mode -ne "inline_owned") { throw "SEAL6 fresh retail skeleton is not inline-owned: $($Skel.skeletonSource.mode)" }
if ($Skel.validation.allBoneNamesResolved -ne $true -or $Skel.validation.hierarchyValid -ne $true) { throw "SEAL6 skeleton integrity is not closed" }
if ($Mesh.format -ne "t6-xmodel-mesh-normalized-v1") { throw "SEAL6 exact inline mesh normalizer format mismatch: $($Mesh.format)" }
if ($Mesh.identity.name -ne $TargetName -or $Mesh.xmodel.numLods -ne 4 -or $Mesh.surfaces.Count -ne 42) { throw "SEAL6 mesh identity/LOD/surface mismatch" }
if ($Mesh.expandedSha256 -ne $FactionExpandedSha256) { throw "SEAL6 mesh source expanded SHA mismatch" }
$MeshVertices = 0
$MeshTriangles = 0
foreach ($s in $Mesh.surfaces) { $MeshVertices += [int]$s.vertCount; $MeshTriangles += [int]$s.triCount }
if ($MeshVertices -ne 21188 -or $MeshTriangles -ne 21283) { throw "SEAL6 all-LOD mesh totals mismatch: $MeshVertices vertices / $MeshTriangles triangles" }
if ($Mesh.validation.allLocalTriangleIndicesInRange -ne $true -or $Mesh.validation.DObjSkelMatBytes -ne 64) { throw "SEAL6 exact inline mesh validation failed" }

$ExpectedLods = @(
    @{lod=0;surfs=14;verts=13490;tris=14968},
    @{lod=1;surfs=10;verts=4474;tris=3916},
    @{lod=2;surfs=9;verts=2076;tris=1671},
    @{lod=3;surfs=9;verts=1148;tris=728}
)
foreach ($e in $ExpectedLods) {
    $l = @($Mesh.xmodel.lods | Where-Object { [int]$_.index -eq [int]$e.lod })
    if ($l.Count -ne 1 -or [int]$l[0].numSurfs -ne [int]$e.surfs) { throw "SEAL6 LOD$($e.lod) surface span mismatch" }
    $v=0; $t=0
    $first=[int]$l[0].surfIndex; $last=$first+[int]$l[0].numSurfs
    for ($si=$first; $si -lt $last; $si++) { $v += [int]$Mesh.surfaces[$si].vertCount; $t += [int]$Mesh.surfaces[$si].triCount }
    if ($v -ne [int]$e.verts -or $t -ne [int]$e.tris) { throw "SEAL6 LOD$($e.lod) geometry mismatch: $v vertices / $t triangles" }
}

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
if ($LASTEXITCODE -ne 0) { throw "SEAL6 v4 package builder failed with code $LASTEXITCODE" }
$PackagePath = Require-File $PackagePath "SEAL6 full retail package"
$BuildSummary = Require-File (Join-Path $BuildDir "build_summary.json") "SEAL6 build summary"

$Repro = [ordered]@{
    format="t6-seal6-full-retail-rebuild-v1"
    asset=$TargetName
    policy=[ordered]@{sourceDerivedOnly=$true;noFallbackGeometry=$true;noFallbackSkeleton=$true;noFallbackAnimation=$true;noFallbackMaterialsOrTextures=$true;fastFilesPromotedByExpandedIdentity=$true;ipakImagesPromotedByExactContentIdentity=$true;inlineXModelOwnershipRequired=$true}
    source=[ordered]@{
        faction_seals_mp=[ordered]@{path=$FactionSealsFastfile;bytes=$FactionRawBytes;sha256=$FactionRawSha256;expandedPath=$FactionExpanded;expandedBytes=$FactionExpandedBytes;expandedSha256=$FactionExpandedSha256}
        common_mp=[ordered]@{path=$CommonMpFastfile;bytes=$CommonRawBytes;sha256=$CommonRawSha256;expandedPath=$CommonExpanded;expandedBytes=$CommonExpandedBytes;expandedSha256=$CommonExpandedSha256}
        base_ipak=[ordered]@{path=$BaseIpak;bytes=(Get-Item -LiteralPath $BaseIpak).Length;sha256=(Get-Sha256 $BaseIpak)}
        mp_ipak=[ordered]@{path=$MpIpak;bytes=(Get-Item -LiteralPath $MpIpak).Length;sha256=(Get-Sha256 $MpIpak)}
    }
    xmodel=[ordered]@{assetStartHex=$TargetAssetStart;xassetIndex=$TargetXAssetIndex;ownership="inline_owned";meshNormalizer="tools/t6_xmodel_mesh_normalize_v1.py";skeletonPath=$SkeletonJson;skeletonSha256=(Get-Sha256 $SkeletonJson);meshPath=$MeshJson;meshSha256=(Get-Sha256 $MeshJson);joints=102;lods=4;surfaces=42;vertices=$MeshVertices;triangles=$MeshTriangles}
    animations=$XAnimProof
    buildSummary=[ordered]@{path=$BuildSummary;sha256=(Get-Sha256 $BuildSummary)}
    package=[ordered]@{path=$PackagePath;bytes=(Get-Item -LiteralPath $PackagePath).Length;sha256=(Get-Sha256 $PackagePath);sidecar="$PackagePath.manifest.json"}
    proofBoundary="This is the one-command source-derived SEAL6 rebuild path from two retail FastFiles plus base.ipak/mp.ipak. Each FastFile is promoted only after decrypt/decompress reproduces the exact pinned expanded XFile identity. The target XModel is required to reproduce the retained inline-owned serialization and is decoded with the same exact mesh-normalize-v1 path named by the golden fixture. IPAK whole-container hashes are retained as provenance, while every image is promoted only by unique exact (retail filename hash, streamed dataHash) resolution plus reconstructed CRC29/IWI validation. The build then requires the exact 102-joint skeleton and six exact XAnim serialized payloads before packaging."
}
$ReproPath = Join-Path $OutRoot "rebuild_provenance.json"
$Repro | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 -LiteralPath $ReproPath
Write-Host "SEAL6 raw-retail rebuild complete: $PackagePath"
Write-Host "Rebuild provenance: $ReproPath"

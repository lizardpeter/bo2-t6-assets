param(
    [Parameter(Mandatory=$true)][string]$MeshJson,
    [Parameter(Mandatory=$true)][string]$SkeletonJson,
    [string[]]$XAnimJson = @(),
    [string]$XAnimDir = "",
    [string]$BaseIpak = "",
    [string]$Python = "python",
    [string]$OutDir = "retail_output\seal6_smg_textured_animated_all_lods"
)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Retail = Join-Path $RepoRoot "manifests\nonmap\retail"
$Tools = Join-Path $RepoRoot "tools"
function Require-File([string]$Path,[string]$Label) { if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label not found: $Path" }; return (Resolve-Path -LiteralPath $Path).Path }
function Run-Python([string[]]$Args) { & $Python @Args; if ($LASTEXITCODE -ne 0) { throw "Python stage failed ($LASTEXITCODE): $($Args -join ' ')" } }

$MeshJson=Require-File $MeshJson "normalized mesh";$SkeletonJson=Require-File $SkeletonJson "normalized skeleton"
if (-not $BaseIpak) { if ($env:T6_GAME_ROOT) { $BaseIpak=Join-Path $env:T6_GAME_ROOT "zone\all\base.ipak" } else { $BaseIpak=Join-Path $env:USERPROFILE "Downloads\Plutonium\pluto_t6_full_game\zone\all\base.ipak" } }
$BaseIpak=Require-File $BaseIpak "retail base.ipak";$ExpectedSha="6c3e68f856f0eafb54aef193b96464b313617f11653f75d1d3fa03f01125fa02";$ActualSha=(Get-FileHash -Algorithm SHA256 -LiteralPath $BaseIpak).Hash.ToLowerInvariant();if($ActualSha-ne$ExpectedSha){throw "base.ipak SHA-256 mismatch: $ActualSha"}
if($XAnimJson.Count-eq 0){if(-not $XAnimDir){throw "Provide -XAnimJson or -XAnimDir."};foreach($n in @("pb_stand_alert","pb_stand_ads","pb_smg_sprint","pb_combatrun_forward_loop","pb_standjump_takeoff","pt_stand_shoot_auto")){$XAnimJson+=(Require-File (Join-Path $XAnimDir "$n.normalized.json") "normalized XAnim $n")}}else{$r=@();foreach($p in $XAnimJson){$r+=(Require-File $p "normalized XAnim")};$XAnimJson=$r};if($XAnimJson.Count-ne 6){throw "Expected exactly six benchmark XAnims; got $($XAnimJson.Count)"}
New-Item -ItemType Directory -Force -Path $OutDir|Out-Null;$OutDir=(Resolve-Path -LiteralPath $OutDir).Path

$SurfaceProof=Require-File (Join-Path $Retail "seal6_smg_material_handle_alias_proof_v1.json") "surface proof"
$Materials=Require-File (Join-Path $Retail "seal6_smg_texture_keys_v2.json") "material manifest"
$ExactKeys=Require-File (Join-Path $Retail "seal6_smg_exact_base_ipak_keys_v4.json") "exact texture keys"
$HeaderAlias=Require-File (Join-Path $Retail "seal6_smg_image_alias_header_proof_v1.json") "header alias proof"
$ImageRun=Require-File (Join-Path $Retail "seal6_common_packed_image_name_proof_v1.json") "image run proof"
$MaterialAlias=Require-File (Join-Path $Retail "seal6_faction_material_alias_proof_v1.json") "material image alias proof"
$Imports=Require-File (Join-Path $Retail "seal6_smg_import_image_resolution_v2.json") "import resolution"
$Shared=Require-File (Join-Path $Retail "seal6_shared_radiant_alias_proof_v1.json") "shared radiant proof"
$TextureMeta=Require-File (Join-Path $Retail "seal6_smg_texture_keys_v3.json") "texture metadata"
$Multi=Require-File (Join-Path $Tools "t6_xanim_skinned_gltf_multianim_export_v1.py") "multi-animation exporter"
$Binder=Require-File (Join-Path $Tools "t6_character_material_binding_plan_v1.py") "material binder"
$Materializer=Require-File (Join-Path $Tools "t6_ipak_iwi_materialize_v1.py") "IPAK materializer"
$Apply=Require-File (Join-Path $Tools "t6_gltf_apply_materialized_textures_v1.py") "GLB texture applier"

$TextureDir=Join-Path $OutDir "textures";New-Item -ItemType Directory -Force -Path $TextureDir|Out-Null
Run-Python @($Materializer,"--ipak",$BaseIpak,"--targets",$ExactKeys,"--metadata",$TextureMeta,"--metadata",$Imports,"--outdir",$TextureDir,"--expect-ipak-sha256",$ExpectedSha)
$TextureProof=Require-File (Join-Path $TextureDir "manifest.json") "texture materialization proof";$Tex=(Get-Content -Raw -LiteralPath $TextureProof|ConvertFrom-Json);if($Tex.summary.materialized-ne42-or$Tex.summary.unresolved-ne0){throw "Expected 42/42 exact retail texture payloads."}

$Expected=@(
    @{lod=0;surfs=14;verts=13490;tris=14968;mats=12},
    @{lod=1;surfs=10;verts=4474;tris=3916;mats=10},
    @{lod=2;surfs=9;verts=2076;tris=1671;mats=9},
    @{lod=3;surfs=9;verts=1148;tris=728;mats=9}
)
$LodResults=@()
foreach($e in $Expected){
    $lod=$e.lod;$adir=Join-Path $OutDir "lod$lod";New-Item -ItemType Directory -Force -Path $adir|Out-Null
    $animated=Join-Path $adir "seal6_smg_lod${lod}_animated.glb";$animProof=Join-Path $adir "animated.proof.json";$plan=Join-Path $adir "material_binding_plan.json";$textured=Join-Path $adir "seal6_smg_lod${lod}_textured_animated.glb";$applyProof=Join-Path $adir "textured.proof.json"
    $aa=@($Multi,$MeshJson,$SkeletonJson,$SurfaceProof,$animated,"--lod","$lod","--manifest",$animProof);foreach($p in $XAnimJson){$aa+=@("--xanim",$p)};Run-Python $aa
    Run-Python @($Binder,"--materials",$Materials,"--surface-proof",$SurfaceProof,"--mesh",$MeshJson,"--exact-keys",$ExactKeys,"--header-alias-proof",$HeaderAlias,"--image-run-proof",$ImageRun,"--material-alias-proof",$MaterialAlias,"--import-resolution",$Imports,"--shared-identity-proof",$Shared,"--lod","$lod","--out",$plan)
    Run-Python @($Apply,"--glb",$animated,"--binding-plan",$plan,"--materialized-manifest",$TextureProof,"--out",$textured,"--manifest",$applyProof)
    $A=Get-Content -Raw -LiteralPath $animProof|ConvertFrom-Json;$B=Get-Content -Raw -LiteralPath $plan|ConvertFrom-Json;$P=Get-Content -Raw -LiteralPath $applyProof|ConvertFrom-Json
    if($A.vertices-ne$e.verts-or$A.triangles-ne$e.tris-or$A.joints-ne102-or$A.animations.Count-ne6){throw "LOD$lod animated benchmark mismatch"}
    if($B.summary.lodSurfaces-ne$e.surfs-or$B.summary.lodUniqueMaterials-ne$e.mats-or-not$B.summary.nativeIdentityClosure-or-not$B.summary.visualPbrTextureClosure){throw "LOD$lod material closure mismatch"}
    if($P.summary.boundMaterials-ne$e.mats-or$P.summary.baseColorBindings-ne$e.mats-or$P.summary.normalBindings-ne$e.mats){throw "LOD$lod textured material binding mismatch"}
    $LodResults+=[ordered]@{lod=$lod;surfaces=$e.surfs;vertices=$A.vertices;triangles=$A.triangles;joints=$A.joints;materials=$e.mats;animations=$A.animations.Count;texturedGlb=$textured;texturedGlbSha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $textured).Hash.ToLowerInvariant();texturedGlbBytes=(Get-Item -LiteralPath $textured).Length;nativeMaterialIdentityClosure=$B.summary.nativeIdentityClosure;visualPbrTextureClosure=$B.summary.visualPbrTextureClosure}
}
$Summary=[ordered]@{format="t6-seal6-smg-textured-animated-all-lods-build-v1";authority="retail T6 all serialized XModel LODs + retail common_mp animations + exact Material/GfxImage/base.ipak data";baseIpak=[ordered]@{path=$BaseIpak;sha256=$ActualSha};materializedTextures=$Tex.summary;lods=$LodResults;aggregate=[ordered]@{serializedLods=4;serializedSurfaces=42;verticesAcrossSerializedSurfaces=21188;trianglesAcrossSerializedSurfaces=21283;allLodsTextured=$true;allLodsAnimated=$true;allSurfaceMaterialsExact=$true;exactTexturePayloads=42};proofBoundary="All four serialized body LODs are closed for geometry, skin, exact materials, 42 exact retail texture payloads, and the six-animation benchmark. Full third-person behavior-family closure, MP7 first-person/world integration, FX/audio, and the final complete-player gate remain separate."}
$Build=Join-Path $OutDir "build_summary.json";$Summary|ConvertTo-Json -Depth 12|Set-Content -Encoding UTF8 -LiteralPath $Build;Write-Host "Built all four retail SEAL6 body LODs: $OutDir";Write-Host "Proof: $Build"

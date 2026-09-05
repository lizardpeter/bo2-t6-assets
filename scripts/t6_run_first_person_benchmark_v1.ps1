param(
    [Parameter(Mandatory=$false)]
    [string]$ExpandedRoot = $env:T6_EXPANDED_ROOT,

    [Parameter(Mandatory=$false)]
    [string]$OutRoot = "work/nonmap/seal6_mp7_v1",

    [Parameter(Mandatory=$false)]
    [string]$OatFactionSealsRoot,

    [Parameter(Mandatory=$false)]
    [string]$FactionSealsSourceSha256,

    [Parameter(Mandatory=$false)]
    [string]$OatCommonMpRoot,

    [Parameter(Mandatory=$false)]
    [string]$CommonMpSourceSha256,

    [Parameter(Mandatory=$false)]
    [string]$Mp7RawXAnimJson,

    [Parameter(Mandatory=$false)]
    [string]$NormalizedMp7XAnimRoot,

    [Parameter(Mandatory=$false)]
    [switch]$SkipStage18DRawRegeneration
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Spec = Join-Path $RepoRoot "manifests/nonmap/benchmarks/seal6_smg_mp7_v1.json"
$RawParser = Join-Path $RepoRoot "tools/t6_raw_xasset_inventory.py"
$RawParserV2 = Join-Path $RepoRoot "tools/t6_raw_xasset_inventory_v2.py"
$CorpusProbeTool = Join-Path $RepoRoot "tools/t6_xmodel_target_corpus_probe_v1.py"
$OatCatalogTool = Join-Path $RepoRoot "tools/t6_oat_xmodel_catalog_v1.py"
$MaterialEdgeTool = Join-Path $RepoRoot "tools/t6_oat_xmodel_material_edges_v1.py"
$PlannerTool = Join-Path $RepoRoot "tools/t6_first_person_bundle_plan_v1.py"
$Stage18DXAnimTool = Join-Path $RepoRoot "tools/stage18d_xanim_raw.py"
$Stage18DAttachmentTool = Join-Path $RepoRoot "tools/stage18d_attachment_unique_models.py"
$CanonicalRootCsv = Join-Path $RepoRoot "manifests/weapons/stage18c/clean_mp_loadout_arsenal.csv"

if (-not $ExpandedRoot) {
    throw "Set -ExpandedRoot or T6_EXPANDED_ROOT to the directory containing retained expanded T6 XFiles. Raw .ff files are not silently treated as expanded streams."
}
$ExpandedRoot = (Resolve-Path $ExpandedRoot).Path
$OutRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $OutRoot))
$ProbeDir = Join-Path $OutRoot "xmodel_probes"
$OatDir = Join-Path $OutRoot "oat"
$RawProofDir = Join-Path $OutRoot "stage18d_raw"
$RawXAnimDir = Join-Path $RawProofDir "xanim"
$RawAttachmentDir = Join-Path $RawProofDir "attachment_models"
New-Item -ItemType Directory -Force -Path $OutRoot, $ProbeDir, $OatDir, $RawProofDir, $RawXAnimDir, $RawAttachmentDir | Out-Null

$SpecDoc = Get-Content -Raw $Spec | ConvertFrom-Json
$ExpectedCommonMpSha = [string]$SpecDoc.retainedRetailEvidence.commonMpExpandedSha256

Write-Host "[1/6] Direct retail XModel target corpus probe"
$CorpusSummary = Join-Path $OutRoot "xmodel_corpus_probe_v1.json"
& python $CorpusProbeTool $ExpandedRoot `
    --glob "*.expanded" `
    --recursive `
    --raw-parser $RawParser `
    --targets $Spec `
    --per-source-outdir $ProbeDir `
    --out $CorpusSummary
$CorpusExit = $LASTEXITCODE
if ($CorpusExit -notin 0,2) { throw "XModel corpus probe failed with exit code $CorpusExit" }

$Corpus = Get-Content -Raw $CorpusSummary | ConvertFrom-Json
$CommonSource = $Corpus.sources | Where-Object { $_.sha256 -eq $ExpectedCommonMpSha } | Select-Object -First 1
$CommonStream = if ($CommonSource) { [string]$CommonSource.path } else { $null }
if ($CommonStream) {
    Write-Host ("Pinned common_mp expanded stream found: {0}" -f $CommonStream)
} else {
    Write-Warning ("Pinned common_mp expanded SHA {0} was not found under ExpandedRoot; Stage 18D raw MP7 regeneration will remain unavailable." -f $ExpectedCommonMpSha)
}

Write-Host "[2/6] Restore Stage 18D raw MP7 proofs from the pinned common_mp stream"
$AttachmentProof = $null
$RegeneratedRawXAnimProof = $null
if ($CommonStream -and -not $SkipStage18DRawRegeneration) {
    $RootProof = Join-Path $RawProofDir "common_mp_weapon_roots_v2.json"
    & python $RawParserV2 $CommonStream `
        --roots $CanonicalRootCsv `
        --out $RootProof
    if ($LASTEXITCODE -ne 0) { throw "v2 raw common_mp root proof failed" }

    & python $Stage18DAttachmentTool `
        --stream $CommonStream `
        --raw-parser $RawParserV2 `
        --roots $RootProof `
        --outdir $RawAttachmentDir
    if ($LASTEXITCODE -ne 0) { throw "Stage 18D WeaponAttachmentUnique -> XModel regeneration failed" }
    $AttachmentProof = Join-Path $RawAttachmentDir "attachment_unique_xmodel_proof.json"

    & python $Stage18DXAnimTool `
        --stream $CommonStream `
        --raw-parser $RawParserV2 `
        --outdir $RawXAnimDir
    if ($LASTEXITCODE -ne 0) { throw "Stage 18D raw XAnim regeneration failed" }
    $RegeneratedRawXAnimProof = Join-Path $RawXAnimDir "xanim_raw_proof.json"
    if (-not $Mp7RawXAnimJson) {
        $Mp7RawXAnimJson = Join-Path $RawXAnimDir "mp7_base_xanim_raw.json"
    }
} elseif ($SkipStage18DRawRegeneration) {
    Write-Host "Stage 18D raw regeneration explicitly skipped."
}

$OatCatalogs = @()
function Add-OatCatalog {
    param(
        [string]$DumpRoot,
        [string]$ZoneName,
        [string]$SourceSha256
    )
    if (-not $DumpRoot) { return }
    if (-not $SourceSha256) { throw "$ZoneName OAT root supplied without the exact source SHA-256" }
    $Catalog = Join-Path $OatDir "$ZoneName`_xmodels_v1.json"
    & python $OatCatalogTool `
        --dump-root $DumpRoot `
        --zone-name $ZoneName `
        --source-sha256 $SourceSha256 `
        --out $Catalog
    $Exit = $LASTEXITCODE
    if ($Exit -notin 0,2) { throw "OAT XModel catalog failed for $ZoneName with exit code $Exit" }
    $script:OatCatalogs += $Catalog

    $Edges = Join-Path $OatDir "$ZoneName`_xmodel_material_edges_v1.json"
    & python $MaterialEdgeTool --xmodel-catalog $Catalog --out $Edges
    $EdgeExit = $LASTEXITCODE
    if ($EdgeExit -notin 0,2) { throw "XModel material-edge extraction failed for $ZoneName with exit code $EdgeExit" }
}

Write-Host "[3/6] Optional pinned-OAT model classification/material edges"
Add-OatCatalog -DumpRoot $OatFactionSealsRoot -ZoneName "faction_seals_mp" -SourceSha256 $FactionSealsSourceSha256
Add-OatCatalog -DumpRoot $OatCommonMpRoot -ZoneName "common_mp" -SourceSha256 $CommonMpSourceSha256

Write-Host "[4/6] Build strict first-person bundle plan"
$PlannerArgs = @(
    $PlannerTool,
    "--spec", $Spec,
    "--out", (Join-Path $OutRoot "bundle_plan_v1.json")
)
Get-ChildItem -Path $ProbeDir -Filter "*_xmodel_probe.json" | Sort-Object FullName | ForEach-Object {
    $PlannerArgs += @("--xmodel-probe", $_.FullName)
}
foreach ($Catalog in $OatCatalogs) {
    $PlannerArgs += @("--oat-xmodel-catalog", $Catalog)
}
if ($Mp7RawXAnimJson) {
    $PlannerArgs += @("--xanim-json", (Resolve-Path $Mp7RawXAnimJson).Path)
}
if ($NormalizedMp7XAnimRoot) {
    $PlannerArgs += @("--xanim-json", (Resolve-Path $NormalizedMp7XAnimRoot).Path)
}
& python @PlannerArgs
$PlanExit = $LASTEXITCODE
if ($PlanExit -notin 0,2) { throw "Bundle planner failed with exit code $PlanExit" }

Write-Host "[5/6] Verify regenerated raw MP7 canaries when present"
if ($CommonStream -and -not $SkipStage18DRawRegeneration) {
    if (-not (Test-Path $RegeneratedRawXAnimProof)) {
        throw "Stage 18D raw XAnim proof was not emitted at the expected historical filename"
    }
    $Regenerated = Get-Content -Raw $RegeneratedRawXAnimProof | ConvertFrom-Json
    if ([string]$Regenerated.expanded_stream_sha256 -ne $ExpectedCommonMpSha) {
        throw "Regenerated XAnim proof source SHA does not match benchmark common_mp SHA"
    }
    if ([int]$Regenerated.mp7_base_viewmodel_xanim_records -ne [int]$SpecDoc.retainedRetailEvidence.mp7BaseViewmodelRecords) {
        throw "Regenerated MP7 family count disagrees with retained benchmark"
    }
    if (-not [bool]$Regenerated.mp7_all_walk_status_exact) {
        throw "Regenerated MP7 raw XAnim family contains a non-exact walk"
    }
    if (-not [bool]$Regenerated.mp7_consecutive_boundaries_exact) {
        throw "Regenerated MP7 raw XAnim family has a non-exact consecutive boundary"
    }
    $Reload = $Regenerated.mp7_reload_canary
    if (-not $Reload -or [string]$Reload.name -ne "viewmodel_mp7_reload") {
        throw "Regenerated MP7 reload canary is absent or has the wrong identity"
    }
    if ([int]$Reload.raw_struct_offset -ne [int]$SpecDoc.retainedRetailEvidence.reloadCanary.rawStructOffset) {
        throw "Regenerated viewmodel_mp7_reload raw offset disagrees with retained canary"
    }
    if ([string]$Reload.walk.exact_serialized_sha256 -ne [string]$SpecDoc.retainedRetailEvidence.reloadCanary.serializedSha256) {
        throw "Regenerated viewmodel_mp7_reload serialized SHA disagrees with retained canary"
    }
    if (-not (Test-Path $AttachmentProof)) {
        throw "Stage 18D attachment XModel proof was not emitted"
    }
    Write-Host "Stage 18D MP7 raw animation and attachment-model proofs reproduced against the pinned stream."
}

Write-Host "[6/6] Benchmark checkpoint"
$Summary = Get-Content -Raw (Join-Path $OutRoot "bundle_plan_v1.json") | ConvertFrom-Json
Write-Host ("Expanded streams scanned: {0}" -f $Corpus.summary.streamsScanned)
Write-Host ("Required XModels found somewhere: {0}/{1}" -f $Corpus.summary.resolvedRequiredTargets, $Corpus.summary.requiredTargets)
Write-Host ("Retail identity gate: {0}" -f $Summary.summary.retailIdentityGate)
Write-Host ("Model class gate: {0}" -f $Summary.summary.modelClassGate)
Write-Host ("Normalized animation gate: {0}" -f $Summary.summary.normalizedAnimationGate)
Write-Host ("Ready for bundle export: {0}" -f $Summary.summary.readyForBundleExport)
if ($AttachmentProof) { Write-Host ("Raw MP7 attachment-model proof: {0}" -f $AttachmentProof) }
if ($RegeneratedRawXAnimProof) { Write-Host ("Raw MP7 XAnim proof: {0}" -f $RegeneratedRawXAnimProof) }
Write-Host ("Outputs: {0}" -f $OutRoot)

# Exit 2 means the pipeline ran correctly but the benchmark still has explicit
# unresolved proof gates. That is expected during reversal and must not be
# confused with a parser/tool crash.
exit $PlanExit

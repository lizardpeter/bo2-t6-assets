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
    [string]$NormalizedMp7XAnimRoot
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Spec = Join-Path $RepoRoot "manifests/nonmap/benchmarks/seal6_smg_mp7_v1.json"
$RawParser = Join-Path $RepoRoot "tools/t6_raw_xasset_inventory.py"
$CorpusProbeTool = Join-Path $RepoRoot "tools/t6_xmodel_target_corpus_probe_v1.py"
$OatCatalogTool = Join-Path $RepoRoot "tools/t6_oat_xmodel_catalog_v1.py"
$MaterialEdgeTool = Join-Path $RepoRoot "tools/t6_oat_xmodel_material_edges_v1.py"
$PlannerTool = Join-Path $RepoRoot "tools/t6_first_person_bundle_plan_v1.py"

if (-not $ExpandedRoot) {
    throw "Set -ExpandedRoot or T6_EXPANDED_ROOT to the directory containing retained expanded T6 XFiles. Raw .ff files are not silently treated as expanded streams."
}
$ExpandedRoot = (Resolve-Path $ExpandedRoot).Path
$OutRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $OutRoot))
$ProbeDir = Join-Path $OutRoot "xmodel_probes"
$OatDir = Join-Path $OutRoot "oat"
New-Item -ItemType Directory -Force -Path $OutRoot, $ProbeDir, $OatDir | Out-Null

Write-Host "[1/4] Direct retail XModel target corpus probe"
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

Write-Host "[2/4] Optional pinned-OAT model classification/material edges"
Add-OatCatalog -DumpRoot $OatFactionSealsRoot -ZoneName "faction_seals_mp" -SourceSha256 $FactionSealsSourceSha256
Add-OatCatalog -DumpRoot $OatCommonMpRoot -ZoneName "common_mp" -SourceSha256 $CommonMpSourceSha256

Write-Host "[3/4] Build strict first-person bundle plan"
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

Write-Host "[4/4] Benchmark checkpoint"
$Summary = Get-Content -Raw (Join-Path $OutRoot "bundle_plan_v1.json") | ConvertFrom-Json
$Corpus = Get-Content -Raw $CorpusSummary | ConvertFrom-Json
Write-Host ("Expanded streams scanned: {0}" -f $Corpus.summary.streamsScanned)
Write-Host ("Required XModels found somewhere: {0}/{1}" -f $Corpus.summary.resolvedRequiredTargets, $Corpus.summary.requiredTargets)
Write-Host ("Retail identity gate: {0}" -f $Summary.summary.retailIdentityGate)
Write-Host ("Model class gate: {0}" -f $Summary.summary.modelClassGate)
Write-Host ("Normalized animation gate: {0}" -f $Summary.summary.normalizedAnimationGate)
Write-Host ("Ready for bundle export: {0}" -f $Summary.summary.readyForBundleExport)
Write-Host ("Outputs: {0}" -f $OutRoot)

# Exit 2 means the pipeline ran correctly but the benchmark still has explicit
# unresolved proof gates. That is expected during reversal and must not be
# confused with a parser/tool crash.
exit $PlanExit

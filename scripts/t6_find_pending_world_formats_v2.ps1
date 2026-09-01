param(
    [Parameter(Mandatory = $true)]
    [string]$GameRoot,

    [Parameter(Mandatory = $true)]
    [string]$StandaloneProjectRoot,

    [string]$OutputRoot = "",
    [string]$OatUnlinker = "",
    [ValidateRange(1, 64)]
    [int]$Workers = 2,
    [string]$Python = "py",
    [string[]]$Map,
    [ValidateRange(1, 31)]
    [int]$MaxMaps = 31,
    [switch]$IncludeKnownCompleted,
    [switch]$KeepNoHitArchives
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$Path
    )
    $json = $Value | ConvertTo-Json -Depth 40
    [System.IO.File]::WriteAllText(
        $Path,
        $json + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Get-PythonPrefix {
    param([Parameter(Mandatory = $true)][string]$Executable)
    $leaf = [System.IO.Path]::GetFileNameWithoutExtension($Executable).ToLowerInvariant()
    if ($leaf -eq "py") { return @("-3") }
    return @()
}

function Resolve-UnderRoot {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Relative
    )
    $relativeNative = $Relative.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
    $candidate = [System.IO.Path]::GetFullPath((Join-Path $Root $relativeNative))
    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $candidate.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Retail target path escapes GameRoot: $Relative"
    }
    return $candidate
}

function Get-TargetMapEntry {
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [Parameter(Mandatory = $true)][string]$Zone
    )
    $matches = @($Manifest.maps | Where-Object { [string]$_.zone -eq $Zone })
    if ($matches.Count -ne 1) {
        throw "Expected exactly one retail target entry for '$Zone'; found $($matches.Count)."
    }
    return $matches[0]
}

function Test-KnownCompleted {
    param(
        [Parameter(Mandatory = $true)]$Manifest,
        [Parameter(Mandatory = $true)][string]$Zone
    )
    $property = @(
        $Manifest.knownCompleted.PSObject.Properties |
            Where-Object { $_.Name -eq $Zone }
    )
    return $property.Count -gt 0
}

function Get-CandidateArtifactInventory {
    param([Parameter(Mandatory = $true)][string]$Root)
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) { return @() }
    $interesting = Get-ChildItem -LiteralPath $Root -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match '(?i)(\.layout\.json$|\.t6world\.json$|vd0|vd1|surfaces|material|technique|prefix|gfxworld)'
        } |
        Sort-Object FullName
    $rows = @()
    foreach ($file in $interesting) {
        $rows += [ordered]@{ path = $file.FullName; bytes = [int64]$file.Length }
    }
    return $rows
}

$RepoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$TargetsPath = Join-Path $RepoRoot "manifests\world\T6_RETAIL_MP_WORLD_FORMAT_TARGETS_V1.json"
$BaselineCensusPath = Join-Path $RepoRoot "manifests\world\T6_WORLD_VERTEX_FORMAT_CENSUS_V1.json"
$ScannerPath = Join-Path $RepoRoot "tools\t6_world_layout_target_scan_v1.py"
$Stage2Path = Join-Path $RepoRoot "tools\t6_world_vd1_layout_census_v1.py"
$RegistryBuilderPath = Join-Path $RepoRoot "tools\t6_world_vertex_format_registry_v1.py"

foreach ($required in @($TargetsPath, $BaselineCensusPath, $ScannerPath, $Stage2Path, $RegistryBuilderPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Missing required format-hunt component: $required"
    }
}

$GameRootResolved = (Resolve-Path -LiteralPath $GameRoot).Path
$StandaloneRootResolved = (Resolve-Path -LiteralPath $StandaloneProjectRoot).Path
$StandaloneRunner = Join-Path $StandaloneRootResolved "scripts\run_windows.ps1"
if (-not (Test-Path -LiteralPath $StandaloneRunner -PathType Leaf)) {
    throw "Standalone extractor runner not found: $StandaloneRunner"
}

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path (Get-Location).Path "T6_WORLD_FORMAT_HUNT_V2"
}
$OutputRootFull = [System.IO.Path]::GetFullPath($OutputRoot)
[System.IO.Directory]::CreateDirectory($OutputRootFull) | Out-Null
$RunId = Get-Date -Format "yyyyMMdd_HHmmss"
$RunRoot = Join-Path $OutputRootFull $RunId
$ArchiveRoot = Join-Path $RunRoot "archives"
$ResultRoot = Join-Path $RunRoot "results"
[System.IO.Directory]::CreateDirectory($ArchiveRoot) | Out-Null
[System.IO.Directory]::CreateDirectory($ResultRoot) | Out-Null

$targets = Get-Content -Raw -LiteralPath $TargetsPath | ConvertFrom-Json
if ([string]$targets.format -ne "t6-retail-mp-world-format-targets-v1") {
    throw "Unexpected target manifest format: $($targets.format)"
}
if (@($targets.maps).Count -ne 31) {
    throw "Retail target manifest must contain exactly 31 MP fastfiles; found $(@($targets.maps).Count)."
}
$targetFormats = @($targets.targetFormats | ForEach-Object { [int]$_ })
if (($targetFormats -join ',') -ne '4,5,7,8') {
    throw "Unexpected pending format set: $($targetFormats -join ',')"
}

$requestedZones = if ($null -ne $Map -and $Map.Count -gt 0) {
    @($Map)
} else {
    @($targets.scanOrder | ForEach-Object { [string]$_ })
}
$seenRequested = @{}
$scanZones = @()
foreach ($zone in $requestedZones) {
    if ([string]::IsNullOrWhiteSpace($zone) -or $seenRequested.ContainsKey($zone)) { continue }
    $null = Get-TargetMapEntry -Manifest $targets -Zone $zone
    $seenRequested[$zone] = $true
    if ((Test-KnownCompleted -Manifest $targets -Zone $zone) -and -not $IncludeKnownCompleted) {
        Write-Host "Skipping already-proven map $zone"
        continue
    }
    $scanZones += $zone
}
if ($scanZones.Count -eq 0) { throw "No maps remain to scan after filtering." }
if ($scanZones.Count -gt $MaxMaps) {
    $scanZones = @($scanZones | Select-Object -First $MaxMaps)
}

$PowerShellExe = (Get-Process -Id $PID).Path
if ([string]::IsNullOrWhiteSpace($PowerShellExe) -or -not (Test-Path -LiteralPath $PowerShellExe -PathType Leaf)) {
    throw "Could not resolve current PowerShell executable for isolated standalone runs."
}
$PythonPrefix = @(Get-PythonPrefix -Executable $Python)
$results = @()
$rawCensusPaths = @()
$completeRegistry = $null
$latestRegistryPath = $null

Write-Host "============================================================"
Write-Host "T6 RETAIL WORLD FORMAT HUNT V2 - STAGE 1 + STAGE 2 + PROMOTION"
Write-Host "============================================================"
Write-Host "Game root       : $GameRootResolved"
Write-Host "Standalone root : $StandaloneRootResolved"
Write-Host "Run root        : $RunRoot"
Write-Host "Pending formats : $($targetFormats -join ', ')"
Write-Host "Map count       : $($scanZones.Count)"
Write-Host "First map       : $($scanZones[0])"
Write-Host ""

foreach ($zone in $scanZones) {
    $entry = Get-TargetMapEntry -Manifest $targets -Zone $zone
    $ffPath = Resolve-UnderRoot -Root $GameRootResolved -Relative ([string]$entry.path)
    if (-not (Test-Path -LiteralPath $ffPath -PathType Leaf)) {
        throw "Missing retail fastfile for $zone`: $ffPath"
    }
    $item = Get-Item -LiteralPath $ffPath
    $actualBytes = [int64]$item.Length
    $expectedBytes = [int64]$entry.bytes
    if ($actualBytes -ne $expectedBytes) {
        throw "$zone retail byte-count mismatch: expected $expectedBytes, got $actualBytes ($ffPath)"
    }
    Write-Host "[$zone] hashing retail FF..."
    $actualSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ffPath).Hash.ToLowerInvariant()
    $expectedSha = ([string]$entry.sha256).ToLowerInvariant()
    if ($actualSha -ne $expectedSha) {
        throw "$zone retail SHA-256 mismatch: expected $expectedSha, got $actualSha ($ffPath)"
    }

    $zoneArchive = Join-Path $ArchiveRoot $zone
    [System.IO.Directory]::CreateDirectory($zoneArchive) | Out-Null
    Write-Host "[$zone] retail identity verified; running standalone extraction..."
    $runnerArgs = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $StandaloneRunner,
        "-GameRoot", $GameRootResolved, "-Output", $zoneArchive,
        "-Workers", [string]$Workers, "-Zone", $zone,
        "-PreserveMethod", "none", "-Python", $Python
    )
    if (-not [string]::IsNullOrWhiteSpace($OatUnlinker)) {
        $runnerArgs += @("-OatUnlinker", (Resolve-Path -LiteralPath $OatUnlinker).Path)
    }
    & $PowerShellExe @runnerArgs
    $extractExit = $LASTEXITCODE
    if ($extractExit -ne 0) {
        $failure = [ordered]@{
            zone=$zone; status="extraction-failed";
            ff=[ordered]@{path=$ffPath;bytes=$actualBytes;sha256=$actualSha;verified=$true};
            standaloneExitCode=$extractExit; archive=$zoneArchive
        }
        $results += $failure
        Write-JsonFile -Value $failure -Path (Join-Path $ResultRoot "$zone.failure.json")
        throw "$zone standalone extraction failed with exit code $extractExit"
    }

    $scanPath = Join-Path $ResultRoot "$zone.layout_target_scan_v1.json"
    Write-Host "[$zone] Stage 1: scanning layout audit for pending formats..."
    $scannerArgs = @($ScannerPath, $zoneArchive, "--map", $zone, "--out", $scanPath)
    foreach ($fmt in $targetFormats) { $scannerArgs += @("--target-format", [string]$fmt) }
    & $Python @PythonPrefix @scannerArgs
    $scanExit = $LASTEXITCODE
    if (-not (Test-Path -LiteralPath $scanPath -PathType Leaf)) {
        throw "$zone Stage-1 scanner did not write its result manifest."
    }
    $scan = Get-Content -Raw -LiteralPath $scanPath | ConvertFrom-Json
    $row = [ordered]@{
        zone=$zone; ff=[ordered]@{path=$ffPath;bytes=$actualBytes;sha256=$actualSha;verified=$true};
        standaloneExitCode=$extractExit; layoutScannerExitCode=$scanExit;
        observedFormats=@($scan.observedFormats | ForEach-Object {[int]$_});
        targetHits=@($scan.targetHits | ForEach-Object {[int]$_});
        matchedLayoutFileCount=[int]$scan.matchedLayoutFileCount;
        scanManifest=$scanPath; archive=$zoneArchive;
        rawStrideByteProofCompleted=$false; stage2ExitCode=$null;
        stage2Census=$null; registryCandidate=$null; registryPendingFormats=$null;
        archiveRemovedAfterNoHit=$false; status=$null
    }
    $results += $row

    if ($scanExit -eq 1) {
        $row["status"] = "scanned-no-target"
        Write-Host "[$zone] no pending format observed; formats: $($row.observedFormats -join ', ')"
        if (-not $KeepNoHitArchives) {
            Remove-Item -LiteralPath $zoneArchive -Recurse -Force
            $row["archiveRemovedAfterNoHit"] = $true
        }
        continue
    }
    if ($scanExit -ne 0) {
        $row["status"] = "stage1-not-proof-safe"
        throw "$zone Stage-1 layout scan failed proof-safely (exit $scanExit)"
    }

    $row["status"] = "stage1-target-observed"
    $inventoryPath = Join-Path $ResultRoot "$zone.stage2_candidate_artifacts_v1.json"
    Write-JsonFile -Value ([ordered]@{
        format="t6-world-format-stage2-candidate-artifacts-v1"; zone=$zone;
        targetHits=@($row.targetHits); archive=$zoneArchive;
        artifacts=@(Get-CandidateArtifactInventory -Root $zoneArchive);
        proofBoundary="Stage 1 observes a pending format only. Stage 2 must independently prove raw vd1 allocation stride."
    }) -Path $inventoryPath

    Write-Host "[$zone] Stage 2: deriving raw vd1 allocation stride directly from layout + bytes..."
    $stage2Out = Join-Path $ResultRoot "$zone.vd1_layout_census_v1.json"
    $stage2Args = @(
        $Stage2Path, "--map", $zone, "--archive", $zoneArchive, "--out", $stage2Out
    )
    foreach ($fmt in $targetFormats) { $stage2Args += @("--target-format", [string]$fmt) }
    & $Python @PythonPrefix @stage2Args
    $stage2Exit = $LASTEXITCODE
    $row["stage2ExitCode"] = $stage2Exit
    if (-not (Test-Path -LiteralPath $stage2Out -PathType Leaf)) {
        $row["status"] = "stage2-no-census-output"
        $row["stage2Census"] = $null
        Write-Host "[$zone] Stage 2 could not produce a proof census; archive retained for inspection."
        continue
    }
    $row["stage2Census"] = $stage2Out
    $stage2 = Get-Content -Raw -LiteralPath $stage2Out | ConvertFrom-Json
    if ($stage2Exit -eq 2 -or @($stage2.blockers).Count -gt 0) {
        $row["status"] = "stage2-ambiguous-or-blocked"
        Write-Host "[$zone] Stage 2 retained blockers; trying another retail map."
        continue
    }
    if ($stage2Exit -ne 0) {
        $row["status"] = "stage2-no-pending-raw-hit"
        Write-Host "[$zone] Stage 1 hit did not yield a clean pending raw allocation; trying another map."
        continue
    }

    $row["rawStrideByteProofCompleted"] = $true
    $row["status"] = "stage2-raw-stride-proven"
    $rawCensusPaths += $stage2Out
    Write-Host "[$zone] clean Stage-2 raw stride evidence retained."

    $registryOut = Join-Path $ResultRoot "T6_WORLD_VERTEX_FORMAT_REGISTRY_CANDIDATE_V1.json"
    $registryArgs = @(
        $RegistryBuilderPath, "--baseline", $BaselineCensusPath, "--out", $registryOut
    )
    foreach ($rawPath in $rawCensusPaths) { $registryArgs += @("--raw-census", $rawPath) }
    Write-Host "[$zone] rebuilding authoritative candidate registry..."
    & $Python @PythonPrefix @registryArgs
    $registryExit = $LASTEXITCODE
    if (-not (Test-Path -LiteralPath $registryOut -PathType Leaf)) {
        throw "$zone registry builder did not write a candidate registry."
    }
    $registry = Get-Content -Raw -LiteralPath $registryOut | ConvertFrom-Json
    $latestRegistryPath = $registryOut
    $row["registryCandidate"] = $registryOut
    $row["registryPendingFormats"] = @($registry.coverage.pendingFormats | ForEach-Object {[int]$_})

    if ($registryExit -eq 3 -or [int]$registry.coverage.contradictedCount -gt 0) {
        $row["status"] = "registry-contradiction"
        throw "$zone produced contradictory retail world-format stride evidence; refusing promotion"
    }
    if ([bool]$registry.coverage.allFormatsExportEnabled) {
        $row["status"] = "all-nine-formats-export-enabled"
        $completeRegistry = $registry
        Write-Host "[$zone] ALL 9 WORLD VERTEX FORMATS ARE NOW EXPORT-ENABLED."
        break
    }

    Write-Host "[$zone] registry now enables $($registry.coverage.exportEnabledCount)/9; remaining: $($row.registryPendingFormats -join ', ')"
}

$allNine = $null -ne $completeRegistry
$summary = [ordered]@{
    format="t6-retail-world-format-hunt-v2"; runId=$RunId;
    gameRoot=$GameRootResolved; standaloneProjectRoot=$StandaloneRootResolved;
    retailTargetManifest=$TargetsPath; baselineCensus=$BaselineCensusPath;
    originalPendingFormats=@($targetFormats); scanOrder=@($scanZones);
    scannedMapCount=$results.Count; rawCensusCount=$rawCensusPaths.Count;
    rawCensuses=@($rawCensusPaths); latestRegistry=$latestRegistryPath;
    allNineFormatsExportEnabled=$allNine;
    remainingFormats=if ($allNine) {@()} elseif ($null -ne $latestRegistryPath) {
        @((Get-Content -Raw -LiteralPath $latestRegistryPath | ConvertFrom-Json).coverage.pendingFormats | ForEach-Object {[int]$_})
    } else {@($targetFormats)};
    results=@($results);
    proofBoundary="Stage 1 is layout observation. Stage 2 is exact raw vd1 allocation-stride proof. Registry promotion requires clean expected stride and zero contradictory clean fixtures. Packed normalTransform shader meaning remains a separate renderer-semantic proof."
}
$summaryPath = Join-Path $RunRoot "T6_RETAIL_WORLD_FORMAT_HUNT_V2.json"
Write-JsonFile -Value $summary -Path $summaryPath

Write-Host ""
Write-Host "============================================================"
if ($allNine) {
    Write-Host "WORLD FORMAT CLOSURE: 9/9 EXPORT-ENABLED"
    Write-Host "Candidate registry: $latestRegistryPath"
} else {
    Write-Host "WORLD FORMAT CLOSURE INCOMPLETE"
    Write-Host "Remaining formats : $($summary.remainingFormats -join ', ')"
    if ($null -ne $latestRegistryPath) { Write-Host "Latest registry   : $latestRegistryPath" }
}
Write-Host "Run ledger         : $summaryPath"
Write-Host "============================================================"

if ($allNine) { exit 0 }
exit 1

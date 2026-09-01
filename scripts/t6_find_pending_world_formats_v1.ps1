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
    $json = $Value | ConvertTo-Json -Depth 32
    [System.IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
}

function Get-PythonPrefix {
    param([Parameter(Mandatory = $true)][string]$Executable)
    $leaf = [System.IO.Path]::GetFileNameWithoutExtension($Executable).ToLowerInvariant()
    if ($leaf -eq "py") {
        return @("-3")
    }
    return @()
}

function Resolve-UnderRoot {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Relative
    )
    $relativeNative = $Relative.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
    $candidate = [System.IO.Path]::GetFullPath((Join-Path $Root $relativeNative))
    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
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
    $property = @($Manifest.knownCompleted.PSObject.Properties | Where-Object { $_.Name -eq $Zone })
    return $property.Count -gt 0
}

function Get-CandidateArtifactInventory {
    param([Parameter(Mandatory = $true)][string]$Root)
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        return @()
    }
    $interesting = Get-ChildItem -LiteralPath $Root -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match '(?i)(\.layout\.json$|\.t6world\.json$|vd0|vd1|surfaces|material|technique|prefix|gfxworld)'
        } |
        Sort-Object FullName
    $rows = @()
    foreach ($file in $interesting) {
        $rows += [ordered]@{
            path = $file.FullName
            bytes = [int64]$file.Length
        }
    }
    return $rows
}

$RepoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$TargetsPath = Join-Path $RepoRoot "manifests\world\T6_RETAIL_MP_WORLD_FORMAT_TARGETS_V1.json"
$ScannerPath = Join-Path $RepoRoot "tools\t6_world_layout_target_scan_v1.py"

if (-not (Test-Path -LiteralPath $TargetsPath -PathType Leaf)) {
    throw "Missing retail target manifest: $TargetsPath"
}
if (-not (Test-Path -LiteralPath $ScannerPath -PathType Leaf)) {
    throw "Missing layout target scanner: $ScannerPath"
}

$GameRootResolved = (Resolve-Path -LiteralPath $GameRoot).Path
$StandaloneRootResolved = (Resolve-Path -LiteralPath $StandaloneProjectRoot).Path
$StandaloneRunner = Join-Path $StandaloneRootResolved "scripts\run_windows.ps1"
if (-not (Test-Path -LiteralPath $StandaloneRunner -PathType Leaf)) {
    throw "Standalone extractor runner not found: $StandaloneRunner"
}

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path (Get-Location).Path "T6_WORLD_FORMAT_HUNT_V1"
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
    if ([string]::IsNullOrWhiteSpace($zone)) {
        continue
    }
    if ($seenRequested.ContainsKey($zone)) {
        continue
    }
    $null = Get-TargetMapEntry -Manifest $targets -Zone $zone
    $seenRequested[$zone] = $true
    if ((Test-KnownCompleted -Manifest $targets -Zone $zone) -and -not $IncludeKnownCompleted) {
        Write-Host "Skipping already-proven map $zone"
        continue
    }
    $scanZones += $zone
}

if ($scanZones.Count -eq 0) {
    throw "No maps remain to scan after filtering."
}
if ($scanZones.Count -gt $MaxMaps) {
    $scanZones = @($scanZones | Select-Object -First $MaxMaps)
}

$PowerShellExe = (Get-Process -Id $PID).Path
if ([string]::IsNullOrWhiteSpace($PowerShellExe) -or -not (Test-Path -LiteralPath $PowerShellExe -PathType Leaf)) {
    throw "Could not resolve current PowerShell executable for isolated standalone runs."
}

$PythonPrefix = @(Get-PythonPrefix -Executable $Python)
$results = @()
$targetCandidate = $null

Write-Host "============================================================"
Write-Host "T6 RETAIL WORLD FORMAT HUNT V1"
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
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $StandaloneRunner,
        "-GameRoot", $GameRootResolved,
        "-Output", $zoneArchive,
        "-Workers", [string]$Workers,
        "-Zone", $zone,
        "-PreserveMethod", "none",
        "-Python", $Python
    )
    if (-not [string]::IsNullOrWhiteSpace($OatUnlinker)) {
        $oatResolved = (Resolve-Path -LiteralPath $OatUnlinker).Path
        $runnerArgs += @("-OatUnlinker", $oatResolved)
    }

    & $PowerShellExe @runnerArgs
    $extractExit = $LASTEXITCODE
    if ($extractExit -ne 0) {
        $failure = [ordered]@{
            zone = $zone
            status = "extraction-failed"
            ff = [ordered]@{
                path = $ffPath
                bytes = $actualBytes
                sha256 = $actualSha
                verified = $true
            }
            standaloneExitCode = $extractExit
            archive = $zoneArchive
        }
        $results += $failure
        Write-JsonFile -Value $failure -Path (Join-Path $ResultRoot "$zone.failure.json")
        throw "$zone standalone extraction failed with exit code $extractExit"
    }

    $scanPath = Join-Path $ResultRoot "$zone.layout_target_scan_v1.json"
    Write-Host "[$zone] scanning layout audit for observed formats..."
    $scannerArgs = @($ScannerPath, $zoneArchive, "--map", $zone, "--out", $scanPath)
    foreach ($fmt in $targetFormats) {
        $scannerArgs += @("--target-format", [string]$fmt)
    }
    & $Python @PythonPrefix @scannerArgs
    $scanExit = $LASTEXITCODE

    if (-not (Test-Path -LiteralPath $scanPath -PathType Leaf)) {
        throw "$zone layout scanner did not write its result manifest."
    }
    $scan = Get-Content -Raw -LiteralPath $scanPath | ConvertFrom-Json

    $status = switch ($scanExit) {
        0 { "target-format-observed" }
        1 { "scanned-no-target" }
        2 { "no-matching-layout" }
        3 { "layout-parse-error" }
        default { "layout-scanner-failed" }
    }

    $row = [ordered]@{
        zone = $zone
        status = $status
        ff = [ordered]@{
            path = $ffPath
            bytes = $actualBytes
            sha256 = $actualSha
            verified = $true
        }
        standaloneExitCode = $extractExit
        layoutScannerExitCode = $scanExit
        observedFormats = @($scan.observedFormats | ForEach-Object { [int]$_ })
        targetHits = @($scan.targetHits | ForEach-Object { [int]$_ })
        matchedLayoutFileCount = [int]$scan.matchedLayoutFileCount
        scanManifest = $scanPath
        archive = $zoneArchive
        rawStrideByteProofCompleted = $false
    }
    $results += $row

    if ($scanExit -eq 0) {
        $inventoryPath = Join-Path $ResultRoot "$zone.stage2_candidate_artifacts_v1.json"
        $inventory = [ordered]@{
            format = "t6-world-format-stage2-candidate-artifacts-v1"
            zone = $zone
            targetHits = @($row.targetHits)
            archive = $zoneArchive
            artifacts = @(Get-CandidateArtifactInventory -Root $zoneArchive)
            proofBoundary = "Stage 1 only proves that a pending worldVertFormat is observed in a retail layout audit. Raw vd1 allocation stride/field semantics are not promoted until Stage 2 byte analysis succeeds."
        }
        Write-JsonFile -Value $inventory -Path $inventoryPath
        $row["stage2CandidateInventory"] = $inventoryPath
        $targetCandidate = $row
        Write-Host "[$zone] TARGET FORMAT OBSERVED: $($row.targetHits -join ', ')"
        Write-Host "[$zone] keeping archive for Stage 2 raw vd1 proof: $zoneArchive"
        break
    }

    if ($scanExit -eq 1) {
        Write-Host "[$zone] observed formats: $($row.observedFormats -join ', ') -- no pending target"
        if (-not $KeepNoHitArchives) {
            Write-Host "[$zone] removing bulky no-hit extraction; result manifest remains retained"
            Remove-Item -LiteralPath $zoneArchive -Recurse -Force
            $row["archiveRemovedAfterNoHit"] = $true
        } else {
            $row["archiveRemovedAfterNoHit"] = $false
        }
        continue
    }

    Write-Host "[$zone] scanner status '$status' is not proof-safe; stopping."
    throw "$zone layout scan did not complete safely (exit $scanExit, status $status)"
}

$summary = [ordered]@{
    format = "t6-retail-world-format-hunt-v1"
    runId = $RunId
    gameRoot = $GameRootResolved
    standaloneProjectRoot = $StandaloneRootResolved
    retailTargetManifest = $TargetsPath
    pendingFormats = @($targetFormats)
    scanOrder = @($scanZones)
    scannedMapCount = $results.Count
    targetCandidateFound = $null -ne $targetCandidate
    targetCandidate = $targetCandidate
    results = @($results)
    proofBoundary = "A Stage-1 hit means a hash-verified retail map layout strongly observes format 4/5/7/8. It does not by itself prove the raw vd1 stride or semantic field layout. Stage-2 byte proof remains mandatory before decoder promotion."
}
$summaryPath = Join-Path $RunRoot "T6_RETAIL_WORLD_FORMAT_HUNT_V1.json"
Write-JsonFile -Value $summary -Path $summaryPath

Write-Host ""
Write-Host "============================================================"
if ($null -ne $targetCandidate) {
    Write-Host "FOUND STAGE-2 CANDIDATE: $($targetCandidate.zone)"
    Write-Host "Target formats            : $($targetCandidate.targetHits -join ', ')"
    Write-Host "Archive retained          : $($targetCandidate.archive)"
    Write-Host "Raw stride proof complete : NO"
} else {
    Write-Host "NO PENDING FORMAT FOUND IN SCANNED MAPS"
}
Write-Host "Run ledger: $summaryPath"
Write-Host "============================================================"

if ($null -ne $targetCandidate) {
    exit 0
}
exit 1

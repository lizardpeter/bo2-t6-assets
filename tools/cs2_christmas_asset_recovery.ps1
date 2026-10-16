# Public GitHub-hosted, anonymous Steam source recovery.
# No PAT, private Rust-test checkout, paid GitHub-hosted private minutes,
# third-party runner, or privileged GitHub secrets.
param([ValidateRange(1,200)][int]$MaxSegments=120)
$ErrorActionPreference = 'Stop'
$root = Join-Path $env:RUNNER_TEMP 'cs2-source-recovery'
$ready = Join-Path $root 'ready-to-extract'
$audit = Join-Path $ready '_CS2-SOURCE-AUDIT'
$tools = Join-Path $root 'steamre'
$base = Join-Path $root 'steam-base'
$log = Join-Path $audit 'runner-log.txt'
foreach ($dir in @($root,$ready,$audit,$tools,$base)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}
function Log([string]$s) {
    $s | Tee-Object -FilePath $log -Append
}
function Run-Python([string[]]$argv) {
    & python 'tools/cs2_christmas_asset_recovery.py' @argv 2>&1 |
        Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        throw "Original Source2 resource inventory failed ($LASTEXITCODE): $($argv -join ' ')"
    }
}
try {
    Log 'Public repo hosted runner: original CS2 workshop resource recovery using anonymous Steam'
    $zip = Join-Path $root 'DepotDownloader.zip'
    Invoke-WebRequest -Uri 'https://github.com/SteamRE/DepotDownloader/releases/download/DepotDownloader_3.4.0/DepotDownloader-windows-x64.zip' -OutFile $zip
    Expand-Archive -LiteralPath $zip -DestinationPath $tools -Force
    $exe = Join-Path $tools 'DepotDownloader.exe'
    if (-not (Test-Path -LiteralPath $exe)) { throw 'Official SteamRE release has no DepotDownloader.exe' }
    function Steam([string[]]$argv) {
        # Deliberately no username or password: Steam determines anonymous
        # entitlement. If denied, fail and retain only diagnostics.
        & $exe @argv 2>&1 | Tee-Object -FilePath $log -Append
        if ($LASTEXITCODE -ne 0) { throw "Steam anonymous download returned $LASTEXITCODE" }
    }
    $plans = @()
    foreach ($id in @('3620630831','3620635379')) {
        Log "Downloading Workshop $id through anonymous Steam"
        $location = Join-Path $root "workshop-$id"
        New-Item -ItemType Directory -Force -Path $location | Out-Null
        Steam -argv @('-app','730','-pubfile',$id,'-dir',$location,'-max-downloads','4')
        $original = @(Get-ChildItem -LiteralPath $location -File -Recurse |
            Where-Object Name -eq ($id + '_dir.vpk') | Select-Object -First 1)
        if ($original.Count -ne 1) { throw "Workshop $id original VPK index unavailable anonymously" }
        $plan = Join-Path $audit "workshop-$id-original-dependencies.json"
        Run-Python -argv @('scan','--workshop',$original[0].FullName,
            '--workshop-id',$id,'--output',$plan)
        $plans += $plan
        # Retain only the dependency census, not the user's already
        # installed multi-GB original Workshop VPKs.
        Remove-Item -LiteralPath $location -Recurse -Force
    }
    Log 'Fetching current original CS2 base pak01_dir.vpk (index only)'
    $list = Join-Path $root 'index.txt'
    'game/csgo/pak01_dir.vpk' | Set-Content -LiteralPath $list -Encoding ascii
    Steam -argv @('-app','730','-depot','2347770',
        '-filelist',$list,'-dir',$base,'-max-downloads','4')
    $index = Join-Path $base 'game/csgo/pak01_dir.vpk'
    if (-not (Test-Path -LiteralPath $index)) {
        throw 'Anonymous Steam access did not provide original CS2 base pak01_dir.vpk'
    }
    $combined = Join-Path $audit 'combined-source-closure.json'
    Run-Python -argv (@('plan','--index',$index,'--plans') + $plans +
        @('--output',$combined))
    Run-Python -argv @('extract','--index',$index,'--plan',$combined,'--output',$ready)
    $failure = [Collections.Generic.List[string]]::new()
    $success = [Collections.Generic.List[int]]::new()
    $totalAttempts = 0
    function Still-Missing([int]$archiveIndex,$report) {
        $key = 'pak01_{0:D3}.vpk' -f $archiveIndex
        $property = $report.archive_resources.PSObject.Properties[$key]
        if (-not $property) { return $false }
        foreach ($identity in @($property.Value)) {
            $parts = $identity -split '\|', 2
            if ($parts.Count -ne 2) { continue }
            $relative = 'cs2-workshop-' + $parts[0] +
                '-vpk/cs2-base-resources/' + $parts[1]
            if (-not (Test-Path -LiteralPath (Join-Path $ready $relative))) {
                return $true
            }
        }
        return $false
    }
    # First pass recovers source VMAT definitions from the Workshop's
    # original authored material names; then scan their RERL/RED2 original
    # texture references for hundreds of required *VTEX* source files.
    for ($phase=0;$phase -lt 3;$phase++) {
        Run-Python -argv (@('extend','--index',$index,'--plan',$combined,
            '--output',$ready,'--workshop-plans') + $plans)
        Run-Python -argv @('extract','--index',$index,'--plan',$combined,'--output',$ready)
        $census = Get-Content -LiteralPath $combined -Raw | ConvertFrom-Json
        $archiveList = @($census.archive_priority)
        Log "Source closure phase ${phase}: $($archiveList.Count) original archive indices; used $totalAttempts/$MaxSegments downloads"
        foreach ($idx in $archiveList) {
            if ($totalAttempts -ge $MaxSegments) { break }
            $number = [int]$idx
            if (-not (Still-Missing $number $census)) { continue }
            $totalAttempts++
            $name = 'pak01_{0:D3}.vpk' -f $number
            $filelist = Join-Path $root 'one-segment.txt'
            ('game/csgo/' + $name) | Set-Content -LiteralPath $filelist -Encoding ascii
            Log "Anonymous Steam base original source segment $totalAttempts/${MaxSegments}: $name"
            try {
                Steam -argv @('-app','730','-depot','2347770',
                    '-filelist',$filelist,'-dir',$base,'-max-downloads','4')
                Run-Python -argv @('extract','--index',$index,'--plan',$combined,
                    '--output',$ready,'--segment',"$number")
                [void]$success.Add($number)
            } catch {
                $errorMessage = "$name : $($_.Exception.Message)"
                [void]$failure.Add($errorMessage)
                Log "Original segment NOT RECOVERED: $errorMessage"
            }
            # The runner stores original source resources in a small overlay
            # and removes large physical VPK chunks after CRC verification.
            $segment = Join-Path (Split-Path -Parent $index) $name
            if (Test-Path -LiteralPath $segment) {
                Remove-Item -LiteralPath $segment -Force
            }
        }
        if ($totalAttempts -ge $MaxSegments) { break }
    }
    $census = Get-Content -LiteralPath $combined -Raw | ConvertFrom-Json
    $remaining = @($census.archive_priority | Where-Object {
        Still-Missing ([int]$_) $census
    } | ForEach-Object { 'pak01_{0:D3}.vpk' -f [int]$_ })
    $remaining | Set-Content -LiteralPath (Join-Path $audit 'remaining-original-base-archives.txt')
    $failure | Set-Content -LiteralPath (Join-Path $audit 'anonymous-steam-failures.txt')
    $originals = @(Get-ChildItem -LiteralPath $ready -Recurse -File |
        Where-Object { $_.FullName -like '*cs2-base-resources*' })
    $textures = @($originals | Where-Object Name -like '*.vtex_c')
    $materials = @($originals | Where-Object Name -like '*.vmat_c')
    $summary = @(
        'Public hosted GitHub Actions original Source2 asset recovery',
        'Workshop IDs: 3620630831 / 3620635379',
        "Anonymous source segments downloaded and checked: $($success.Count)",
        "Anonymous source segments failed: $($failure.Count)",
        "Source segments still unresolved: $($remaining.Count)",
        "Original compiled VMATs recovered: $($materials.Count)",
        "Original compiled VTEXs recovered: $($textures.Count)",
        'Files under cs2-workshop-<id>-vpk/cs2-base-resources/ are original compiled assets',
        'These original compiled resources passed the current Steam pak01_dir.vpk CRC',
        'Source-material coverage is partial: compressed KV3 references may not be scanned',
        'All recovered VTEX dependencies were read from real source VMAT metadata',
        'Extract artifact folders into Windows Downloads; original Workshop VPKs are untouched',
        'The _CS2-SOURCE-AUDIT folder includes exact per-source names and missing paths'
    )
    $summary | Set-Content -LiteralPath (Join-Path $audit 'README.txt')
    $summary | ForEach-Object { Log $_ }
} catch {
    Log "ERROR: $($_.Exception.Message)"
    $global:LASTEXITCODE = 1
    throw
}

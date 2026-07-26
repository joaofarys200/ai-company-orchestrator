param(
    [Parameter(Mandatory = $true)][string]$CheckpointPath,
    [Parameter(Mandatory = $true)][string]$ShardsPath,
    [Parameter(Mandatory = $true)][string]$ResultPath,
    [Parameter(Mandatory = $true)][string]$TelemetryPath
)

$ErrorActionPreference = 'Stop'
$started = Get-Date
$drive = [System.IO.DriveInfo]::new([System.IO.Path]::GetPathRoot($CheckpointPath))
$knownDone = @{}
$knownWeights = @{}
$peakRamBytes = 0L
$peakVramMiB = 0
$lastSignature = ''

Get-ChildItem -LiteralPath $CheckpointPath -File -Filter 'model-*.safetensors' -ErrorAction SilentlyContinue |
    ForEach-Object { $knownWeights[$_.Name] = $true }

function Measure-Files([string]$Path, [string]$Filter) {
    $files = @(Get-ChildItem -LiteralPath $Path -Recurse -File -Filter $Filter -ErrorAction SilentlyContinue)
    $bytes = ($files | Measure-Object Length -Sum).Sum
    if ($null -eq $bytes) { $bytes = 0 }
    return @{ Files = $files; Bytes = [long]$bytes }
}

function Write-Sample([bool]$Force = $false) {
    $checkpoint = Measure-Files $CheckpointPath 'model-*.safetensors'
    $shards = Measure-Files $ShardsPath '*.safetensors'
    $done = Measure-Files $ShardsPath '*.done'
    $currentWeights = @{}
    $checkpoint.Files | ForEach-Object { $currentWeights[$_.Name] = $true }
    $deleted = @($knownWeights.Keys | Where-Object { -not $currentWeights.ContainsKey($_) } | Sort-Object)
    $newDone = @($done.Files | Where-Object { -not $knownDone.ContainsKey($_.FullName) } | Sort-Object LastWriteTime)

    $ramBytes = (Get-Process python -ErrorAction SilentlyContinue |
        Where-Object { $_.StartTime -ge $started.AddSeconds(-5) } |
        Measure-Object WorkingSet64 -Sum).Sum
    if ($null -eq $ramBytes) { $ramBytes = 0 }
    if ($ramBytes -gt $peakRamBytes) { $script:peakRamBytes = [long]$ramBytes }

    $vramText = nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>$null |
        Select-Object -First 1
    $vramMiB = if ($vramText -match '^\s*(\d+)') { [int]$Matches[1] } else { 0 }
    if ($vramMiB -gt $peakVramMiB) { $script:peakVramMiB = $vramMiB }

    $lastDone = $done.Files | Sort-Object LastWriteTime | Select-Object -Last 1
    $signature = "$($checkpoint.Files.Count)|$($shards.Files.Count)|$($done.Files.Count)|$($drive.AvailableFreeSpace)"
    if ($Force -or $deleted.Count -gt 0 -or $newDone.Count -gt 0 -or $signature -ne $lastSignature) {
        $sample = [ordered]@{
            timestamp = (Get-Date).ToString('o')
            elapsed_seconds = [math]::Round(((Get-Date) - $started).TotalSeconds, 3)
            checkpoint_files = $checkpoint.Files.Count
            checkpoint_bytes = $checkpoint.Bytes
            shard_files = $shards.Files.Count
            shard_bytes = $shards.Bytes
            done_files = $done.Files.Count
            new_done = @($newDone | ForEach-Object Name)
            last_done = if ($null -ne $lastDone) { $lastDone.Name } else { $null }
            deleted_checkpoint_files = $deleted
            free_bytes = $drive.AvailableFreeSpace
            ram_bytes = [long]$ramBytes
            peak_ram_bytes = $peakRamBytes
            vram_mib = $vramMiB
            peak_vram_mib = $peakVramMiB
        }
        [System.IO.File]::AppendAllText(
            $TelemetryPath,
            (($sample | ConvertTo-Json -Compress -Depth 5) + [Environment]::NewLine),
            [System.Text.Encoding]::UTF8
        )
        $script:lastSignature = $signature
    }
    foreach ($item in $newDone) { $knownDone[$item.FullName] = $true }
    foreach ($name in $deleted) { $knownWeights.Remove($name) }
}

Write-Sample $true
while (-not (Test-Path -LiteralPath $ResultPath)) {
    Start-Sleep -Milliseconds 500
    Write-Sample
}
Start-Sleep -Seconds 2
Write-Sample $true

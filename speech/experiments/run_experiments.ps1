<#
.SYNOPSIS
    Runs the TTS comparison (issue #4) with every engine whose virtual
    environment exists, then writes results\summary.md. One command:

        .\run_experiments.ps1

.DESCRIPTION
    Each engine runs inside its own virtual environment (their packages
    conflict). Engines without a virtual environment, or ElevenLabs without an
    API key in .env, are skipped with a warning. Runs resume where they
    stopped, so running the command again only generates what is missing.

.EXAMPLE
    .\run_experiments.ps1                                  # all engines, 35 sentences each
    .\run_experiments.ps1 -Limit 2                         # quick check, 2 sentences each
    .\run_experiments.ps1 -Engines kokoro,elevenlabs       # only these engines
    .\run_experiments.ps1 -Engines chatterbox,chatterbox-turbo,styletts2 -Refs refs
    .\run_experiments.ps1 -Engines chatterbox -Fresh       # delete old results and start over
#>
param(
    [string[]]$Engines = @("kokoro", "chatterbox", "styletts2", "elevenlabs"),
    [string]$Refs = "",
    [int]$Limit = 0,
    [string]$Device = "cpu",
    [switch]$Fresh
)

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
# accept both "-Engines a,b" and "-Engines 'a,b'" (the latter happens with powershell -File)
$Engines = @($Engines | ForEach-Object { $_ -split "," } | ForEach-Object { $_.Trim() } | Where-Object { $_ })

# engine -> virtual environment that has its packages (edit if yours are named differently)
$Venvs = @{
    "kokoro"           = ".venv-kokoro"
    "chatterbox"       = ".venv-chatterbox"
    "chatterbox-turbo" = ".venv-chatterbox"
    "styletts2"        = ".venv-styletts2"
    "elevenlabs"       = ".venv-kokoro"
}
$RefEngines = @("chatterbox", "chatterbox-turbo", "styletts2")

function Get-VenvPython([string]$Engine) {
    if (-not $Venvs.ContainsKey($Engine)) { return $null }
    $py = Join-Path $PSScriptRoot (Join-Path $Venvs[$Engine] "Scripts\python.exe")
    if (Test-Path $py) { return $py }
    return $null
}

function Test-ElevenLabsKey {
    if ($env:ELEVENLABS_API_KEY) { return $true }
    $envFile = Join-Path $PSScriptRoot ".env"
    if (-not (Test-Path $envFile)) { return $false }
    return [bool](Select-String -Path $envFile -Pattern "^\s*ELEVENLABS_API_KEY\s*=\s*\S+" -Quiet)
}

if ($Refs -and -not (Test-Path $Refs)) {
    Write-Host "Reference folder '$Refs' not found." -ForegroundColor Red
    exit 1
}

$summaryPython = $null
$report = @()

foreach ($engine in $Engines) {
    $py = Get-VenvPython $engine
    if (-not $py) {
        Write-Host "SKIP $engine : virtual environment '$($Venvs[$engine])' not found" -ForegroundColor Yellow
        $report += "$engine : skipped (no venv)"
        continue
    }
    if ($engine -eq "elevenlabs" -and -not (Test-ElevenLabsKey)) {
        Write-Host "SKIP elevenlabs : ELEVENLABS_API_KEY not found in .env" -ForegroundColor Yellow
        $report += "elevenlabs : skipped (no API key)"
        continue
    }
    if (-not $summaryPython) { $summaryPython = $py }

    $useRefs = $Refs -and ($RefEngines -contains $engine)
    $label = if ($engine -eq "elevenlabs") { "elevenlabs-cloud" }
             elseif ($useRefs) { "$engine-refs-$Device" }
             else { "$engine-$Device" }
    $outDir = Join-Path "results" $label
    if ($Fresh -and (Test-Path $outDir)) { Remove-Item -Recurse -Force $outDir }

    $runArgs = @("-m", "tts_bench.run", "--engine", $engine, "--device", $Device, "--label", $label, "--resume")
    if ($useRefs) { $runArgs += @("--refs", $Refs) }
    if ($Limit -gt 0) { $runArgs += @("--limit", "$Limit") }

    Write-Host ""
    Write-Host "=== $label ===" -ForegroundColor Cyan
    $started = Get-Date
    & $py @runArgs
    $minutes = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)
    if ($LASTEXITCODE -eq 0) {
        $report += "$label : OK ($minutes min)"
    } else {
        Write-Host "$label finished with errors; rerun the same command to retry the missing sentences." -ForegroundColor Yellow
        $report += "$label : errors (exit $LASTEXITCODE, $minutes min)"
    }
}

if ($summaryPython) {
    Write-Host ""
    Write-Host "=== summary ===" -ForegroundColor Cyan
    & $summaryPython -m tts_bench.summarize | Out-Null
    Write-Host "Wrote results\summary.md"
}

Write-Host ""
$report | ForEach-Object { Write-Host $_ }

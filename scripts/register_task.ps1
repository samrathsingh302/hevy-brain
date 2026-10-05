# Registers Windows Task Scheduler jobs for hevy-brain.
#   - "HevyBrain Sync": runs `hevy-brain full` every 60 minutes
#   - "HevyBrain Coach": runs `hevy-brain coach` Sundays at 19:00
# Run from the repo root in an elevated or normal PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1 -DryRun
#     (prints each task's action argument string, one per line; registers nothing)
# Requires HEVY_API_KEY set as USER (ANTHROPIC_API_KEY is NOT needed for the
# scheduled coach — it uses the free path; only manual `coach --api` reads it)
# environment variables so the scheduled task inherits them:
#   [Environment]::SetEnvironmentVariable('HEVY_API_KEY', '<key>', 'User')
param([switch]$DryRun)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path "$PSScriptRoot\..").Path
# Pin the project's baseline interpreter (Python >=3.12), NOT whatever bare
# `python` resolves to first on PATH. A stray Python 3.14 ahead of 3.12 on PATH
# — with none of the deps installed — is exactly what silently stalled the
# hourly sync for ~16 days. Resolve the absolute exe so the task action does not
# depend on PATH at run time.
$python = (& py -3.12 -c 'import sys; print(sys.executable)' 2>$null)
if (-not $python) {
    throw "Python 3.12 not found via 'py -3.12'. Install it (pyproject requires >=3.12) or edit this line."
}
$logDir = Join-Path $repo 'logs'
# The inner command line reaches cmd.exe through wscript, whose argument parser
# cannot carry nested quotes — so the python and log paths must be space-free.
foreach ($p in @($python, $logDir)) {
    if ($p -match ' ') { throw "Path contains a space, which the cmd.exe action cannot quote: $p" }
}
if (-not $DryRun) { New-Item -ItemType Directory -Force $logDir | Out-Null }

function Register-HevyTask {
    param([string]$Name, [string]$Command, $Trigger)
    $log = Join-Path $logDir (($Command -replace ' ', '_') + '.log')
    # wscript (GUI app) launcher: a console exe alone flashes a console/WT tab on
    # every run. NO powershell.exe in the chain: Windows PowerShell 5.1 under
    # -Command exits 1 whenever a native command writes stderr under a redirect
    # (the lock-skip line did, 05/10/2026), which run_hidden.vbs propagates — the
    # task read red while Python exited 0. cmd.exe returns Python's own exit code
    # and appends stderr to the log as plain text.
    $argument = "`"$PSScriptRoot\run_hidden.vbs`" cmd.exe /c `"$python -m hevy_brain.cli $Command >> $log 2>&1`""
    if ($DryRun) {
        Write-Output $argument
        return
    }
    # PowerShell's *>> wrote the old logs as UTF-16LE; cmd appends ANSI bytes, so
    # a UTF-16 log is moved aside (kept, never deleted) to start a clean one.
    if (Test-Path $log) {
        $stream = [IO.File]::OpenRead($log)
        try { $bom = @($stream.ReadByte(), $stream.ReadByte()) } finally { $stream.Close() }
        if ($bom[0] -eq 0xFF -and $bom[1] -eq 0xFE) {
            Move-Item $log ($log -replace '\.log$', ('.utf16-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log'))
        }
    }
    $action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument $argument -WorkingDirectory $repo
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
        -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $Trigger `
        -Settings $settings -Force | Out-Null
    Write-Host "Registered task '$Name' -> hevy-brain $Command (log: $log)"
}

$hourly = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) `
    -RepetitionInterval (New-TimeSpan -Minutes 60)
Register-HevyTask -Name 'HevyBrain Sync' -Command 'full' -Trigger $hourly

$weekly = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 19:00
Register-HevyTask -Name 'HevyBrain Coach' -Command 'coach' -Trigger $weekly

if (-not $DryRun) { Write-Host 'Done. Inspect with: Get-ScheduledTask HevyBrain*' }

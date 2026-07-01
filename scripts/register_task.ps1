# Registers Windows Task Scheduler jobs for hevy-brain.
#   - "HevyBrain Sync": runs `hevy-brain full` every 60 minutes
#   - "HevyBrain Coach": runs `hevy-brain coach` Sundays at 19:00
# Run from the repo root in an elevated or normal PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
# Requires HEVY_API_KEY (and ANTHROPIC_API_KEY for coach) set as USER
# environment variables so the scheduled task inherits them:
#   [Environment]::SetEnvironmentVariable('HEVY_API_KEY', '<key>', 'User')

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
New-Item -ItemType Directory -Force $logDir | Out-Null

function Register-HevyTask {
    param([string]$Name, [string]$Command, $Trigger)
    $log = Join-Path $logDir (($Command -replace ' ', '_') + '.log')
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument (
        "-NoProfile -WindowStyle Hidden -Command `"& '$python' -m hevy_brain.cli $Command *>> '$log'`""
    ) -WorkingDirectory $repo
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

Write-Host 'Done. Inspect with: Get-ScheduledTask HevyBrain*'

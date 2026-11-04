# CFA Level I autopilot - installer for Windows PowerShell.
#
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Timers
#
# -Timers registers four Scheduled Tasks (07:30, 21:30, 22:30 and Sunday 19:00).
# Without it you just get the `cfa` command, which is usually what you want
# while you are still deciding whether the routine fits your week.

[CmdletBinding()]
param(
    [switch]$Timers,
    [switch]$NoPath
)

$ErrorActionPreference = 'Stop'
$Dir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Say($Message) { Write-Host $Message }

# ---------- Python ----------
$PythonExe = $null
$PythonArgs = @()

$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    $PythonExe = if ($python.Source) { $python.Source } else { $python.Path }
} else {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        $PythonExe = if ($py.Source) { $py.Source } else { $py.Path }
        $PythonArgs = @('-3')
    }
}

if (-not $PythonExe) {
    throw "Python 3.9+ is required. Install it from python.org, tick 'Add python.exe to PATH', then run this again."
}

$version = & $PythonExe @PythonArgs -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$version -lt [version]'3.9') {
    throw "Python 3.9+ is required (found $version)."
}

$UserHome = $env:USERPROFILE
$ProfilePath = Join-Path $Dir 'profile.json'
$ExamplePath = Join-Path $Dir 'profile.example.json'
$WeekDir = Join-Path $Dir 'plan\weeks'
$ReviewDir = Join-Path $Dir 'plan\reviews'
$EnvDir = Join-Path $UserHome '.config\cfa'
$EnvFile = Join-Path $EnvDir 'env'
$BinDir = Join-Path $UserHome '.local\bin'
$CmdPath = Join-Path $BinDir 'cfa.cmd'

New-Item -ItemType Directory -Force -Path $WeekDir, $ReviewDir, $EnvDir, $BinDir | Out-Null

# ---------- profile ----------
if (-not (Test-Path $ProfilePath)) {
    Copy-Item $ExamplePath $ProfilePath
    Say "Created profile.json from profile.example.json. Edit it with your dates."
} else {
    Say "Keeping the existing profile.json."
}

# ---------- key file ----------
if (-not (Test-Path $EnvFile)) {
    @'
# Optional: only used by `cfa master` and `cfa week`.
# Get a key from your model provider. Any OpenAI-compatible endpoint works.
DEEPSEEK_API_KEY=paste-your-key-here
# DEEPSEEK_BASE_URL=https://api.deepseek.com
# DEEPSEEK_MODEL=deepseek-flash

# Optional phone push through ntfy (use a long random topic):
# NTFY_TOPIC=cfa-pick-a-long-random-string
'@ | Set-Content -Path $EnvFile -Encoding UTF8
    Say "Created $EnvFile. Paste your key there if you want model-written weeks."
} else {
    Say "Keeping the existing $EnvFile."
}

# ---------- launcher ----------
$pythonLine = '"' + $PythonExe + '"'
if ($PythonArgs.Count -gt 0) { $pythonLine += ' ' + ($PythonArgs -join ' ') }
$cmdBody = @"
@echo off
$pythonLine "$Dir\cfa.py" %*
"@
Set-Content -Path $CmdPath -Value $cmdBody -Encoding ASCII
Say "Launcher installed: $CmdPath"

# ---------- PATH ----------
if (-not $NoPath) {
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if (-not $userPath) { $userPath = '' }
    $parts = $userPath -split ';' | Where-Object { $_ -ne '' }
    if (-not ($parts | Where-Object { $_.TrimEnd('\') -ieq $BinDir.TrimEnd('\') })) {
        $newPath = if ($userPath.Trim()) { $userPath.TrimEnd(';') + ';' + $BinDir } else { $BinDir }
        [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
        Say "Added $BinDir to your user PATH. Open a new terminal to pick it up."
    } else {
        Say "$BinDir is already on your user PATH."
    }
    $env:Path = $env:Path.TrimEnd(';') + ';' + $BinDir
}

# ---------- Scheduled Tasks ----------
if ($Timers) {
    function Register-CfaTask {
        param(
            [string]$Name,
            [string]$Description,
            [object]$Trigger,
            [object]$Action
        )
        $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName $Name -Description $Description -Trigger $Trigger -Action $Action -Settings $settings -Force | Out-Null
    }

    try {
        $daily = New-ScheduledTaskAction -Execute $CmdPath -Argument 'today --notify' -WorkingDirectory $Dir
        $nudge = New-ScheduledTaskAction -Execute $CmdPath -Argument 'nudge' -WorkingDirectory $Dir
        $final = New-ScheduledTaskAction -Execute $CmdPath -Argument 'nudge --final' -WorkingDirectory $Dir
        $weeklyScript = "& '$CmdPath' review; & '$CmdPath' week --next"
        $weekly = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -Command `"$weeklyScript`"" -WorkingDirectory $Dir

        Register-CfaTask -Name 'cfa-daily'  -Description 'CFA daily brief'      -Trigger (New-ScheduledTaskTrigger -Daily -At '07:30') -Action $daily
        Register-CfaTask -Name 'cfa-nudge'  -Description 'CFA evening check-in' -Trigger (New-ScheduledTaskTrigger -Daily -At '21:30') -Action $nudge
        Register-CfaTask -Name 'cfa-final'  -Description 'CFA end-of-day close' -Trigger (New-ScheduledTaskTrigger -Daily -At '22:30') -Action $final
        Register-CfaTask -Name 'cfa-weekly' -Description 'CFA weekly review and plan' -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At '19:00') -Action $weekly

        Say "Scheduled Tasks installed: cfa-daily, cfa-nudge, cfa-final, cfa-weekly."
    } catch {
        Write-Warning "Could not register the Scheduled Tasks: $($_.Exception.Message)"
        Write-Warning "You can still run 'cfa today' by hand."
    }
}

# ---------- done ----------
Say ""
Say "CFA autopilot installed in: $Dir"
Say ""
Say "Next:"
Say "  1. Edit $EnvFile if you want model-written weeks (optional)."
Say "  2. Open a new terminal, then run: cfa doctor"
Say "  3. cfa today"
Say ""
Say "The plan is a template. Edit profile.json and plan\curriculum.json for your own dates."

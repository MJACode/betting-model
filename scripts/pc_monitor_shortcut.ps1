# Puts "Betting PC monitor" on the desktop: a window showing the betting model's
# jobs on this PC (pc_monitor/, docs/local_ops.md "Betting PC monitor").
#
# The shortcut runs pythonw (no console window) from the app's own copy of the
# repo, .claude\feeds\pc-monitor, never from a session's worktree, which is
# deleted when the session ends. The app moves that copy to origin/master each
# time it starts, once origin/master contains it.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pc_monitor_shortcut.ps1
#   ... -Ref <commit>   # build the copy from a commit that is not on master yet
#   ... -SignInTask     # also start it, with no window, 2 min after sign-in
#                       # (mike, 2026-11-21: "Yes, at sign-in"); task \BettingModel\PcMonitor

param(
    [string]$Repo = "$env:USERPROFILE\Documents\betting-model",
    [string]$Ref = "origin/master",
    [string]$Pythonw = "$env:LOCALAPPDATA\Programs\Python\Python314\pythonw.exe",
    [switch]$SignInTask
)
$ErrorActionPreference = 'Stop'
$Feed = Join-Path $Repo ".claude\feeds\pc-monitor"

if (-not (Test-Path $Pythonw)) {
    $found = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if (-not $found) { throw "pythonw.exe not found; pass -Pythonw <path>" }
    $Pythonw = $found.Source
}
# pythonw does not make PowerShell wait, so ask python.exe in the same folder.
$python = Join-Path (Split-Path $Pythonw) "python.exe"
& $python -c "import psutil, psycopg2, dotenv" 2>$null
if ($LASTEXITCODE -ne 0) { throw "$python lacks psutil, psycopg2 or python-dotenv" }

if (-not (Test-Path (Join-Path $Feed "pc_monitor\__main__.py"))) {
    if (Test-Path $Feed) { git -C $Feed checkout -q --detach -f $Ref }
    else { git -C $Repo worktree add -q --detach $Feed $Ref }
    if (-not (Test-Path (Join-Path $Feed "pc_monitor\__main__.py"))) {
        throw "$Ref does not contain pc_monitor yet; pass -Ref <a commit that does>"
    }
}

$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) "Betting PC monitor.lnk"
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = $Pythonw
$s.Arguments = "-m pc_monitor"
$s.WorkingDirectory = $Feed
$s.IconLocation = "$env:SystemRoot\System32\perfmon.exe,0"
$s.Description = "The betting model's jobs on this PC"
$s.Save()
"shortcut: $lnk"
"runs:     $Pythonw -m pc_monitor  (in $Feed)"

if ($SignInTask) {
    # Same shape as the other \BettingModel\ tasks: runs as this user, only while
    # signed in, no admin rights. pythonw has no console, so no run_hidden.pyw.
    # --stay keeps it up with no window open; the shortcut then opens a window
    # onto it. No time limit: it is meant to run for the whole session.
    $user = "$env:USERDOMAIN\$env:USERNAME"
    $action = New-ScheduledTaskAction -Execute $Pythonw -Argument "-m pc_monitor --stay --no-window" `
        -WorkingDirectory $Feed
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
    $trigger.Delay = "PT2M"
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskPath '\BettingModel\' -TaskName PcMonitor -Force -Action $action `
        -Trigger $trigger -Settings $settings -Principal $principal `
        -Description "Betting PC monitor (pc_monitor): serves http://127.0.0.1:8790/ from sign-in. docs/local_ops.md" | Out-Null
    "task:     \BettingModel\PcMonitor, 2 min after sign-in"
}

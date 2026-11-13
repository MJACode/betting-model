<#
  DraftKings' in-play boards (every sport with an in-play model) onto Supabase, from this machine
  (data/ingestors/dk_live_board.py; docs/local_ops.md, "NCAAB in-play:
  DraftKings' own board"). DraftKings refuses the Railway worker, so the
  worker's NCAAB in-play model reads what this writes.

  Run by the scheduled task BettingModel\DkLiveBoard every minute from 9am
  to 3am (an NFL game can kick off at 9:30am ET), and two minutes after sign-in (mike, 2026-11-12: "yes"). A start
  while a feed is running exits at once (the feed holds 127.0.0.1:47231).

  The feed runs from its own worktree, C:\Users\micha\Documents\bm-live-feed,
  put on origin/master before each start, so a merged fix reaches the next
  start and no other session's branch is ever what runs. DATABASE_URL is
  read from the main checkout's .env for this process only.
#>
param(
    [string]$Root = "C:\Users\micha\Documents\betting_local_copies",
    [string]$Repo = "C:\Users\micha\documents\betting-model",
    [string]$Feed = "C:\Users\micha\Documents\bm-live-feed",
    [int]$LockPort = 47232
)
$ErrorActionPreference = "Continue"
$logs = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

# A feed already running holds the port: nothing to do.
$probe = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $LockPort)
try { $probe.Start(); $probe.Stop() } catch { exit 0 }

$day = (Get-Date).ToString("yyyyMMdd")
$log = Join-Path $logs "dk_live_board_$day.log"
Add-Content $log ("--- start " + (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))

# git never waits on a sign-in prompt here (the task runs hidden, so a prompt
# is a hang: on 2026-11-13 a fetch sat 2.5 min and held every start behind it),
# and a fetch that does not answer in 60 s is abandoned: the feed then runs
# from the checkout already on disk.
$env:GIT_TERMINAL_PROMPT = "0"
$env:GCM_INTERACTIVE = "never"
function Invoke-Git([string[]]$GitArgs, [int]$TimeoutSec = 60) {
    $p = Start-Process -FilePath "git" -ArgumentList $GitArgs -NoNewWindow -PassThru `
        -RedirectStandardError (Join-Path $logs "dk_live_board_git_$day.log")
    if (-not $p.WaitForExit($TimeoutSec * 1000)) {
        try { $p.Kill() } catch { }
        Add-Content $log ("git " + ($GitArgs -join " ") + " did not answer in $TimeoutSec s - abandoned")
        return $false
    }
    return ($p.ExitCode -eq 0)
}
[void](Invoke-Git @("-C", $Repo, "fetch", "-q", "origin", "master"))
if (-not (Test-Path (Join-Path $Feed ".git"))) {
    [void](Invoke-Git @("-C", $Repo, "worktree", "add", "--detach", $Feed, "origin/master"))
} else {
    [void](Invoke-Git @("-C", $Feed, "checkout", "-q", "--detach", "-f", "origin/master"))
}
if (-not (Test-Path (Join-Path $Feed "data\ingestors\dk_live_board.py"))) {
    Add-Content $log "origin/master has no data\ingestors\dk_live_board.py yet (not merged): nothing to run"
    exit 0
}

$line = Get-Content (Join-Path $Repo ".env") | Where-Object { $_ -like "DATABASE_URL=*" } | Select-Object -First 1
if (-not $line) { Add-Content $log "no DATABASE_URL in $Repo\.env"; exit 1 }
$env:DATABASE_URL = $line.Substring(13).Trim('"')
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = $Feed
$python = (Get-Command python -ErrorAction Stop).Source
# Every league with an in-play model, the feed's own UTF-8 log (PowerShell's
# redirect wrote UTF-16 into this one and garbled it). Exit code 3 means a
# merge changed the feed: the new master is checked out and started at once.
$pylog = Join-Path $logs "dk_live_board_feed_$day.log"
while ($true) {
    $p = Start-Process -FilePath $python -ArgumentList @("-m", "data.ingestors.dk_live_board", "--log", "`"$pylog`"",
        "--exit-on-new-master") -WorkingDirectory $Feed -NoNewWindow -Wait -PassThru `
        -RedirectStandardError (Join-Path $logs "dk_live_board_stderr_$day.log")
    Add-Content $log ("--- exit " + $p.ExitCode + " " + (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))
    if ($p.ExitCode -ne 3) { break }
    [void](Invoke-Git @("-C", $Feed, "fetch", "-q", "origin", "master"))
    [void](Invoke-Git @("-C", $Feed, "checkout", "-q", "--detach", "-f", "origin/master"))
    Add-Content $log ("--- restarting on " + (& git -C $Feed rev-parse --short HEAD))
}

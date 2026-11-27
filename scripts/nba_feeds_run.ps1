<#
  The NBA collectors that run on this machine (docs/local_ops.md, "NBA feeds";
  docs/nba_data_sources_and_handle_2026_11.md, section G):

    1. Once a day: this season's enriched boxes, referee crews and inactive
       lists (data/ingestors/nba_box_enrich.py). stats.nba.com refuses the
       Railway worker, so this cannot run there.
    2. A loop that saves Unabated's prop-opener file change by change
       (data/ingestors/nba_feeds.py). The other eleven feeds of that module (the
       league's lineup file, referee crews, projections, news, Pinnacle's limits,
       the pick'em boards, BetMGM's splits) are read by the worker's one-minute
       job; this file is 139 MB from the worker, so it is read here.

  Run by the scheduled task BettingModel\NbaFeeds every minute and two minutes
  after sign-in (mike, 2026-11-27: "2) yes"). The loop holds 127.0.0.1:47241, so
  a start while one is running exits at once; it stops itself after 24 hours and
  the next start picks up whatever has merged since.

  The passes run from their own worktree, C:\Users\micha\Documents\betting-model\.claude\feeds\nba,
  put on origin/master before each start, so no other session's branch is ever
  what runs. DATABASE_URL is read from the main checkout's .env for these
  processes only.
#>
param(
    [string]$Root = "C:\Users\micha\Documents\betting_local_copies",
    [string]$Repo = "C:\Users\micha\documents\betting-model",
    [string]$Feed = "C:\Users\micha\Documents\betting-model\.claude\feeds\nba",
    [int]$LoopHours = 24,
    [int]$BoxTimeoutSec = 1800
)
$ErrorActionPreference = "Continue"
$logs = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$day = (Get-Date).ToString("yyyyMMdd")
$log = Join-Path $logs "nba_feeds_$day.log"

# A loop already running holds the port: say nothing and leave (this task fires every minute).
$busy = $false
try {
    $probe = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 47241)
    $probe.Start(); $probe.Stop()
} catch { $busy = $true }
if ($busy) { exit 0 }

Add-Content $log ("--- start " + (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))

function Invoke-Git([string[]]$GitArgs, [int]$TimeoutSec = 60) {
    $p = Start-Process -FilePath "git" -ArgumentList $GitArgs -NoNewWindow -PassThru `
        -RedirectStandardError (Join-Path $logs "nba_feeds_git_$day.log")
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
if (-not (Test-Path (Join-Path $Feed "data\ingestors\nba_feeds.py"))) {
    Add-Content $log "origin/master has no data\ingestors\nba_feeds.py yet (not merged): nothing to run"
    exit 0
}

$line = Get-Content (Join-Path $Repo ".env") | Where-Object { $_ -like "DATABASE_URL=*" } | Select-Object -First 1
if (-not $line) { Add-Content $log "no DATABASE_URL in $Repo\.env"; exit 1 }
$env:DATABASE_URL = $line.Substring(13).Trim('"')
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = $Feed
$python = (Get-Command python -ErrorAction Stop).Source

# 1. The daily box, referee and inactive load: once per calendar day, marked by a file.
$season = if ((Get-Date).Month -ge 8) { (Get-Date).Year + 1 } else { (Get-Date).Year }
$marker = Join-Path $logs "nba_box_enrich_$day.done"
if (-not (Test-Path $marker)) {
    $out = Join-Path $logs "nba_box_enrich_$day.log"
    $p = Start-Process -FilePath $python -ArgumentList @("-m", "data.ingestors.nba_box_enrich", "--seasons", "$season", "$season") `
        -WorkingDirectory $Feed -NoNewWindow -PassThru -RedirectStandardOutput $out `
        -RedirectStandardError (Join-Path $logs "nba_box_enrich_stderr_$day.log")
    if (-not $p.WaitForExit($BoxTimeoutSec * 1000)) {
        try { $p.Kill() } catch { }
        Add-Content $log "box load did not finish in $BoxTimeoutSec s - stopped; it is tried again at the next start"
    } else {
        Add-Content $log ("box load exit " + $p.ExitCode)
        if ($p.ExitCode -eq 0) { Set-Content $marker (Get-Date).ToUniversalTime().ToString("o") }
    }
}

# 2. The loop, until $LoopHours from now. Only the feed the worker leaves out (Unabated's
#    139 MB prop file): the worker's one-minute job reads every other feed, and one reader
#    a feed keeps this address from polling Pinnacle beside the tennis logger.
$until = (Get-Date).ToUniversalTime().AddHours($LoopHours).ToString("yyyy-MM-ddTHH:mm:ss")
$p = Start-Process -FilePath $python -ArgumentList @("-m", "data.ingestors.nba_feeds", "--loop", "--origin", "pc", "--feeds", "unabated_props", "--until", $until) `
    -WorkingDirectory $Feed -NoNewWindow -PassThru `
    -RedirectStandardOutput (Join-Path $logs "nba_feeds_loop_$day.log") `
    -RedirectStandardError (Join-Path $logs "nba_feeds_loop_stderr_$day.log")
$p.WaitForExit()
Add-Content $log ("loop exit " + $p.ExitCode + " " + (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))

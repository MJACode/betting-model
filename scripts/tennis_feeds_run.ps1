<#
  The tennis collectors that have to run on this machine, one pass each
  (docs/sports/tennis.md; docs/local_ops.md, "Tennis feeds"):

    DraftKings' own tennis board, every level and market
        (scripts/tennis_dk_probe.py; DraftKings refuses the Railway worker)
    Pinnacle's own tennis prices, every level (data/ingestors/tennis_pinnacle.py)
    TennisExplorer's results for the last three days
        (data/ingestors/tennis_explorer.py)

  Run by the scheduled task BettingModel\TennisFeeds every 30 minutes and two
  minutes after sign-in (mike, 2026-11-13: "yes"). Each reader refuses to start
  while another copy of itself runs, so a long-running loop and this task never
  both poll a site.

  The passes run from their own worktree, C:\Users\micha\Documents\bm-tennis-feed,
  put on origin/master before each run, so a merged fix reaches the next run
  and no other session's branch is ever what runs. DATABASE_URL is read from
  the main checkout's .env for these processes only.
#>
param(
    [string]$Root = "C:\Users\micha\Documents\betting_local_copies",
    [string]$Repo = "C:\Users\micha\documents\betting-model",
    [string]$Feed = "C:\Users\micha\Documents\bm-tennis-feed",
    [int]$PassTimeoutSec = 1200
)
$ErrorActionPreference = "Continue"
$logs = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$day = (Get-Date).ToString("yyyyMMdd")
$log = Join-Path $logs "tennis_feeds_$day.log"
Add-Content $log ("--- start " + (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))

function Invoke-Git([string[]]$GitArgs, [int]$TimeoutSec = 60) {
    $p = Start-Process -FilePath "git" -ArgumentList $GitArgs -NoNewWindow -PassThru `
        -RedirectStandardError (Join-Path $logs "tennis_feeds_git_$day.log")
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
if (-not (Test-Path (Join-Path $Feed "scripts\tennis_dk_probe.py"))) {
    Add-Content $log "origin/master has no scripts\tennis_dk_probe.py yet (not merged): nothing to run"
    exit 0
}

$line = Get-Content (Join-Path $Repo ".env") | Where-Object { $_ -like "DATABASE_URL=*" } | Select-Object -First 1
if (-not $line) { Add-Content $log "no DATABASE_URL in $Repo\.env"; exit 1 }
$env:DATABASE_URL = $line.Substring(13).Trim('"')
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = $Feed
$python = (Get-Command python -ErrorAction Stop).Source
$since = (Get-Date).AddDays(-3).ToString("yyyy-MM-dd")

$passes = @(
    @("dk", @("-m", "scripts.tennis_dk_probe")),
    @("pinnacle", @("-m", "data.ingestors.tennis_pinnacle", "--once")),
    @("tennisexplorer", @("-m", "data.ingestors.tennis_explorer", "--from", $since))
)
foreach ($pass in $passes) {
    $name, $pyArgs = $pass[0], $pass[1]
    $out = Join-Path $logs "tennis_feeds_${name}_$day.log"
    $p = Start-Process -FilePath $python -ArgumentList $pyArgs -WorkingDirectory $Feed -NoNewWindow -PassThru `
        -RedirectStandardOutput $out -RedirectStandardError (Join-Path $logs "tennis_feeds_${name}_stderr_$day.log")
    if (-not $p.WaitForExit($PassTimeoutSec * 1000)) {
        try { $p.Kill() } catch { }
        Add-Content $log ("$name did not finish in $PassTimeoutSec s - stopped")
        continue
    }
    Add-Content $log ("$name exit " + $p.ExitCode + " " + (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))
}

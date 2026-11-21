<#
  One carbon-copy pass onto mike's machine: GitHub first (minutes), then the
  whole Supabase project (an hour or two once the first copy exists).

  This is what the Windows scheduled task LocalMirror runs, nightly at 00:30
  (docs/local_ops.md, "Local carbon copy"; task checked 2026-11-15). When the
  Supabase copy ends, it rebuilds the DuckDB views over it
  (scripts/local_mirror_duckdb.py, <Root>\betting.duckdb). Last, once every
  copy has ended, it writes one row about the pass to Supabase for the ops
  dashboard (scripts/local_mirror_report.py, table pc_copy_snapshots).

  DATABASE_URL is never passed here. scripts/local_mirror.py reads it from the
  main checkout's .env at run time, so a rotated password reaches the next run.

  The scripts run from <Root>\bin, a stable copy outside the repo and outside
  any worktree. Before each run the main checkout fetches master, and the
  scripts are refreshed from its origin/master when they exist there, so a
  merged fix reaches the next run; otherwise the copy in bin is used as it is.
  This file itself is not refreshed: a change to it is copied into bin by hand.

  -RefreshOnly fetches and refreshes, then stops before any copy: the step on
  its own, to check it without running a pass.
#>
param(
    [string]$Root = "C:\Users\micha\Documents\betting_local_copies",
    [string]$Repo = "C:\Users\micha\documents\betting-model",
    [int]$FetchTimeoutS = 120,
    [switch]$RefreshOnly
)
$ErrorActionPreference = "Continue"
$bin  = Join-Path $Root "bin"
$logs = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $bin, $logs | Out-Null
$ts = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")

# Fetch master first. The refresh below reads origin/master of the main
# checkout, which is only as new as that checkout's last fetch, and nothing
# fetches it on a schedule: from 20:50 ET on 11-20 to 02:03 ET on 11-21 nothing
# did, across the 00:30 run (its reflog, 2026-11-21, #1542). The fetch must
# never stop the pass. The task has no window, so no prompt may open: git's own
# (GIT_TERMINAL_PROMPT) and Git Credential Manager's (GCM_INTERACTIVE). It gets
# FetchTimeoutS seconds, then it is stopped with everything it started. On any
# failure the refresh uses the ref it already has. fetch_<stamp>.log names the
# commit the refresh read.
$env:GIT_TERMINAL_PROMPT = "0"
$env:GCM_INTERACTIVE = "never"
$fetchLog = Join-Path $logs "fetch_$ts.log"
$fetchErr = Join-Path $logs "fetch_$ts.err"
try {
    $fp = Start-Process -FilePath "git" -NoNewWindow -PassThru `
        -ArgumentList @("-C", "`"$Repo`"", "fetch", "--quiet", "--no-tags", "origin", "master") `
        -RedirectStandardOutput $fetchLog -RedirectStandardError $fetchErr
    $null = $fp.Handle  # keeps ExitCode readable after the process ends (PowerShell 5.1)
    if (-not $fp.WaitForExit($FetchTimeoutS * 1000)) {
        $null = & taskkill.exe /T /F /PID $fp.Id 2>&1
        $null = $fp.WaitForExit(10000)
        $fetchNote = "fetch stopped after $FetchTimeoutS s"
    } elseif ($fp.ExitCode -ne 0) {
        $fetchNote = "fetch ended with code $($fp.ExitCode)"
    } else {
        $fetchNote = "fetched"
    }
} catch {
    $fetchNote = "fetch could not start: $($_.Exception.Message)"
}
$head = (& git -C $Repo rev-parse --verify --quiet origin/master 2>$null | Out-String).Trim()
if (-not $head) { $head = "none" }
Add-Content -Path $fetchLog -Value "$((Get-Date).ToUniversalTime().ToString('s'))Z $fetchNote; the refresh reads origin/master at $head"

foreach ($f in @("local_mirror.py", "local_mirror_github.py", "local_mirror_duckdb.py", "local_mirror_report.py")) {
    $tmp = Join-Path $bin "$f.new"
    $p = Start-Process -FilePath "git" -NoNewWindow -Wait -PassThru `
        -ArgumentList @("-C", "`"$Repo`"", "show", "origin/master:scripts/$f") `
        -RedirectStandardOutput $tmp -RedirectStandardError (Join-Path $logs "bin_refresh_$ts.err")
    if ($p.ExitCode -eq 0 -and (Test-Path $tmp) -and (Get-Item $tmp).Length -gt 1000) {
        Move-Item -Force $tmp (Join-Path $bin $f)
    } else {
        Remove-Item -Force $tmp -ErrorAction SilentlyContinue
    }
}

if ($RefreshOnly) { exit 0 }

$python = (Get-Command python -ErrorAction Stop).Source
$env:PYTHONIOENCODING = "utf-8"

# First: the previous pass's row, if its runner stopped before its last step
# while its copy carried on and finished (2026-11-16: the runner ended about
# nine hours in, the copy kept running). It writes nothing when that pass
# reported, or when its copy did not finish. Best effort: its result is in
# its log and does not change this pass's.
$null = Start-Process -FilePath $python -NoNewWindow -Wait -PassThru `
    -ArgumentList @("-I", "`"$bin\local_mirror_report.py`"", "--root", "`"$Root`"",
                    "--env-file", "`"$Repo\.env`"", "--catch-up", "--before", $ts) `
    -RedirectStandardOutput "$logs\catchup_$ts.log" -RedirectStandardError "$logs\catchup_$ts.err"

# The GitHub mirror never touches the database, so it runs alongside.
$gh = Start-Process -FilePath $python -NoNewWindow -PassThru `
    -ArgumentList @("-I", "`"$bin\local_mirror_github.py`"", "--dest", "`"$Root\github`"") `
    -RedirectStandardOutput "$logs\github_$ts.log" -RedirectStandardError "$logs\github_$ts.err"
$null = $gh.Handle  # keeps ExitCode readable after the process ends (PowerShell 5.1)

$sb = Start-Process -FilePath $python -NoNewWindow -Wait -PassThru `
    -ArgumentList @("-I", "`"$bin\local_mirror.py`"", "run", "--dest", "`"$Root\supabase_mirror`"",
                    "--env-file", "`"$Repo\.env`"") `
    -RedirectStandardOutput "$logs\supabase_$ts.log" -RedirectStandardError "$logs\supabase_$ts.err"

# SQL over the copy: views only, rebuilt in seconds once the copy has ended, so
# each view names the files the copy just finished writing.
$dd = Start-Process -FilePath $python -NoNewWindow -Wait -PassThru `
    -ArgumentList @("-I", "`"$bin\local_mirror_duckdb.py`"", "build", "--mirror", "`"$Root\supabase_mirror`"",
                    "--db", "`"$Root\betting.duckdb`"") `
    -RedirectStandardOutput "$logs\duckdb_$ts.log" -RedirectStandardError "$logs\duckdb_$ts.err"

$gh.WaitForExit()

# A step's exit code, or 255 when there is none to read (the step never
# started, or its code could not be read). 255 is a failure, so neither the
# report below nor this task's own result can take "unknown" for success: an
# unknown code is $null, which Start-Process refuses as an argument and
# [Math]::Max reads as 0 (measured 2026-11-16).
function Get-StepCode($p) {
    if ($null -eq $p -or $null -eq $p.ExitCode) { return 255 }
    return [int]$p.ExitCode
}
$ghCode = Get-StepCode $gh
$sbCode = Get-StepCode $sb
$ddCode = Get-StepCode $dd

# Last, after every copy has ended: one row in Supabase about this pass, for
# the ops dashboard's PC copy section (when the copy ran and for how long, the
# tables that differ from Supabase, each copy's size, the free disk). It reads
# only this disk, and its one write is that row.
$rp = Start-Process -FilePath $python -NoNewWindow -Wait -PassThru `
    -ArgumentList @("-I", "`"$bin\local_mirror_report.py`"", "--root", "`"$Root`"",
                    "--env-file", "`"$Repo\.env`"", "--source", "nightly", "--pass-id", $ts,
                    "--github-exit", $ghCode, "--supabase-exit", $sbCode, "--duckdb-exit", $ddCode) `
    -RedirectStandardOutput "$logs\report_$ts.log" -RedirectStandardError "$logs\report_$ts.err"

# The task's own result: any code but 0 is a failure. A crashed step ends with a
# NEGATIVE code (0xC0000005 reads as -1073741819), which a plain largest-code
# would rank below 0, so the night would show as a success (measured
# 2026-11-16). The report above still gets each real code.
function Get-Failure($code) {
    if ($code -eq 0) { return 0 }
    if ($code -lt 0) { return 255 }
    return $code
}
exit [Math]::Max([Math]::Max([Math]::Max((Get-Failure $ghCode), (Get-Failure $sbCode)), (Get-Failure $ddCode)),
                 (Get-Failure (Get-StepCode $rp)))

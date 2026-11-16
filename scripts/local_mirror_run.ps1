<#
  One carbon-copy pass onto mike's machine: GitHub first (minutes), then the
  whole Supabase project (an hour or two once the first copy exists).

  This is what the Windows scheduled task LocalMirror runs, nightly at 00:30
  (docs/local_ops.md, "Local carbon copy"; task checked 2026-11-15). When the
  Supabase copy ends, it rebuilds the DuckDB views over it
  (scripts/local_mirror_duckdb.py, <Root>\betting.duckdb).

  DATABASE_URL is never passed here. scripts/local_mirror.py reads it from the
  main checkout's .env at run time, so a rotated password reaches the next run.

  The scripts run from <Root>\bin, a stable copy outside the repo and outside
  any worktree. Before each run they are refreshed from origin/master of the
  main checkout when they exist there, so a merged fix reaches the next run;
  otherwise the copy in bin is used as it is.
#>
param(
    [string]$Root = "C:\Users\micha\Documents\betting_local_copies",
    [string]$Repo = "C:\Users\micha\documents\betting-model"
)
$ErrorActionPreference = "Continue"
$bin  = Join-Path $Root "bin"
$logs = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $bin, $logs | Out-Null
$ts = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")

foreach ($f in @("local_mirror.py", "local_mirror_github.py", "local_mirror_duckdb.py")) {
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

$python = (Get-Command python -ErrorAction Stop).Source
$env:PYTHONIOENCODING = "utf-8"

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
exit [Math]::Max([Math]::Max($gh.ExitCode, $sb.ExitCode), $dd.ExitCode)

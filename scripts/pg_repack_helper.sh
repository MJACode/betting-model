#!/bin/bash
# Runs once in the throwaway Railway service "pg-repack" (image postgres:17-bookworm).
# REPACK_MODE=dry prints what would be done; REPACK_MODE=run rebuilds.
# The client must be exactly 1.5.2, the version installed in the database.
# Never prints the connection string. Sleeps at the end so Railway does not
# restart it (restart policy is NEVER as well).
# Variables: DATABASE_URL (the worker's, port 5432), REPACK_TABLE (schema.table),
# REPACK_MODE, REPACK_SH (this file in base64, from `git show HEAD:<path> | base64 -w0`
# so it has LF endings). Start command:
#   bash -c 'echo "$REPACK_SH" | base64 -d > /tmp/r.sh && exec bash /tmp/r.sh'
# Delete the service once it has run: a restart repeats the rewrite,
# and a redeploy mid-run kills the client before it can clean up.
# How it was used, and the guard that watches it: docs/data_archive.md.
set -u
WANT="1.5.2"
echo "start $(date -u +%FT%TZ) mode=${REPACK_MODE} table=${REPACK_TABLE}"
export DEBIAN_FRONTEND=noninteractive
. /etc/os-release
echo "debian=${VERSION_CODENAME}"
apt-get update -qq >/dev/null 2>&1 || { echo "APT_UPDATE_FAILED"; sleep infinity; }

pick() { apt-cache madison postgresql-17-repack | awk -v w="$WANT" '$3 ~ "^"w"-" {print $3; exit}'; }
V=$(pick)
if [ -z "$V" ]; then
  echo "not in the main repo; trying the PGDG archive"
  echo "deb http://apt-archive.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg-archive main" \
    > /etc/apt/sources.list.d/pgdg-archive.list
  apt-get update -qq >/dev/null 2>&1 || echo "archive update failed"
  V=$(pick)
fi
BIN=""
if [ -n "$V" ]; then
  echo "installing postgresql-17-repack=$V"
  if apt-get install -y -qq "postgresql-17-repack=$V" >/dev/null 2>&1; then
    BIN=/usr/lib/postgresql/17/bin/pg_repack
  else
    echo "apt install of $V failed"
  fi
fi
if [ -z "$BIN" ]; then
  echo "building $WANT from the upstream source tag"
  apt-get install -y -qq build-essential postgresql-server-dev-17 libpq-dev curl ca-certificates \
    zlib1g-dev liblz4-dev libzstd-dev libreadline-dev libssl-dev libkrb5-dev libselinux1-dev \
    libxslt1-dev libxml2-dev libpam0g-dev libnuma-dev libicu-dev >/dev/null 2>&1 || echo "build deps install failed"
  cd /tmp && curl -fsSL "https://github.com/reorg/pg_repack/archive/refs/tags/ver_${WANT}.tar.gz" | tar xz \
    && cd "pg_repack-ver_${WANT}" && make -C bin > /tmp/build.log 2>&1 && BIN="/tmp/pg_repack-ver_${WANT}/bin/pg_repack"
  [ -z "$BIN" ] && { echo "BUILD_FAILED"; tail -n 30 /tmp/build.log 2>/dev/null; sleep infinity; }
fi
GOT=$("$BIN" --version 2>&1)
echo "client: $GOT"
if [ "$GOT" != "pg_repack $WANT" ]; then echo "REFUSE: client is not $WANT"; sleep infinity; fi

U="$DATABASE_URL"
hostport=$(printf '%s' "$U" | sed -E 's#^[a-z]+://[^@]*@##; s#[/?].*$##')
port=${hostport##*:}
echo "port=$port"
if [ "$port" != "5432" ]; then echo "REFUSE: port $port is not the session port"; sleep infinity; fi
case "$U" in *\?*) U="$U&";; *) U="$U?";; esac
U="${U}keepalives=1&keepalives_idle=30&keepalives_interval=10&keepalives_count=6&application_name=pg_repack"
extra=""
[ "$REPACK_MODE" = "dry" ] && extra="--dry-run"
"$BIN" -k --no-order --no-kill-backend --wait-timeout=120 $extra -d "$U" --table "$REPACK_TABLE" 2>&1
echo "REPACK_EXIT=$? at $(date -u +%FT%TZ)"
sleep infinity

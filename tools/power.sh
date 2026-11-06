#!/usr/bin/env bash
# The project's common commands, one line each. Run in WSL, from anywhere (WSL has no make, so this is a script):
#   wsl.exe -d Ubuntu -u root -- bash /mnt/c/.../Power-Seeking/tools/power.sh <command> [options]
#
#   status                  what's running: the queue's counts and deadline, containers, load, the read cache
#   sync                    copy harness/ into WSL, where jobs run from (harness/sync.sh)
#   test                    the known-answer tests of power_horizons.py and the read cache
#   links                   check every relative link in the project's .md files; must report 0 broken
#   scan [list]             secret scan of files changed since the last commit, or of a file list; prints paths and kinds only
#   cache [warm|stats|clear]  the read cache of the run records (tools/record_cache.py)
#   dataset [--refresh]     rebuild analysis/data/ and its digests; --refresh re-reads the records and raw logs
#   power [config] [json]   print POWER_H for a config's arms (default viz/run-v4-both.json), optionally writing its --json
#   page [config] [--out f] build one results page from a config (default viz/run-v4-both.json)
#   pages [--dry-run] [--both-only]  the findings tables and all three pages, keeping each page's arms at one scoring density
#
# While the every-turn rescoring is partial, `power` and `page` mix every-turn and every-5-turn arms where a config sets
# "rollback_rows": for numbers to report use `pages`, which leaves out a task's rows until all that page's arms have them.
# POWER_CACHE names the read cache's folder; set it empty to read the records directly (same output, slower).
set -euo pipefail
PROJECT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
EXP=$PROJECT/3-experiments/linuxarena-power-v0
HOME_V0=${POWER_V0_HOME:-$HOME/power-v0}
export POWER_CACHE=${POWER_CACHE-$HOME_V0/cache}
# Bytecode goes to WSL, not into the repository (-I ignores PYTHONPYCACHEPREFIX, so it's -X here).
PY=(python3 -I -X "pycache_prefix=$HOME_V0/cache/pycache")
CT_PY=${POWER_V0_CT:-$HOME_V0/src/control-tower}/.venv/bin/python
cmd=${1:-help}; shift || true

config() {  # the config's path, from a name relative to the experiment folder or viz/
  local c=${1:-viz/run-v4-both.json}
  for f in "$c" "$EXP/$c" "$EXP/viz/$c"; do [ -f "$f" ] && { (cd "$(dirname "$f")" && echo "$PWD/$(basename "$f")"); return; }; done
  echo "config not found: $c" >&2; exit 2
}

case $cmd in
  status)
    q=$HOME_V0/queue
    echo "queue: $(cut -f2 "$q/status.tsv" 2>/dev/null | sort | uniq -c | sort -rn | head -5 | awk '{c=$1; $1=""; printf "%s%s; ", c, $0}')"
    echo "deadline $(cat "$q/deadline" 2>/dev/null), cap $(cat "$q/max_envs" 2>/dev/null); containers $(docker ps -q | wc -l); load $(cut -d' ' -f1-3 /proc/loadavg)"
    "${PY[@]}" "$PROJECT/tools/record_cache.py" stats
    ;;
  sync) bash "$EXP/harness/sync.sh" ;;
  test)
    "${PY[@]}" "$EXP/harness/test_power_horizons.py" | tail -1
    "${PY[@]}" "$PROJECT/tools/test_record_cache.py" | tail -1
    ;;
  links) "${PY[@]}" "$PROJECT/tools/check_links.py" "$PROJECT" ;;
  scan)
    list=${1:-}
    if [ -z "$list" ]; then
      list=$(mktemp); trap 'rm -f "$list"' EXIT
      since=$(git -C "$PROJECT" -c safe.directory='*' log -1 --format=%ct)
      find "$PROJECT" -path "$PROJECT/.git" -prune -o -type f -newermt "@$since" -print > "$list"
    fi
    PYTHONDONTWRITEBYTECODE=1 "$CT_PY" "$EXP/harness/vm/secret_scan.py" "$list" | grep -E '^(HIT|UNREADABLE|scanned) '
    ;;
  cache) "${PY[@]}" "$PROJECT/tools/record_cache.py" "${1:-stats}" ;;
  dataset) "${PY[@]}" "$EXP/analysis/build_dataset.py" "$@" ;;
  power)
    mapfile -t args < <("${PY[@]}" - "$(config "${1:-}")" <<'EOF'
import json, sys
c = json.load(open(sys.argv[1]))
print("--before", c["before"][0], "--nowork-before", c["before"][1], sep="\n")
for k, (lab, nw) in c["afters"].items():
    print("--after", f"{k}={lab}", "--nowork-after", f"{k}={nw}", sep="\n")
print("--reward", c.get("reward", "first-pass"), sep="\n")
if c.get("rollback_rows") is True:
    print("--rollback-rows")
EOF
    )
    "${PY[@]}" "$EXP/harness/power_horizons.py" "${args[@]}" ${2:+--json "$2"}
    ;;
  page)
    cfg=$(config "${1:-}"); shift || true
    cd "$EXP/viz" && "${PY[@]}" build_dashboard.py --config "$cfg" "$@"
    ;;
  pages) "${PY[@]}" "$EXP/harness/vm/sync_rollback_pages.py" "$@" ;;
  *) sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}" | grep -v '^set -euo' | sed 's/^# \{0,1\}//'; [ "$cmd" = help ] ;;
esac

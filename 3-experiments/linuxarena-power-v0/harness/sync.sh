#!/usr/bin/env bash
# Copy the harness from the repository (the one copy that is edited) into $POWER_V0_HOME/harness, where it runs,
# then check that every file matches. Copies the scripts at the top and the task files in tasks/; old/ (retired
# scripts) stays in the repository only. It also writes the experiment folder's location into the copy's exp-dir
# file, for power_paths.py. Run it from the repository's harness folder (in WSL, as root):  bash <repo>/.../harness/sync.sh
set -eu
SRC=$(cd "$(dirname "$0")" && pwd)
. "$SRC/paths.sh"
DST=$POWER_V0_HOME/harness
mkdir -p "$DST/tasks"
[ "$SRC" -ef "$DST" ] && { echo "this is the synced copy: run sync.sh from the repository's harness folder"; exit 1; }
echo "$(dirname "$SRC")" > "$DST/exp-dir.new" && mv -f "$DST/exp-dir.new" "$DST/exp-dir"
files() { (cd "$1" && ls *.py *.sh tasks/*.txt 2>/dev/null); }
# Copy to a temporary name, then rename: a launch.sh that bash is still executing keeps reading its old copy.
for f in $(files "$SRC"); do
  cp "$SRC/$f" "$DST/$f.new" && mv -f "$DST/$f.new" "$DST/$f"
done
chmod +x "$DST"/*.sh
bad=0
for f in $(files "$SRC"); do
  [ "$(sha256sum < "$SRC/$f")" = "$(sha256sum < "$DST/$f")" ] || { echo "MISMATCH $f"; bad=1; }
done
for f in $(files "$DST"); do
  [ -e "$SRC/$f" ] || echo "only in WSL (not in the project folder): $f"
done
[ $bad = 0 ] && echo "harness in sync, combined hash $(cd "$DST" && cat $(files "$DST") | sha256sum | cut -c1-12)"

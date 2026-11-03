#!/usr/bin/env bash
# Copy the harness from the project folder (the one copy that is edited) into WSL, then check that
# every file matches. Copies the scripts at the top and the task files in tasks/; old/ (retired scripts)
# stays in the project folder only. Run inside WSL as root:  bash /mnt/c/.../harness/sync.sh
set -eu
SRC=/mnt/c/Users/arya/OneDrive/Desktop/AI-Safety/Projects/Power-Seeking/3-experiments/linuxarena-power-v0/harness
DST=/root/power-v0/harness
mkdir -p "$DST/tasks"
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

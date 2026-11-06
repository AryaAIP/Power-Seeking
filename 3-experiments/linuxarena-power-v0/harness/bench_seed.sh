#!/usr/bin/env bash
# Test 4: build a seed of root's Go build cache in a throwaway container of the final image (cgo on, no extra flags, the real
# paths), and prove it gives the same bytes as a cold build. Prints hashes, sizes and times only.
#   bench_seed.sh <output folder>      writes seed.tar there
set -u
OUT=$1; mkdir -p "$OUT"
H=$(cd "$(dirname "$0")" && pwd); . "$H/paths.sh"
set -a; . "$POWER_V0_HOME/config/ct.env"; set +a
IMG=linuxarena/env-model_registry:${ENV_IMAGE_TAG_MODEL_REGISTRY:-latest}
cat > "$OUT/inner.sh" <<'I'
set -u
cd /app/model-registry
el() { awk -v a="$1" -v b="$(date +%s.%N)" 'BEGIN{printf "%.1f", b-a}'; }
case "$1" in
  cold)
    echo "go: $(go version); cgo: $(go env CGO_ENABLED); GOCACHE: $(go env GOCACHE); GOFLAGS: $(go env GOFLAGS)"
    s=$(date +%s.%N); go build -o /out/cold.bin . ; echo "cold build rc=$? seconds=$(el $s)"
    s=$(date +%s.%N); go test -run '^$' ./... >/dev/null 2>&1; echo "test binaries rc=$? seconds=$(el $s)"
    go clean -testcache
    tar -C "$(go env GOCACHE)" -cf /out/seed.tar .
    echo "seed files: $(find "$(go env GOCACHE)" -type f | wc -l)"
    ;;
  seeded)
    mkdir -p /root/.cache/go-build
    s=$(date +%s.%N); tar -C /root/.cache/go-build --touch --no-same-owner -xf /out/seed.tar; echo "load rc=$? seconds=$(el $s)"
    s=$(date +%s.%N); go build -o /out/seeded.bin . ; echo "seeded build rc=$? seconds=$(el $s)"
    s=$(date +%s.%N); GODEBUG=gocacheverify=1 go build -o /out/verify.bin . 2>/out/verify.err; rc=$?; echo "gocacheverify rc=$rc seconds=$(el $s) lines_with_panic=$(grep -c panic /out/verify.err)"
    ;;
esac
I
run() { docker run --rm --network none --entrypoint bash -v "$OUT:/out" "$IMG" /out/inner.sh "$1" 2>&1 | sed -E 's/(pass|secret|token|key|DATABASE_URL)[^ ,"]*/<m>/Ig' | cut -c1-200; }
echo "== cold, in a fresh container"; s=$(date +%s); run cold; echo "container seconds: $(( $(date +%s) - s ))"
echo "== seeded, in a fresh container"; s=$(date +%s); run seeded; echo "container seconds: $(( $(date +%s) - s ))"
cd "$OUT" || exit 1
sha256sum cold.bin seeded.bin verify.bin | cut -c1-16,65-
cmp cold.bin seeded.bin && echo "cmp: cold and seeded are byte-identical"
cmp cold.bin verify.bin && echo "cmp: cold and gocacheverify are byte-identical"
ls -la seed.tar | awk '{print "seed.tar bytes:", $5}'
rm -f cold.bin seeded.bin verify.bin verify.err inner.sh

#!/bin/sh
# Build one target in a checkout or worktree with devkitARM, log to <worktree>/build/<target>.log,
# and print only the exit code plus errors and warnings.
# Usage: sh .claude/build.sh <worktree> [rom|release|generated|<file.c>]
#   rom        pokeemerald.gba (debug menus on; the default)
#   release    pokeemerald-release.gba (debug menus off)
#   generated  build tools, then generated headers (what a fresh worktree needs before a partial build)
#   src/x.c    compile just that file (also builds tools and generated sources on a cold tree)
wt=${1:?usage: build.sh <worktree> [rom|release|generated|src/file.c]}
target=${2:-rom}
export PATH=/opt/devkitpro/devkitARM/bin:$PATH
tc=TOOLCHAIN=/opt/devkitpro/devkitARM
mkdir -p "$wt/build"
log="$wt/build/$(echo "$target" | tr / _).log"

case "$target" in
    rom) make -C "$wt" -j16 $tc > "$log" 2>&1 ;;
    release) make -C "$wt" -j16 release $tc > "$log" 2>&1 ;;
    # `generated` skips the tool prebuild (it's in RULES_NO_SCAN), so build the tools first.
    generated) make -C "$wt" -j16 -f make_tools.mk > "$log" 2>&1 && make -C "$wt" -j16 generated $tc >> "$log" 2>&1 ;;
    *.c) make -C "$wt" -j16 "build/emerald/${target%.c}.o" $tc > "$log" 2>&1 ;;
    *) echo "unknown target: $target"; exit 2 ;;
esac
status=$?

echo "exit $status, log $log"
# Expected warnings (pokedex.c stringop-overflow, LTO type mismatches, RWX segment, libpng bKGD,
# tool-build json.hpp) are filtered out.
grep -E 'error:|warning:|\*\*\*' "$log" | grep -vE 'pokedex\.c|lto-type-mismatch|type of .* does not match|RWX|json\.hpp|libpng warning' | head -20
exit $status

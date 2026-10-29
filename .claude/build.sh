#!/bin/sh
# Build one target in a checkout or worktree with devkitARM, log to <worktree>/build/<target>.log,
# and print only the exit code plus errors and warnings.
# Usage: sh .claude/build.sh <worktree> [rom|release|debug|check [TESTS]|generated|<file.c>]
#   rom        pokeemerald.gba (debug menus on; the default)
#   release    pokeemerald-release.gba (debug menus off)
#   debug      the -Og/-g build, as pokeemerald-debug.gba so it can't stand in for the rom output
#   check      make check (headless tests); an optional third argument is the TESTS name prefix
#   generated  build tools, then generated headers (what a fresh worktree needs before a partial build)
#   src/x.c    compile just that file (also builds tools and generated sources on a cold tree)
wt=${1:?usage: build.sh <worktree> [rom|release|debug|check [TESTS]|generated|src/file.c]}
target=${2:-rom}
export PATH=/opt/devkitpro/devkitARM/bin:$PATH
# Host compiler settings leak into the build. arm-none-eabi-gcc honours CPATH (the owner's points at
# the macOS SDK headers), so the GBA code compiles against Darwin's libc headers with _FORTIFY_SOURCE:
# `make debug` and `make check` fail to link, and the ROM bytes depend on the shell. The Makefile
# appends to CFLAGS, and the host tool builds can pick up the rest (e.g. Homebrew LDFLAGS).
unset CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH OBJC_INCLUDE_PATH LIBRARY_PATH LDFLAGS CFLAGS CPPFLAGS
tc=TOOLCHAIN=/opt/devkitpro/devkitARM
mkdir -p "$wt/build"
log="$wt/build/$(echo "$target" | tr / _).log"

case "$target" in
    rom) make -C "$wt" -j16 $tc > "$log" 2>&1 ;;
    release) make -C "$wt" -j16 release $tc > "$log" 2>&1 ;;
    debug) make -C "$wt" -j16 debug FILE_NAME=pokeemerald-debug $tc > "$log" 2>&1 ;;
    check) make -C "$wt" -j16 check ${3:+"TESTS=$3"} $tc > "$log" 2>&1 ;;
    # `generated` skips the tool prebuild (it's in RULES_NO_SCAN), so build the tools first.
    generated) make -C "$wt" -j16 -f make_tools.mk > "$log" 2>&1 && make -C "$wt" -j16 generated $tc >> "$log" 2>&1 ;;
    *.c) make -C "$wt" -j16 "build/emerald/${target%.c}.o" $tc > "$log" 2>&1 ;;
    *) echo "unknown target: $target"; exit 2 ;;
esac
status=$?

echo "exit $status, log $log"
# The logs hold non-UTF-8 bytes (tool and test output), which BSD sed/awk reject in a UTF-8 locale.
LC_ALL=C
export LC_ALL
# Known warnings. Each entry matches one whole line, so a new warning in the same file (or an error)
# still shows. The src/ and include/ ones come from the LTO link and appear only in `release`; besides
# them, every ROM link gives the RWX one, the tool build json.hpp and the asset conversion libpng
# (under -j a libpng warning can lose its newline and share a line with another one or with a make
# recipe; [^:]* lets that through but not a glued warning, which has a colon). The note: lines that
# follow a warning are never printed (only error/warning/make *** lines, in any case, are).
# The LTO assembler's compound_string warnings (`release` only) need a pattern, because their temp .s
# names (which may hold spaces, never a colon) and section hashes change on every build. So that a
# new one shows, a successful build with any of them must have exactly compound_count (each LTO link
# prints all 6).
compound="^[^:]*\.s: Warning: section .\.rodata\.compound_string\.[0-9a-f]+' size \(0x[0-9a-f]+\) is not a multiple of its entry size 0x[0-9a-f]+\$"
compound_count=6
expected="^\.\./\.\./src/pokedex\.c:4507: warning: writing 1 byte into a region of size 0 \[-Wstringop-overflow=\]\$
^\.\./\.\./src/mystery_gift_client\.c:102: warning: '(__builtin_)?memcpy' reading 1024 bytes from a region of size 16 \[-Wstringop-overread\]\$
^\.\./\.\./src/intro_frlg\.c:249: warning: type of 'gMultiBootProgram_PokemonColosseum_Start' does not match original declaration \[-Wlto-type-mismatch\]\$
^\.\./\.\./include/faraway_island\.h:4: warning: type of 'GetMewMoveDirection' does not match original declaration \[-Wlto-type-mismatch\]\$
$compound
^[^ ]*ld: warning: [^ ]*\.elf has a LOAD segment with RWX permissions\$
^\./nlohmann/json\.hpp:[0-9:]* warning: identifier '_json(_pointer)?' preceded by whitespace in a literal operator declaration is deprecated \[-Wdeprecated-literal-operator\]\$
^(libpng warning: bKGD: invalid index)+[^:]*\$"
problems='error:|warning:|\*\*\*'
grep -aiE "$problems" "$log" | grep -vE "$expected" |
    awk 'NR <= 40; END { if (NR > 40) printf "... %d more (%d in total), see the log\n", NR - 40, NR }'
found=$(grep -acE "$compound" "$log")
[ "$status" -eq 0 ] && [ "$found" -gt 0 ] && [ "$found" -ne "$compound_count" ] &&
    echo "$found .rodata.compound_string assembler warnings, expected $compound_count: see the log"
filtered=$(grep -aiE "$problems" "$log" | grep -cE "$expected")
[ "$filtered" -gt 0 ] && echo "($filtered expected warning lines filtered)"
# For check, also print mgba-rom-test-hydra's end-of-run summary without its colour codes: the
# per-test lists ("  - file:line: test name: first output line", at most 15 per list here) under the
# FAILED / ASSUMPTIONS_FAILED / KNOWN_FAILING-passing headings, then the counts per result. Hydra
# leaves out the FAILED count when it's 0, so print it then too (not after "No tests found.",
# which comes without counts, so it doesn't read as a pass).
[ "$target" = check ] && awk '
    function more() { if (n > 15) printf "  ... %d more, see the log\n", n - 15; n = 0 }
    /mgba-rom-test-hydra / { on = 1; next }
    !on { next }
    { gsub(/\033\[[0-9;]*m/, "") }
    /^  (FAILED tests|Tests with ASSUMPTIONS_FAILED|KNOWN_FAILING tests PASSING):$/ { more(); inlist = 1; print; next }
    /^$/ { inlist = 0; next }
    inlist && /^  - / { if (++n <= 15) print; next }
    /^No tests found\.$/ { print; next }
    /^- (Tests )?(FAILED|EXPECTED_FAIL_PASSING|KNOWN_FAILING|ASSUMPTIONS_FAILED|TO_DO|KNOWN_FAILING_PASSING|EXPECT_FAILING|PASSED|TOTAL): / {
        counts = counts $0 "\n"
        if (/^- Tests FAILED:/) failed = 1
    }
    END {
        more()
        if (counts != "" && !failed) print "- Tests FAILED:          0"
        printf "%s", counts
    }' "$log"
# The ROM resets a runner's exit code when it restarts after "Tests resume after CRASH"
# (test/test_test_runner.c), so a failure that ran earlier on the same runner is counted but
# make check still exits 0 (#73). Fail on hydra's count lines for the results that should fail:
# FAILED (the only one with "Add TESTS="), KNOWN_FAILING_PASSING and EXPECTED_FAIL_PASSING.
if [ "$target" = check ] && [ "$status" -eq 0 ] &&
    grep -aqE '^- .*(Add TESTS=|KNOWN_FAILING_PASSING|EXPECTED_FAIL_PASSING)' "$log"; then
    echo "make check exited 0 with failing results, so exiting 1"
    status=1
fi
exit $status

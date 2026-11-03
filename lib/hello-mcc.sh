# shellcheck shell=bash
# hello-mcc.sh — shared library for the hello-galaxy-mesh-change-control scenarios.
#
# Sourced by every scenario driver: path resolution, narration, colour, and
# lightweight assertions. Same shape as lib/hello-external.sh in
# hello-galaxy-external-service.
#
# Scenarios 01, 02, 03, 05 and 06 run on the laptop and talk to nothing.
# Scenario 04 is the only one that reaches a goatnet, and it only reads.

set -o pipefail

MC_LIB="${BASH_SOURCE[0]}"
MC_ROOT="$(cd "$(dirname "$MC_LIB")/.." && pwd)"
export MC_ROOT
cd "$MC_ROOT" || exit 2
MC_RUN="${MC_RUN:-.run}"
export MC_RUN
mkdir -p "$MC_RUN"

# The scenarios pin "today" so the expiry dates in the fixtures do not rot.
export MCC_TODAY="${MCC_TODAY:-2026-09-23}"

# The python that has PyYAML. Set MC_PY to force one.
mc_pick_python() {
  local c
  for c in "$@"; do
    command -v "$c" >/dev/null 2>&1 || continue
    "$c" -c 'import yaml' 2>/dev/null && { printf '%s\n' "$c"; return 0; }
  done
  for c in "$@"; do
    command -v "$c" >/dev/null 2>&1 && { printf '%s\n' "$c"; return 0; }
  done
  return 1
}
MC_PY="${MC_PY:-$(mc_pick_python python3 python || echo python3)}"
export MC_PY

# --- presentation -----------------------------------------------------------
if [ -t 1 ] && [ "${NO_COLOR:-}" = "" ]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'
  C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_CYAN=$'\033[36m'; C_BLUE=$'\033[34m'
else
  C_RESET=""; C_BOLD=""; C_DIM=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_CYAN=""; C_BLUE=""
fi

MC_STEP=0
mc_step()  { MC_STEP=$((MC_STEP+1)); printf '\n%s%s── Step %d ─ %s%s\n' "$C_BOLD" "$C_CYAN" "$MC_STEP" "$1" "$C_RESET"; }
mc_say()   { printf '%s%s%s\n' "$C_DIM" "$*" "$C_RESET"; }
mc_note()  { printf '%s  • %s%s\n' "$C_BLUE" "$*" "$C_RESET"; }
mc_cmd()   { printf '%s$ %s%s\n' "$C_BOLD" "$*" "$C_RESET"; }
mc_ok()    { printf '%s  ✓ %s%s\n' "$C_GREEN" "$*" "$C_RESET"; }
mc_warn()  { printf '%s  ! %s%s\n' "$C_YELLOW" "$*" "$C_RESET"; }
mc_fail()  { printf '%s  ✗ %s%s\n' "$C_RED" "$*" "$C_RESET"; }
mc_honest(){ printf '%s  ⓘ honesty: %s%s\n' "$C_YELLOW" "$*" "$C_RESET"; }
mc_quote() { sed 's/^/    │ /'; }
mc_banner() {
  printf '\n%s%s════════════════════════════════════════════════════════════%s\n' "$C_BOLD" "$C_CYAN" "$C_RESET"
  printf '%s%s  %s%s\n' "$C_BOLD" "$C_CYAN" "$1" "$C_RESET"
  printf '%s%s════════════════════════════════════════════════════════════%s\n' "$C_BOLD" "$C_CYAN" "$C_RESET"
  [ -n "${2:-}" ] && printf '%s  %s%s\n' "$C_DIM" "$2" "$C_RESET"
  printf '%s  mode: %s%s\n' "$C_DIM" "${3:-offline (fixtures only, no goatnet)}" "$C_RESET"
}

# --- assertions -------------------------------------------------------------
MC_PASS=0; MC_FAIL=0; MC_SKIP=0
mc_assert() { local d="$1"; shift; if "$@"; then MC_PASS=$((MC_PASS+1)); mc_ok "$d"; return 0; else MC_FAIL=$((MC_FAIL+1)); mc_fail "$d"; return 1; fi; }
mc_skip()   { MC_SKIP=$((MC_SKIP+1)); mc_warn "skipped: $*"; }
mc_summary() {
  printf '\n%s%s── result ─ %d passed, %d failed, %d skipped%s\n' \
    "$C_BOLD" "$( [ "$MC_FAIL" -eq 0 ] && echo "$C_GREEN" || echo "$C_RED")" \
    "$MC_PASS" "$MC_FAIL" "$MC_SKIP" "$C_RESET"
  [ "$MC_FAIL" -eq 0 ]
}

# mc_not <cmd...> -> 0 iff the command fails (asserting a refusal), output hidden.
mc_not() { ! "$@" >/dev/null 2>&1; }
# mc_exit <code> <cmd...> -> 0 iff the command exits with exactly that code.
mc_exit() { local want="$1"; shift; "$@" >/dev/null 2>&1; [ "$?" -eq "$want" ]; }
# mc_has <needle> <cmd...> -> 0 iff the command's output contains the needle.
# (Captured first: `cmd | grep -q` under pipefail fails when grep exits early.)
mc_has() { local n="$1" out; shift; out="$("$@" 2>&1)"; [[ "$out" == *"$n"* ]]; }

# mcc <args...> -> the offline model.
mcc() { "$MC_PY" bin/mcc "$@"; }

mc_preflight() {
  command -v "$MC_PY" >/dev/null 2>&1 || { mc_fail "no python on PATH (tried python3, python)"; return 1; }
  "$MC_PY" -c 'import yaml' 2>/dev/null \
    || { mc_fail "$MC_PY has no PyYAML — run:  $MC_PY -m pip install -r requirements.txt"; return 1; }
}

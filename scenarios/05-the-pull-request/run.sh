#!/usr/bin/env bash
# Scenario 05 — The pull request, rehearsed. A grant, a hold and a release, each
# as a commit in a SCRATCH git repository under .run/, with the two checks CI
# runs on each. It never touches goat. The real steps are in this scenario's
# README.md.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/lib/hello-mcc.sh"
mc_preflight || exit 1
command -v git >/dev/null 2>&1 || { mc_fail "git not on PATH"; exit 1; }

REH="$MC_RUN/pr-rehearsal"
F="ops/warrant/membership/zagros-dev"   # same path as in goat, inside the scratch repo
rm -rf "$REH"; mkdir -p "$REH/ops/warrant/membership"
g() { git -C "$REH" -c user.name=rehearsal -c user.email=rehearsal@example.internal "$@"; }
g init -q -b main
cp -R fixtures/declarations/ordinary/zagros-dev "$REH/$F"
g add -A && g commit -q -m "base: the membership declaration as merged"

# checks <base-ref> -> what CI would say about HEAD against <base-ref>. CI extracts the
# base revision's whole scope directory and compares merged views.
BASE_DIR="$MC_RUN/pr-base/zagros-dev"
checks() {
  local base="$1"
  rm -rf "$MC_RUN/pr-base"; mkdir -p "$MC_RUN/pr-base"
  g archive "$base" "$F" | tar -x -C "$MC_RUN/pr-base" && mv "$MC_RUN/pr-base/$F" "$BASE_DIR"
  mc_cmd "python3 ops/warrant/membership.py --check        (here: bin/mcc check)"
  mcc check "$REH/$F" | mc_quote
  mc_cmd "python3 ops/ci/check-warrant-narrowing.py --membership BASE_DIR HEAD_DIR   (here: bin/mcc diff)"
  mcc diff "$BASE_DIR" "$REH/$F" | mc_quote
}

mc_banner "The pull request, rehearsed — grant, hold, release" \
          "Each change as a commit, with the two checks CI runs on it. A scratch repo; goat is untouched."

mc_step "PR 1 — give bob P2P for a development clique (a widening): a row in people.yaml"
cat >> "$REH/$F/people.yaml" <<'EOF'
  - peer: peer-bob-zagros-dev-2026-09-02-laptop
    grant: [ZAGROS-DEV-P2P]
    owner: bob
    reason: joins the development clique for the sensor-fusion work
    expires: 2026-12-01
EOF
g diff | grep '^[+-] ' | mc_quote
checks HEAD
mc_assert "the entry is valid" mc_exit 0 mcc check "$REH/$F"
mc_assert "CI calls it a widening: it waits for a CODEOWNERS review" mc_exit 1 mcc diff "$BASE_DIR" "$REH/$F"
g commit -qam "feat(warrant): grant ZAGROS-DEV-P2P to bob's laptop on zagros-dev"
mcc plan --decl "$REH/$F" | grep -E '^peer-bob|changes planned' | mc_quote
mc_note "after merge and deploy, the converger's next pass adds P2P (and removes the PLATFORM-ADMIN"
mc_note "someone gave bob in the dashboard — the file does not list it, so it goes)"

mc_step "PR 2 — quarantine carol (a narrowing): a new holds.yaml"
mc_say "carol has no entry yet, so the hold goes into holds.yaml. (Had she one, the hold would"
mc_say "REPLACE it where it is: one entry per peer across every fragment.)"
cat > "$REH/$F/holds.yaml" <<'EOF'
# Holds: quarantine, and dormancy (PROBATION) lanes.
version: 1
entries:
  - peer: peer-carol-zagros-dev-2026-09-03-laptop
    hold: quarantine
    owner: platform-admins
    reason: signal flood from this device; see the incident issue
    expires: 2026-09-30
EOF
g add -A; g diff --cached | grep '^[+-] ' | mc_quote
checks HEAD
mc_assert "CI proves it a narrowing: one owner's approving click and it merges" \
  mc_exit 0 mcc diff "$BASE_DIR" "$REH/$F"
g commit -qm "fix(warrant): quarantine carol's laptop on zagros-dev"
HOLD_SHA=$(g rev-parse --short HEAD)
mcc plan --decl "$REH/$F" | grep -E '^peer-carol' | mc_quote

mc_step "PR 3 — release carol: revert the hold commit (a widening)"
mc_cmd "git revert $HOLD_SHA"
g revert --no-edit "$HOLD_SHA" >/dev/null
g show --stat --format='%s' HEAD | head -1 | mc_quote
g show HEAD | grep '^[+-] ' | mc_quote
checks HEAD~1
mc_assert "a release is a widening: giving access back is reviewed" \
  mc_exit 1 mcc diff "$BASE_DIR" "$REH/$F"
mc_assert "after the revert, carol's desired set is exactly what it was before the hold" \
  "$MC_PY" - "$REH/$F" <<'PY'
import json, sys
sys.path.insert(0, "lib")
from mcc import layout, model
live = json.load(open("fixtures/mgmt-state/zagros-dev.json"))
keys = model.key_baselines(live["events"], live["setup_keys"], live["groups"])
d = layout.load_decl(sys.argv[1])
e = next((x for x in d["entries"] if x["peer"].startswith("peer-carol")), None)
base, _ = model.baseline_for("peer-carol-zagros-dev-2026-09-03-laptop", "p-carol", d["baseline"], keys, {})
sys.exit(0 if model.desired_set(e, base, "ZAGROS-DEV") == {"ZAGROS-DEV-DEVELOPER", "ZAGROS-DEV-OBSERVER"} else 1)
PY

mc_step "The rehearsal's history"
g log --oneline | mc_quote
mc_say "Three reviewed diffs. The history IS the record: who changed what, when, and why."
mc_honest "the checks here are this repo's re-implementations; in goat, CI runs goat's own."
mc_honest "the plan here is computed from fixtures; in goat, the converger reads the live goatnet."

echo
mc_say "The real steps, in your goatnet's repository: scenarios/05-the-pull-request/README.md"
mc_say "Next: bash scenarios/06-why-blocked/run.sh"
mc_summary

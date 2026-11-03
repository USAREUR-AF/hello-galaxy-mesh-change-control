#!/usr/bin/env bash
# Scenario 02 — The CI governance rules: entries the check refuses, and why.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/lib/hello-mcc.sh"
mc_preflight || exit 1

mc_banner "What CI refuses — and the reason behind each rule" \
          "The same checks the warrant-registry workflow runs on every membership pull request."

ORD=fixtures/declarations/ordinary/zagros-dev
mc_step "A good declaration passes"
mc_cmd "bin/mcc check $ORD"
mcc check "$ORD" | mc_quote
mc_assert "scenario 01's declaration is valid" mc_exit 0 mcc check "$ORD"
mc_say "The check reads the scope DIRECTORY: its shape first (_scope.yaml, fragments, the"
mc_say "generated baseline), then every rule below over the merged entries of all fragments."

# refuse <fixture> <why> — each fixture is fixtures/refused/<name>/zagros-dev/ (or, for the
# retired layout, the single file in fixtures/refused/<name>/).
refuse() {
  local d="fixtures/refused/$1" why="$2" f title
  if [ -d "$d/zagros-dev" ]; then f="$d/zagros-dev"; title=$(sed -n '1s/^# //p' "$f/_scope.yaml")
  else f=$(ls "$d"/*.yaml); title=$(sed -n '1s/^# //p' "$f"); fi
  mc_step "$title"
  if [ -d "$f" ]; then
    ( cd "$f" && find . -type f | sort | sed 's#^\./##' ) | mc_quote
  fi
  mc_cmd "bin/mcc check $f"
  mcc check "$f" | tail -n +2 | mc_quote
  mc_note "why: $why"
  mc_assert "refused" mc_not mcc check "$f"
}

refuse 01-external-infra-beside-a-person-role \
  "EXTERNAL-INFRA is the tier for a host running an external service (ADR 1178). It is never stacked on a person's role: a person's device holding EXTERNAL-INFRA would carry service-host reach."
refuse 02-external-infra-in-a-mixed-exact \
  "A service host holds EXTERNAL-INFRA alone. The only accepted shape is exact: [ZAGROS-DEV-EXTERNAL-INFRA]."
refuse 03-platform-admin-on-a-machine \
  "PLATFORM-ADMIN reaches everything. It belongs to a person's device, whose holder can be asked; a machine holding it is a standing any-port path nobody is accountable for."
refuse 04-hold-with-no-expiry \
  "A quarantine with no date is a quarantine nobody reviews. The expiry is the review date: when it passes, CI goes red and the expiry job opens the removal PR."
refuse 05-p2p-grant-with-no-expiry \
  "EXTERNAL-INFRA, PLATFORM-ADMIN, BREAKGLASS and P2P widen reach enough that a grant of them must lapse. A grant nobody renews ends."
refuse 06-expired \
  "A past expiry fails CI, and a scheduled job opens the PR that removes the entry. To keep it, say in a PR why it is still needed and who is asking — do not just move the date."
refuse 07-wrong-prefix \
  "One file per goatnet. A group from another goatnet's prefix cannot be managed here, and the converger only ever touches its own prefix."
refuse 08-group-not-in-taxonomy \
  "Group names must exist in the goatnet's taxonomy. A typo is refused rather than creating, or silently ignoring, a group."
refuse 09-two-forms-in-one-entry \
  "An entry is exactly one of grant/absent, exact, or hold. Two forms would leave the desired set ambiguous."
refuse 10-duplicate-peer \
  "One entry per peer ACROSS every fragment, so there is one answer to 'what should this peer hold'. An org's own fragment cannot quietly override people.yaml. This is also why a hold REPLACES a peer's grant entry (scenario 01)."
refuse 11-typo-key \
  "An unknown key is refused. Were it ignored, 'grants:' would parse as an entry with no form and silently mean 'back to the key baseline'."
refuse 12-no-owner-no-reason \
  "Every entry names who to ask and why it exists. The reason is what a reviewer approves on; 200 characters at most."

mc_say ""
mc_say "── The directory's own shape ──"
refuse 13-single-file-layout \
  "The single file is retired. A scope is a directory so an org can own its own fragment (orgs/<org>.yaml) and people, services, substrate and holds are filed apart — without two sources of truth."
refuse 14-converge-in-a-fragment \
  "converge: enforce is the switch that makes every entry real. It lives in _scope.yaml alone, which only the platform owners in CODEOWNERS approve; a fragment an org owns must not be able to flip it."
refuse 15-stray-underscore-file \
  "Names starting _ are reserved for the switch and the generated baseline. Anything else would look special and be read as an ordinary fragment by nothing, or by everything."
refuse 16-no-baseline \
  "The generated baseline is every person-device's starting set. Without it the converger falls back to setup keys, which can be deleted or edited; CI requires the file and, where the manifests are present, that it is not stale."

mc_step "Where this runs for real"
mc_note "goat: ops/warrant/membership.py --check, in the warrant-registry workflow, on every PR"
mc_note "      that touches ops/warrant/membership/ or ops/operators/. Run it yourself before pushing."
mc_note "      After editing a manifest: ops/warrant/membership.py --generate-baseline, and commit it."
mc_honest "lib/mcc/rules.py re-implements that check for this demo. It was checked to give the"
mc_honest "same verdicts as goat's checker on every fixture here; if the two ever disagree, goat's is right."

echo
mc_say "Next: bash scenarios/03-narrowing-vs-widening/run.sh"
mc_summary

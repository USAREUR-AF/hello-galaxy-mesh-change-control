#!/usr/bin/env bash
# Scenario 03 — Narrowing vs widening: which diffs only take access away.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/lib/hello-mcc.sh"
mc_preflight || exit 1
D=fixtures/diffs

mc_banner "Narrowing vs widening — what CI can prove, and what waits for a person" \
          "Twenty-two small changes to one scope's declaration, and the verdict CI posts on each."
B=$D/base/zagros-dev

mc_step "The declaration before every change"
for f in _scope.yaml substrate.yaml people.yaml holds.yaml; do
  mc_cmd "cat $B/$f"; grep -v '^#' "$B/$f" | mc_quote
done
mc_say "(and _baseline.generated.yaml: alice, bob, carol, erin, frank, gina, hana at DEVELOPER + OBSERVER)"
mc_say "CI runs the narrowing prover on the base and head versions of the directory — the merged"
mc_say "entries of every fragment, _scope.yaml and the baseline — and posts the"
mc_say "verdict on the pull request. A narrowing still needs one owner's approving click —"
mc_say "GitHub will not let a workflow approve its own pull request — but the review question"
mc_say "has already been answered. A widening waits for a real review. Neither is a CI failure."

# show <case> <expected: narrowing|widening>
show() {
  local want="$2" f="$D/$1/zagros-dev"
  mc_step "$(sed -n '1s/^# //p' "$f/_scope.yaml")"
  diff -r "$B" "$f" | grep -E '^([<>] |Only in)' | grep -v '^[<>] #' | mc_quote
  mc_cmd "bin/mcc diff $B $f"
  mcc diff "$B" "$f" | mc_quote
  if [ "$want" = narrowing ]; then
    mc_assert "proven a narrowing, or no change (exit 0)" mc_exit 0 mcc diff "$B" "$f"
  else
    mc_assert "a widening (exit 1) — waits for review" mc_exit 1 mcc diff "$B" "$f"
  fi
}

mc_say ""
mc_say "── Narrowings: each only takes access away ──"
show n1-remove-a-grant narrowing
show n2-new-absent-entry narrowing
show n3-add-a-hold narrowing
show n4-shrink-an-exact narrowing
show n5-delete-a-grant-only-entry narrowing
show n6-earlier-expiry narrowing
show n7-owner-and-reason-only narrowing
show n8-dormancy-probation narrowing
show n9-move-to-another-fragment narrowing
mc_note "which fragment an entry sits in is filing, not access: the prover compares merged views"
show n10-baseline-loses-a-group narrowing
mc_note "the generated baseline is graded too: a person's starting set shrinking only takes away"

mc_say ""
mc_say "── Widenings: each gives something back or keeps it longer ──"
show w1-add-a-grant widening
show w2-release-a-hold widening
mc_note "releasing a quarantine is a widening: containment is fast, giving access back is reviewed"
show w3-hold-back-to-an-entry widening
show w4-extend-expiry widening
mc_note "do not just move the date: say in the PR why it is still needed and who is asking"
show w5-remove-expiry widening
mc_note "this one is also refused outright by scenario 02's rules: a P2P grant must carry an expiry"
mc_assert "…and the schema check refuses it too" mc_not mcc check "$D/w5-remove-expiry/zagros-dev"
show w6-drop-an-absent widening
show w7-delete-an-absent-entry widening
mc_note "deleting an entry is only a narrowing when the entry only granted"
show w8-converge-change widening
mc_note "report -> enforce is what makes every entry real, so a converge change is never proven"

mc_step "Deleting the whole scope directory"
mc_cmd "bin/mcc diff $B -"
mcc diff "$B" - | mc_quote
mc_assert "deleting the declaration ungoverns the scope — a widening" mc_exit 1 mcc diff "$B" -

show w9-new-grant-entry widening
show w10-baseline-gains-a-group widening
mc_note "a manifest change that raises a person's tier reaches every one of their devices"
show w11-person-added-to-baseline widening
mc_note "dave was unknown and never changed; with a manifest he is planned — that is new reach"

mc_step "Where this runs for real"
mc_note "goat: ops/ci/check-warrant-narrowing.py --membership BASE_DIR HEAD_DIR, in the warrant-registry"
mc_note "      workflow. It posts 'warrant: narrowing' or 'warrant: widening' as a PR comment."
mc_note "owners who approve: the CODEOWNERS owners of ops/warrant/membership/"
mc_honest "lib/mcc/narrowing.py re-implements the prover. It was checked to return the same lines as"
mc_honest "goat's prover for every case here; if the two ever disagree, goat's is right."

echo
mc_say "Next: bash scenarios/04-live-read-only/run.sh   (needs your own goatnet's mesh and your token)"
mc_summary

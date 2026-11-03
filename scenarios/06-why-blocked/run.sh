#!/usr/bin/env bash
# Scenario 06 — `goat warrant why-blocked`: is it the ACL, or is it membership?
#
# Needs the goat CLI (built from goatcore). Needs NO
# network, NO token and NO mesh: it reads the declared ACL compiled into goat.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/lib/hello-mcc.sh"
GOAT="${GOAT_BIN:-goat}"
SCOPE="${MCC_WHY_SCOPE:-zagros-dev}"

mc_banner "why-blocked — ask the declared ACL before you write a rule" \
          "PERMITTED, BLOCKED, a refused question, and a one-way path that is correct." \
          "offline (goat reads the declaration compiled into it; no network)"

command -v "$GOAT" >/dev/null 2>&1 || {
  mc_fail "no goat on PATH. Build it from goatcore (crates/goat-cli), or set GOAT_BIN"
  mc_warn "INCOMPLETE: nothing ran."; exit 2; }
"$GOAT" --version | mc_quote

why() { "$GOAT" warrant why-blocked --scope "$SCOPE" "$@"; }

probe=$(why --from DEVELOPER --to INFRA --port 7447 2>&1)
if printf '%s' "$probe" | grep -q 'NoSuchSite'; then
  mc_warn "this goat does not know scope $SCOPE. Using scope zagros instead;"
  mc_warn "the lessons are the same. Set MCC_WHY_SCOPE to a scope your goat knows."
  SCOPE=zagros
fi

mc_step "PERMITTED — the ACL is not your problem"
mc_cmd "goat warrant why-blocked --scope $SCOPE --from DEVELOPER --to INFRA --port 7447"
why --from DEVELOPER --to INFRA --port 7447 2>&1 | mc_quote
mc_assert "a developer may reach the substrate's fabric port" mc_has "PERMITTED" why --from DEVELOPER --to INFRA --port 7447
mc_note "so if a developer's laptop cannot reach the router, the first question is whether the laptop"
mc_note "HOLDS the developer group. That is membership — scenario 01 predicts it, scenario 04 reads it."
mc_note "If the key never granted it, the fix is a grant: entry (scenario 05), not a new rule."

mc_step "BLOCKED — and the smallest change that would open it"
mc_cmd "goat warrant why-blocked --scope $SCOPE --from OBSERVER --to INFRA --port 22"
why --from OBSERVER --to INFRA --port 22 2>&1 | mc_quote
mc_assert "observer -> infra ssh is blocked, with a named port set" mc_has "The minimal port-set that closes it: shell" \
  why --from OBSERVER --to INFRA --port 22
mc_note "the diff it prints is a RULE change (an access rule intent, reviewed like any widening)."
mc_note "Before you paste it, ask whether the person needs the rule, or needs a different group."

mc_step "A malformed question is refused, not answered 'blocked'"
mc_cmd "goat warrant why-blocked --scope $SCOPE --from DEVELOPERS --to INFRA --port 22"
why --from DEVELOPERS --to INFRA --port 22 2>&1 | mc_quote
mc_assert "a group the scope does not have: exit 1, with near matches" mc_not why --from DEVELOPERS --to INFRA --port 22
mc_assert "…and it says it is a malformed question" mc_has "is not a group in scope" why --from DEVELOPERS --to INFRA --port 22
mc_note "the same typo in a membership file is refused by CI (scenario 02, group-not-in-taxonomy)."

mc_step "A one-way path that is correct"
mc_cmd "goat warrant why-blocked --scope $SCOPE --from INFRA --to P2P --port 22"
why --from INFRA --to P2P --port 22 2>&1 | mc_quote
mc_assert "nothing initiates toward P2P" mc_has "No rule connects" why --from INFRA --to P2P --port 22
mc_note "P2P grants a peer outbound lateral reach and nothing inbound. A peer that holds ONLY P2P is"
mc_note "reached by nothing — its role group is what makes it reachable. Writing 'infra -> P2P' to fix"
mc_note "one box would open every P2P peer on the goatnet. Check the peer's groups first."

mc_step "Machine-readable, for scripts"
mc_cmd "goat warrant why-blocked --scope $SCOPE --from OBSERVER --to INFRA --port 22 --json"
why --from OBSERVER --to INFRA --port 22 --json 2>&1 | head -20 | mc_quote
mc_assert "the JSON says which plane it read and what it did not consult" \
  mc_has '"not_consulted"' why --from OBSERVER --to INFRA --port 22 --json

mc_honest "why-blocked reads the DECLARED plane. It does not read live membership, what is listening,"
mc_honest "or DNS, and it says so on every run: it can prove a path is not permitted, not that one works."

echo
mc_say "That is the series. The runbook to keep open: warrant-runbook §4A (membership), in goatcore."
mc_summary

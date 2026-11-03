#!/usr/bin/env bash
# Scenario 01 — Read a membership declaration and predict what the converger does.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/lib/hello-mcc.sh"
mc_preflight || exit 1
D=fixtures/declarations
ORD=$D/ordinary/zagros-dev
HOLD=$D/hold/zagros-dev
REL=$D/release-by-delete/zagros-dev

mc_banner "Predict the plan — the declaration says what each peer should hold" \
          "Declared and key baselines, grant/absent, exact, hold, unknown, and groups that are not ours."

mc_step "The management server, as the converger reads it"
mc_say "Ten peers on scope zagros-dev, the setup keys that minted them, and the event"
mc_say "that ties each peer to its key. All made up: fixtures/mgmt-state/zagros-dev.json."
"$MC_PY" - <<'PY' | mc_quote
import json, sys
sys.path.insert(0, "lib")
from mcc.model import key_baselines
live = json.load(open("fixtures/mgmt-state/zagros-dev.json"))
base = key_baselines(live["events"], live["setup_keys"], live["groups"])
print(f"{'PEER':<40} {'KEY BASELINE':<40} HOLDS NOW")
for p in live["peers"]:
    b = base.get(p["id"])
    print(f"{p['name']:<40} {', '.join(sorted(b)) if b is not None else '(none)':<40} {', '.join(p['groups'])}")
PY
mc_note "dave logged in interactively and erin's key was deleted: neither has a key baseline"
mc_note "mgmt-demo-01's key granted nothing, so its baseline is the empty set, not 'none'"
mc_note "hana's phone enrolled on her key for phones and tablets (its name ends -handset)"

mc_step "The declared baseline — each person's groups, from their manifest"
mc_say "A person's peer does not have to trust its setup key: the key can be deleted (erin's"
mc_say "was) or edited. The scope's _baseline.generated.yaml is generated from the operator"
mc_say "manifests — in goat, ops/operators/<env>/<handle>.yml — and says, per person, what a"
mc_say "laptop starts from (device) and what a phone or tablet starts from (handset)."
mc_cmd "bin/mcc baseline      (from fixtures/manifests/zagros-dev/*.yml; in goat: membership.py --generate-baseline)"
mcc baseline | grep -v '^#' | mc_quote
mc_assert "the committed baseline matches the manifests (CI fails a stale one)" \
  mc_exit 0 mcc baseline --check "$ORD"
mc_note "ivy's manifest is revoked: she is not in it. dave has no manifest: he is not either."
mc_note "phones and tablets get OBSERVER (+ HANDSET, which only carries mesh DNS) whatever the person's tier"
mc_say ""
mc_say "Baseline, per peer: DECLARED if the name is peer-<handle>[-<org>]-zagros-dev-<date>… and the handle is listed;"
mc_say "else the KEY that minted it; else none, and the peer is unknown."

mc_step "The declaration — a directory of exceptions"
mc_cmd "ls $ORD"
( cd "$ORD" && find . -type f | sort | sed 's#^\./##' ) | mc_quote
mc_say "_scope.yaml is the switch (scope and converge, nothing else). The fragments hold entries"
mc_say "by purpose — people.yaml, services.yaml, substrate.yaml, holds.yaml, orgs/<org>.yaml — and"
mc_say "the converger reads them merged: one entry per peer across all of them."
for f in _scope.yaml substrate.yaml services.yaml people.yaml; do
  mc_cmd "cat $ORD/$f"
  grep -v '^#' "$ORD/$f" | mc_quote
done

mc_step "The plan: desired = hold ? {QUARANTINED} : exact ? list : baseline ∪ grant − absent"
mc_cmd "bin/mcc plan --decl $ORD --all"
mcc plan --decl "$ORD" --all | mc_quote
mc_note "alice    grant/absent: declared baseline {DEVELOPER, OBSERVER} + P2P − OBSERVER"
mc_note "bob      no entry: back to his baseline. His PLATFORM-ADMIN was a dashboard edit; it goes"
mc_note "service  exact: the key granted DEVELOPER, the entry says EXTERNAL-INFRA alone"
mc_note "dave     unknown: no manifest, no key, no exact/hold — never changed, even his PLATFORM-ADMIN"
mc_note "erin     her key was deleted, but her manifest declares {DEVELOPER, OBSERVER}: planned, + P2P"
mc_note "hana     a phone: her phones-and-tablets set, which it already holds"
mc_note "sensor   blocked: KID is covered by no enabled policy; the converger refuses to add into it"
mc_note "frank    missing-peer: the entry was written before the device enrolled"
mc_note "All, mesh-dns and EX-DEMO-* are not ZAGROS-DEV-* groups: listed, never touched"
mc_assert "alice gains P2P and loses OBSERVER" \
  mc_has "peer-alice-zagros-dev-2026-09-01-laptop  drift         ZAGROS-DEV-P2P                 ZAGROS-DEV-OBSERVER" mcc plan --decl "$ORD"
mc_assert "bob's hand-added PLATFORM-ADMIN is planned for removal" \
  mc_has "ZAGROS-DEV-PLATFORM-ADMIN" mcc plan --decl "$ORD"
mc_assert "dave (no baseline, no entry) is unknown, not changed" \
  mc_has "peer-dave-zagros-dev-2026-09-04-desktop  unknown" mcc plan --decl "$ORD"
mc_assert "erin is planned from her declared baseline although her key is gone" \
  mc_has "baseline: declared erin device" mcc plan --decl "$ORD" --all
mc_assert "hana's phone starts from her phones-and-tablets set" \
  mc_has "baseline: declared hana handset" mcc plan --decl "$ORD" --all
mc_assert "6 changes planned; blocked and unknown rows are not counted" \
  mc_has "changes planned 6" mcc plan --decl "$ORD"

mc_step "Quarantine: add a hold entry (holds.yaml)"
mc_cmd "diff -r $ORD $HOLD"
diff -r "$ORD" "$HOLD" | grep -v '^#' | mc_quote
mcc plan --decl "$HOLD" | grep -E 'carol|alice|changes planned' | mc_quote
mc_assert "a held peer's managed set becomes ZAGROS-DEV-QUARANTINED alone" \
  mc_has "peer-carol-zagros-dev-2026-09-03-laptop  drift         ZAGROS-DEV-QUARANTINED         ZAGROS-DEV-DEVELOPER,ZAGROS-DEV-OBSERVER" \
  mcc plan --decl "$HOLD"
mc_note "alice's hold went into holds.yaml and her grant entry left people.yaml: one entry per peer"
mc_note "carol keeps EX-DEMO-DEVELOPER and All: a hold changes managed groups only"
mc_honest "for 'off the mesh this second' the tool is still \`goat admin peer cut\`;"
mc_honest "a hold takes a pull request plus one converger pass (about five minutes)."

mc_step "Release: what does the peer get back?"
"$MC_PY" - <<'PY' | mc_quote
import json, sys
sys.path.insert(0, "lib")
from mcc import layout, model
live = json.load(open("fixtures/mgmt-state/zagros-dev.json"))
keys = model.key_baselines(live["events"], live["setup_keys"], live["groups"])
names = model.minting_keys(live["events"], live["setup_keys"])
ids = {p["name"]: p["id"] for p in live["peers"]}
def desired(path, peer):
    d = layout.load_decl(path)
    e = next((x for x in d["entries"] if x["peer"] == peer), None)
    base, _ = model.baseline_for(peer, ids[peer], d["baseline"], keys, names)
    return sorted(model.desired_set(e, base, "ZAGROS-DEV"))
D = "fixtures/declarations/"
for peer in ("peer-carol-zagros-dev-2026-09-03-laptop", "peer-alice-zagros-dev-2026-09-01-laptop"):
    print(peer)
    print(f"  before the hold        {desired(D + 'ordinary/zagros-dev', peer)}")
    print(f"  held                   {desired(D + 'hold/zagros-dev', peer)}")
    print(f"  hold entry deleted     {desired(D + 'release-by-delete/zagros-dev', peer)}")
    print(f"  hold commit reverted   {desired(D + 'ordinary/zagros-dev', peer)}")
PY
mc_note "carol had no entry before: deleting the hold returns exactly what she held before"
mc_note "alice HAD an entry (grant P2P, absent OBSERVER). One entry per peer, so the hold replaced it."
mc_note "Deleting the hold returns her to her baseline and loses the P2P grant."
mc_note "Reverting the commit that added the hold restores her old entry, and exactly her old groups."
mc_say  "So: release a hold with \`git revert\` of the pull request that added it. Nothing records"
mc_say  "prior groups anywhere — the declaration's history in git is the record."
mc_assert "carol: released = before" "$MC_PY" -c '
import sys; sys.path.insert(0,"lib"); from mcc import layout, model
d=lambda f: layout.load_decl(f)
def s(f):
    x=d(f); e=[y for y in x["entries"] if y["peer"].startswith("peer-carol")]
    b,_=model.baseline_for("peer-carol-zagros-dev-2026-09-03-laptop","p-carol",x["baseline"],{},{})
    return model.desired_set(e[0] if e else None, b, "ZAGROS-DEV")
sys.exit(0 if s("fixtures/declarations/ordinary/zagros-dev")==s("fixtures/declarations/release-by-delete/zagros-dev")=={"ZAGROS-DEV-DEVELOPER","ZAGROS-DEV-OBSERVER"} else 1)'

mc_step "The two gates in front of enforce"
mc_cmd "bin/mcc plan --decl $HOLD --mode enforce --max-changes 5"
mcc plan --decl "$HOLD" --mode enforce --max-changes 5 2>&1 | tail -2 | mc_quote
mc_assert "over --max-changes: the whole run is refused, exit 3, nothing changed" \
  mc_exit 3 mcc plan --decl "$HOLD" --mode enforce --max-changes 5
RO="$MC_RUN/report-only/zagros-dev"
rm -rf "$MC_RUN/report-only"; mkdir -p "$MC_RUN/report-only"; cp -R "$ORD" "$RO"
sed -i.bak 's/^converge: enforce/converge: report/' "$RO/_scope.yaml" && rm -f "$RO/_scope.yaml.bak"
mc_cmd "bin/mcc plan --decl <copy whose _scope.yaml says converge: report> --mode enforce"
mcc plan --decl "$RO" --mode enforce 2>&1 | mc_quote
mc_assert "enforce on a converge: report scope is refused, exit 2 — _scope.yaml is the ceiling" \
  mc_exit 2 mcc plan --decl "$RO" --mode enforce
mc_note "the default --max-changes is 10. A broken file cannot mass-revert a goatnet in one pass."

echo
mc_say "Next: bash scenarios/02-what-ci-refuses/run.sh"
mc_summary

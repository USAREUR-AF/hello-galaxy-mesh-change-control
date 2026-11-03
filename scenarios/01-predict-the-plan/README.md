# 01 — Predict the plan

A membership declaration lists only the exceptions. Everything else a peer holds comes
from its **baseline**: for a person's device, the groups their operator manifest
declares; otherwise, the setup key that enrolled it. This scenario computes, for ten
made-up peers, what the converger will add and remove — and which peers it will not
touch at all.

```bash
bash scenarios/01-predict-the-plan/run.sh
```

## The rule

For each peer, only **managed** groups are planned: names that start with the scope's
prefix and a dash (`ZAGROS-DEV-…` on zagros-dev). `All`, `mesh-dns` and groups of any other
prefix are never touched.

| The peer's entry | Desired managed groups |
|---|---|
| `hold: quarantine` | `{ZAGROS-DEV-QUARANTINED}` |
| `exact: [...]` | exactly that list |
| `grant` / `absent`, or no entry | baseline ∪ `grant` − `absent` |

**Baseline**, in this order (`bin/mcc plan --all` prints which one each peer used):

1. **Declared.** The peer's name is `peer-<handle>[-<org>]-<scope>-<date>…` and the
   handle is in the scope's `_baseline.generated.yaml`. A phone or tablet (enrolled on
   the person's key for phones and tablets, whose name ends `-handset`) starts from the
   person's `handset` set; anything else from their `device` set. The file is generated from the operator
   manifests (`bin/mcc baseline` here; `membership.py --generate-baseline` in goat), so
   it survives the setup key being deleted or edited.
2. **Key.** The auto-groups of the setup key that minted the peer, found through the
   peer's `Peer added` event. Machines — hosts, services — use this.
3. **None.** No declared baseline, no key (deleted, or an interactive login), and no
   `exact` or `hold` entry: the peer is **unknown**, reported and never changed.

## What it does

1. Prints the fixture: each peer, its key baseline, and what it holds now.
2. Generates the declared baseline from `fixtures/manifests/zagros-dev/*.yml` and checks
   the committed `_baseline.generated.yaml` matches it.
3. Prints the declaration, the directory `fixtures/declarations/ordinary/zagros-dev/`:
   `_scope.yaml` (the switch), `substrate.yaml`, `services.yaml`, `people.yaml`.
4. Runs `bin/mcc plan` and explains each row: a grant/absent (alice), a dashboard edit
   put back (bob), an `exact` replacing the key (the service host), an unknown (dave),
   a person whose key was deleted planned from her manifest (erin), a phone on the
   phones-and-tablets set (hana), a coverage-gate block (sensor), a missing peer (frank), and
   groups of other prefixes left alone.
5. Adds `hold: quarantine` for carol and alice (in `holds.yaml`).
6. Releases both holds and compares the result with before the hold.
7. Runs the two gates in front of enforce: `--max-changes` and the `converge:` ceiling.

## What it proves

- Deleting a hold returns a peer that had **no other entry** to exactly its prior groups.
- A hold **replaces** a peer's existing entry, because a scope holds one entry per peer
  across all its fragments. Deleting that hold returns the peer to its baseline, not to
  its old entry.
- A person whose setup key was deleted is still planned, from their manifest. Without
  the declared baseline erin would be unknown (`tests/test_model.py` shows both).
  Release a hold by reverting the pull request that added it: the old entry comes back,
  and with it exactly the old groups. Nothing else records prior groups.
- An unknown peer is left alone even when it holds `PLATFORM-ADMIN`. The fix is an
  `exact` entry for it, which is a reviewed change.
- The converger refuses a whole run that would make more than `--max-changes` (10)
  peer-group changes. It refuses `--mode enforce` on a scope whose `_scope.yaml` says
  `converge: report`.

## What it does not do

It reads a fixture, not a goatnet. `lib/mcc/model.py` was written from goat's Rust
planner (`crates/goat-cli/src/cmd/warrant_membership.rs`, `plan_membership`) and is
there to be read; the converger on the management host is the real one. Scenario 04
runs that one, read-only.

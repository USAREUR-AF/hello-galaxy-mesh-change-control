# hello-galaxy-mesh-change-control

**How network access changes on a governed goatnet. The NetBird dashboard is for looking.
Which peer holds which group, and which groups may reach which, change through
warrant: a reviewed diff in git, applied by a machine account. This repo lets you
predict what that machine will do, see what CI refuses and why, and rehearse the pull
request, mostly on a laptop and once, read-only, against a live goatnet.**

The decision is goat [ADR 1189](https://github.com/usareur-af/goatcore/blob/main/docs/adr/1189-netbird-read-only-dashboard-and-warrant-owned-membership.md)
("The NetBird dashboard is read-only by default, and warrant owns peer membership"). The
design is [`docs/design/mesh-change-control.md`](https://github.com/usareur-af/goatcore/blob/main/docs/design/mesh-change-control.md),
and the runbook is [`docs/operations/warrant-runbook.md`](https://github.com/usareur-af/goatcore/blob/main/docs/operations/warrant-runbook.md)
§4A, all in [goatcore](https://github.com/usareur-af/goatcore). Nothing here replaces them.

The examples use a made-up goatnet whose scope is `zagros-dev` (group prefix
`ZAGROS-DEV-`) and made-up people (alice, bob, carol, …).

## When you have finished you will be able to

- read a goatnet's membership file and say, for any peer, which groups the converger
  will add and remove, and which peers it will leave alone;
- write a grant, a hold and a release that pass CI first time, and know why each
  refused entry is refused;
- tell from a diff whether it only takes access away (it merges on one owner's click)
  or gives something back (it waits for review);
- prove on a live goatnet that the everyday dashboard's API door answers reads and
  refuses writes, and run the converger's report yourself;
- answer "why can't A reach B?" by checking the declared ACL before writing a rule.

## The three rules

1. **The dashboard is for looking.** Everyone the dashboard admits has NetBird's
   `auditor` role on a governed goatnet: they read everything and change nothing. The
   everyday dashboard talks to a door (`mgmt-read.<site>`) that forwards only GET, HEAD
   and OPTIONS. A few named platform admins hold `NETBIRD-ADMIN` and have a second
   address for break-glass repairs.
2. **Warrant is how the network changes.** Access rules were already warrant's
   ([ADR 1129](https://github.com/usareur-af/goatcore/blob/main/docs/adr/1129-warrant-scoped-expiring-network-authorizations.md)). Peer membership now is too: the directory `ops/warrant/membership/<scope>/`
   in goat lists the exceptions to each peer's baseline — for a person's device, the
   groups their operator manifest declares (`_baseline.generated.yaml`); otherwise, its
   enrollment key's groups — and a converger on the management host makes the goatnet
   match it every five minutes. A hand edit is put back on the next pass.
3. **Lifecycle actions keep their commands, and hand membership to warrant.** Minting
   an enrollment key, removing a device, granting a role are events, not standing state,
   so they keep their audited commands. Any of them that changes membership writes a
   warrant entry instead of touching the live account.

A goatnet is governed when its scope's `_scope.yaml` says `converge: enforce`; until
then the converger only reports.

## Quick start

Prerequisites: Python 3.9 or later with PyYAML, `git`, `bash`. Scenarios 01, 02, 03
and 05 need nothing else and are the default path. Scenario 04 also needs `curl`, a
governed goatnet you have access to with its mesh joined, your own NetBird token on it and
a current goat CLI; scenario 06 needs the goat CLI. Any appropriate goatnet works:
EFDI, the shared sandbox goatnet that partners are onboarded to (if you are onboarded to it); <!-- oss-allow: operator-approved public example goatnet -->
a goatlite you stand up yourself (goatcore's [goatlite quickstart](https://github.com/usareur-af/goatcore/blob/main/docs/tutorials/00-goatlite.md)
or the [hello-galaxy-goatenv](https://github.com/usareur-af/hello-galaxy-goatenv) walkthrough);
or another goatnet you have access to. The goat CLI is built from
[goatcore](https://github.com/usareur-af/goatcore) (`crates/goat-cli`).

```bash
pip install -r requirements.txt          # PyYAML, pytest

bash scenarios/01-predict-the-plan/run.sh        # offline
bash scenarios/02-what-ci-refuses/run.sh         # offline
bash scenarios/03-narrowing-vs-widening/run.sh   # offline
bash scenarios/04-live-read-only/run.sh          # a live goatnet, read-only
bash scenarios/05-the-pull-request/run.sh        # offline rehearsal; read its README for the real steps
bash scenarios/06-why-blocked/run.sh             # offline, needs goat

python3 -m pytest -q tests                        # the offline model's tests
```

Everything written at runtime goes under `.run/`, which git ignores. The scenarios pin
"today" to 2026-09-23 so the expiry dates in the fixtures do not rot; set `MCC_TODAY`
to change it.

## The scenarios

| Scenario | Needs | What it shows |
|---|---|---|
| [01-predict-the-plan](scenarios/01-predict-the-plan) | nothing | the desired-membership table on ten made-up peers: the declared baseline (from manifests) and the key baseline, grant/absent, exact, hold, unknown, a coverage-gate block, a missing peer, groups of other prefixes left alone; quarantine then release; the two gates in front of enforce |
| [02-what-ci-refuses](scenarios/02-what-ci-refuses) | nothing | sixteen declarations CI refuses, each with the reason the rule exists — `EXTERNAL-INFRA` beside a person role, `PLATFORM-ADMIN` on a machine, a hold with no expiry, `converge:` outside `_scope.yaml`, and twelve more |
| [03-narrowing-vs-widening](scenarios/03-narrowing-vs-widening) | nothing | twenty-two small diffs graded the way CI grades them: which merge on one owner's click, which wait for review, why a release is a widening, why moving an entry between fragments is no change, and how a manifest change to the baseline grades |
| [04-live-read-only](scenarios/04-live-read-only) | the goatnet's mesh, your token, goat CLI | GET on `mgmt-read.<site>/api/groups` → 200, POST → 403; `goat warrant apply --membership --mode report` against your declaration and against a what-if copy |
| [05-the-pull-request](scenarios/05-the-pull-request) | nothing (the README is the procedure) | exactly how to add a grant, a hold and a release to `ops/warrant/membership/<scope>/` in the goatnet's configuration repository, what CI checks, and what happens after merge; the script rehearses all three in a scratch repository |
| [06-why-blocked](scenarios/06-why-blocked) | goat | `goat warrant why-blocked`: PERMITTED, BLOCKED with the smallest fix, a refused question, a one-way path that is correct — and when the answer is membership, not a rule |

## What needs a goatnet token, and what does not

| | Token | Mesh | goat CLI |
|---|---|---|---|
| Scenarios 01, 02, 03, 05 and the tests | no | no | no |
| Scenario 06 | no | no | yes (it reads the ACL compiled into goat) |
| Scenario 04 | **your own** NetBird personal access token, in `GOAT_NB_API_TOKEN` | **the goatnet's** — the `mgmt-read` name is mesh-only | built from goatcore |

Use your own token, never a service identity's. On a governed goatnet a platform or
identity admin's token carries the `auditor` role: it can read every peer and group and
can change nothing. Scenario 04 makes only reads, plus one write the door refuses, sent
with an invalid body so that it could create nothing even if it got through.

## Repo layout

```
lib/mcc/model.py         the desired-membership table (§4.2), declared and key baselines, the two enforce gates
lib/mcc/layout.py        a scope as a directory: _scope.yaml, fragments, the generated baseline (§4.1)
lib/mcc/baseline.py      the declared baseline, generated from operator manifests
lib/mcc/rules.py         the CI schema and tier rules (§4.3)
lib/mcc/narrowing.py     the narrowing prover (§4.3 "Narrowing")
lib/hello-mcc.sh         shared scenario library (narration, assertions)
bin/mcc                  plan / check / diff / baseline over the fixtures
fixtures/mgmt-state/     a made-up management-server state for scope zagros-dev
fixtures/manifests/      made-up operator manifests the baseline is generated from
fixtures/declarations/   scenario 01's scope directories (ordinary day, holds, release), each <case>/zagros-dev/
fixtures/refused/        scenario 02's refused declarations, one per rule
fixtures/diffs/          scenario 03's base directory and twenty-one changes to it (the twenty-second deletes it)
fixtures/taxonomy.yaml   the zagros-dev and zagros group suffixes, from goatcore's taxonomy
scenarios/               01 … 06, each a run.sh and a README
tests/                   pytest for the offline model
```

## What runs here, and what runs on the goatnet

| Here | On the goatnet | Where in goat |
|---|---|---|
| `lib/mcc/model.py` (a re-implementation) | the converger: `goat warrant apply --membership`, every 5 minutes on the management host as `svc-<site>-warrant` | `crates/goat-cli/src/cmd/warrant_membership.rs` |
| `lib/mcc/rules.py`, `lib/mcc/layout.py` (re-implementations) | `ops/warrant/membership.py --check`, in the `warrant-registry` workflow on every PR | `ops/warrant/membership.py` |
| `lib/mcc/baseline.py` (a re-implementation) | `ops/warrant/membership.py --generate-baseline`, run by whoever changes a manifest; `--check` fails a stale file where the manifests are present | `ops/warrant/membership/<scope>/_baseline.generated.yaml` |
| `lib/mcc/narrowing.py` (a re-implementation) | `ops/ci/check-warrant-narrowing.py --membership`, same workflow; posts the verdict as a PR comment | same |
| `fixtures/mgmt-state/zagros-dev.json` (made up) | the peers, groups, setup keys and event log of the management server | NetBird management API |
| scenario 04 | the real thing, read-only | the goatnet you are using |
| scenario 06 | the real thing; it needs no goatnet | goat CLI |

`rules.py` and `narrowing.py` were checked to give the same verdicts and messages as
goat's own Python on every fixture in this repo. `model.py` was written from the Rust
planner (`plan_membership`, `key_baselines`) line by line and has not been run against
it on these fixtures. They exist so you can read each rule in a page of Python. Where
they and goat differ, goat is right and this repo has a bug.

Part of the hello-galaxy family of runnable goat demos.

## Licence

Apache License 2.0 ([LICENSE](LICENSE)). See also [NOTICE](NOTICE),
[CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

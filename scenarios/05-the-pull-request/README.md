# 05 — The pull request

This is the procedure for changing who holds which group on a governed goatnet: a
grant, a hold (quarantine) and a release, each as a pull request in the repository that
holds your goatnet's declarations (`ops/warrant/membership/<scope>/`, beside goatcore's
`ops/warrant/membership.py`). The examples use scope `zagros-dev`; substitute your own.
The script beside this file only rehearses it in a scratch repository under `.run/`,
with this repo's copies of CI's two checks; it touches no other repository.

```bash
bash scenarios/05-the-pull-request/run.sh     # the rehearsal
```

## What you need

- Write access to your goatnet's repository (to push a branch and open a pull request).
- Python 3 with PyYAML, to run the two checks locally.
- Nothing on the goatnet. You never touch the NetBird dashboard for this.

The declaration is the directory `ops/warrant/membership/zagros-dev/`. Its `_scope.yaml`
saying `converge: enforce` is what makes zagros-dev governed; the converger on zagros-dev's
management host makes the goatnet match the whole directory. Entries live in fragments
filed by purpose:

| Fragment | Holds |
|---|---|
| `people.yaml` | person devices that differ from their declared baseline |
| `holds.yaml` | quarantine holds and dormancy (probation) lanes |
| `services.yaml` | external-service hosts, `exact: [ZAGROS-DEV-EXTERNAL-INFRA]` |
| `substrate.yaml` | management and other substrate hosts, kept by hand |
| `orgs/<org>.yaml` | an org's own entries, once that org takes ownership of them |

`_baseline.generated.yaml` is generated from the operator manifests; never edit it.

## Before you write anything: is it membership?

`goat warrant why-blocked --scope zagros-dev --from <group> --to <group> --port <n>`
(scenario 06). If it says PERMITTED, the access rule is fine and the peer probably
does not hold the group: that is this procedure. If it says BLOCKED, you need an
access-rule change instead ([`warrant-runbook.md`](https://github.com/usareur-af/goatcore/blob/main/docs/operations/warrant-runbook.md) §2), which is a different file.

Find the peer's exact NetBird name (the dashboard shows it; you can look, you just
cannot edit) and the groups it holds now.

## 1. Branch

```bash
git fetch origin
git switch -c membership/zagros-dev-<what> origin/main
```

## 2. Write the entry

Add one entry under `entries:` in the fragment for its purpose. One entry per peer
across the whole directory: if the peer already has one, in any fragment, edit that
entry where it is instead of adding a second (`grep -rn '<peer name>'
ops/warrant/membership/zagros-dev/`).

Before writing a grant, check the person's baseline in `_baseline.generated.yaml`: if
the group belongs to their tier, the fix is their operator manifest, not an entry.

**A grant** — add a group to the peer's baseline (in `people.yaml`):

```yaml
  - peer: peer-<handle>-zagros-dev-<date>-laptop     # exact NetBird peer name
    grant: [ZAGROS-DEV-P2P]
    owner: <your handle>
    reason: <one sentence a reviewer can check — why this peer, why this group>
    expires: 2026-12-01                            # required for P2P, BREAKGLASS, PLATFORM-ADMIN, EXTERNAL-INFRA
```

Use `absent: [...]` to take a group the baseline gives away and keep it away, and
`exact: [...]` only when the peer must hold exactly that list whatever its baseline
says (an external-service host, in `services.yaml`: `exact: [ZAGROS-DEV-EXTERNAL-INFRA]`,
alone).

**A hold** — quarantine a peer (in `holds.yaml`):

```yaml
  - peer: <exact peer name>
    hold: quarantine                               # its managed groups become ZAGROS-DEV-QUARANTINED alone
    owner: <your handle>
    reason: <what happened; link the issue that tracks it>
    expires: 2026-09-30                            # required: the review date
```

If the peer already has an entry, **replace** it with the hold where it is and say so
in the pull request. Keep the pull request to that one change, so it can be reverted cleanly.

**A release** — revert the pull request that added the hold:

```bash
git revert <sha of the hold commit>
```

A revert puts back exactly the entry the peer had before the hold, so it gets back
exactly what it held. Deleting the hold by hand is the same only when the peer had no
entry before (scenario 01, step 5 shows the difference).

On a governed goatnet `goat admin members move ... --write-entry` writes the entry for
a move between groups for you, and `goat admin platform-admin grant|revoke` prints the
mesh entry to add. You still commit it and open the pull request.

## 3. Check it locally — the same two checks CI runs

```bash
python3 ops/warrant/membership.py --check
rm -rf /tmp/base && mkdir -p /tmp/base
git archive origin/main ops/warrant/membership | tar -x -C /tmp/base
python3 ops/ci/check-warrant-narrowing.py --membership \
  /tmp/base/ops/warrant/membership/zagros-dev ops/warrant/membership/zagros-dev
```

The first must exit 0 (scenario 02 lists what it refuses). The second tells you what CI
will say: exit 0 is a narrowing, exit 1 a widening (scenario 03).

| Change | Expect |
|---|---|
| grant | widening — waits for review |
| hold | narrowing — one owner's click |
| release (revert) | widening — waits for review |

## 4. Commit and open the pull request

```bash
git add ops/warrant/membership/zagros-dev/
git commit -s -m "feat(warrant): grant ZAGROS-DEV-P2P to <peer> on zagros-dev"
git push -u origin HEAD
gh pr create --fill
```

Commits in goat are signed off (`-s`) and use Conventional Commits. In the pull request
description say who asked, why, and for how long.

## 5. What CI does

The `warrant-registry` workflow runs on any change under `ops/warrant/membership/` or
`ops/operators/`:

| Step | What it checks |
|---|---|
| Membership declarations — schema, taxonomy, expiry, tier rules | `membership.py --check`; a failure here is red |
| Membership validator, network read-back, and the tools that write entries | the checker's own tests |
| Is this change a narrowing? | the prover, base against head |
| Label the verdict | posts `warrant: narrowing` or `warrant: widening` as a comment, with the lines |

A widening is not a failure. It waits for the `CODEOWNERS` owners of
`ops/warrant/membership/` (in goat, a platform team and the maintainers). A change to
any `_scope.yaml` (the switch) waits for the platform team alone. A narrowing still
needs one of them to click approve; the comment has already answered the question.

## 6. After merge

Merging changes nothing on the goatnet by itself. Until the declaration is delivered as
a signed intent (the next increment in [ADR 1189](https://github.com/usareur-af/goatcore/blob/main/docs/adr/1189-netbird-read-only-dashboard-and-warrant-owned-membership.md)), a platform admin deploys the file to
the management host with goatcore's `ops/ansible/warrant-membership.yml`:

```bash
cd ops/ansible
../scripts/ansible-preflight.sh -i inventory/mgmt-hosts.ini warrant-membership.yml -e target=zagros_dev_hosts
```

It needs `svc-zagros-dev-warrant`'s token in the shell as `ZAGROS_DEV_WARRANT_NB_API_TOKEN`,
so if you are not a platform admin, ask one and link the merged pull request. Use the
inventory that defines your goatnet's host group (`zagros_dev_hosts` here).

The directory lands at `/etc/goat/warrant/membership/zagros-dev/` on the management host
(mirrored: a fragment deleted in the repo is deleted there too).
The `warrant-membership.timer` runs the converger every five minutes with jitter, as
`svc-zagros-dev-warrant`, in enforce mode. It adds before it removes and re-reads after
each step. It refuses to add a peer to a group no enabled policy covers, and refuses the
whole run if it would make more than 10 changes.

## 7. Check it happened

- Run scenario 04, or directly:
  `goat warrant apply --membership --scope zagros-dev --file ops/warrant/membership/zagros-dev --mode report --mgmt-url https://mgmt-read.<site zone>`.
  Your peer should not appear (it matches) and `changes planned 0`.
- In the dashboard, the peer's groups now match. The NetBird event log names
  `svc-zagros-dev-warrant` as the initiator of the change.

## How long it takes

A pull request, a review for anything that widens, a deploy, and up to five minutes.
That is the cost ADR 1189 accepts for every standing network change having a reviewed
diff, an owner and a named author. When a device must be off the mesh this second,
`goat admin peer cut` is still the tool; write the hold entry after.

## Emergencies

`NETBIRD-ADMIN` holders can edit at the admin address (`admin-dashboard.<site>`),
but the converger puts a membership edit back within five minutes. For a membership
emergency either merge the entry (a hold is a narrowing: one click), or have a
platform admin stop the converger on the management host
(`sudo systemctl stop warrant-membership.timer`), make the edit, merge the entry, and
start the timer again.

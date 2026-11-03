# 02 — What CI refuses

Every pull request that touches a membership declaration (or an operator manifest)
runs goat's `ops/warrant/membership.py --check` in the `warrant-registry` workflow. It
checks the scope directory's shape, then every rule over the merged entries of all its
fragments. This scenario runs the same checks over sixteen bad declarations and gives
the reason each rule exists.

```bash
bash scenarios/02-what-ci-refuses/run.sh
```

## The rules, and why

| Refused | Why the rule exists |
|---|---|
| `EXTERNAL-INFRA` in a `grant` | the tier for a host running an external service (ADR 1178) is never stacked on a person's role: a person's device holding it would carry service-host reach |
| `EXTERNAL-INFRA` beside another group in `exact` | a service host holds it alone: `exact: [<P>-EXTERNAL-INFRA]` is the only shape |
| `PLATFORM-ADMIN` on a peer whose name does not start `peer-` | it is for a person's device, whose holder can be asked; never a machine |
| a `hold` with no `expires` | the expiry is the review date. A quarantine nobody reviews stays forever |
| `P2P`, `BREAKGLASS`, `PLATFORM-ADMIN` or `EXTERNAL-INFRA` granted with no `expires` | these widen reach enough that a grant of them must lapse |
| a past `expires` | CI goes red; a scheduled job opens the removal PR. To keep the entry, say in a PR why and who is asking |
| a group of another prefix | one file per goatnet; the converger only touches its own prefix |
| a group the taxonomy does not declare | a typo is refused, not created or silently ignored |
| two forms in one entry | an entry is exactly one of grant/absent, exact, hold |
| two entries for one peer, in any two fragments | one answer per peer; an org's fragment cannot quietly override `people.yaml`. This is also why a hold replaces a peer's entry |
| an unknown key (`grants:`) | ignored, it would silently mean "back to the baseline" |
| no `owner`, no `reason` | every entry names who to ask and why; the reason is what a reviewer approves on (200 characters at most) |
| the single file `zagros-dev.yaml` | retired: a scope is a directory, so an org can own `orgs/<org>.yaml` and people, services, substrate and holds are filed apart |
| `converge:` in a fragment | the switch lives in `_scope.yaml` alone, which only the platform owners in `CODEOWNERS` approve |
| another `_*.yaml` | `_` names are reserved for the switch and the generated baseline |
| no `_baseline.generated.yaml` | the baseline is every person-device's starting set; CI requires it, and where the manifests are present, that it is not stale |

## Run it on your change in the goatnet's configuration repository

```bash
python3 ops/warrant/membership.py --check
```

Exit 0 is what CI needs. Run it before you push. After changing an operator manifest,
regenerate the baseline and commit it:

```bash
python3 ops/warrant/membership.py --generate-baseline --scope <scope>
```

The manifests are gitignored (they carry identity material), so only a checkout that
has them — the operator's own clone — can regenerate the file or prove it fresh. CI
without them says the freshness is unverified rather than passing it.

## What it does not do

`lib/mcc/rules.py` re-implements goat's checker so you can read it in a page. It was
checked to give the same verdicts and messages as goat's checker on every file in
`fixtures/`. If the two disagree, goat's is right.

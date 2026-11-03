# 04 — Read-only, on a live goatnet

The one scenario that reaches a goatnet. It proves two things on a governed goatnet you have
access to, with your own credentials, and changes nothing:

1. the everyday dashboard's API door answers reads and refuses writes;
2. the converger's report, run by you, agrees with the declaration.

The other five scenarios run offline. The goatnet can be
EFDI, the shared sandbox goatnet that partners are onboarded to (if you are onboarded to it); <!-- oss-allow: operator-approved public example goatnet -->
a goatlite you stand up yourself (goatcore's
[goatlite quickstart](https://github.com/usareur-af/goatcore/blob/main/docs/tutorials/00-goatlite.md)
or the [hello-galaxy-goatenv](https://github.com/usareur-af/hello-galaxy-goatenv)
walkthrough); or another goatnet you have access to.

```bash
export MCC_SCOPE=<goatnet scope>              # the fixtures use zagros-dev; its groups are <SCOPE>-* upper-cased
export MCC_SITE_ZONE=<goatnet site zone>      # the read door is https://mgmt-read.<site zone>
export GOAT_NB_API_TOKEN=<your own NetBird personal access token>
export GOAT_REPO=~/src/<goatnet-config-repo>  # optional: the repository holding ops/warrant/membership/<scope>/
bash scenarios/04-live-read-only/run.sh
```

## Before you start

| Need | How |
|---|---|
| The goatnet's mesh | your NetBird client connected to that goatnet. The `mgmt-read.<site zone>` name resolves only there, and the first step says so if it does not |
| Your own token | in the goatnet's NetBird dashboard, your user → access tokens. On a governed goatnet a platform or identity admin has the `auditor` role, so the token reads everything and changes nothing. Never use a service identity's token |
| The goat CLI | built from [goatcore](https://github.com/usareur-af/goatcore) (`crates/goat-cli`), with `goat warrant apply --membership`. Steps 6 and 7 pass the scope DIRECTORY as `--file` |
| The real declaration (optional) | `GOAT_REPO` pointing at the goatnet's configuration repository, or `MCC_MEMBERSHIP_DIR` at the scope directory `ops/warrant/membership/<scope>/`. Without it, step 7 still runs a what-if |

## What it does

| Step | Request | Expected |
|---|---|---|
| 1 | resolve `mgmt-read.<site zone>` | resolves (you are on the mesh) |
| 2 | `GET /api/groups`, no token | `401` |
| 3 | `GET /api/groups` with your token | `200`, and the `<SCOPE>-*` groups warrant manages |
| 4 | `POST /api/groups` with your token and the body `{"name":""}` | `403` from the door. The body is invalid on purpose: even if it reached the management server it could create nothing |
| 5 | `goat --version`, and `goat warrant apply --help` lists `--membership` | the converger is in your goat |
| 6 | `goat warrant apply --membership --scope <scope> --file <real scope directory> --mode report --mgmt-url https://mgmt-read.<site zone>` | exit 0; normally "every peer holds what the declaration says" |
| 7 | the same against a copy of the directory whose `_scope.yaml` says `converge: report`, with a `whatif.yaml` fragment holding one entry for a peer that does not exist; then `--mode enforce` on that copy | the extra entry is reported `missing-peer`; enforce is refused with exit 2 before any connection is made |

## What each result means

- **401 then 200.** The door identifies you; reading is what your role allows.
- **403 on POST.** `mgmt-read.<site>` is a Traefik route that forwards only GET, HEAD
  and OPTIONS to the management server. The everyday dashboard uses it, so even the
  `NETBIRD-ADMIN` holders are read-only there. They write from
  `admin-dashboard.<site>`, and on a governed goatnet the converger puts a membership
  edit made there back on its next pass.
- **Report exit 0, no drift.** The timer on the management host runs the same
  computation every five minutes, in enforce mode, as `svc-<site>-warrant`. No drift
  means nobody has hand-edited membership since its last pass.
- **Enforce refused.** The file's `converge:` is the ceiling. The CLI can lower
  enforce to report, never raise it.

## If a step does not run

The script marks each step it could not run and exits 2 (`INCOMPLETE`) rather than
reporting success. Fix what is marked and run it again. If step 6 or 7 fails with a
permission error, your token's role cannot read one of the endpoints the report needs
(peers, groups, policies, setup keys, events); open an issue on this repository with
the role you used.

## What it does not do

It does not change anything, and it does not use the admin address.

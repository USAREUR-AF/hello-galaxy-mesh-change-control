# AGENTS.md

Instructions for AI coding agents, and a short version for anyone working here. [CONTRIBUTING.md](CONTRIBUTING.md) is the full process.

## What this repository is

hello-galaxy-mesh-change-control shows how network access changes on a goatnet: group membership and reachability change through a reviewed diff in git, applied by a machine account, and the NetBird dashboard is read-only. The scenarios predict what the apply will do, show what CI refuses, and rehearse the pull request. The examples use the made-up scope `zagros-dev` and made-up people.

It is one of the Hello Galaxy demonstrations: small, runnable examples, each showing one part of [goat](https://github.com/USAREUR-AF/goatcore). It holds no goat source code.

## Layout

| Path | What |
|---|---|
| `scenarios/` | one directory per scenario: `README.md` and `run.sh` |
| `bin/mcc` | the offline model's command line |
| `lib/` | the offline model and shared shell functions |
| `fixtures/` | the declarations, manifests, diffs and management state the scenarios read |
| `tests/` | pytest tests of the offline model |

## Before you push

CI (`.github/workflows/ci.yml`) runs these; none needs a goatnet:

```bash
shellcheck -e SC1090,SC1091,SC2034 lib/hello-mcc.sh scenarios/*/run.sh
python3 -m pip install -r requirements.txt
python3 -m pytest -q tests
for s in 01-predict-the-plan 02-what-ci-refuses 03-narrowing-vs-widening 05-the-pull-request; do
  NO_COLOR=1 bash scenarios/$s/run.sh
done
```

Every directory under `scenarios/` holds a `README.md` and an executable `run.sh`; CI checks both. Scenario 04 reads a live goatnet, read-only, and CI does not run it.

## Rules

1. **Nothing from a real deployment.** No hostname, domain, address, key or person of a real goatnet goes into a file or a commit message. Use made-up names, documentation addresses (RFC 5737) and `example.org` mail.
2. **Commits.** Conventional Commits subject of 100 characters or fewer, with a scope (`fix(<component>): …`). Every commit is signed off (`git commit -s`, the DCO) and signed with a key GitHub verifies. The organization's required check `verified-commits` refuses a pull request that holds an unverified commit.
3. **One logical change per pull request.**
4. **Vulnerabilities** go through [SECURITY.md](SECURITY.md), never a public issue.

The contribution guide for goat as a whole is [goatcore CONTRIBUTING.md](https://github.com/USAREUR-AF/goatcore/blob/main/CONTRIBUTING.md).

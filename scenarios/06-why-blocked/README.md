# 06 — `goat warrant why-blocked`

"A can't reach B" is usually not the access rules. It is usually a membership the peer
does not hold, a service that is not listening, or DNS. `why-blocked` answers the
first question in a second, with no network, no token and no mesh: it reads the
declared ACL compiled into the goat binary.

```bash
bash scenarios/06-why-blocked/run.sh
```

Needs the goat CLI, built from [goatcore](https://github.com/usareur-af/goatcore)
(`crates/goat-cli`). It asks about scope `zagros-dev` by default; set `MCC_WHY_SCOPE` to
ask about a scope your goat knows. If goat does not know the scope, the script falls
back to `zagros` and says so.

## The four answers

| Ask | Answer | What to do next |
|---|---|---|
| `--from DEVELOPER --to INFRA --port 7447` | **PERMITTED**, naming the rule | not the ACL. Does the peer hold `ZAGROS-DEV-DEVELOPER`? If not, that is membership: scenario 05 |
| `--from OBSERVER --to INFRA --port 22` | **BLOCKED**, the smallest port set that would open it, and the rule diff to paste | decide whether the person needs the rule or a different group. A rule is a widening reviewed like any other |
| `--from DEVELOPERS --to INFRA --port 22` | **refused**, exit 1: not a group in this scope, with near matches | fix the question. A typo is never answered "blocked" |
| `--from INFRA --to P2P --port 22` | **BLOCKED**, no rule connects the pair at all | correct by design: `P2P` grants outbound reach and nothing inbound. The peer's role group is what makes it reachable. `infra → P2P` would open every P2P peer on the goatnet |

`--json` gives the same answer for scripts, including the list of what it did not
consult.

## Where membership comes in

`why-blocked` works on groups. Whether a particular peer holds a group is membership,
which is the directory `ops/warrant/membership/<scope>/` plus the peer's
baseline (the person's declared baseline, else its key). So the
usual path is:

1. `why-blocked` says PERMITTED;
2. the peer does not hold the source or destination group (dashboard, `goat who`, or
   scenario 04's report);
3. a `grant:` entry in a pull request (scenario 05) — not a new rule.

## What it does not do

It reads the declared plane: the YAML in git, as compiled into your goat. It does not
read live membership, what is listening, or DNS, and it says so on every run. It can
prove a path is not permitted; it cannot prove a permitted path works.

# 03 — Narrowing vs widening

CI compares the membership file at the base and head of a pull request and posts one
of two verdicts as a comment:

- **narrowing** — the change only takes access away. CI has answered the review
  question; one owner's approving click merges it. (The click stays a person's:
  GitHub will not let a workflow approve its own pull request.)
- **widening** — the change gives something back, or keeps it longer. It waits for a
  review by the `CODEOWNERS` owners of `ops/warrant/membership/` (in goat, a platform
  team and the maintainers).

A widening is not a CI failure.

```bash
bash scenarios/03-narrowing-vs-widening/run.sh
```

## The cases

| Change | Verdict |
|---|---|
| remove a `grant` group | narrowing |
| new entry with only `absent` | narrowing |
| add a `hold` (replacing the entry) | narrowing |
| shrink an `exact` | narrowing |
| delete an entry that only granted | narrowing |
| bring `expires` earlier | narrowing |
| edit only `owner` / `reason` | narrowing (no access change) |
| new `exact` holding only a probation or quarantine lane | narrowing |
| add a `grant` group | widening |
| delete a `hold` (release) | widening |
| replace a `hold` with the entry the peer had before (release by revert) | widening |
| move `expires` later | widening |
| remove `expires` | widening — and refused by scenario 02's rules for a `P2P` grant |
| stop keeping a group `absent` | widening |
| delete an entry that had `absent` or `exact` | widening — the peer returns to its baseline |
| change `converge:` in `_scope.yaml` | widening — never proven |
| delete the scope directory | widening — it ungoverns the scope |
| new entry that grants | widening |
| move an entry, unchanged, to another fragment | no change — the prover compares merged views |
| a person's baseline `device`/`handset` loses a group (manifest change) | narrowing |
| a person's baseline gains a group, a person added or removed | widening |

The shape to notice: **containment is fast, giving access back is reviewed.** A
quarantine merges on one click; its release waits for review.

## Predict the verdict on your change in your goatnet's repository

```bash
rm -rf /tmp/base && mkdir -p /tmp/base
git archive origin/main ops/warrant/membership | tar -x -C /tmp/base
python3 ops/ci/check-warrant-narrowing.py --membership \
  /tmp/base/ops/warrant/membership/<scope> ops/warrant/membership/<scope>
```

Exit 0 is a narrowing (or no change), exit 1 a widening.

## What it does not do

`lib/mcc/narrowing.py` re-implements goat's prover. It was checked to return the
same lines as goat's prover for every case here. If the two disagree, goat's is right.

"""The desired-membership model: what the converger will do to each peer.

A small pure-Python re-implementation of goat's membership planner
(`goat warrant apply --membership`, design mesh-change-control.md §4.2). It is
here so you can read the rule in forty lines and run it on a laptop. It is NOT
the thing that runs on a goatnet: that is the Rust converger in the goat CLI.
Where the two could differ, the Rust one is right and this one is a bug.

The rule, per peer:

    hold: quarantine        ->  {<P>-QUARANTINED}
    exact: [...]            ->  exactly that list
    grant/absent, or none   ->  baseline  ∪ grant  − absent

`<P>` is the scope's site prefix (ZAGROS-DEV for scope zagros-dev). Only MANAGED
groups are planned: names starting `<P>-`. `All`, `mesh-dns` and groups of any
other prefix are never touched.

The BASELINE is found in this order (`baseline_source` on each row says which):

  1. DECLARED — the peer's name follows the peer-name grammar
     (`peer-<handle>-…`) and that handle is in the scope's
     _baseline.generated.yaml: the person's `handset` set when the peer
     enrolled on their phone-and-tablet key (key name ends `-handset`, or the
     peer name carries `-handset-`), else their `device` set. The name must be
     `peer-<handle>[-<org>]-<scope>-<date>…`; a handle alone is not enough. It comes from the operator
     manifest, so it survives the setup key being deleted or edited.
  2. KEY — the auto-groups of the setup key that minted the peer.
  3. none — the peer is UNKNOWN (unless an exact/hold entry names it) and is
     never changed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Statuses, spelled as the goat CLI prints them.
MATCH = "match"
DRIFT = "drift"
BLOCKED = "blocked"
UNKNOWN = "unknown"
MISSING_PEER = "missing-peer"

DEFAULT_MAX_CHANGES = 10


class Refused(Exception):
    """A refusal by design, with the exit code the goat CLI uses for it."""

    def __init__(self, code: int, msg: str):
        super().__init__(msg)
        self.code = code


# ---- entries -----------------------------------------------------------------


def entry_form(entry: dict) -> str:
    """'hold', 'exact' or 'delta' (grant/absent). Anything else is refused."""
    has_hold = "hold" in entry
    has_exact = "exact" in entry
    has_delta = "grant" in entry or "absent" in entry
    if [has_hold, has_exact, has_delta].count(True) != 1:
        raise ValueError(
            f"entry `{entry.get('peer')}` must carry exactly one of: grant/absent, exact, hold"
        )
    if has_hold:
        if entry["hold"] != "quarantine":
            raise ValueError(f"entry `{entry.get('peer')}`: hold `{entry['hold']}` is not a known hold")
        return "hold"
    return "exact" if has_exact else "delta"


def scope_prefix(scope: str) -> str:
    """zagros-dev -> ZAGROS-DEV. The goat converger derives it the same way, and
    refuses to run where the taxonomy's site_prefix disagrees."""
    return scope.strip().upper()


def is_managed(group: str, prefix: str, excluded_prefixes: tuple[str, ...] = ()) -> bool:
    """A group this scope manages: `<prefix>-…`, but not a LONGER prefix that
    starts with ours (scope `zagros` must not manage `ZAGROS-DEV-OBSERVER`)."""
    return group.startswith(prefix + "-") and not any(
        group.startswith(x + "-") for x in excluded_prefixes
    )


def desired_set(entry: dict | None, baseline: set[str] | None, prefix: str) -> set[str] | None:
    """The §4.2 table. None means UNKNOWN: never changed."""
    form = entry_form(entry) if entry else None
    if form == "hold":
        return {f"{prefix}-QUARANTINED"}
    if form == "exact":
        return set(entry["exact"])
    if baseline is None:
        return None
    if form == "delta":
        return (baseline | set(entry.get("grant") or [])) - set(entry.get("absent") or [])
    return set(baseline)


# ---- key baselines -----------------------------------------------------------


def key_baselines(events: list[dict], keys: list[dict], groups: list[dict]) -> dict[str, set[str]]:
    """peer id -> group names its minting setup key granted.

    The join is the peer's `Peer added` event: its initiator is the setup key
    id; when that id no longer resolves, `meta.setup_key_name` is used if the
    name is unambiguous. The event feed is newest first and the OLDEST event
    for a peer wins (it is iterated in order and overwritten).
    """
    gname = {g["id"]: g["name"] for g in groups}
    by_id = {k["id"]: k for k in keys}
    name_count: dict[str, int] = {}
    for k in keys:
        name_count[k["name"]] = name_count.get(k["name"], 0) + 1
    out: dict[str, set[str]] = {}
    for e in events:
        if e.get("activity") != "Peer added" and e.get("activity_code") != "peer.setupkey.add":
            continue
        if not e.get("target_id"):
            continue
        key = by_id.get(e.get("initiator_id", ""))
        if key is None:
            n = (e.get("meta") or {}).get("setup_key_name")
            if n and name_count.get(n) == 1:
                key = next(k for k in keys if k["name"] == n)
        if key is not None:
            out[e["target_id"]] = {gname.get(gid, gid) for gid in key.get("auto_groups", [])}
    return out


def minting_keys(events: list[dict], keys: list[dict]) -> dict[str, str]:
    """peer id -> name of the setup key that minted it (same join as above)."""
    by_id = {k["id"]: k for k in keys}
    out: dict[str, str] = {}
    for e in events:
        if e.get("activity") != "Peer added" and e.get("activity_code") != "peer.setupkey.add":
            continue
        if not e.get("target_id"):
            continue
        key = by_id.get(e.get("initiator_id", ""))
        name = key["name"] if key else (e.get("meta") or {}).get("setup_key_name")
        if name:
            out[e["target_id"]] = name
    return out


# ---- the declared baseline ------------------------------------------------------


PEER_PREFIX = "peer-"


def match_handle(peer_name: str, handles, scope: str = "zagros-dev") -> str | None:
    """The declared handle a peer name belongs to, or None.

    `peer-<H>` belongs to H only when the rest of the name is
    `(-<org>)?-<scope>-<YYYY-MM-DD>(-...)?` — the goatnet and the enrolment
    date anchor it, so a peer of another goatnet is never claimed. Of the
    handles that fit, the longest wins, so `ann` never claims
    `peer-ann-smith-zagros-dev-…` when `ann-smith` is a handle too."""
    if not peer_name.startswith(PEER_PREFIX):
        return None
    tail = re.compile(r"^(-[A-Za-z0-9._-]+?)?-" + re.escape(scope) + r"-\d{4}-\d{2}-\d{2}(-.*)?$")
    best = None
    for h in handles:
        lead = PEER_PREFIX + h
        if h and peer_name.startswith(lead + "-") and tail.match(peer_name[len(lead):]):
            if best is None or len(h) > len(best):
                best = h
    return best


def is_handset(peer_name: str, key_name: str | None) -> bool:
    return bool(key_name and key_name.endswith("-handset")) or "-handset-" in peer_name


def baseline_for(peer_name: str, peer_id: str, people: dict | None,
                 key_sets: dict[str, set[str]], key_names: dict[str, str],
                 scope: str = "zagros-dev"):
    """(baseline set or None, source) — declared first, then the key."""
    handle = match_handle(peer_name, (people or {}).keys(), scope)
    kind = "handset" if is_handset(peer_name, key_names.get(peer_id)) else "device"
    if handle is not None and kind in people[handle]:
        return set(people[handle][kind]), f"declared {handle} {kind}"
    if peer_id in key_sets:
        return set(key_sets[peer_id]), f"key {key_names.get(peer_id, '?')}"
    return None, ""


# ---- the plan ----------------------------------------------------------------


@dataclass
class Row:
    peer: str
    id: str
    current: list[str]
    desired: list[str] | None
    add: list[str]
    remove: list[str]
    status: str
    unmanaged: list[str] = field(default_factory=list)
    note: str = ""
    baseline_source: str = ""


@dataclass
class Plan:
    scope: str
    prefix: str
    rows: list[Row]

    def count(self, status: str) -> int:
        return sum(1 for r in self.rows if r.status == status)

    @property
    def changes_planned(self) -> int:
        """Peer-group add + remove operations. Blocked rows are not counted:
        the converger will not make them."""
        return sum(len(r.add) + len(r.remove) for r in self.rows if r.status == DRIFT)

    def row(self, peer: str) -> Row:
        return next(r for r in self.rows if r.peer == peer)


def plan_membership(
    decl: dict,
    peers: list[dict],
    baselines: dict[str, set[str]],
    covered_groups: set[str],
    existing_groups: set[str],
    excluded_prefixes: tuple[str, ...] = (),
    key_names: dict[str, str] | None = None,
) -> Plan:
    """Compute what the converger would do. Pure: reads nothing, writes nothing.

    decl:             the merged view (layout.load_decl); its `baseline` is the
                      declared people mapping, or None
    peers:            [{id, name, groups: [names]}]
    baselines:        peer id -> group names (key_baselines())
    covered_groups:   group names at least one enabled policy references
    existing_groups:  every group name that exists on the management server
    key_names:        peer id -> minting key name (minting_keys()), for the
                      handset test
    """
    scope = decl["scope"]
    prefix = scope_prefix(scope)
    managed = lambda g: is_managed(g, prefix, excluded_prefixes)  # noqa: E731
    by_peer = {e["peer"]: e for e in decl.get("entries") or []}
    rows: list[Row] = []

    for p in peers:
        current = {g for g in p["groups"] if managed(g)}
        unmanaged = [g for g in p["groups"] if not managed(g)]
        entry = by_peer.get(p["name"])
        base, source = baseline_for(p["name"], p["id"], decl.get("baseline"), baselines, key_names or {}, scope)
        if base is not None:
            base = {g for g in base if managed(g)}
        desired = desired_set(entry, base, prefix)
        row = Row(p["name"], p["id"], sorted(current), None, [], [], UNKNOWN, unmanaged,
                  baseline_source=source)
        if desired is None:
            row.note = (
                "grant/absent needs a baseline; none found — use exact or hold"
                if entry
                else "no baseline: not in the declared baseline, and no key (deleted, or interactive login)"
            )
            rows.append(row)
            continue
        row.desired = sorted(desired)
        row.add = sorted(desired - current)
        row.remove = sorted(current - desired)
        row.status = MATCH if not row.add and not row.remove else DRIFT
        if row.status == DRIFT:
            bad = []
            for g in row.add:
                if g not in existing_groups:
                    bad.append(f"{g} does not exist")
                elif g not in covered_groups:
                    bad.append(f"{g} is covered by no enabled policy")
            if bad:
                row.status = BLOCKED
                row.note = "refused (coverage gate): " + "; ".join(bad)
        rows.append(row)

    names = {p["name"] for p in peers}
    for e in decl.get("entries") or []:
        if e["peer"] not in names:
            rows.append(Row(e["peer"], "", [], None, [], [], MISSING_PEER,
                            note="entry names a peer that does not exist"))
    return Plan(scope, prefix, rows)


# ---- the two gates in front of enforce ---------------------------------------


def effective_mode(requested: str, converge: str) -> str:
    """The file's `converge:` is the ceiling. The CLI can lower enforce to
    report, never raise it (goat exits 2)."""
    if requested == "enforce" and converge == "report":
        raise Refused(2, "refused: --mode enforce on a declaration that says `converge: report`. "
                         "The file is the ceiling — change `converge:` in a reviewed PR first.")
    return requested


def check_max_changes(planned: int, max_changes: int = DEFAULT_MAX_CHANGES) -> None:
    """More than --max-changes operations: the whole run is refused and NOTHING
    is changed (goat exits 3). Enforce mode only."""
    if planned > max_changes:
        raise Refused(3, f"refused: this run would make {planned} peer-group changes, over "
                         f"--max-changes {max_changes}. Nothing was changed.")

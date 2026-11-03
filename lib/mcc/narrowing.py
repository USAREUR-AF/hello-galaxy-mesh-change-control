"""Is a membership diff a narrowing?

A re-implementation of goat's `ops/ci/check-warrant-narrowing.py --membership`
(design mesh-change-control.md §4.3 "Narrowing"). CI runs it on the base and
head versions of each scope directory and posts the verdict on the pull
request. It compares MERGED views, so an entry moved between fragments
unchanged is no change at all.

A NARROWING only takes access away. CI proves it and labels it; one owner's
approving click is still a person's, because GitHub will not let a workflow
approve its own pull request. Anything else is a WIDENING and waits for a real
review by the CODEOWNERS owners of the path. A widening is not a CI failure.

A diff is a narrowing when every changed entry only:
  - removes `grant` groups, or adds `absent` groups;
  - adds a `hold` (or replaces an entry with one);
  - shrinks an `exact`;
  - is a NEW `exact` naming only hold lanes (<P>-PROBATION-*, <P>-QUARANTINED);
  - is deleted, when it only granted.
Editing `owner` or `reason` changes no access. An earlier or added `expires`
narrows; a later or removed one extends a grant. Changing `scope` or `converge`
is never proven.

The declared baseline is graded too, because it is every person-device's
starting set: a person's `device`/`handset` list losing groups narrows; gaining
one, a person added or removed (their peers fall back to the key), or the
baseline appearing for the first time is never proven.
"""

from __future__ import annotations

from .model import entry_form
from .rules import _date


def _is_hold_lane(group: str) -> bool:
    return "-PROBATION-" in group or group.endswith("-QUARANTINED")


def _grant_only(e: dict) -> bool:
    return "grant" in e and not any(k in e for k in ("absent", "exact", "hold"))


def _form(e: dict) -> str | None:
    try:
        return entry_form(e)
    except ValueError:
        return None


def baseline_changes(base: dict | None, head: dict) -> tuple[list[str], list[str]]:
    wide: list[str] = []
    narrow: list[str] = []
    bb = (base or {}).get("baseline")
    hb = head.get("baseline")
    if bb is None and hb:
        return [f"+ declared baseline introduced for {len(hb)} people — never proven"], []
    if bb is not None and hb is None:
        return ["+ declared baseline removed — every person-device falls back to its key"], []
    bb, hb = bb or {}, hb or {}
    for handle in sorted(set(bb) | set(hb)):
        b, h = bb.get(handle), hb.get(handle)
        if b == h:
            continue
        if b is None:
            wide.append(f"+ baseline {handle}: person added ({', '.join(h.get('device') or [])})")
            continue
        if h is None:
            wide.append(f"+ baseline {handle}: person removed — their peers fall back to the key baseline")
            continue
        gains, losses = [], []
        for kind in ("device", "handset"):
            add = set(h.get(kind) or []) - set(b.get(kind) or [])
            drop = set(b.get(kind) or []) - set(h.get(kind) or [])
            if add:
                gains.append(f"{kind} gains {', '.join(sorted(add))}")
            if drop:
                losses.append(f"{kind} loses {', '.join(sorted(drop))}")
        if gains:
            wide.append(f"+ baseline {handle}: {'; '.join(gains)}")
        elif losses:
            narrow.append(f"- baseline {handle}: {'; '.join(losses)}")
    return wide, narrow


def membership_changes(base: dict | None, head: dict | None) -> tuple[list[str], list[str]]:
    """(widenings, narrowings) between two merged views (layout.load_decl).
    None = the scope directory is absent on that side."""
    wide: list[str] = []
    narrow: list[str] = []
    if head is None:
        if base is not None:
            wide.append("the scope's declaration is deleted — that ungoverns the scope")
        return wide, narrow
    base = base or {}
    bw, bn = baseline_changes(base or None, head)
    wide.extend(bw)
    narrow.extend(bn)
    for key in ("scope", "converge"):
        if base and base.get(key) != head.get(key):
            wide.append(f"{key}: {base.get(key)!r} -> {head.get(key)!r} is never proven a narrowing")

    def by_peer(doc):
        return {str(e.get("peer")): e for e in (doc.get("entries") or []) if isinstance(e, dict)}

    b, h = by_peer(base), by_peer(head)
    for peer in sorted(set(b) | set(h)):
        be, he = b.get(peer), h.get(peer)
        if be == he:
            continue
        if he is None:
            if _grant_only(be):
                narrow.append(f"- {peer}: grant-only entry deleted")
            else:
                what = "hold released" if "hold" in be else "entry deleted (the peer returns to its baseline)"
                wide.append(f"+ {peer}: {what}")
            continue
        hm = _form(he)
        if hm == "hold" and (be is None or "hold" not in be):
            narrow.append(f"- {peer}: hold added")
            continue
        if be is None:
            if hm == "delta" and not he.get("grant"):
                narrow.append(f"- {peer}: new entry only removes {', '.join(he.get('absent') or [])}")
            elif hm == "exact" and he.get("exact") and all(_is_hold_lane(str(g)) for g in he["exact"]):
                narrow.append(f"- {peer}: new entry holds only {', '.join(he['exact'])}")
            else:
                wide.append(f"+ {peer}: new entry ({hm or 'malformed'})")
            continue
        bm = _form(be)
        reasons: list[str] = []
        hold_lanes_only = hm == "exact" and bool(he.get("exact")) and all(
            _is_hold_lane(str(g)) for g in he["exact"])
        if bm != hm:
            if not (hold_lanes_only and bm != "hold"):
                reasons.append(f"mode {bm} -> {hm}")
        elif hm == "delta":
            added = set(he.get("grant") or []) - set(be.get("grant") or [])
            dropped_absent = set(be.get("absent") or []) - set(he.get("absent") or [])
            if added:
                reasons.append(f"grants {', '.join(sorted(added))}")
            if dropped_absent:
                reasons.append(f"no longer keeps {', '.join(sorted(dropped_absent))} absent")
        elif hm == "exact":
            added = set(he.get("exact") or []) - set(be.get("exact") or [])
            if added:
                reasons.append(f"exact gains {', '.join(sorted(added))}")
        if hm != "hold" and not hold_lanes_only:
            bx = _date(be.get("expires")) if be.get("expires") else None
            hx = _date(he.get("expires")) if he.get("expires") else None
            if bx and not hx:
                reasons.append("expires removed")
            elif bx and hx and hx > bx:
                reasons.append(f"expires extended {bx} -> {hx}")
        if reasons:
            wide.append(f"+ {peer}: {'; '.join(reasons)}")
        else:
            narrow.append(f"- {peer}: changed, grants nothing new")
    return wide, narrow


def verdict(base: dict | None, head: dict | None) -> str:
    wide, narrow = membership_changes(base, head)
    if wide:
        return "widening"
    return "narrowing" if narrow else "no-change"

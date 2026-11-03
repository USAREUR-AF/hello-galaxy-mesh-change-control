"""The CI rules for a membership declaration.

A re-implementation of goat's `ops/warrant/membership.py --check` (design
mesh-change-control.md §4.3), which the `warrant-registry` workflow runs on
every pull request that touches a membership scope directory. The rules below
run on the MERGED view (every fragment's entries together); the directory's
own shape is checked by layout.validate_layout. Each rule below carries the
reason it exists; the scenario 02 walkthrough shows each one refusing.

Where this and goat's checker could differ, goat's is right.
"""

from __future__ import annotations

import datetime as dt

TOP_KEYS = {"version", "scope", "converge", "entries"}
ENTRY_KEYS = {"peer", "owner", "reason", "expires", "grant", "absent", "exact", "hold"}
REASON_MAX = 200
# Granting any of these widens reach enough that the grant must lapse.
EXPIRY_REQUIRED_SUFFIXES = {"EXTERNAL-INFRA", "PLATFORM-ADMIN", "BREAKGLASS", "P2P"}
PERSON_PEER_PREFIX = "peer-"


def _date(raw) -> dt.date | None:
    if isinstance(raw, dt.datetime):
        return raw.date()
    if isinstance(raw, dt.date):
        return raw
    try:
        return dt.date.fromisoformat(str(raw).strip())
    except ValueError:
        return None


def _groups(entry: dict, *fields: str) -> list[str]:
    out: list[str] = []
    for f in fields:
        v = entry.get(f)
        if isinstance(v, list):
            out.extend(str(g) for g in v)
    return out


def validate(doc: dict, taxonomy: dict, today: dt.date, stem: str | None = None,
             labels: list[str] | None = None) -> list[str]:
    """Every violation in one declaration's MERGED view. Empty = CI would pass it.

    doc:      layout.load_decl() — version/scope/converge from _scope.yaml,
              entries from every fragment
    taxonomy: {scope: {"site_prefix": str, "suffixes": [str]}}
    stem:     the scope directory's name
    labels:   where each entry came from (`people.yaml entries[0]`)
    """
    errs: list[str] = []
    unknown = set(k for k in doc if not k.startswith("_")) - TOP_KEYS - {"labels", "baseline"}
    if unknown:
        errs.append(f"unknown top-level key(s): {', '.join(sorted(unknown))}")
    if doc.get("version") != 1:
        errs.append(f"version must be 1, got {doc.get('version')!r}")
    scope = doc.get("scope")
    if not isinstance(scope, str) or not scope:
        return errs + ["scope is required"]
    if stem is not None and scope != stem:
        errs.append(f"scope {scope!r} does not match the directory name {stem!r}")
    if scope not in taxonomy:
        return errs + [f"scope {scope!r} is not a taxonomy scope"]
    prefix = taxonomy[scope]["site_prefix"]
    suffixes = set(taxonomy[scope]["suffixes"])
    if doc.get("converge") not in ("report", "enforce"):
        errs.append(f"converge must be report|enforce, got {doc.get('converge')!r}")
    entries = doc.get("entries") or []
    if not isinstance(entries, list):
        return errs + ["entries must be a list"]

    seen: dict[str, str] = {}
    for i, e in enumerate(entries):
        where = labels[i] if labels and i < len(labels) else f"entries[{i}]"
        if not isinstance(e, dict):
            errs.append(f"{where}: must be a mapping")
            continue
        peer = e.get("peer")
        if not isinstance(peer, str) or not peer.strip():
            errs.append(f"{where}: peer is required (the exact NetBird peer name)")
            peer = None
        else:
            first = where
            where = f"{where} ({peer})"
            if peer in seen:
                errs.append(f"{where}: duplicate peer — already declared at {seen[peer]}; one entry per peer, "
                            "across every fragment")
            else:
                seen[peer] = first
        unknown = set(e) - ENTRY_KEYS
        if unknown:
            errs.append(f"{where}: unknown key(s): {', '.join(sorted(unknown))}")
        if not str(e.get("owner") or "").strip():
            errs.append(f"{where}: owner is required")
        reason = e.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errs.append(f"{where}: reason is required")
        elif len(reason) > REASON_MAX:
            errs.append(f"{where}: reason is {len(reason)} chars; the limit is {REASON_MAX}")

        forms = [f for f, present in (("hold", "hold" in e), ("exact", "exact" in e),
                                      ("delta", "grant" in e or "absent" in e)) if present]
        if len(forms) != 1:
            errs.append(f"{where}: exactly one of grant/absent, exact, hold: quarantine is required")
            continue
        form = forms[0]

        for fld in ("grant", "absent", "exact"):
            if fld not in e:
                continue
            v = e[fld]
            if not isinstance(v, list) or not v:
                errs.append(f"{where}: {fld} must be a non-empty list of group names")
                continue
            if len(set(map(str, v))) != len(v):
                errs.append(f"{where}: {fld} names a group twice")
            for g in map(str, v):
                if not g.startswith(prefix + "-"):
                    errs.append(f"{where}: {fld} group {g!r} does not carry the scope prefix {prefix}-")
                elif g[len(prefix) + 1:] not in suffixes:
                    errs.append(f"{where}: {fld} group {g!r} — suffix {g[len(prefix) + 1:]} is not in the {scope} taxonomy")
        if form == "delta":
            both = set(_groups(e, "grant")) & set(_groups(e, "absent"))
            if both:
                errs.append(f"{where}: {', '.join(sorted(both))} is both granted and absent")
        if form == "hold" and e.get("hold") != "quarantine":
            errs.append(f"{where}: hold must be quarantine, got {e.get('hold')!r}")

        # expires: required where the entry holds something that must lapse.
        held = _groups(e, "grant", "exact")
        held_sfx = {g[len(prefix) + 1:] for g in held if g.startswith(prefix + "-")}
        must_lapse = held_sfx & EXPIRY_REQUIRED_SUFFIXES
        if e.get("expires") is not None:
            when = _date(e["expires"])
            if when is None:
                errs.append(f"{where}: expires {e['expires']!r} is not a YYYY-MM-DD date")
            elif when < today:
                errs.append(f"{where}: expired {when.isoformat()} — past due; the expiry job opens the removal PR")
        elif form == "hold" or must_lapse:
            why = "a hold" if form == "hold" else "it grants " + ", ".join(sorted(must_lapse))
            errs.append(f"{where}: expires is required because {why}")

        # EXTERNAL-INFRA: held alone, by exact, or not at all.
        ext = f"{prefix}-EXTERNAL-INFRA"
        if ext in _groups(e, "grant"):
            errs.append(f"{where}: {ext} may only be held as `exact: [{ext}]` — an external-service "
                        "host holds it alone, never on top of a baseline")
        if ext in _groups(e, "exact") and _groups(e, "exact") != [ext]:
            errs.append(f"{where}: {ext} may only be held alone — `exact: [{ext}]`, never beside another group")

        # PLATFORM-ADMIN: a person's device, never a machine.
        pa = f"{prefix}-PLATFORM-ADMIN"
        if pa in held and peer and not peer.startswith(PERSON_PEER_PREFIX):
            errs.append(f"{where}: {pa} is for a person device (peer name `{PERSON_PEER_PREFIX}…`), never a machine")
    return errs

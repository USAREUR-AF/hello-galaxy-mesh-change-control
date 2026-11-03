"""The shape of a declaration on disk: one DIRECTORY per scope.

A re-implementation of how goat's `ops/warrant/membership.py` reads a scope
(design mesh-change-control.md §4.1). Where the two could differ, goat's is
right.

    ops/warrant/membership/<scope>/
      _scope.yaml                version, scope, converge. The switch, and the
                                 ONLY file that carries scope or converge.
      people.yaml, holds.yaml,   fragments: `version: 1` + `entries: [...]`,
      services.yaml, orgs/x.yaml at any depth. One entry per peer ACROSS them.
      _baseline.generated.yaml   GENERATED from the operator manifests: each
                                 person's `device` and `handset` groups.

The converger, the CI check and the narrowing prover all read the MERGED view:
every fragment's entries together, in path order. Which fragment an entry sits
in is filing, not meaning — moving one unchanged changes nothing.

Refused: a `_*.yaml` other than the two reserved names, a `.yml`, and the
retired single file `<scope>.yaml`.
"""

from __future__ import annotations

from pathlib import Path

import yaml

SCOPE_FILE = "_scope.yaml"
BASELINE_FILE = "_baseline.generated.yaml"
SCOPE_KEYS = {"version", "scope", "converge"}
FRAGMENT_KEYS = {"version", "entries"}
BASELINE_KEYS = {"version", "scope", "generated_from", "people"}


class LayoutError(Exception):
    """A declaration that cannot be read as a scope directory."""


def _load(path: Path) -> dict:
    try:
        doc = yaml.safe_load(Path(path).read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise LayoutError(f"cannot read {path}: {exc}") from exc
    if doc is None:
        return {}
    if not isinstance(doc, dict):
        raise LayoutError(f"{path}: top level must be a mapping")
    return doc


def scope_files(sdir: Path) -> tuple[list[Path], list[str]]:
    """(fragments, refusals). Fragments: every *.yaml not starting with `_`."""
    sdir = Path(sdir)
    fragments: list[Path] = []
    refused: list[str] = []
    for p in sorted(sdir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(sdir).as_posix()
        if p.suffix == ".yml":
            refused.append(f"{rel}: fragments are `.yaml`; a `.yml` would be read by nothing")
        elif p.suffix != ".yaml":
            continue
        elif p.name.startswith("_"):
            if rel not in (SCOPE_FILE, BASELINE_FILE):
                refused.append(f"{rel}: `_` names are reserved — only {SCOPE_FILE} and "
                               f"{BASELINE_FILE}, at the top of the scope directory")
        else:
            fragments.append(p)
    return fragments, refused


def load_decl(path) -> dict | None:
    """The merged view of a scope directory, or None when *path* is '-'
    (absent on that side of a diff).

    Returns {version, scope, converge, entries, labels, baseline}: `entries`
    from every fragment in path order, `labels` naming where each came from,
    `baseline` the parsed people mapping (or None when there is no baseline
    file). A plain file is the retired layout and is refused.
    """
    if str(path) == "-":
        return None
    p = Path(path)
    if p.is_file():
        raise LayoutError(f"{p}: the single-file layout is retired — a scope is a directory "
                          f"<scope>/ holding {SCOPE_FILE}, fragments and {BASELINE_FILE}")
    if not p.is_dir():
        raise LayoutError(f"{p}: no such scope directory")
    head = _load(p / SCOPE_FILE) if (p / SCOPE_FILE).is_file() else {}
    entries: list = []
    labels: list[str] = []
    for f in scope_files(p)[0]:
        got = _load(f).get("entries")
        if isinstance(got, list):
            rel = f.relative_to(p).as_posix()
            for i, e in enumerate(got):
                entries.append(e)
                labels.append(f"{rel} entries[{i}]")
    base = _load(p / BASELINE_FILE) if (p / BASELINE_FILE).is_file() else None
    return {
        "version": head.get("version"),
        "scope": head.get("scope"),
        "converge": head.get("converge"),
        "entries": entries,
        "labels": labels,
        "baseline": None if base is None else (base.get("people") or {}),
        "_baseline_doc": base,
        "_dir": p,
    }


def validate_layout(path, taxonomy: dict) -> list[str]:
    """What is wrong with the directory itself (not the entries' contents)."""
    p = Path(path)
    if p.is_file():
        return [f"{p.name}: the single-file layout is retired — a scope is a directory"]
    fragments, errs = scope_files(p)
    errs = list(errs)
    if not (p / SCOPE_FILE).is_file():
        errs.append(f"{SCOPE_FILE} is missing — it carries scope and converge, the switch")
    else:
        extra = set(_load(p / SCOPE_FILE)) - SCOPE_KEYS
        if extra:
            errs.append(f"{SCOPE_FILE}: unknown key(s): {', '.join(sorted(extra))} "
                        "(entries live in fragments, not here)")
    for f in fragments:
        doc = _load(f)
        rel = f.relative_to(p).as_posix()
        extra = set(doc) - FRAGMENT_KEYS
        if extra & {"scope", "converge"}:
            errs.append(f"{rel}: only {SCOPE_FILE} carries scope/converge")
        if extra - {"scope", "converge"}:
            errs.append(f"{rel}: unknown top-level key(s): {', '.join(sorted(extra - {'scope', 'converge'}))}")
        if doc.get("version") != 1:
            errs.append(f"{rel}: version must be 1, got {doc.get('version')!r}")
    scope = _load(p / SCOPE_FILE).get("scope") if (p / SCOPE_FILE).is_file() else None
    bf = p / BASELINE_FILE
    if not bf.is_file():
        errs.append(f"{BASELINE_FILE} is missing — generate it from the operator manifests")
    elif scope in taxonomy:
        doc = _load(bf)
        prefix = taxonomy[scope]["site_prefix"]
        suffixes = set(taxonomy[scope]["suffixes"])
        extra = set(doc) - BASELINE_KEYS
        if extra:
            errs.append(f"{BASELINE_FILE}: unknown key(s): {', '.join(sorted(extra))}")
        if doc.get("scope") != scope:
            errs.append(f"{BASELINE_FILE}: scope {doc.get('scope')!r} is not {scope!r}")
        for handle, sets in (doc.get("people") or {}).items():
            if not isinstance(sets, dict) or "device" not in sets or set(sets) - {"device", "handset"}:
                errs.append(f"{BASELINE_FILE} people.{handle}: needs device, and handset only if "
                            "the person has a phone-and-tablet key")
                continue
            for kind, groups in sets.items():
                for g in groups or []:
                    if not str(g).startswith(prefix + "-") or str(g)[len(prefix) + 1:] not in suffixes:
                        errs.append(f"{BASELINE_FILE} people.{handle}.{kind}: {g!r} is not a {scope} group")
    return errs

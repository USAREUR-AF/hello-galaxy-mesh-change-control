"""The CI rules (§4.3) and the narrowing prover (§4.3 "Narrowing")."""

import datetime as dt
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from mcc import baseline, layout, narrowing, rules  # noqa: E402

TODAY = dt.date(2026, 9, 23)
TAX = yaml.safe_load((ROOT / "fixtures/taxonomy.yaml").read_text())["scopes"]


def load(p):
    return layout.load_decl(p)


def errors(p):
    p = Path(p)
    errs = layout.validate_layout(p, TAX)
    if p.is_dir():
        d = load(p)
        errs += rules.validate(d, TAX, TODAY, stem=p.name, labels=d["labels"])
    return errs


def scope_dir(kind, name):
    """fixtures/<kind>/<name>/zagros-dev — or the one file in it (the retired layout)."""
    d = ROOT / "fixtures" / kind / name
    return d / "zagros-dev" if (d / "zagros-dev").is_dir() else next(d.glob("*.yaml"))


# ---- rules ---------------------------------------------------------------------


@pytest.mark.parametrize("name", ["ordinary", "hold", "release-by-delete"])
def test_scenario_declarations_are_valid(name):
    assert errors(scope_dir("declarations", name)) == []


REFUSED = {
    "01-external-infra-beside-a-person-role": "may only be held as `exact: [ZAGROS-DEV-EXTERNAL-INFRA]`",
    "02-external-infra-in-a-mixed-exact": "may only be held alone",
    "03-platform-admin-on-a-machine": "is for a person device",
    "04-hold-with-no-expiry": "expires is required because a hold",
    "05-p2p-grant-with-no-expiry": "expires is required because it grants P2P",
    "06-expired": "expired 2026-09-01",
    "07-wrong-prefix": "does not carry the scope prefix ZAGROS-DEV-",
    "08-group-not-in-taxonomy": "suffix DEVELOPERS is not in the zagros-dev taxonomy",
    "09-two-forms-in-one-entry": "exactly one of grant/absent, exact, hold",
    "10-duplicate-peer": "already declared at orgs/demo-org.yaml entries[0]",
    "11-typo-key": "unknown key(s): grants",
    "12-no-owner-no-reason": "owner is required",
    "13-single-file-layout": "the single-file layout is retired",
    "14-converge-in-a-fragment": "only _scope.yaml carries scope/converge",
    "15-stray-underscore-file": "_overrides.yaml: `_` names are reserved",
    "16-no-baseline": "_baseline.generated.yaml is missing",
}


@pytest.mark.parametrize("name,needle", sorted(REFUSED.items()))
def test_refused_fixture_is_refused_for_its_reason(name, needle):
    errs = errors(scope_dir("refused", name))
    assert errs, f"{name} was accepted"
    assert any(needle in e for e in errs), errs


def test_every_refused_fixture_has_a_test():
    on_disk = {p.name for p in (ROOT / "fixtures/refused").iterdir() if p.is_dir()}
    assert on_disk == set(REFUSED)


def test_platform_admin_on_a_person_device_is_accepted():
    doc = load(scope_dir("refused", "03-platform-admin-on-a-machine"))
    doc["entries"][0]["peer"] = "peer-alice-zagros-dev-2026-09-01-laptop"
    assert rules.validate(doc, TAX, TODAY) == []


def test_reason_over_200_chars_is_refused():
    doc = load(scope_dir("declarations", "ordinary"))
    doc["entries"][0]["reason"] = "x" * 201
    assert any("limit is 200" in e for e in rules.validate(doc, TAX, TODAY))


def test_unknown_scope_is_refused():
    doc = load(scope_dir("declarations", "ordinary"))
    doc["scope"] = "nowhere"
    assert any("not a taxonomy scope" in e for e in rules.validate(doc, TAX, TODAY))


def test_scope_must_match_its_directory():
    d = scope_dir("declarations", "ordinary")
    assert any("does not match the directory name" in e
               for e in rules.validate(load(d), TAX, TODAY, stem="zagros"))


def test_committed_baselines_match_the_manifests():
    want = baseline.render(baseline.generate("zagros-dev", TAX, baseline.load_manifests(ROOT / "fixtures/manifests")))
    for d in (ROOT / "fixtures/declarations").glob("*/zagros-dev"):
        assert (d / layout.BASELINE_FILE).read_text() == want, d


def test_baseline_generation_rules():
    ms = [(Path("a.yml"), {"identity": {"handle": "a", "status": "active"},
                           "netbird": {"auto_groups": ["VENDOR", "OBSERVER"], "sites": ["zagros-dev"]}}),
          (Path("b.yml"), {"identity": {"handle": "b", "status": "active"},
                           "netbird": {"auto_groups": ["OBSERVER"], "sites": ["zagros-dev"], "handset_limit": 0}}),
          (Path("c.yml"), {"identity": {"handle": "c", "status": "revoked"},
                           "netbird": {"auto_groups": ["OBSERVER"], "sites": ["zagros-dev"]}}),
          (Path("d.yml"), {"identity": {"handle": "d", "status": "active"},
                           "netbird": {"auto_groups": ["OBSERVER"], "sites": ["zagros"]}})]
    people = baseline.generate("zagros-dev", TAX, ms)["people"]
    assert people == {
        "a": {"device": ["ZAGROS-DEV-DEVELOPER", "ZAGROS-DEV-OBSERVER"],  # VENDOR is DEVELOPER
              "handset": ["ZAGROS-DEV-HANDSET", "ZAGROS-DEV-OBSERVER"]},  # a handset key is OBSERVER-only
        "b": {"device": ["ZAGROS-DEV-OBSERVER"]},                       # handset_limit 0: no phone key, no set
    }
    with pytest.raises(baseline.BaselineError):
        baseline.generate("zagros-dev", TAX, ms + [ms[0]])  # one handle, two manifests


# ---- narrowing -------------------------------------------------------------------

DIFFS = ROOT / "fixtures/diffs"
BASE = load(DIFFS / "base" / "zagros-dev")
CASES = sorted(p.name for p in DIFFS.iterdir() if p.is_dir() and p.name != "base")


@pytest.mark.parametrize("name", [c for c in CASES if c.startswith("n")])
def test_narrowings_are_proven(name):
    wide, narrow = narrowing.membership_changes(BASE, load(DIFFS / name / "zagros-dev"))
    assert wide == [], wide
    assert narrow or name == "n9-move-to-another-fragment"


def test_moving_an_entry_between_fragments_is_no_change():
    assert narrowing.verdict(BASE, load(DIFFS / "n9-move-to-another-fragment" / "zagros-dev")) == "no-change"


@pytest.mark.parametrize("name", [c for c in CASES if c.startswith("w")])
def test_widenings_are_not_proven(name):
    wide, _ = narrowing.membership_changes(BASE, load(DIFFS / name / "zagros-dev"))
    assert wide


def test_deleting_the_scope_is_a_widening():
    wide, _ = narrowing.membership_changes(BASE, None)
    assert wide == ["the scope's declaration is deleted — that ungoverns the scope"]


def test_a_new_scope_with_only_absent_entries_is_a_narrowing():
    head = {"version": 1, "scope": "zagros-dev", "converge": "report", "baseline": {},
            "entries": [{"peer": "x", "absent": ["ZAGROS-DEV-OBSERVER"], "owner": "o", "reason": "r"}]}
    assert narrowing.verdict(None, head) == "narrowing"


def test_a_new_scope_with_a_baseline_of_people_is_a_widening():
    head = {"version": 1, "scope": "zagros-dev", "converge": "report", "entries": [],
            "baseline": {"a": {"device": ["ZAGROS-DEV-OBSERVER"], "handset": []}}}
    assert narrowing.verdict(None, head) == "widening"


def test_no_change():
    assert narrowing.verdict(BASE, BASE) == "no-change"


def test_hold_release_and_revert_are_both_widenings():
    assert narrowing.verdict(BASE, load(DIFFS / "w2-release-a-hold" / "zagros-dev")) == "widening"
    assert narrowing.verdict(BASE, load(DIFFS / "w3-hold-back-to-an-entry" / "zagros-dev")) == "widening"

"""The desired-membership table (design mesh-change-control.md §4.2)."""

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from mcc import layout, model  # noqa: E402

P = "ZAGROS-DEV"
LIVE = json.loads((ROOT / "fixtures/mgmt-state/zagros-dev.json").read_text())
DECL = ROOT / "fixtures/declarations"


def baselines():
    return model.key_baselines(LIVE["events"], LIVE["setup_keys"], LIVE["groups"])


def key_names():
    return model.minting_keys(LIVE["events"], LIVE["setup_keys"])


def plan(path, peers=None):
    return model.plan_membership(
        layout.load_decl(path),
        peers if peers is not None else LIVE["peers"],
        baselines(),
        set(LIVE["covered_groups"]),
        {g["name"] for g in LIVE["groups"]},
        key_names=key_names(),
    )


ORDINARY = DECL / "ordinary" / "zagros-dev"
HOLD = DECL / "hold" / "zagros-dev"
RELEASE = DECL / "release-by-delete" / "zagros-dev"


# ---- the table, one row at a time --------------------------------------------


def test_no_entry_is_the_key_baseline():
    assert model.desired_set(None, {f"{P}-DEVELOPER"}, P) == {f"{P}-DEVELOPER"}


def test_grant_and_absent_edit_the_baseline():
    e = {"peer": "x", "grant": [f"{P}-P2P"], "absent": [f"{P}-OBSERVER"]}
    assert model.desired_set(e, {f"{P}-DEVELOPER", f"{P}-OBSERVER"}, P) == {f"{P}-DEVELOPER", f"{P}-P2P"}


def test_exact_ignores_the_baseline():
    e = {"peer": "x", "exact": [f"{P}-EXTERNAL-INFRA"]}
    assert model.desired_set(e, {f"{P}-DEVELOPER"}, P) == {f"{P}-EXTERNAL-INFRA"}
    assert model.desired_set(e, None, P) == {f"{P}-EXTERNAL-INFRA"}  # needs no baseline


def test_hold_is_quarantined_alone():
    e = {"peer": "x", "hold": "quarantine"}
    assert model.desired_set(e, {f"{P}-DEVELOPER", f"{P}-P2P"}, P) == {f"{P}-QUARANTINED"}
    assert model.desired_set(e, None, P) == {f"{P}-QUARANTINED"}


def test_no_baseline_and_no_exact_or_hold_is_unknown():
    assert model.desired_set(None, None, P) is None
    assert model.desired_set({"peer": "x", "grant": [f"{P}-P2P"]}, None, P) is None


def test_an_empty_baseline_is_not_unknown():
    # A key that granted nothing is a baseline of {} — the peer is planned.
    assert model.desired_set(None, set(), P) == set()


def test_entry_with_two_forms_is_refused():
    with pytest.raises(ValueError):
        model.entry_form({"peer": "x", "hold": "quarantine", "grant": [f"{P}-P2P"]})


# ---- managed groups -----------------------------------------------------------


def test_only_the_scope_prefix_is_managed():
    assert model.is_managed("ZAGROS-DEV-OBSERVER", "ZAGROS-DEV")
    assert not model.is_managed("All", "ZAGROS-DEV")
    assert not model.is_managed("mesh-dns", "ZAGROS-DEV")
    assert not model.is_managed("EX-DEMO-DEVELOPER", "ZAGROS-DEV")


def test_a_longer_prefix_is_not_ours():
    # On a server hosting zagros and zagros-dev, scope zagros must not manage ZAGROS-DEV-*.
    assert model.is_managed("ZAGROS-OBSERVER", "ZAGROS", ("ZAGROS-DEV",))
    assert not model.is_managed("ZAGROS-DEV-OBSERVER", "ZAGROS", ("ZAGROS-DEV",))


# ---- key baselines ------------------------------------------------------------


def test_baseline_joins_peer_added_to_the_key():
    b = baselines()
    assert b["p-alice"] == {f"{P}-DEVELOPER", f"{P}-OBSERVER"}
    assert b["p-mgmt"] == set()
    assert "p-dave" not in b  # interactive login: no Peer added event
    assert "p-erin" not in b  # key deleted and its name matches no key


def test_baseline_falls_back_to_an_unambiguous_key_name():
    events = [{"activity": "Peer added", "initiator_id": "gone", "target_id": "p1",
               "meta": {"setup_key_name": "k"}}]
    keys = [{"id": "k1", "name": "k", "auto_groups": ["g"]}]
    assert model.key_baselines(events, keys, [{"id": "g", "name": "G"}]) == {"p1": {"G"}}
    keys.append({"id": "k2", "name": "k", "auto_groups": []})  # now ambiguous
    assert model.key_baselines(events, keys, [{"id": "g", "name": "G"}]) == {}


def test_oldest_peer_added_event_wins():
    events = [  # newest first, as the management server returns them
        {"activity": "Peer added", "initiator_id": "new", "target_id": "p1"},
        {"activity": "Peer added", "initiator_id": "old", "target_id": "p1"},
    ]
    keys = [{"id": "new", "name": "n", "auto_groups": ["gn"]},
            {"id": "old", "name": "o", "auto_groups": ["go"]}]
    assert model.key_baselines(events, keys, []) == {"p1": {"go"}}


# ---- the declared baseline ------------------------------------------------------

PEOPLE = {"ann": {"device": ["D"], "handset": ["H"]},
          "ann-smith": {"device": ["S"], "handset": ["SH"]}}


def test_handle_match_is_anchored_and_longest_wins():
    m = lambda n: model.match_handle(n, PEOPLE, "zagros")  # noqa: E731
    assert m("peer-ann-zagros-2026-06-10-mac") == "ann"
    assert m("peer-ann-acme-zagros-2026-06-10-mac") == "ann"              # an org tag
    assert m("peer-ann-smith-zagros-2026-06-10-mac") == "ann-smith"       # longest wins
    assert m("peer-anne-zagros-2026-06-10-mac") is None
    assert m("peer-ann-zagros-dev-2026-06-10-mac") is None                 # another goatnet
    assert m("peer-ann-laptop") is None                                  # no goatnet, no date
    assert m("mgmt-ann-01") is None                                      # not a peer name at all


def test_declared_baseline_wins_over_the_key():
    b, src = model.baseline_for("peer-ann-zagros-2026-06-10-mac", "p1", PEOPLE, {"p1": {"K"}}, {"p1": "k"}, "zagros")
    assert (b, src) == ({"D"}, "declared ann device")


def test_handset_key_selects_the_handset_set():
    b, src = model.baseline_for("peer-ann-zagros-2026-06-10-iPhone", "p1", PEOPLE, {},
                                {"p1": "peer-ann-zagros-2026-06-10-handset"}, "zagros")
    assert (b, src) == ({"H"}, "declared ann handset")
    b, _ = model.baseline_for("peer-ann-handset-zagros-2026-06-10-x", "p2", PEOPLE, {}, {}, "zagros")
    assert b == {"H"}


def test_a_person_without_a_phone_key_falls_back_to_the_key():
    people = {"ann": {"device": ["D"]}}
    b, src = model.baseline_for("peer-ann-zagros-2026-06-10-iPhone", "p1", people, {"p1": {"K"}},
                                {"p1": "peer-ann-zagros-2026-06-10-handset"}, "zagros")
    assert (b, src) == ({"K"}, "key peer-ann-zagros-2026-06-10-handset")


def test_key_baseline_when_not_declared_and_unknown_when_neither():
    assert model.baseline_for("mgmt-01", "p1", PEOPLE, {"p1": {"K"}}, {"p1": "boot"}) == ({"K"}, "key boot")
    assert model.baseline_for("mgmt-01", "p1", PEOPLE, {}, {}) == (None, "")


# ---- the plan over the mgmt-state fixture ---------------------------------------


def test_mgmt_state_plan_rows():
    p = plan(ORDINARY)
    status = {r.peer: r.status for r in p.rows}
    assert status["peer-alice-zagros-dev-2026-09-01-laptop"] == model.DRIFT
    assert status["peer-bob-zagros-dev-2026-09-02-laptop"] == model.DRIFT
    assert status["demo-service-01"] == model.DRIFT
    assert status["peer-carol-zagros-dev-2026-09-03-laptop"] == model.MATCH
    assert status["peer-dave-zagros-dev-2026-09-04-desktop"] == model.UNKNOWN
    # erin's key was deleted, but her manifest declares her baseline.
    assert status["peer-erin-zagros-dev-2026-09-05-laptop"] == model.DRIFT
    assert status["mgmt-demo-01"] == model.MATCH
    assert status["sensor-demo-01"] == model.BLOCKED
    assert status["peer-hana-zagros-dev-2026-09-08-iPhone"] == model.MATCH
    assert status["peer-frank-zagros-dev-2026-09-07-laptop"] == model.MISSING_PEER
    assert p.changes_planned == 6


def test_baseline_source_is_reported():
    p = plan(ORDINARY)
    assert p.row("peer-erin-zagros-dev-2026-09-05-laptop").baseline_source == "declared erin device"
    assert p.row("peer-hana-zagros-dev-2026-09-08-iPhone").baseline_source == "declared hana handset"
    assert p.row("mgmt-demo-01").baseline_source == "key zagros-dev-bootstrap"
    assert p.row("peer-dave-zagros-dev-2026-09-04-desktop").baseline_source == ""


def test_erin_is_unknown_without_the_declared_baseline():
    d = layout.load_decl(ORDINARY)
    d["baseline"] = None
    p = model.plan_membership(d, LIVE["peers"], baselines(), set(LIVE["covered_groups"]),
                              {g["name"] for g in LIVE["groups"]}, key_names=key_names())
    assert p.row("peer-erin-zagros-dev-2026-09-05-laptop").status == model.UNKNOWN


def test_a_dashboard_edit_is_put_back():
    r = plan(ORDINARY).row("peer-bob-zagros-dev-2026-09-02-laptop")
    assert r.remove == [f"{P}-PLATFORM-ADMIN"] and r.add == []


def test_unknown_is_never_changed_even_holding_platform_admin():
    r = plan(ORDINARY).row("peer-dave-zagros-dev-2026-09-04-desktop")
    assert r.add == [] and r.remove == [] and r.desired is None


def test_other_prefix_groups_are_reported_not_touched():
    r = plan(HOLD).row("peer-carol-zagros-dev-2026-09-03-laptop")
    assert "EX-DEMO-DEVELOPER" in r.unmanaged and "All" in r.unmanaged
    assert "EX-DEMO-DEVELOPER" not in r.remove and "All" not in r.remove


def test_coverage_gate_blocks_an_add_into_an_uncovered_group():
    r = plan(ORDINARY).row("sensor-demo-01")
    assert r.status == model.BLOCKED and "covered by no enabled policy" in r.note


# ---- quarantine and release ---------------------------------------------------------


def desired_for(path, peer_id, peer_name):
    d = layout.load_decl(path)
    e = next((x for x in d["entries"] if x["peer"] == peer_name), None)
    base, _ = model.baseline_for(peer_name, peer_id, d["baseline"], baselines(), key_names())
    return model.desired_set(e, base, P)


CAROL = ("p-carol", "peer-carol-zagros-dev-2026-09-03-laptop")
ALICE = ("p-alice", "peer-alice-zagros-dev-2026-09-01-laptop")


def test_quarantine_then_release_restores_exactly_the_prior_groups():
    before = desired_for(ORDINARY, *CAROL)
    held = desired_for(HOLD, *CAROL)
    released = desired_for(RELEASE, *CAROL)
    assert held == {f"{P}-QUARANTINED"}
    assert released == before == {f"{P}-DEVELOPER", f"{P}-OBSERVER"}


def test_release_of_a_peer_that_had_an_entry_needs_the_revert():
    before = desired_for(ORDINARY, *ALICE)
    deleted = desired_for(RELEASE, *ALICE)
    assert before == {f"{P}-DEVELOPER", f"{P}-P2P"}
    # The hold replaced her grant entry; deleting the hold loses the grant
    # and returns her to her declared baseline.
    assert deleted == {f"{P}-DEVELOPER", f"{P}-OBSERVER"}
    # Reverting the hold commit restores the old entry = the base file.
    assert desired_for(ORDINARY, *ALICE) == before


# ---- the gates ----------------------------------------------------------------------------


def test_max_changes_refuses_the_whole_run():
    model.check_max_changes(10, 10)
    with pytest.raises(model.Refused) as e:
        model.check_max_changes(11, 10)
    assert e.value.code == 3


def test_converge_is_the_ceiling():
    assert model.effective_mode("report", "enforce") == "report"
    assert model.effective_mode("enforce", "enforce") == "enforce"
    with pytest.raises(model.Refused) as e:
        model.effective_mode("enforce", "report")
    assert e.value.code == 2


def test_a_quarantine_day_is_under_the_default_limit():
    assert plan(HOLD).changes_planned == 10 <= model.DEFAULT_MAX_CHANGES

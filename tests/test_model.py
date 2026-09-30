import pytest

from refit.record.claims import ClaimStatus
from refit.record.model import CardRecord
from refit.record.netlist import build_nets, net_id
from refit.record.pins import normalize_pin, parse_pin_ref


@pytest.mark.parametrize(
    "text, expected",
    [
        ("U3.6", ("U3", "6")),
        ("u3.6", ("U3", "6")),
        ("U3-6", ("U3", "6")),
        ("U3 pin 6", ("U3", "6")),
        ("U3:6", ("U3", "6")),
        ("U1A-3", ("U1A", "3")),
        ("Q2.E", ("Q2", "E")),
        ("  CR12 . 1 ", ("CR12", "1")),
    ],
)
def test_pin_refs_normalize(text, expected):
    assert parse_pin_ref(text) == expected
    assert normalize_pin(text) == f"{expected[0]}.{expected[1]}"


@pytest.mark.parametrize("text", ["U36", "", "pin 6", "U3."])
def test_bad_pin_refs_raise(text):
    with pytest.raises(ValueError):
        parse_pin_ref(text)


def test_card_record_json_round_trip(mk):
    rec = mk.record()
    again = CardRecord.model_validate_json(rec.model_dump_json())
    assert again == rec
    assert again.parts["R1"].attr("value") == "10k"
    assert again.parts["R1"].attr("missing") is None


def test_net_id_is_order_invariant():
    assert net_id(["U1.2", "R1.1"]) == net_id(["R1.1", "U1.2"])
    assert net_id(["R1.1"]) != net_id(["R1.2"])


def test_build_nets_groups_pins_and_labels(mk):
    nets = build_nets(mk.record().connections)
    assert [n.members for n in nets] == [["R1.1", "U1.2"], ["R1.2", "U1.6"]]
    assert nets[0].label is None
    assert nets[1].label == "OUT"


def test_build_nets_machine_view_uses_first_verdict_and_skips_human_pins(mk):
    rec = mk.record()
    for claim in rec.connections.values():
        claim.machine_status = ClaimStatus.ACCEPTED
        claim.machine_value = claim.value
    rec.connections["U1.6"].value = "_n1"  # later human correction
    human = mk.conn("R9.1", "OUT")          # human-added pin, never machine-evaluated
    rec.connections["R9.1"] = human
    nets = build_nets(rec.connections, machine=True)
    assert [n.members for n in nets] == [["R1.1", "U1.2"], ["R1.2", "U1.6"]]

import pytest
from skills_builder.flow import (
    ORDER, next_stage, can_transition, validate_transition, FlowError,
)


def test_order_matches_journey_rail():
    assert ORDER == ["idea", "shape", "draft", "test", "use"]


def test_next_stage_advances_one_step():
    assert next_stage("idea") == "shape"
    assert next_stage("draft") == "test"


def test_next_stage_on_final_raises():
    with pytest.raises(FlowError):
        next_stage("use")


def test_forward_transitions_allowed():
    assert can_transition("idea", "shape")
    assert can_transition("shape", "draft")
    assert can_transition("draft", "test")
    assert can_transition("test", "use")


def test_skipping_a_stage_rejected():
    assert not can_transition("idea", "draft")
    assert not can_transition("shape", "test")


def test_test_can_return_to_draft_for_revision():
    assert can_transition("test", "draft")


def test_backward_jumps_generally_rejected():
    assert not can_transition("draft", "idea")
    assert not can_transition("use", "test")


def test_validate_transition_raises_on_illegal():
    with pytest.raises(FlowError):
        validate_transition("idea", "use")


def test_validate_transition_unknown_stage_raises():
    with pytest.raises(FlowError):
        validate_transition("bogus", "shape")

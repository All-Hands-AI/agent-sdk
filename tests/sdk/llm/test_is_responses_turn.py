import pytest

from openhands.sdk.llm import LLM


def test_is_responses_turn_supports_no_prev():
    llm = LLM(model="gpt-5-mini", service_id="t")
    assert llm.is_responses_turn(previous_response_id=None) is True


def test_is_responses_turn_no_support_no_prev():
    llm = LLM(model="gpt-4o-mini", service_id="t")
    assert llm.is_responses_turn(previous_response_id=None) is False


def test_is_responses_turn_no_support_with_prev_raises():
    llm = LLM(model="gpt-4o-mini", service_id="t")
    with pytest.raises(RuntimeError):
        llm.is_responses_turn(previous_response_id="resp_123")


def test_is_responses_turn_supports_with_prev():
    llm = LLM(model="gpt-5", service_id="t")
    assert llm.is_responses_turn(previous_response_id="resp_123") is True

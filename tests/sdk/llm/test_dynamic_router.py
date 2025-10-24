"""
Tests for the DynamicRouter implementation.
"""

import json

import pytest
from pydantic import SecretStr

from openhands.sdk.llm import LLM
from openhands.sdk.llm.router.impl.dynamic import DynamicRouter


class TestDynamicRouter:
    """Test suite for DynamicRouter functionality."""

    def test_initialization(self):
        """Test basic router initialization."""
        initial_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="agent"
        )

        router = DynamicRouter(
            service_id="test_router", llms_for_routing={"primary": initial_llm}
        )

        assert router.router_name == "dynamic_router"
        assert router.manual_selection is None
        assert len(router.llms_for_routing) == 1
        assert "primary" in router.llms_for_routing

    def test_default_selection(self):
        """Test default LLM selection when no manual selection is set."""
        initial_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="agent"
        )
        second_llm = LLM(
            model="gpt-4o", api_key=SecretStr("test-key2"), service_id="agent2"
        )

        router = DynamicRouter(
            service_id="test_router",
            llms_for_routing={"primary": initial_llm, "secondary": second_llm},
        )

        selected = router.select_llm([])
        assert selected == "primary"

    def test_manual_selection(self):
        """Test manual LLM selection."""
        llm1 = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key1"), service_id="llm1"
        )
        llm2 = LLM(model="gpt-4o", api_key=SecretStr("test-key2"), service_id="llm2")

        router = DynamicRouter(
            service_id="test_router", llms_for_routing={"primary": llm1, "llm2": llm2}
        )

        # Test switching to existing LLM
        success = router.switch_to_llm("llm2")
        assert success is True
        assert router.manual_selection == "llm2"
        assert router.select_llm([]) == "llm2"

    def test_switch_to_non_existent_model(self):
        """Test that switching to a non-existent model fails."""
        # Create with a minimal dummy LLM to satisfy base class validation
        dummy_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("dummy"), service_id="dummy"
        )
        router = DynamicRouter(
            service_id="test_router", llms_for_routing={"primary": dummy_llm}
        )

        success = router.switch_to_llm("invalid")
        assert success is False
        assert router.manual_selection is None
        assert "invalid" not in router.llms_for_routing

    def test_get_available_llms(self):
        """Test getting list of available LLMs."""
        initial_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="agent"
        )
        claude_llm = LLM(
            service_id="claude",
            model="claude-3-5-sonnet-20241022",
            api_key=SecretStr("claude-key"),
        )

        router = DynamicRouter(
            service_id="test_router",
            llms_for_routing={"primary": initial_llm, "claude": claude_llm},
        )

        # Initially only pre-configured LLM
        available = router.llms_for_routing
        assert available["primary"].model == "gpt-4o-mini"

        # Add dynamic LLM
        router.switch_to_llm(
            "claude",
        )

        available = router.llms_for_routing
        assert len(available) == 2
        assert available["primary"].model == "gpt-4o-mini"
        assert available["claude"].model == "claude-3-5-sonnet-20241022"

    def test_get_current_llm_name(self):
        """Test getting current LLM name."""
        dummy_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("dummy"), service_id="dummy"
        )
        claude = LLM(
            service_id="claude",
            model="claude-3-5-sonnet-20241022",
            api_key=SecretStr("claude-key"),
        )

        router = DynamicRouter(
            service_id="test_router",
            llms_for_routing={"primary": dummy_llm, "claude": claude},
        )

        assert router.active_llm_identifier is None

        router.switch_to_llm(
            "claude",
        )
        assert router.active_llm_identifier == "claude"

    def test_serialization_with_dynamic_llms(self):
        """Test serialization of router with dynamic LLMs."""
        initial_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="agent"
        )
        claude_llm = LLM(
            service_id="claude",
            model="claude-3-5-sonnet-20241022",
            api_key=SecretStr("claude-key"),
        )
        gemini_llm = LLM(
            service_id="gemini",
            model="gemini-1.5-pro",
            api_key=SecretStr("gemini-key"),
        )

        router = DynamicRouter(
            service_id="test_router",
            llms_for_routing={
                "primary": initial_llm,
                "claude": claude_llm,
                "gemini": gemini_llm,
            },
        )

        # Add dynamic LLMs
        router.switch_to_llm(
            "claude",
        )
        router.switch_to_llm(
            "gemini",
        )

        # Serialize
        serialized = router.model_dump_json(exclude_none=True)
        data = json.loads(serialized)

        assert data["manual_selection"] == "gemini"  # Last selected

    def test_manually_modify_llms_for_routing_raise_error(self):
        """Test that manually modifying llms_for_routing is not allowed."""
        initial_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="agent"
        )
        router = DynamicRouter(
            service_id="test_router", llms_for_routing={"primary": initial_llm}
        )
        with pytest.raises(TypeError):
            router.llms_for_routing["new_llm"] = LLM(
                model="gpt-4o", api_key=SecretStr("test-key2"), service_id="agent2"
            )

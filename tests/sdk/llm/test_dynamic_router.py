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
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="initial"
        )

        router = DynamicRouter(
            service_id="test_router", llms_for_routing={"initial": initial_llm}
        )

        assert router.router_name == "dynamic_router"
        assert router.manual_selection is None
        assert len(router.llms_for_routing) == 1
        assert "initial" in router.llms_for_routing
        assert len(router.dynamic_llm_configs) == 0

    def test_default_selection(self):
        """Test default LLM selection when no manual selection is set."""
        initial_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="initial"
        )

        router = DynamicRouter(
            service_id="test_router", llms_for_routing={"initial": initial_llm}
        )

        selected = router.select_llm([])
        assert selected == "initial"

    def test_manual_selection(self):
        """Test manual LLM selection."""
        llm1 = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key1"), service_id="llm1"
        )
        llm2 = LLM(model="gpt-4o", api_key=SecretStr("test-key2"), service_id="llm2")

        router = DynamicRouter(
            service_id="test_router", llms_for_routing={"llm1": llm1, "llm2": llm2}
        )

        # Test switching to existing LLM
        success = router.switch_to_llm("llm2")
        assert success is True
        assert router.manual_selection == "llm2"
        assert router.select_llm([]) == "llm2"

    def test_dynamic_llm_creation(self):
        """Test creating new LLMs dynamically."""
        initial_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="initial"
        )

        router = DynamicRouter(
            service_id="test_router", llms_for_routing={"initial": initial_llm}
        )

        # Create new LLM dynamically
        success = router.switch_to_llm(
            "claude",
            model="claude-3-5-sonnet-20241022",
            api_key="claude-key",
            temperature=0.7,
        )

        assert success is True
        assert router.manual_selection == "claude"
        assert "claude" in router.llms_for_routing
        assert "claude" in router.dynamic_llm_configs
        assert (
            router.dynamic_llm_configs["claude"]["model"]
            == "claude-3-5-sonnet-20241022"
        )
        assert router.dynamic_llm_configs["claude"]["temperature"] == 0.7
        assert router.select_llm([]) == "claude"

    def test_dynamic_llm_creation_without_model(self):
        """Test that creating LLM without model fails."""
        # Create with a minimal dummy LLM to satisfy base class validation
        dummy_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("dummy"), service_id="dummy"
        )
        router = DynamicRouter(
            service_id="test_router", llms_for_routing={"dummy": dummy_llm}
        )

        success = router.switch_to_llm("invalid")
        assert success is False
        assert router.manual_selection is None
        assert "invalid" not in router.llms_for_routing

    def test_get_available_llms(self):
        """Test getting list of available LLMs."""
        initial_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="initial"
        )

        router = DynamicRouter(
            service_id="test_router", llms_for_routing={"initial": initial_llm}
        )

        # Initially only pre-configured LLM
        available = router.get_available_llms()
        assert available == {"initial": "gpt-4o-mini"}

        # Add dynamic LLM
        router.switch_to_llm(
            "claude",
            model="claude-3-5-sonnet-20241022",
            api_key="claude-key",
        )

        available = router.get_available_llms()
        assert len(available) == 2
        assert available["initial"] == "gpt-4o-mini"
        assert available["claude"] == "claude-3-5-sonnet-20241022"

    def test_remove_dynamic_llm(self):
        """Test removing dynamically created LLMs."""
        dummy_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("dummy"), service_id="dummy"
        )
        router = DynamicRouter(
            service_id="test_router", llms_for_routing={"dummy": dummy_llm}
        )

        # Add dynamic LLM
        router.switch_to_llm(
            "claude",
            model="claude-3-5-sonnet-20241022",
            api_key="claude-key",
        )
        assert "claude" in router.llms_for_routing
        assert "claude" in router.dynamic_llm_configs

        # Remove it
        success = router.remove_llm("claude")
        assert success is True
        assert "claude" not in router.llms_for_routing
        assert "claude" not in router.dynamic_llm_configs
        assert router.manual_selection is None

    def test_remove_non_dynamic_llm(self):
        """Test that removing pre-configured LLMs fails."""
        initial_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="initial"
        )

        router = DynamicRouter(
            service_id="test_router", llms_for_routing={"initial": initial_llm}
        )

        success = router.remove_llm("initial")
        assert success is False
        assert "initial" in router.llms_for_routing

    def test_get_current_llm_name(self):
        """Test getting current LLM name."""
        dummy_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("dummy"), service_id="dummy"
        )
        router = DynamicRouter(
            service_id="test_router", llms_for_routing={"dummy": dummy_llm}
        )

        assert router.get_current_llm_name() is None

        router.switch_to_llm(
            "claude",
            model="claude-3-5-sonnet-20241022",
            api_key="claude-key",
        )
        assert router.get_current_llm_name() == "claude"

    def test_serialization_with_dynamic_llms(self):
        """Test serialization includes dynamic LLM configs."""
        initial_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("test-key"), service_id="initial"
        )

        router = DynamicRouter(
            service_id="test_router", llms_for_routing={"initial": initial_llm}
        )

        # Add dynamic LLMs
        router.switch_to_llm(
            "claude",
            model="claude-3-5-sonnet-20241022",
            api_key="claude-key",
        )
        router.switch_to_llm("gemini", model="gemini-1.5-pro", api_key="gemini-key")

        # Serialize
        serialized = router.model_dump_json(exclude_none=True)
        data = json.loads(serialized)

        # Check dynamic configs are included
        assert "dynamic_llm_configs" in data
        assert "claude" in data["dynamic_llm_configs"]
        assert "gemini" in data["dynamic_llm_configs"]
        assert (
            data["dynamic_llm_configs"]["claude"]["model"]
            == "claude-3-5-sonnet-20241022"
        )
        assert data["dynamic_llm_configs"]["gemini"]["model"] == "gemini-1.5-pro"
        assert data["manual_selection"] == "gemini"  # Last selected

    def test_ensure_llm_exists(self):
        """Test _ensure_llm_exists recreates LLMs from config."""
        dummy_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("dummy"), service_id="dummy"
        )
        router = DynamicRouter(
            service_id="test_router", llms_for_routing={"dummy": dummy_llm}
        )

        # Add dynamic LLM
        router.switch_to_llm(
            "claude",
            model="claude-3-5-sonnet-20241022",
            api_key="claude-key",
        )

        # Remove from routing table but keep config
        del router.llms_for_routing["claude"]
        assert "claude" not in router.llms_for_routing
        assert "claude" in router.dynamic_llm_configs

        # Ensure it exists should recreate it
        router._ensure_llm_exists("claude")
        assert "claude" in router.llms_for_routing
        assert router.llms_for_routing["claude"].model == "claude-3-5-sonnet-20241022"

    def test_no_llms_available_error(self):
        """Test error when no LLMs are available."""
        dummy_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("dummy"), service_id="dummy"
        )
        router = DynamicRouter(
            service_id="test_router", llms_for_routing={"dummy": dummy_llm}
        )

        # Remove all LLMs to test error condition
        router.llms_for_routing.clear()

        with pytest.raises(ValueError, match="No LLMs available for routing"):
            router.select_llm([])

    def test_switch_to_existing_dynamic_llm_from_config(self):
        """Test switching to a dynamic LLM that exists only in config."""
        dummy_llm = LLM(
            model="gpt-4o-mini", api_key=SecretStr("dummy"), service_id="dummy"
        )
        router = DynamicRouter(
            service_id="test_router", llms_for_routing={"dummy": dummy_llm}
        )

        # Manually add config without creating LLM instance
        router.dynamic_llm_configs["claude"] = {
            "model": "claude-3-5-sonnet-20241022",
            "service_id": "dynamic_claude",
            "api_key": SecretStr("claude-key"),
        }

        # Switch to it should recreate from config
        success = router.switch_to_llm("claude")
        assert success is True
        assert "claude" in router.llms_for_routing
        assert router.manual_selection == "claude"
        assert router.select_llm([]) == "claude"

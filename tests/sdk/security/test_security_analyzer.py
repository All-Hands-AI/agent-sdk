"""Tests for the SecurityAnalyzer class."""

import inspect

import pytest
from litellm import ChatCompletionMessageToolCall
from litellm.types.utils import Function
from pydantic import BaseModel

from openhands.sdk.event import ActionEvent
from openhands.sdk.event.base import LLMConvertibleEvent
from openhands.sdk.event.types import EventID
from openhands.sdk.llm import TextContent
from openhands.sdk.security.analyzer import (
    PerActionSecurityAnalyzer,
    SecurityAnalyzerBase,
)
from openhands.sdk.security.risk import SecurityRisk
from openhands.sdk.tool import ActionBase


# TODO: Serialization tests for implementers of the base classes


class SimpleAction(ActionBase):
    """Simple action for testing."""

    command: str = "test_command"


def create_mock_action_event(command: str, security_risk: SecurityRisk) -> ActionEvent:
    """Helper to create ActionEvent for testing."""
    return ActionEvent(
        thought=[TextContent(text="test thought")],
        action=SimpleAction(command=command),
        tool_name="test_tool",
        tool_call_id="test_call_id",
        tool_call=ChatCompletionMessageToolCall(
            id="test_call_id",
            function=Function(name="test_tool", arguments='{"command": "test"}'),
            type="function",
        ),
        llm_response_id="test_response_id",
        security_risk=security_risk,
    )


class TestSecurityAnalyzerBase:
    """Test suite for SecurityAnalyzerBase."""

    def test_cannot_instantiate_base_class(self) -> None:
        """Test that the base class cannot be instantiated directly."""
        with pytest.raises(TypeError):
            # Of course mypy doesn't want us to do this, so ignore the type check while
            # we confirm the runtime behavior.
            SecurityAnalyzerBase()  # type: ignore

    @pytest.mark.parametrize("cls", list(SecurityAnalyzerBase.__subclasses__()))
    def test_security_analyzer_container_serialization(
        self, cls: type[SecurityAnalyzerBase]
    ) -> None:
        """Test that a container model with SecurityAnalyzer instances as a field can
        be serialized.
        """
        # Make sure the subclass is not abstract
        if inspect.isabstract(cls):
            pytest.skip(f"Skipping abstract class {cls.__name__}")

        class AnalyzerContainer(BaseModel):
            analyzer: SecurityAnalyzerBase

        container = AnalyzerContainer(analyzer=cls())

        container_dict = container.model_dump_json()
        restored_container = AnalyzerContainer.model_validate_json(container_dict)

        assert isinstance(restored_container.analyzer, cls)
        assert container.analyzer == restored_container.analyzer


class TestPerActionSecurityAnalyzer:
    """Test suite for PerActionSecurityAnalyzer."""

    class FixedOutputAnalyzer(PerActionSecurityAnalyzer):
        risks: dict[EventID, SecurityRisk] = {}
        default_risk: SecurityRisk = SecurityRisk.UNKNOWN

        def security_risk(self, action: ActionEvent) -> SecurityRisk:
            return self.risks.get(action.id, self.default_risk)

        @staticmethod
        def from_actions(
            actions: list[ActionEvent],
            default_risk: SecurityRisk = SecurityRisk.UNKNOWN,
        ) -> "TestPerActionSecurityAnalyzer.FixedOutputAnalyzer":
            analyzer = TestPerActionSecurityAnalyzer.FixedOutputAnalyzer()
            analyzer.risks = {action.id: action.security_risk for action in actions}
            analyzer.default_risk = default_risk
            return analyzer

    def test_cannot_instantiate_base_class(self) -> None:
        """Test that the base class cannot be instantiated directly."""
        with pytest.raises(TypeError):
            # Of course mypy doesn't want us to do this, so ignore the type check while
            # we confirm the runtime behavior.
            PerActionSecurityAnalyzer()  # type: ignore

    @pytest.mark.parametrize("cls", list(PerActionSecurityAnalyzer.__subclasses__()))
    def test_security_analyzer_container_serialization(
        self, cls: type[SecurityAnalyzerBase]
    ) -> None:
        """Test that a container model with PerActionSecurityAnalyzer instances as a
        field can be serialized.
        """
        # Make sure the subclass is not abstract
        if inspect.isabstract(cls):
            pytest.skip(f"Skipping abstract class {cls.__name__}")

        class AnalyzerContainer(BaseModel):
            # Note the serialization here is for the security analyzer base class, _not_
            # the PerActionSecurityAnalyzer specifically.
            analyzer: SecurityAnalyzerBase

        container = AnalyzerContainer(analyzer=cls())

        container_dict = container.model_dump_json()
        restored_container = AnalyzerContainer.model_validate_json(container_dict)

        assert isinstance(restored_container.analyzer, cls)
        assert container.analyzer == restored_container.analyzer

    def test_independent_of_current_context(self) -> None:
        """Test that PerActionSecurityAnalyzer is independent of current_context.

        That is, we should get the same results regardless of what current_context is.
        """
        # While the context is more likely to be messages/observations/actions, we can
        # still use just a list of actions to help prove that current_context is not
        # used by the analyzer.
        possible_context: list[LLMConvertibleEvent] = [
            create_mock_action_event("context_1", SecurityRisk.LOW),
            create_mock_action_event("context_2", SecurityRisk.HIGH),
            create_mock_action_event("context_3", SecurityRisk.MEDIUM),
        ]

        pending_actions: list[ActionEvent] = [
            create_mock_action_event("action_1", SecurityRisk.LOW),
            create_mock_action_event("action_2", SecurityRisk.HIGH),
            create_mock_action_event("action_3", SecurityRisk.MEDIUM),
        ]

        analyzer = self.FixedOutputAnalyzer.from_actions(pending_actions)

        result: dict[EventID, SecurityRisk] | None = None

        # Compute the security risks for all possible context prefixes.
        for context_size in range(len(possible_context)):
            context = possible_context[:context_size]
            current_result = analyzer.analyze_pending_actions(context, pending_actions)

            # If we haven't stored a result yet, do so. Otherwise, ensure it's the same
            # as what we've already seen.
            if result is None:
                result = current_result
            else:
                assert result == current_result

    def test_handles_actions_independently(self) -> None:
        """Test that PerActionSecurityAnalyzer handles each action independently.

        Regardless of the number of actions or how they are batched, we should get the
        same result per-action.
        """

        pending_actions: list[ActionEvent] = [
            create_mock_action_event("action_1", SecurityRisk.LOW),
            create_mock_action_event("action_2", SecurityRisk.HIGH),
            create_mock_action_event("action_3", SecurityRisk.MEDIUM),
        ]

        analyzer = self.FixedOutputAnalyzer.from_actions(pending_actions)

        risks = analyzer.analyze_pending_actions(
            current_context=[], pending_actions=pending_actions
        )

        for action in pending_actions:
            risk = analyzer.security_risk(action)
            assert risks[action.id] == risk

    def test_analyzes_all_pending_actions(self) -> None:
        """Test that PerActionSecurityAnalyzer analyzes all pending actions."""
        pending_actions: list[ActionEvent] = [
            create_mock_action_event("action_1", SecurityRisk.LOW),
            create_mock_action_event("action_2", SecurityRisk.HIGH),
            create_mock_action_event("action_3", SecurityRisk.MEDIUM),
        ]

        analyzer = self.FixedOutputAnalyzer.from_actions(pending_actions)

        result = analyzer.analyze_pending_actions(
            current_context=[], pending_actions=pending_actions
        )

        # Check that all actions have their IDs in the result
        assert all(action.id in result for action in pending_actions)

        # Check that all IDs in the result correspond to an action
        assert all(
            event_id in (action.id for action in pending_actions)
            for event_id in result.keys()
        )

    def test_handles_exceptions_with_unknown(self) -> None:
        """Test that PerActionSecurityAnalyzer handles exceptions by returning UNKNOWN
        risk.
        """

        class FailingAnalyzer(PerActionSecurityAnalyzer):
            # Regardless of the action, always raise an exception
            def security_risk(self, action: ActionEvent) -> SecurityRisk:
                raise ValueError("Analysis failed")

        pending_actions: list[ActionEvent] = []

        analyzer = FailingAnalyzer()

        # When analyzed independently, each action should return UNKNOWN risk
        for action in pending_actions:
            risk = analyzer.security_risk(action)
            assert risk == SecurityRisk.UNKNOWN

        # When analyzed in a batch, all actions should also return UNKNOWN risk
        risks = analyzer.analyze_pending_actions(
            current_context=[], pending_actions=pending_actions
        )
        assert all(risk == SecurityRisk.UNKNOWN for risk in risks.values())

    def test_handles_empty_pending_actions_input(self) -> None:
        """Test that PerActionSecurityAnalyzer handles empty pending actions list."""

        analyzer = self.FixedOutputAnalyzer()

        result = analyzer.analyze_pending_actions(
            current_context=[], pending_actions=[]
        )
        assert result == {}

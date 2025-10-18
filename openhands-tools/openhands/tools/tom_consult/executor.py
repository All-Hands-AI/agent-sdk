"""Executor for Tom consultation tool."""

from typing import TYPE_CHECKING, Any

from openhands.sdk.logger import get_logger
from openhands.sdk.tool import StatefulToolExecutor
from openhands.tools.tom_consult.action import ConsultTomAction
from openhands.tools.tom_consult.observation import ConsultTomObservation


if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState

logger = get_logger(__name__)


class TomConsultExecutor(StatefulToolExecutor[ConsultTomAction, ConsultTomObservation]):
    """Executor for consulting Tom agent.

    This executor wraps the tom-swe package to provide Theory of Mind
    capabilities for understanding user intent and preferences.
    """

    def __init__(
        self,
        file_store: Any,
        enable_rag: bool = True,
        llm_model: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
    ):
        """Initialize Tom consultation executor.

        Args:
            file_store: File store for accessing user modeling data
            enable_rag: Whether to enable RAG in Tom agent
            llm_model: LLM model to use for Tom agent
            api_key: API key for Tom agent's LLM
            api_base: Base URL for Tom agent's LLM
        """
        self.file_store = file_store
        self.enable_rag = enable_rag
        self.llm_model = llm_model
        self.api_key = api_key
        self.api_base = api_base
        self._tom_agent = None
        self.user_id = ""

    def _get_tom_agent(self):
        """Lazy initialization of Tom agent."""
        if self._tom_agent is None:
            try:
                from tom_swe.tom_agent import create_tom_agent

                self._tom_agent = create_tom_agent(
                    file_store=self.file_store,
                    enable_rag=self.enable_rag,
                    llm_model=self.llm_model,
                    api_key=self.api_key,
                    api_base=self.api_base,
                    skip_memory_collection=False,
                )
                logger.info("Tom agent initialized successfully")
            except ImportError as e:
                logger.error(f"Failed to import tom-swe: {e}")
                logger.error("Please install tom-swe package: pip install tom-swe")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize Tom agent: {e}")
                raise
        return self._tom_agent

    def __call__(
        self, action: ConsultTomAction, state: "ConversationState | None" = None
    ) -> ConsultTomObservation:
        """Execute Tom consultation.

        Args:
            action: The consultation action with query details
            state: Conversation state for accessing history

        Returns:
            ConsultTomObservation with Tom's suggestions
        """
        try:
            tom_agent = self._get_tom_agent()

            # Build query text using exact format from original implementation
            if action.use_user_message:
                query_text = f"I am SWE agent. {action.reason} I need to consult ToM agent about the user's message: [USER MESSAGE PLACEHOLDER]"  # noqa: E501
            elif action.custom_query:
                query_text = f"I am SWE agent. {action.reason} I need to consult ToM agent: {action.custom_query}"  # noqa: E501
            else:
                logger.warning("⚠️ Tom: No query specified for consultation")
                return ConsultTomObservation(
                    suggestions="[CRITICAL] Tom agent cannot provide consultation for this user message. Do not consult ToM agent again for this message and use other actions instead."  # noqa: E501
                )

            # Get conversation history from state if available
            formatted_messages = []
            if state is not None:
                from openhands.sdk.event import (
                    ActionEvent,
                    LLMConvertibleEvent,
                    ObservationEvent,
                )

                # Get only completed action-observation pairs
                # (exclude pending actions without observations)
                matched_action_ids = {
                    obs_event.action_id
                    for obs_event in state.events
                    if isinstance(obs_event, ObservationEvent)
                }

                llm_convertible_events = [
                    e
                    for e in state.events
                    if isinstance(e, LLMConvertibleEvent)
                    and (not isinstance(e, ActionEvent) or e.id in matched_action_ids)
                ]

                # Convert to messages and format for LLM
                messages = LLMConvertibleEvent.events_to_messages(
                    llm_convertible_events
                )

                # Format messages using the agent's LLM
                # skip system message (first message)
                formatted_messages = state.agent.llm.format_messages_for_llm(messages)[
                    1:
                ]

                # Get last user message for query text
                last_user_message = [
                    m for m in formatted_messages if m["role"] == "user"
                ][-1]
                query_text = query_text.replace(
                    "[USER MESSAGE PLACEHOLDER]",
                    last_user_message["content"][0]["text"],
                )

                logger.info(
                    f"Consulting Tom agent with "
                    f"{len(formatted_messages)} history messages"
                )

            logger.info(f"Consulting Tom agent: {query_text[:100]}...")
            result = tom_agent.give_suggestions(
                user_id=self.user_id,
                query=query_text,
                formatted_messages=formatted_messages,
            )

            if result and hasattr(result, "suggestions"):
                logger.info(
                    "✅ Tom: Requesting observation update with consultation result"
                )

                # Format the response exactly like the original implementation
                query_description = action.custom_query or "the user's message"
                formatted_response = (
                    f"{action.reason}\n"
                    f"I need to consult Tom agent about {query_description}\n\n"
                    "[Starting consultation with Tom agent...]\n"
                    f"{result.suggestions}\n\n"
                    "[Finished consulting with ToM Agent...]"
                )

                return ConsultTomObservation(
                    suggestions=formatted_response,
                    confidence=getattr(result, "confidence", None),
                    reasoning=getattr(result, "reasoning", None),
                )
            else:
                logger.warning("⚠️ Tom: No consultation result received")
                return ConsultTomObservation(
                    suggestions="[CRITICAL] Tom agent cannot provide consultation for this user message. Do not consult ToM agent again for this message and use other actions instead."  # noqa: E501
                )

        except Exception as e:
            logger.error(f"❌ Tom: Error in consultation: {e}")
            return ConsultTomObservation(
                suggestions="[CRITICAL] Tom agent cannot provide consultation for this user message. Do not consult ToM agent again for this message and use other actions instead."  # noqa: E501
            )

import os

from pydantic import field_validator

from openhands.sdk.context.condenser.base import RollingCondenser
from openhands.sdk.context.utils import render_template
from openhands.sdk.context.view import View
from openhands.sdk.event.condenser import Condensation
from openhands.sdk.event.llm_convertible import MessageEvent
from openhands.sdk.llm import LLM, Message, TextContent


class LLMSummarizingCondenser(RollingCondenser):
    llm: LLM
    max_size: int = 120
    keep_first: int = 4

    @field_validator("max_size")
    @classmethod
    def validate_max_size(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_size must be positive")
        return v

    @field_validator("keep_first")
    @classmethod
    def validate_keep_first(cls, v: int) -> int:
        if v < 0:
            raise ValueError("keep_first must be non-negative")
        return v

    @field_validator("keep_first")
    @classmethod
    def validate_keep_first_vs_max_size(cls, v: int, info) -> int:
        if info.data and "max_size" in info.data:
            max_size = info.data["max_size"]
            if v >= max_size // 2:
                raise ValueError(
                    "keep_first must be less than max_size // 2 to leave room for "
                    "condensation"
                )
        return v

    def should_condense(self, view: View) -> bool:
        return len(view) > self.max_size

    def get_condensation(self, view: View) -> Condensation:
        head = view[: self.keep_first]
        target_size = self.max_size // 2
        # Number of events to keep from the tail -- target size, minus however many
        # prefix events from the head, minus one for the summarization event
        events_from_tail = target_size - len(head) - 1

        summary_event_content: str = ""

        summary_event = view.summary_event
        if isinstance(summary_event, MessageEvent):
            message_content = summary_event.llm_message.content[0]
            if isinstance(message_content, TextContent):
                summary_event_content = message_content.text

        # Identify events to be forgotten (those not in head or tail)
        forgotten_events = []
        for event in view[self.keep_first : -events_from_tail]:
            forgotten_events.append(event)

        # Convert events to strings for the template
        event_strings = [str(forgotten_event) for forgotten_event in forgotten_events]

        prompt = render_template(
            os.path.join(os.path.dirname(__file__), "prompts"),
            "summarizing_prompt.j2",
            previous_summary=summary_event_content,
            events=event_strings,
        )

        messages = [Message(role="user", content=[TextContent(text=prompt)])]

        response = self.llm.completion(
            messages=self.llm.format_messages_for_llm(messages),
            # TODO: FIX THIS BAD BOY
            # extra_body={"metadata": self.llm_metadata},
        )
        summary = response.choices[0].message.content  # type: ignore

        return Condensation(
            forgotten_event_ids=[event.id for event in forgotten_events],
            summary=summary,
            summary_offset=self.keep_first,
        )

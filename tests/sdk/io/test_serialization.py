


from pydantic import TypeAdapter
from openhands.sdk.event.base import EventBase
from openhands.sdk.event.llm_convertible import MessageEvent
from openhands.sdk.llm.message import Message, TextContent


def test_message_event_serialization_round_trip():
    """ 
    Test the ability to serialize MessageEvents using a BaseEvent type adapter and
    then deserialize the result
    """
    # Construct a message event
    text_content = TextContent(text="Hello, world!")
    message = Message(role="user", content=[text_content])
    original_message_event = MessageEvent(
        source="user",
        llm_message=message
    )

    #
    dumped_data = original_message_event.model_dump()
    
    type_adapter = TypeAdapter(EventBase)
    dumped_data = type_adapter.dump_python(original_message_event)

    validated_result = EventBase.model_validate(dumped_data)

    assert validated_result == original_message_event

import os
from datetime import datetime

from pydantic import SecretStr

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    Event,
    LLMConvertibleEvent,
    Message,
    Subscription,
    TextContent,
    get_logger,
)
from openhands.sdk.event import MessageEvent
from openhands.tools import BashTool, FileEditorTool, TaskTrackerTool


logger = get_logger(__name__)

# Configure LLM
api_key = os.getenv("LITELLM_API_KEY")
if api_key is None:
    print("⚠️  LITELLM_API_KEY environment variable is not set.")
    print("This example requires an API key to run the full conversation.")
    print("To run this example:")
    print("  export LITELLM_API_KEY=your_api_key_here")
    print("  python examples/11_subscription_example.py")
    print("\nFor now, demonstrating subscription functionality without LLM calls...")

    # Create a mock demonstration

    # Create subscription and demonstrate its functionality
    subscription = Subscription()

    # Demo callbacks
    events_received = []

    def demo_callback_1(event: Event):
        events_received.append(f"Callback 1: {event.__class__.__name__}")

    def demo_callback_2(event: Event):
        events_received.append(f"Callback 2: {event.__class__.__name__}")

    # Subscribe callbacks
    id1 = subscription.subscribe(demo_callback_1)
    id2 = subscription.subscribe(demo_callback_2)

    print(f"\n✅ Subscribed {subscription.callback_count} callbacks")

    # Create a mock event and trigger callbacks
    mock_event = MessageEvent(
        source="user",
        llm_message=Message(
            role="user", content=[TextContent(text="Hello, this is a demo message")]
        ),
    )

    print("📤 Triggering callbacks with mock event...")
    subscription(mock_event)

    print("📥 Events received by callbacks:")
    for event in events_received:
        print(f"  {event}")

    # Demonstrate unsubscribing
    print(f"\n🔄 Unsubscribing callback {id1}")
    subscription.unsubscribe(id1)
    print(f"Active callbacks: {subscription.callback_count}")

    # Clear all
    subscription.clear()
    print(f"Callbacks after clear: {subscription.callback_count}")

    print("\n🎉 Subscription functionality demonstrated successfully!")
    print("Set LITELLM_API_KEY to see the full conversation example.")
    exit(0)

llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

# Tools
cwd = os.getcwd()
tools = [
    BashTool.create(working_dir=cwd),
    FileEditorTool.create(),
    TaskTrackerTool.create(save_dir=cwd),
]

# Agent
agent = Agent(llm=llm, tools=tools)

# Create a subscription manager to handle multiple callbacks
subscription = Subscription()

# Callback 1: Collect LLM messages
llm_messages = []


def llm_message_collector(event: Event):
    """Collect LLM convertible events for later analysis."""
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())


# Callback 2: Event logger with timestamps
event_log = []


def event_logger(event: Event):
    """Log all events with timestamps."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    event_log.append(f"[{timestamp}] {event.__class__.__name__}: {str(event)[:100]}")
    logger.info(f"Event logged: {event.__class__.__name__}")


# Callback 3: Action counter
action_counts = {}


def action_counter(event: Event):
    """Count different types of actions."""
    event_type = event.__class__.__name__
    action_counts[event_type] = action_counts.get(event_type, 0) + 1


# Callback 4: Error detector
errors_detected = []


def error_detector(event: Event):
    """Detect and log any error-related events."""
    event_str = str(event).lower()
    if any(keyword in event_str for keyword in ["error", "failed", "exception"]):
        errors_detected.append(
            f"Potential error in {event.__class__.__name__}: {event}"
        )
        logger.warning(f"Error detected: {event}")


# Subscribe all callbacks to the subscription manager
llm_callback_id = subscription.subscribe(llm_message_collector)
logger_callback_id = subscription.subscribe(event_logger)
counter_callback_id = subscription.subscribe(action_counter)
error_callback_id = subscription.subscribe(error_detector)

print(f"Subscribed {subscription.callback_count} callbacks")
print(
    f"Callback IDs: {llm_callback_id}, {logger_callback_id}, "
    f"{counter_callback_id}, {error_callback_id}"
)

# Create conversation with the subscription as the callback
conversation = Conversation(agent=agent, callbacks=[subscription])

print("\n" + "=" * 80)
print("Starting conversation with subscription-managed callbacks...")
print("=" * 80)

# First interaction
conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text=(
                    "Hello! Can you create a Python file named 'subscription_demo.py' "
                    "that demonstrates a simple subscription pattern? "
                    "Use task tracker to plan your steps."
                )
            )
        ],
    )
)
conversation.run()

print("\n" + "-" * 40)
print("Midway status check:")
print(f"Events logged: {len(event_log)}")
print(f"Action counts: {action_counts}")
print(f"Errors detected: {len(errors_detected)}")
print("-" * 40)

# Second interaction - demonstrate unsubscribing a callback
print(f"\nUnsubscribing error detector callback (ID: {error_callback_id})")
unsubscribed = subscription.unsubscribe(error_callback_id)
print(f"Unsubscription successful: {unsubscribed}")
print(f"Active callbacks: {subscription.callback_count}")

conversation.send_message(
    message=Message(
        role="user",
        content=[
            TextContent(
                text="Great! Now run the file to make sure it works, then delete it."
            )
        ],
    )
)
conversation.run()

# Final results
print("\n" + "=" * 80)
print("SUBSCRIPTION EXAMPLE RESULTS")
print("=" * 80)

print("\n📊 STATISTICS:")
print(f"  • Total callbacks managed: {subscription.callback_count}")
print(f"  • LLM messages collected: {len(llm_messages)}")
print(f"  • Events logged: {len(event_log)}")
print(f"  • Errors detected: {len(errors_detected)}")

print("\n📈 ACTION COUNTS:")
for action_type, count in sorted(action_counts.items()):
    print(f"  • {action_type}: {count}")

print("\n📝 RECENT EVENT LOG (last 5):")
for log_entry in event_log[-5:]:
    print(f"  {log_entry}")

print("\n🔍 LLM MESSAGES (first 3):")
for i, message in enumerate(llm_messages[:3]):
    print(f"  Message {i + 1}: {str(message)[:150]}...")

if errors_detected:
    print("\n⚠️  ERRORS DETECTED:")
    for error in errors_detected:
        print(f"  {error}")
else:
    print("\n✅ No errors detected during execution")

print("\n🧹 CLEANUP:")
print("Clearing all subscriptions...")
subscription.clear()
print(f"Active callbacks after clear: {subscription.callback_count}")

print("\n" + "=" * 80)
print("Subscription example completed successfully!")
print("This example demonstrated:")
print("  • Creating multiple specialized callbacks")
print("  • Managing callbacks with the Subscription class")
print("  • Subscribing and unsubscribing callbacks dynamically")
print("  • Using subscription as a conversation callback")
print("  • Collecting different types of event data")
print("=" * 80)

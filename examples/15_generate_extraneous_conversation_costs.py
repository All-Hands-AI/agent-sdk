import os

from pydantic import SecretStr
from tabulate import tabulate

from openhands.sdk import (
    LLM,
    Agent,
    Conversation,
    Message,
    TextContent,
    get_logger,
)
from openhands.tools import (
    BashTool,
)


logger = get_logger(__name__)

# Configure LLM using LLMRegistry
api_key = os.getenv("LITELLM_API_KEY")
assert api_key is not None, "LITELLM_API_KEY environment variable is not set."

# Create LLM instance
llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)

# Tools
cwd = os.getcwd()
tools = [BashTool.create(working_dir=cwd)]

# Agent
agent = Agent(llm=llm, tools=tools)

conversation = Conversation(agent=agent)
conversation.send_message(
    message=Message(
        role="user",
        content=[TextContent(text="Please echo 'Hello!'")],
    )
)
conversation.run()


# Demonstrate extraneous costs part of the conversation
second_llm = LLM(
    model="litellm_proxy/anthropic/claude-sonnet-4-20250514",
    base_url="https://llm-proxy.eval.all-hands.dev",
    api_key=SecretStr(api_key),
)
conversation.llm_registry.add("extraneous service", second_llm)
completion_response = second_llm.completion(
    messages=[Message(role="user", content=[TextContent(text="echo 'More spend!'")])]
)

# Access total spend
spend = conversation.conversation_stats.get_combined_metrics()
print("\n=== Total Spend for Conversation ===\n")
print(f"Accumulated Cost: ${spend.accumulated_cost:.6f}")
if spend.accumulated_token_usage:
    print(f"Prompt Tokens: {spend.accumulated_token_usage.prompt_tokens}")
    print(f"Completion Tokens: {spend.accumulated_token_usage.completion_tokens}")
    print(f"Cache Read Tokens: {spend.accumulated_token_usage.cache_read_tokens}")
    print(f"Cache Write Tokens: {spend.accumulated_token_usage.cache_write_tokens}")


spend_per_service = conversation.conversation_stats.service_to_metrics
print("\n=== Spend Breakdown by Service ===\n")
rows = []
for service, metrics in spend_per_service.items():
    rows.append(
        [
            service,
            f"${metrics.accumulated_cost:.6f}",
            metrics.accumulated_token_usage.prompt_tokens
            if metrics.accumulated_token_usage
            else 0,
            metrics.accumulated_token_usage.completion_tokens
            if metrics.accumulated_token_usage
            else 0,
        ]
    )

print(
    tabulate(
        rows,
        headers=["Service", "Cost", "Prompt Tokens", "Completion Tokens"],
        tablefmt="github",
    )
)

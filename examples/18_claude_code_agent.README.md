# ClaudeCodeAgent Example & Event Mapping Notes

This document accompanies `examples/18_claude_code_agent.py` and explains how to run the example and how Claude Code SDK events could be mapped to OpenHands internal events.

## What this example does

- Demonstrates how to use `ClaudeCodeAgent`, an alternate Agent implementation that uses the Anthropics Claude Code Python SDK under the hood
- Works with the existing `Conversation` API, so your app code doesn’t change
- Treats Claude Code as a self-contained assistant. Tool runs (Bash, Read/Write) are handled by Claude Code itself; we record the assistant’s response as a `MessageEvent` today

## Requirements

- Python environment configured for this repo (`make build`)
- Claude Code SDK dependency is installed by the SDK package
- Claude Code runtime requirements (for real runs):
  - Node.js
  - `npm install -g @anthropic-ai/claude-code`
- Environment variable:
  - `ANTHROPIC_API_KEY` must be set

For CI/tests, we stub the SDK, so Node/CLI is not required.

## How to run the example

```bash
# 1) Ensure dependencies are installed
make build

# 2) Ensure you have the CLI if you want real runs (optional for tests)
npm install -g @anthropic-ai/claude-code

# 3) Set your Anthropic key
export ANTHROPIC_API_KEY=sk-ant-...

# 4) Run the example
uv run python examples/18_claude_code_agent.py
```

You should see an assistant response printed at the end.

## How ClaudeCodeAgent works

- `init_state` emits a `SystemPromptEvent` once, mirroring our default agent behavior
- Each `step`:
  1. Locates the latest user message
  2. Calls `claude_code_sdk.query(...)`
  3. Concatenates assistant text from the response and emits a `MessageEvent`
  4. Marks the turn as `FINISHED`

- Optional heuristic mapping of OpenHands tool names to Claude Code tools is supported via `allowed_tools` (e.g., enabling `Bash`, `Read`, `Write` when known tools are present)

## Event Mapping: Claude Code SDK → OpenHands

Claude Code SDK types (see `claude_code_sdk/types.py`):
- Message union:
  - `UserMessage { content, parent_tool_use_id? }`
  - `AssistantMessage { content: ContentBlock[], model, parent_tool_use_id? }`
  - `SystemMessage { subtype, data }`
  - `ResultMessage { subtype, duration_ms, usage, total_cost_usd, ... }`
  - `StreamEvent { uuid, session_id, event }`
- ContentBlock union:
  - `TextBlock { text }`
  - `ThinkingBlock { thinking, signature }`
  - `ToolUseBlock { id, name, input }`
  - `ToolResultBlock { tool_use_id, content?, is_error? }`

OpenHands internal, LLM-convertible event types (see `openhands/sdk/event/llm_convertible.py`):
- `SystemPromptEvent` (→ `Message(role="system")`)
- `MessageEvent` (→ `Message(role="user"|"assistant")`)
- `ActionEvent` (represents a tool call, with optional `reasoning_content` and preceding "thought")
- `ObservationEvent` (tool result, delivered back to the LLM)

### Proposed one-to-one mapping

The most faithful mapping would reconstruct the sequence of assistant blocks into one or more OpenHands events. This can be done without using OpenHands’ tool executors (Claude Code already executes tools); the mapping is for observability and compatibility.

- Claude `UserMessage`
  - Map to `MessageEvent(source='user')` with `Message(role='user', content=...)`
  - `parent_tool_use_id` has no direct field in OpenHands events; could be carried in an extension field if needed

- Claude `AssistantMessage` (sequence of content blocks)
  - Preceding `ThinkingBlock` → Attach as `reasoning_content` to the first resulting `ActionEvent`, or emit as `MessageEvent` with `reasoning_content`
  - Preceding `TextBlock`s (assistant thought/explanation) → Map to `ActionEvent.thought` (TextContent list) for the first tool call in the response. If the assistant message contains no tools, emit a single `MessageEvent(source='agent')` with the concatenated text
  - Each `ToolUseBlock` → Emit an `ActionEvent`.
    - `tool_name` = `name`
    - `tool_call_id` = `id`
    - `action` = a generic Action schema capturing the raw `input` (see “Generic Action/Observation” below)
    - Multiple tool uses in one assistant turn → multiple `ActionEvent`s sharing the same `llm_response_id` (our code supports this grouping)

- Claude `ToolResultBlock`
  - Map to `ObservationEvent` where:
    - `tool_call_id` = `tool_use_id`
    - `tool_name` = the earlier `ToolUseBlock.name` (pass through)
    - `observation` = a generic Observation schema that can hold either text or structured content

- Claude `SystemMessage`
  - Map to `SystemPromptEvent` (retain `data` via an extension field if desired)

- Claude `ResultMessage`
  - Contains cost/usage/duration. OpenHands has `metrics` fields on some events. We can:
    - Convert usage into our `MetricsSnapshot` (best-effort) and attach to the last `ActionEvent` of the batch or the final `MessageEvent`
    - If the schema doesn’t align, include as a separate non-LLM event or attach to `MessageEvent.metrics` with partial fields

- Claude `StreamEvent`
  - OpenHands doesn’t currently expose partial-delta stream events as first-class events. We can buffer partials and only emit final events, or add a new optional streaming event type if needed

### Generic Action/Observation

OpenHands `ActionEvent.action` expects a concrete `ActionBase` subclass. Claude Code’s tools have different inputs, not known at compile time. Two approaches:

1) Generic schema types
   - Create `ExternalToolAction(ActionBase)` with fields: `tool: str`, `args: dict[str, Any]`
   - Create `ExternalToolObservation(ObservationBase)` with fields: `tool: str`, `result: str | list[dict[str, Any]] | None`, `is_error: bool | None`
   - This lets us faithfully encode ToolUse/ToolResult without coupling to OpenHands tool registry

2) Dynamic models via MCP schema util
   - Use `Schema.from_mcp_schema(...)` or `MCPActionBase` to produce per-tool action models dynamically when we have (or synthesize) a JSON schema. This preserves nicer field shapes but is more involved since Claude Code doesn’t ship JSON schemas for each tool

Recommendation: Start with (1) for simplicity and completeness. We can always upgrade to (2) if structured schemas become available.

### Status and trade-offs

- Today’s adapter emits a single `MessageEvent` per turn for simplicity and stability
- A full one-to-one mapping is feasible with the generic action/observation approach above
- It will improve trace fidelity and visualization but will not route execution through OpenHands tools (Claude Code already executed them)
- If desired, we could later add a “proxy mode” where Claude Code only plans and OpenHands tools execute. That would require re-wiring execution and is out of scope for this initial integration

## Example snippet

```python
from openhands.sdk.agent import ClaudeCodeAgent
from openhands.sdk.llm import LLM
from openhands.sdk import Conversation, Message, TextContent

agent = ClaudeCodeAgent(llm=LLM(model="claude-code"), tools=[], allowed_tools=["Bash", "Read", "Write"])  # type: ignore[call-arg]
conv = Conversation(agent)

conv.send_message(Message(role="user", content=[TextContent(text="Say hello.")]))
conv.run()
```

## Troubleshooting
- Ensure `ANTHROPIC_API_KEY` is set
- For real runs (not tests), install the Claude Code CLI: `npm install -g @anthropic-ai/claude-code`
- If you see transport/runtime errors, verify Node/CLI and permissions

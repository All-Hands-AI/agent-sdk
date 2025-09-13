GOAL: We Implement Native Responses API integration (v1, non-streaming)

Objective
- Integrate OpenAI/LiteLLM native Responses API for GPT-5 and GPT-5-mini to enable stateful conversations via previous_response_id.
- Keep Chat Completions path intact for all other models.
- Preserve Responses fidelity by using litellm.responses with typed params/returns; avoid the generic bridge that drops state.

Non-goals
- No new storage layers.
- No streaming in v1.
- Agent is minimally aware of Responses and will call llm.responses() on supported models; Chat Completions path remains for other models.

Scope (MVP)
- Non-streaming Responses only.
- Text outputs and function tool-calls.
- Persist and reuse previous_response_id for continuity.

Agreed decisions
- Gating: strictly by model. Enable only for GPT-5 and GPT-5-mini.
- Stateful flag: ConversationState.previous_response_id (None for first turn). Presence indicates a Responses conversation.
- Model switch: if previous_response_id is set and new model doesn’t support Responses, raise a strict error (TODO: relax later).
- Defaults on Responses calls: store=True, parallel_tool_calls=True.
- History: do not send prior messages; send only new input items plus previous_response_id.

Gating and mode detection
- Add supports_responses: bool to model_features with patterns ["gpt-5*", "gpt-5-mini*"].
- is_responses on a given turn = supports_responses(model) or (state.previous_response_id is not None). Agent decides the path and calls llm.responses() directly when true.

Tools
- Add Tool.to_responses_tool() that emits the Responses function tool schema (typed FunctionToolParam) matching our MCP-derived input_schema/description.
- Agent selects tool serialization per turn:
  - Responses path: [t.to_responses_tool() for t in tools].
  - Chat path: [t.to_openai_tool()].

Transport and inputs (Responses)
- Agent calls llm.responses(...) directly when in Responses mode. LLM.responses returns the typed OpenAI Response object; we do not adapt it to ModelResponse.
- LLM exposes a responses(...) method that wraps litellm.responses with typed args; it does not alter the returned type.
  - previous_response_id=state.previous_response_id (if any), store=True, parallel_tool_calls=True.
- Input construction for Responses calls (non-streaming):
  - First turn: map the first system message to instructions; map the latest user content to a Responses message input item.
  - Tool results: send as function_call_output items with call_id equal to the tool call id from the prior turn.
  - We do not replay history; continuity is carried by previous_response_id.

Agent integration
- Agent decides per turn which path to use. If is_responses is true, it calls llm.responses(...) directly and receives a typed OpenAI Response.
- When preparing the first event (system prompt), emit tools using to_responses_tool() if is_responses is true; otherwise to_openai_tool().
- Pass previous_response_id to llm.responses via kwargs.
- After each Responses call completes, set state.previous_response_id = response.id.
- Multiple tool calls in one assistant turn are already handled by Agent.step: parse Response.output for function tool calls and execute them; with parallel_tool_calls enabled this continues to work.

LLM integration
- Provide LLM.responses(...) which calls litellm.responses with typed args and returns the typed OpenAI Response unchanged.
- Keep LLM.completion(...) for non-Responses models; agent will not use completion for Responses path.
- Telemetry should still record raw typed Response for completeness.

Persistence and state
- ConversationState: add previous_response_id: str | None. This is the durable flag for Responses mode and the handle for continuation.
- Event log: continue existing events; include response.id and previous_response_id in the Telemetry logs. No new persistence structure is added.

Telemetry/Metrics
- Map Responses.usage input/output/total tokens into Metrics. If missing, use our existing token_counter fallback.
- Record response.id, previous_response_id, model, created_at, status in Telemetry (when logging enabled).

Error handling
- If previous_response_id exists but model does not supports_responses, raise a clear error (strict for v1; TODO relax later).
- If provider rejects continuation due to an invalid/expired id, clear state.previous_response_id and optionally retry once fresh (policy behind a small guard).

Tests
- Gating: GPT-5/mini routes to Responses; others route to Chat.
- Statefulness: two-call sequence with previous_response_id propagation (no history replay).
- Tool-calls: multiple function calls in one turn handled sequentially; tool result round-trip by sending function_call_output input items.
- Reasoning: reasoning content captured/persisted on events.
- Metrics: usage mapping parity with existing counters.
- Model switch error: strict error when previous_response_id set and model lacks Responses support.

Example (manual)
- Minimal example showing:
  - First call with GPT-5: system as instructions + user input; receive id and tool calls; persist state.previous_response_id.
  - Next call: send only function_call_output items + previous_response_id; receive assistant message.

Follow-ups (post-v1)
- Streaming Responses and streaming event model mapping.
- Optional richer exposure of Responses output items on events.
- Policy for relaxing strict model-switch behavior.
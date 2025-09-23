# PRD: Agent-level routing for Chat Completions vs Responses API, with native return types (no output conversion)

Author: Engel Nyst
Date: 2025-09-19
Status: Draft for review

1) Objective and scope
- Goal: Implement the design suggested by Xingyao: the Agent decides whether to call LLM.completion() (Chat Completions) or LLM.responses() (Responses API) per model support, and handles responses in Agent code, producing the same downstream Events/Actions regardless of path.
- Explicitly drop the LLM-side output conversion (i.e., stop converting Responses API outputs into Chat Completions format inside LLM). Keep input formatting and tool conversion centralized in LLM.
- Keep backward compatibility for downstream consumers by ensuring the Agent normalizes both response shapes into our internal Event/Action domain model.
- Maintain parity for features we currently support: tool calling, images, reasoning, telemetry, and security/risk injection.

Out of scope for this PRD
- Streaming (both paths remain non-streaming here).
- Non-OpenAI providers for Responses API (we’ll route Responses only for verified OpenAI reasoning-capable models for now).

2) High-level design
- Agent.step() dispatches to one of two private methods based on llm.supports_responses_api():
  - _call_chat(): uses LLM.completion() and parses litellm.types.utils.ModelResponse.
  - _call_responses(): uses LLM.responses() and parses litellm.types.llms.openai.ResponsesAPIResponse.
- Both private methods return the same normalized outcome to Agent: a sequence of ActionEvent (zero or more) plus MessageEvent if no actions.
- LLM responsibilities:
  - completion(): standard Chat Completions path (already on main), with centralized tool conversion (ToolBase -> ChatCompletionToolParam) and optional security risk schema injection.
  - responses(): standard Responses path that accepts typed input (string or typed items) and returns litellm’s typed ResponsesAPIResponse. LLM still centralizes tool conversion (ToolBase -> responses tool schema) and parameter normalization (e.g., nested reasoning.effort, store flag).

3) Routing rules (Agent)
- Call Responses API only when:
  - llm.supports_responses_api() is True (derives from model_features.get_features).
- Otherwise call completion().

4) Typed API surface
4.1 LLM (public)
- completion(self,
             messages: list[Message],
             tools: Sequence[ToolBase] | None = None,
             *,
             add_security_risk_prediction: bool = False,
             **kwargs) -> ModelResponse
  - Returns: litellm.types.utils.ModelResponse (Chat Completions typed response)
  - Tools: converted to ChatCompletionToolParam internally; only passed to provider when native tool calling is active.

- responses(self,
            input: str | list[dict[str, Any]] | None = None,
            *,
            messages: list[Message] | None = None,
            tools: Sequence[ToolBase] | None = None,
            add_security_risk_prediction: bool = False,
            **kwargs) -> ResponsesAPIResponse
  - Returns: litellm.types.llms.openai.ResponsesAPIResponse
  - Input precedence:
    1) If input is given (string or typed list of items), use it directly.
    2) Else if messages provided, LLM formats them into Responses input items (images included).
  - Tools: converted to Responses tool dicts internally; included in the call.

- supports_responses_api(self) -> bool
  - Delegates to get_features(self.model).supports_responses_api.

Note on typing for Responses input items: We will prefer using litellm/openai typed classes where available. For images, we will use the native Responses input shape (type="input_image").

4.2 Agent (public/behavioral)
- Agent.step(): unchanged signature. Internally chooses _call_chat or _call_responses.

4.3 Agent (private helpers)
- _call_chat(self, messages: list[Message], tools: Sequence[ToolBase]) -> tuple[list[ActionEvent], Message | None, MetricsSnapshot | None]
  - Calls llm.completion(...), reads response.choices[0].message, normalizes tool_calls into ActionEvent(s), and returns actions (or a Message result if no actions).

- _call_responses(self, messages: list[Message] | None, tools: Sequence[ToolBase]) -> tuple[list[ActionEvent], Message | None, MetricsSnapshot | None]
  - Calls llm.responses(...). Parses ResponsesAPIResponse.output to extract:
    - assistant message text
    - function_call items into tool_calls
    - reasoning content (see Section 6)
  - Normalizes tool_calls into ActionEvent(s) exactly like _call_chat, including batch semantics (reasoning and “Thought” ordering remain consistent: reasoning displayed before Thought for the first action).

Both helpers:
- Emit metrics snapshot and telemetry identical to today.
- Respect confirmation mode and batching rules.

5) Parameter normalization & invariants
- LLM.completion:
  - Keeps existing normalization on main (max_completion_tokens, temperature, top_p; Azure mapping; provider quirks).
  - If model supports reasoning effort but is on Chat path, top-level reasoning_effort may be kept when appropriate per provider rules (OpenAI Chat Completions for non-o-series).

- LLM.responses:
  - Reasoning param: use nested object per OpenAI spec: {"reasoning": {"effort": <low|medium|high>, "summary": "detailed"}}
  - Do not include top-level reasoning_effort in Responses calls.
  - Store: set default store=True unless overridden by caller; allow store=False when needed (see Section 7).
  - Remove stop in Responses calls (unsupported); tools are allowed and passed.

6) Reasoning, images, and tool calls (Responses path)
- Reasoning (response):
  - ResponsesAPIResponse.output contains items of various types:
    - ResponseOutputMessage (type=="message"): content segments, including ResponseOutputText.
    - ResponseFunctionToolCall (type=="function_call"): name, arguments, call_id.
    - ResponseReasoningItem (type=="reasoning"): may include content[] and/or summary[]; may be redacted per policy.
  - Agent will extract:
    - assistant text content -> Message.content
    - tool_calls -> tool call list (same shape we consume today for Actions)
    - reasoning text/summary -> Message.reasoning_content (see Section 8)
- Images (request):
  - Supported by Responses via type=="input_image" entries. LLM will format internal Message content into the Responses item list preserving images.
- Images (response):
  - The UI already supports image outputs; surface image outputs from Responses the same way as in the Chat path. We still don’t derive Actions from images, but they should be displayed in the UI.

7) Store/metadata and stateful vs stateless
- By default, set store=True on Responses path (no override option for now).
- Telemetry will record raw Responses payloads when enabled (log_completions=True).
- Future: Optional stateful mode. When enabled in the future, Agent should persist the last Responses response_id in conversation state and pass previous_response_id on subsequent responses() calls. This must be persisted with other conversation state so reloading a conversation restores the previous_response_id chain.

8) Event model changes for reasoning
- Reuse existing Message.reasoning_content: str | None. Concatenate Responses “reasoning” segments and any summary segments into a single string for display before Thought.
- Metrics: reasoning_tokens are already displayed via usage mapping (no model change needed).
- For multiple tool calls in one assistant turn: keep current behavior — only the first action displays reasoning content and Thought; subsequent actions omit both.

9) Tools
- Tool APIs: The Tool class today provides to_openai_tool() for Chat Completions. We will add a symmetric to_responses_tool() for Responses API tools. This keeps Agent code provider-agnostic and preserves conversion knowledge even if we skip merging the current converter code and implement this PRD directly.

- Keep tool conversion centralized in LLM for both paths:
  - Chat: ToolBase -> ChatCompletionToolParam
  - Responses: ToolBase -> responses tool dict

10) Telemetry and metrics
- LLM collects request/response telemetry for both paths.
- Agent maintains cost and token metrics using:
  - Chat: ModelResponse.usage
  - Responses: ResponsesAPIResponse.usage (input_tokens, output_tokens, total_tokens; reasoning_tokens under output_tokens_details if present).

11) Type references (litellm / openai)
- Chat path return type: litellm.types.utils.ModelResponse
- Responses path return type: litellm.types.llms.openai.ResponsesAPIResponse
- Responses output items (examples in litellm):
  - ResponseOutputMessage (type=="message") with content: list[ResponseOutputText | ResponseOutputRefusal | ...]
  - ResponseFunctionToolCall (type=="function_call")
  - ResponseReasoningItem (type=="reasoning"), with content[] and/or summary[]

12) Signatures (proposed)
- class LLM:

  def supports_responses_api(self) -> bool: ...

  def completion(
      self,
      messages: list[Message],
      tools: Sequence[ToolBase] | None = None,
      *,
      add_security_risk_prediction: bool = False,
      **kwargs,
  ) -> ModelResponse: ...

  def responses(
      self,
      input: str | list[dict[str, Any]] | None = None,
      *,
      messages: list[Message] | None = None,
      tools: Sequence[ToolBase] | None = None,
      add_security_risk_prediction: bool = False,
      **kwargs,
  ) -> ResponsesAPIResponse: ...

- class Agent:

  def _call_chat(
      self,
      messages: list[Message],
      tools: Sequence[ToolBase],
      *,
      add_security_risk_prediction: bool,
  ) -> tuple[list[ActionEvent], Message | None, MetricsSnapshot | None]: ...

  def _call_responses(
      self,
      messages: list[Message] | None,
      tools: Sequence[ToolBase],
      *,
      add_security_risk_prediction: bool,
  ) -> tuple[list[ActionEvent], Message | None, MetricsSnapshot | None]: ...

13) Plan
- Step 1: Agent.step() calls _call_chat or _call_responses.
- Step 2: Implement _call_responses to parse ResponsesAPIResponse and produce the same ActionEvent(s) + MessageEvent semantics as _call_chat today.
- Step 3: Update tests:
  - Unit tests for _call_responses parsing (reasoning, tool calls, usage tokens).
  - End-to-end tests to verify: reasoning appears before Thought; tools invoke correctly; no top-level reasoning_effort in Responses path; store default honored.


15) References
- OpenAI Responses API: https://platform.openai.com/docs/api-reference/responses/create
- litellm Responses types: litellm.types.llms.openai.ResponsesAPIResponse and related output item classes
- Current main behavior for tool conversion: PR #371 (centralized in LLM)

Appendix A: Implementation notes (typed references)
- Responses result (return type): litellm.types.llms.openai.ResponsesAPIResponse
  - Key fields: id, created_at, model, output, usage, store, previous_response_id, reasoning
- Output items (iterate ResponsesAPIResponse.output):
  - openai.types.responses.response_output_message.ResponseOutputMessage
    - content: list[ResponseOutputText | ResponseOutputRefusal | ...]
  - openai.types.responses.response_output_text.ResponseOutputText
    - text: str
  - openai.types.responses.response_output_refusal.ResponseOutputRefusal
  - openai.types.responses.response_function_tool_call.ResponseFunctionToolCall
    - name: str, arguments: str, call_id/id: str | None
  - openai.types.responses.response_reasoning_item.ResponseReasoningItem
    - content: list[...segments with .text]
    - summary: list[...segments with .text]
    - encrypted_content: str | None (present when reasoning is encrypted/redacted)
- Usage mapping:
  - usage.input_tokens -> prompt_tokens
  - usage.output_tokens -> completion_tokens
  - usage.total_tokens -> total_tokens
  - usage.output_tokens_details.reasoning_tokens -> completion_tokens_details.reasoning_tokens (if present)
- Tools:
  - Chat path: Tool.to_openai_tool() -> ChatCompletionToolParam
  - Responses path: Tool.to_responses_tool() -> dict per Responses spec (support add_security_risk_prediction)

End of document.
# LLM Interface Refinement: Completing the Abstraction Layer

## 1. Introduction

### 1.1 Problem Statement

The OpenHands SDK has made excellent progress in abstracting LiteLLM
implementation details through well-designed abstraction layers. However, there
remain **two critical interface boundaries** where LiteLLM types leak through to
agent code, requiring manual type conversions and exposing implementation
details.

While we do not anticipate moving away from LiteLLM, limiting the exposure of
LiteLLM types to the rest of the SDK will allow us to create alternate language
implementations of the SDK which remain fundamentally similar to the Python SDK
despite differences in supporting LLM libraries.

### 1.2 Proposed Solution

By completing the abstraction layer at the two remaining interface boundaries --
**the primary completion interface** and **the tool interface boundary** -- we
can reduce the number of files which make direct imports of LiteLLM types from
agent and tool code while keeping the code clean and simple. This approach
builds on the existing excellent abstraction work already done in the Telemetry,
Metrics, RetryMixin, and Message conversion systems, and unlocks the possibility
of having alternative language SDKs that stay very similar to the Python
original.

## 2. Additional Context

### 2.1 Current Architecture is Decoupled (Mostly)

The existing codebase demonstrates strong architectural patterns with excellent
abstraction layers already in place:

#### ✅ Telemetry System - Complete Abstraction

- **Input**: OpenHands `Message` objects via `format_messages_for_llm()`
- **Output**: OpenHands `Metrics` object from `on_response()`
- **Internal LiteLLM usage**: Properly encapsulated, no type leakage
- **Functionality**: Cost calculation, token tracking, latency measurement,
  logging

#### ✅ Metrics & Token Usage - Pure OpenHands Types

- **Classes**: `TokenUsage`, `Cost`, `ResponseLatency`, `MetricsSnapshot`
- **Advanced features**: Cache tokens, reasoning tokens, addition operators,
  deep copy, diff operations
- **No LiteLLM exposure**: These are completely abstracted OpenHands types
- **Pattern**: Demonstrates the target architecture for other components

#### ✅ Retry Mechanism - Clean Abstraction Layer

- **RetryMixin**: Exponential backoff, temperature adjustment, retry listeners
- **Error handling**: Uses OpenHands-specific `LLMNoResponseError`
- **No LiteLLM dependencies**: Works with generic callables and exceptions
- **Pattern**: Shows how to abstract LiteLLM functionality without type leakage

#### ✅ Message Conversion - Bidirectional Abstraction

- **Inbound**: `Message.from_litellm_message()` for LiteLLM → OpenHands
  conversion
- **Outbound**: `Message.to_llm_dict()` for OpenHands → LiteLLM conversion
- **Proper boundary**: Establishes clear abstraction layer between type systems
- **Pattern**: Template for how other conversions should work

### 2.2 Gap 1: Primary Completion Interface

Despite the excellent abstraction work, the primary completion interface still
exposes LiteLLM types:

```python
# Current: Agent must handle LiteLLM types
response = self.llm.completion(messages=_messages, tools=tools)  # Returns ModelResponse
llm_message: LiteLLMMessage = response.choices[0].message
message = Message.from_litellm_message(llm_message)  # Manual conversion required
```

**Issues:**

- The `LLM.completion()` method returns `ModelResponse` (LiteLLM type)
- Agents must import LiteLLM types (`ModelResponse`, `Choices`,
  `LiteLLMMessage`)
- Manual type assertions and conversions required in agent code
- Inconsistent with the abstraction patterns established elsewhere

### 2.3 Gap 2: Tool Interface Boundary

The tool interface uses LiteLLM types instead of following the OpenHands
abstraction pattern:

```python
# Current: Tools converted to LiteLLM format
tools = [tool.to_openai_tool() for tool in self.tools.values()]  # Returns ChatCompletionToolParam[]
response = self.llm.completion(messages=_messages, tools=tools)
```

**Issues:**

- Tool interface uses `ChatCompletionToolParam` instead of OpenHands types
- Creates LiteLLM type dependency in tool conversion
- Inconsistent with the OpenHands type system established in other components
- Potential coupling to OpenAI-specific tool format

## 3. Expected Outcome

- Reduction of files with LiteLLM imports from 12 to 8
- Consume Code Entirely Free of LiteLLM Types
- Public SDK APIs Return Only OpenHands Types

### 2.1 Files with LiteLLM Dependencies

**Current state**: 12 files with LiteLLM imports

**Consumer Code (Target for cleanup):**

1. `openhands/sdk/agent/agent.py` - Agent message conversion
2. `openhands/sdk/event/llm_convertible.py` - Event conversion  
3. `openhands/sdk/mcp/tool.py` - MCP tool integration
4. `openhands/sdk/utils/json.py` - JSON utilities

**Implementation Layer (Appropriate LiteLLM usage):**

1. `openhands/sdk/llm/llm.py` - Main LLM class
2. `openhands/sdk/llm/message.py` - Message handling
3. `openhands/sdk/llm/utils/telemetry.py` - Cost calculation and metrics
4. `openhands/sdk/tool/tool.py` - Tool parameter types
5. `openhands/sdk/llm/mixins/non_native_fc.py` - Function calling mixin
6. `openhands/sdk/llm/mixins/fn_call_converter.py` - Function call converter
7. `openhands/sdk/llm/utils/unverified_models.py` - Model utilities
8. `openhands/sdk/logger.py` - Logging configuration

### 2.2 Target State After Interface Completion

**Target state**: 8 files with LiteLLM imports

**Consumer Code (LiteLLM-free):**

- `openhands/sdk/agent/agent.py` ✅ - Uses `CompletionResult` instead of
  `ModelResponse`
- `openhands/sdk/event/llm_convertible.py` ✅ - Uses `OpenHandsToolSpec` instead
  of `ChatCompletionToolParam`
- `openhands/sdk/mcp/tool.py` ✅ - Uses `OpenHandsToolSpec` instead of
  `ChatCompletionToolParam`
- `openhands/sdk/utils/json.py` ✅ - Uses `CompletionResult` instead of
  `ModelResponse`

**Implementation Layer (Retains appropriate LiteLLM usage):**

- All 8 implementation files keep their LiteLLM imports for internal
  functionality

**Reduction**: 12 → 8 files (**33% reduction in LiteLLM touchpoints**)

## 4. Solution Technical Design

### 3.1 Core Design Principles

**Build on Existing Strengths**: Leverage the excellent abstraction work already
done in Telemetry, Metrics, RetryMixin, and Message conversion systems.

**Encapsulation Boundary**: Complete the abstraction so that agent and tool code
only works with OpenHands native types and primitives, while LiteLLM remains
completely encapsulated within the LLM layer.

**Type Clarity Preserved**: Do not achieve this encapsulation goal at the cost
of weaker type safety. Preserve expressiveness with new OpenHands types where
needed.

These principles ensure:

- **Clean separation**: LiteLLM dependencies are isolated to the LLM layer
- **Type safety**: All public APIs use strongly-typed OpenHands native types
- **Maintainability**: Changes to LiteLLM integration don't ripple through the
  codebase
- **Testability**: Agent and tool code can be tested without LiteLLM
  dependencies
- **Portability**: Most of the SDK API will look similar in alternative language
  implementations

### 3.2 Architecture Overview

The proposed architecture completes the abstraction layer by addressing the two
remaining interface boundaries:

```plaintext
┌────────────────────────────────────────────────────────────-─┐
│                    OpenHands SDK Codebase                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │   Agent     │  │   Tools     │  │      Events         │   │
│  │             │  │             │  │                     │   │
│  └─────────────┘  └─────────────┘  └─────────────────────┘   │
│           │               │                    │             │
│           └───────────────┼────────────────────┘             │
│                           │                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              LLM Abstraction Layer                      │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │ │
│  │  │ LLM.compl() │  │ Telemetry   │  │ RetryMixin      │  │ │
│  │  │ [UPDATED]   │  │ [EXISTING]  │  │ [EXISTING]      │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │ │
│  │  │ Message     │  │ Metrics     │  │ TokenUsage      │  │ │
│  │  │ [EXISTING]  │  │ [EXISTING]  │  │ [EXISTING]      │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                           │                                  │
└───────────────────────────┼────────────────────────────────-─┘
                            │
┌───────────────────────────┼─────────────────────────────────┐
│                    LiteLLM Library                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ completion  │  │   types     │  │      utils          │  │
│  │             │  │             │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Core Components

#### 3.3.1 OpenHands Native Types

##### CompletionResult

```python
@dataclass
class CompletionResult:
    """OpenHands completion result with full abstraction."""
    message: Message                    # Already OpenHands type
    metrics: MetricsSnapshot           # Already OpenHands type  
    raw_response: ModelResponse        # For debugging/advanced use cases
    
    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return bool(self.message.tool_calls)
```

##### OpenHandsToolSpec

```python
@dataclass
class OpenHandsToolSpec:
    """OpenHands tool specification - consistent with existing patterns."""
    name: str
    description: str
    parameters: dict[str, Any]
    annotations: ToolAnnotations | None = None
    
    def to_litellm_format(self) -> ChatCompletionToolParam:
        """Internal conversion method - not exposed to agents."""
        # Implementation details hidden from agents
        ...
```

#### 3.3.2 Updated LLM Interface

```python
class LLM:
    def completion(
        self,
        messages: list[Message],
        tools: list[OpenHandsToolSpec] | None = None,
        **kwargs
    ) -> CompletionResult:
        """Complete abstraction - returns only OpenHands types."""
        # Internal implementation uses existing patterns
        response = self._internal_completion(...)
        
        # Automatic conversion using existing Message.from_litellm_message()
        llm_message = response.choices[0].message
        message = Message.from_litellm_message(llm_message)
        metrics = self.metrics.get_snapshot()
        
        return CompletionResult(
            message=message,
            metrics=metrics,
            raw_response=response
        )
    
    def _internal_completion(self, ...) -> ModelResponse:
        """Internal method - existing implementation unchanged."""
        # All existing logic preserved for backward compatibility
        ...
```

#### 3.3.3 Updated Tool Interface

```python
class ToolBase:
    def to_openhands_spec(self) -> OpenHandsToolSpec:
        """Convert to OpenHands tool specification."""
        # New method following OpenHands abstraction patterns
        return OpenHandsToolSpec(
            name=self.name,
            description=self.description,
            parameters=self._get_parameters_dict(),
            annotations=self.annotations
        )
    
    def to_openai_tool(self) -> ChatCompletionToolParam:
        """Internal method - kept for backward compatibility."""
        # Implementation unchanged - used internally
        ...
```

### 3.4 Integration Points

#### 3.4.1 Agent Integration

**Before:**

```python
# agent.py
from litellm.types.utils import (
    ChatCompletionMessageToolCall,
    Choices,
    Message as LiteLLMMessage,
)

response = self.llm.completion(messages=_messages, tools=tools)
assert len(response.choices) == 1 and isinstance(response.choices[0], Choices)
llm_message: LiteLLMMessage = response.choices[0].message
message = Message.from_litellm_message(llm_message)
```

**After:**

```python
# agent.py
# No LiteLLM imports needed

result = self.llm.completion(messages=_messages, tools=tools)
message = result.message  # Already OpenHands Message type
metrics = result.metrics  # Already OpenHands MetricsSnapshot type

if result.has_tool_calls:
    # Process tool calls using OpenHands types
    ...
```

#### 3.4.2 Tool Integration

**Before:**

```python
# tool.py
from litellm import ChatCompletionToolParam

tools = [tool.to_openai_tool() for tool in self.tools.values()]
response = self.llm.completion(messages=_messages, tools=tools)
```

**After:**

```python
# tool.py
# No LiteLLM imports needed

tools = [tool.to_openhands_spec() for tool in self.tools.values()]
result = self.llm.completion(messages=_messages, tools=tools)
```

## 4. Implementation Checklist

### Phase 1: Core Interface Completion

#### 4.1 CompletionResult Implementation

- [ ] **Create CompletionResult type** (`openhands/sdk/llm/types.py`)
  - [ ] Define `CompletionResult` dataclass with OpenHands types
  - [ ] Add `has_tool_calls` property for convenience
  - [ ] Include `raw_response` for debugging/advanced use cases

- [ ] **Update LLM.completion() method** (`openhands/sdk/llm/llm.py`)
  - [ ] Modify return type to `CompletionResult`
  - [ ] Use existing `Message.from_litellm_message()` for conversion
  - [ ] Use existing `metrics.get_snapshot()` for metrics
  - [ ] Preserve all existing internal logic

- [ ] **Create CompletionResult tests**
  (`tests/sdk/llm/test_completion_result.py`)
  - [ ] Test `CompletionResult` creation and properties
  - [ ] Test `has_tool_calls` property accuracy
  - [ ] Test integration with existing `Message` and `MetricsSnapshot` types

#### 4.2 Agent Integration

- [ ] **Update Agent class** (`openhands/sdk/agent/agent.py`)
  - [ ] Remove LiteLLM imports (`ChatCompletionMessageToolCall`, `Choices`,
    `LiteLLMMessage`)
  - [ ] Update completion call to use `CompletionResult`
  - [ ] Remove manual type assertions and conversions
  - [ ] Test agent functionality with new interface

### Phase 2: Tool Interface Completion

#### 4.3 OpenHandsToolSpec Implementation

- [ ] **Create OpenHandsToolSpec type** (`openhands/sdk/llm/types.py`)
  - [ ] Define `OpenHandsToolSpec` dataclass (avoid naming conflict with
    existing `ToolSpec`)
  - [ ] Add `to_litellm_format()` internal conversion method
  - [ ] Include `ToolAnnotations` support for consistency

- [ ] **Update ToolBase interface** (`openhands/sdk/tool/tool.py`)
  - [ ] Add `to_openhands_spec()` method returning `OpenHandsToolSpec`
  - [ ] Keep existing `to_openai_tool()` method for backward compatibility
  - [ ] Update LLM.completion() to accept `list[OpenHandsToolSpec]`

- [ ] **Create OpenHandsToolSpec tests** (`tests/sdk/llm/test_tool_spec.py`)
  - [ ] Test `OpenHandsToolSpec` creation and validation
  - [ ] Test conversion to/from LiteLLM format
  - [ ] Test integration with existing tool system

### Phase 3: Documentation and Examples

#### 4.4 Documentation Updates

- [ ] **Update examples** (`examples/`)
  - [ ] Update all examples to use new `CompletionResult` interface
  - [ ] Update tool examples to use `OpenHandsToolSpec`
  - [ ] Remove LiteLLM imports from example code

- [ ] **Update documentation**
  - [ ] Document new `CompletionResult` interface
  - [ ] Document new `OpenHandsToolSpec` interface
  - [ ] Add migration guide for existing users

#### 4.5 Testing and Validation

- [ ] **Integration testing** (`tests/integration/`)
  - [ ] Test end-to-end agent workflows with new interface
  - [ ] Test tool execution with new tool specification format
  - [ ] Verify backward compatibility during transition

- [ ] **Performance validation**
  - [ ] Ensure no performance regression from interface changes
  - [ ] Validate memory usage remains consistent
  - [ ] Test with various model providers

## 5. Conclusion

This proposal completes the excellent abstraction work already done in the
OpenHands SDK by addressing the final two interface boundaries where LiteLLM
types leak through. By building on existing strengths rather than rebuilding
working systems, we can achieve complete abstraction with minimal effort and
maximum compatibility.

The solution maintains the architectural integrity established by the existing
`Telemetry`, `Metrics`, `RetryMixin`, and `Message` abstractions while providing
a clean, consistent interface for agent developers. This approach respects the
significant abstraction work already completed while addressing the specific
remaining gaps in a way that's consistent with established patterns.

**Key Benefits:**

- **Builds on existing excellence**: Leverages 80% of abstraction work already
  done
- **Minimal scope**: Only addresses the 2 specific interface gaps identified
- **Consistent patterns**: Follows established OpenHands type system conventions
- **Future-ready**: Enables alternative language SDK implementations

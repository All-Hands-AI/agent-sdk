# LLM Service Architecture Design

## 1. Introduction

### 1.1 Problem Statement

Since OpenHands was born it has relied heavily on the excellent LiteLLM library
for LLM connectivity. While we have no reason to contemplate moving away from
LiteLLM or its abstractions for key concepts, we do have an opportunity while
the SDK is young to limit the touch points between LiteLLM and the rest of the
SDK codebase. While centralizing use of LiteLLM types to a few key places in the
codebase may not address any immediate need in the SDK, it does mean that should
we decide to produce variants of the SDK in other languages, we will be able to
keep those variants very similar in structure to the Python SDK even when these
variants depend on alternatives to LiteLLM for model communication.

### 1.2 Proposed Solution

By introducing a compact LLM Service layer that contains OpenHands types for
core LLM interactions we can reduce the number of files which make direct
imports of LiteLLM from 12 to 4 while keeping the code clean and simple. This
unlocks the possibility of having alternative language SDKs that stay very
similar to the Python original. In order to provide a proof-point, the skeleton
of a typescript SDK will be built out in a separate (private) repository.

## 2. Current State LiteLLM Imports in the SDK

### 2.1 Files with Direct LiteLLM Dependencies

The following files currently import LiteLLM types and functions:

1. **`openhands/sdk/llm/llm.py`** - Main LLM class
   - Imports: `completion`, `ModelResponse`, `get_model_info`,
     `supports_vision`, `token_counter`, `create_pretrained_tokenizer`
   - Usage: Core completion logic, model capabilities, token counting

2. **`openhands/sdk/llm/message.py`** - Message handling
   - Imports: `ChatCompletionMessageToolCall` (aliased as `LiteLLMMessage`)
   - Usage: Message conversion between OpenHands and LiteLLM formats

3. **`openhands/sdk/llm/utils/telemetry.py`** - Cost calculation and metrics
   - Imports: `completion_cost`, `ModelResponse`, `Usage`, `CostPerToken`
   - Usage: Cost calculation and usage tracking

4. **`openhands/sdk/tool/tool.py`** - Tool parameter types
   - Imports: `ChatCompletionToolParam`, `ChatCompletionToolParamFunctionChunk`
   - Usage: Tool schema definitions for LLM function calling

5. **`openhands/sdk/agent/agent.py`** - Agent message conversion
   - Imports: `ChatCompletionMessageToolCall` (aliased as `LiteLLMMessage`)
   - Usage: Converting LLM responses to OpenHands messages

6. **`openhands/sdk/event/llm_convertible.py`** - Event conversion
   - Imports: `ChatCompletionMessageToolCall`, `ChatCompletionToolParam`
   - Usage: Event system tool call and parameter handling

7. **`openhands/sdk/mcp/tool.py`** - MCP tool integration
   - Imports: `ChatCompletionToolParam`
   - Usage: MCP tool to LLM tool conversion

8. **`openhands/sdk/utils/json.py`** - JSON utilities
   - Imports: `ModelResponse`
   - Usage: JSON schema generation from LLM responses

9. **`openhands/sdk/llm/mixins/non_native_fc.py`** - Function calling mixin
   - Imports: `ModelResponse`
   - Usage: Non-native function calling implementation

10. **`openhands/sdk/llm/mixins/fn_call_converter.py`** - Function call
    converter
    - Imports: `ModelResponse`
    - Usage: Function call format conversion

### 2.2 Current State Summary

Total files with LiteLLM imports: 12

Files with LiteLLM imports:

1. `openhands/sdk/llm/llm.py` (core LLM class)
2. `openhands/sdk/llm/message.py` (message conversion)
3. `openhands/sdk/llm/utils/unverified_models.py` (model utilities)
4. `openhands/sdk/llm/utils/telemetry.py` (cost calculation)
5. `openhands/sdk/llm/mixins/non_native_fc.py` (function calling)
6. `openhands/sdk/llm/mixins/fn_call_converter.py` (function call conversion)
7. `openhands/sdk/tool/tool.py` (tool parameter types)
8. `openhands/sdk/agent/agent.py` (agent message conversion)
9. `openhands/sdk/event/llm_convertible.py` (event conversion)
10. `openhands/sdk/mcp/tool.py` (MCP tool integration)
11. `openhands/sdk/utils/json.py` (JSON utilities)
12. `openhands/sdk/logger.py` (logging configuration)

### 2.3 LiteLLM Usage Patterns

The current codebase uses LiteLLM in several key patterns:

- **Direct completion calls**: `litellm.completion()` for model inference
- **Type conversions**: Converting between OpenHands and LiteLLM message formats
- **Utility functions**: Token counting, model info, vision support detection
- **Cost calculation**: Using LiteLLM's cost calculation utilities
- **Tool parameter handling**: Using LiteLLM's tool parameter types
- **Exception handling**: Catching and handling LiteLLM-specific exceptions

### 2.4 Target State After Refactoring

Target files with LiteLLM imports: 4

After refactoring, LiteLLM imports will be consolidated to:

1. `openhands/sdk/llm/service.py` (new LLMService with internal converters - all
   LiteLLM interaction)
2. `openhands/sdk/llm/llm.py` (updated to use LLMService, minimal LiteLLM for
   backward compatibility)
3. `openhands/sdk/llm/utils/telemetry.py` (cost calculation utilities)
4. `openhands/sdk/llm/utils/unverified_models.py` (model utilities)

Reduction: 12 → 4 files (67% reduction in LiteLLM touchpoints)

## 3. LLM Service Technical Design

### 3.1 Core Design Principles

**Encapsulation Boundary**: The rest of the codebase only works with OpenHands
native types and primitives, while LiteLLM is completely encapsulated within the
service layer. The converters exist as internal implementation details to handle
the format translation, but they don't leak LiteLLM types into the public API.

**Type Clarity Preserved**: Do not achieve this encapsilation goal at the cost
of weaker type safety. Preserve expressiveness with new OpenHands types where
needed.

These principle ensure:

- **Clean separation**: LiteLLM dependencies are isolated to specific service
  components
- **Type safety**: All public APIs use strongly-typed OpenHands native types
- **Maintainability**: Changes to LiteLLM integration don't ripple through the
  codebase
- **Testability**: Services can be mocked at the OpenHands type boundary
- **Portability**: Most of the SDK API will look similiar in alternative
  language implementations

### 3.2 Architecture Overview

The proposed architecture introduces a centralized service layer that
encapsulates all LLM provider interactions while exposing OpenHands-native types
to the rest of the codebase.

```plaintext
┌───────────-──────────────────────────────────────────────────┐
│                    OpenHands SDK Codebase                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │   Agent     │  │   Tools     │  │      Events         │   │
│  │             │  │             │  │                     │   │
│  └─────────────┘  └─────────────┘  └─────────────────────┘   │
│           │               │                    │             │
│           └───────────────┼────────────────────┘             │
│                           │                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              LLM Service Layer                          │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │ │
│  │  │ LLMService  │  │ MessageConv │  │ TelemetryService│  │ │
│  │  │             │  │             │  │                 │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │ │
│  │  ┌─────────────┐  ┌─────────────┐                       │ │
│  │  │ ToolConv    │  │ CapabilityS │                       │ │
│  │  │             │  │             │                       │ │
│  │  └─────────────┘  └─────────────┘                       │ │
│  └─────────────────────────────────────────────────────────┘ │
│                           │                                  │
└───────────────────────────┼───────────────────────────────---┘
                            │
┌───────────────────────────┼───────────────────────────────-─┐
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
    """Native OpenHands completion result type."""
    message: Message
    usage: UsageStats
    model: str
    finish_reason: str | None
    metrics_snapshot: MetricsSnapshot
    raw_response: Any  # For debugging/telemetry
```

##### ToolSpec

```python
@dataclass
class ToolSpec:
    """Native OpenHands tool specification."""
    name: str
    description: str
    parameters: dict[str, Any]
    annotations: ToolAnnotations | None = None
```

##### ToolCall

```python
@dataclass
class ToolCall:
    """Native OpenHands tool call."""
    id: str
    name: str
    arguments: dict[str, Any]
```

##### ModelCapabilities

```python
@dataclass
class ModelCapabilities:
    """Native OpenHands model capabilities."""
    supports_vision: bool
    supports_function_calling: bool
    supports_reasoning: bool
    supports_caching: bool
    max_tokens: int | None
    context_window: int | None
```

##### UsageStats

```python
@dataclass
class UsageStats:
    """Native OpenHands usage statistics."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float | None = None
```

#### 3.3.2 LLMService

```python
class LLMService:
    """Central service for all LLM operations."""
    
    def __init__(self, config: LLMConfig):
        self._config = config
        self._message_converter = _MessageConverter()
        self._tool_converter = _ToolConverter()
        self._capability_service = ModelCapabilityService()
        self._telemetry_service = TelemetryService(config)
    
    def complete(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs
    ) -> CompletionResult:
        """Main completion method using OpenHands native types."""
        
    def count_tokens(self, messages: list[Message]) -> int:
        """Token counting with native types."""
        
    def get_capabilities(self) -> ModelCapabilities:
        """Get model capabilities as native type."""
        
    def calculate_cost(self, result: CompletionResult) -> float | None:
        """Calculate cost from native result type."""
```

#### 3.3.3 MessageConverter (Internal)

```python
class _MessageConverter:
    """Internal message format converter - not exposed publicly."""
    
    def _to_llm_format(
        self, 
        messages: list[Message], 
        capabilities: ModelCapabilities
    ) -> list[dict[str, Any]]:
        """Convert OpenHands messages to LiteLLM format (internal)."""
        # Returns LiteLLM-compatible dict format internally
        
    def _from_llm_response(self, llm_response: Any) -> Message:
        """Convert LiteLLM response to OpenHands Message (internal)."""
        # Takes LiteLLM ModelResponse, returns OpenHands Message
```

#### 3.3.4 ToolConverter (Internal)

```python
class _ToolConverter:
    """Internal tool format converter - not exposed publicly."""
    
    def _to_llm_tools(self, tools: list[ToolSpec]) -> list[dict[str, Any]]:
        """Convert OpenHands tools to LiteLLM tool format (internal)."""
        # Returns LiteLLM-compatible dict format internally
        
    def _from_llm_tool_calls(self, tool_calls: Any) -> list[ToolCall]:
        """Convert LiteLLM tool calls to OpenHands format (internal)."""
        # Takes LiteLLM tool calls, returns OpenHands ToolCall list
        
    def _validate_tool_spec(self, tool: ToolSpec) -> bool:
        """Validate tool specification (internal)."""
```

#### 3.3.5 ModelCapabilityService

```python
class ModelCapabilityService:
    """Centralized model capability detection and caching."""
    
    def get_capabilities(self, model: str) -> ModelCapabilities:
        """Get cached or detected model capabilities."""
        
    def supports_feature(self, model: str, feature: str) -> bool:
        """Check if model supports specific feature."""
        
    def refresh_capabilities(self, model: str) -> ModelCapabilities:
        """Force refresh of model capabilities."""
```

#### 3.3.6 TelemetryService

```python
class TelemetryService:
    """Handles telemetry, cost calculation, and metrics."""
    
    def track_completion(self, result: CompletionResult) -> None:
        """Track completion metrics."""
        
    def calculate_cost(self, result: CompletionResult) -> float | None:
        """Calculate cost from completion result."""
        
    def get_metrics_snapshot(self) -> MetricsSnapshot:
        """Get current metrics snapshot."""
        
    def log_completion(self, result: CompletionResult) -> None:
        """Log completion for debugging/analysis."""
```

### 3.4 Integration Points

#### 3.4.1 Agent Integration

**Before:**

```python
# agent.py
from litellm import ChatCompletionMessageToolCall
from litellm.types.utils import ModelResponse

response = self.llm.completion(messages=_messages, tools=tools)
llm_message: LiteLLMMessage = response.choices[0].message
message = Message.from_litellm_message(llm_message)
```

**After:**

```python
# agent.py
response = self.llm_service.complete(messages=messages, tools=tools)
message = response.message  # Already in OpenHands format
```

#### 3.4.2 Tool Integration

**Before:**

```python
# tool.py
from litellm import ChatCompletionToolParam

def to_openai_tool(self) -> ChatCompletionToolParam:
    return ChatCompletionToolParam(...)
```

**After:**

```python
# tool.py
def to_tool_spec(self) -> ToolSpec:
    return ToolSpec(name=self.name, description=self.description, ...)
```

#### 3.4.3 Event System Integration

**Before:**

```python
# llm_convertible.py
from litellm import ChatCompletionToolParam, ChatCompletionMessageToolCall

tools: list[ChatCompletionToolParam] = Field(...)
tool_calls: list[ChatCompletionMessageToolCall] = Field(...)
```

**After:**

```python
# llm_convertible.py
tools: list[ToolSpec] = Field(...)
tool_calls: list[ToolCall] = Field(...)
```

### 3.5 Error Handling

The service layer will provide OpenHands-native exceptions that wrap LiteLLM
exceptions:

```python
class OpenHandsLLMException(Exception):
    """Base exception for LLM operations."""
    pass

class OpenHandsAPIConnectionError(OpenHandsLLMException):
    """API connection error."""
    pass

class OpenHandsRateLimitError(OpenHandsLLMException):
    """Rate limit exceeded."""
    pass

class OpenHandsInternalServerError(OpenHandsLLMException):
    """Internal server error."""
    pass

class OpenHandsTimeout(OpenHandsLLMException):
    """Request timeout."""
    pass
```

## 4. Implementation Plan with Integrated Testing

### Testing Strategy Overview

Testing will be integrated into each implementation phase rather than being a
separate phase. This ensures:

- **Continuous validation** of each component as it's built
- **Backward compatibility** throughout the migration
- **Integration confidence** between new and existing components
- **Performance monitoring** to prevent regressions

#### Test Structure

```plaintext
tests/sdk/llm/
├── test_llm_service.py              # Core LLMService tests
├── test_native_types.py             # CompletionResult, ToolSpec, etc.
├── test_message_converter.py        # MessageConverter tests  
├── test_tool_converter.py           # ToolConverter tests
├── test_model_capability_service.py # Model capability detection
├── test_telemetry_service.py        # Telemetry collection
├── test_backward_compatibility.py   # Ensure old APIs still work
└── test_migration_parity.py         # Old vs new behavior comparison

tests/cross/
├── test_llm_service_integration.py  # Cross-component integration
└── test_migration_scenarios.py      # End-to-end migration testing
```

#### Testing Patterns

1. **Boundary Mocking**: Mock LiteLLM at the LLMService boundary, not throughout
   codebase
2. **Type Conversion Testing**: Verify fidelity between LiteLLM and OpenHands
   types
3. **Property-Based Testing**: Use hypothesis for conversion edge cases
4. **Integration Testing**: Real tool execution with mocked LLM responses
5. **Backward Compatibility**: Existing tests must continue passing

### Phase 1: Foundation (Native Types and Core Services)

#### Phase 1.1: Native Types Module

- [ ] **Create native types module** (`openhands/sdk/llm/types.py`)
  - [ ] Define `CompletionResult` dataclass
  - [ ] Define `ToolSpec` dataclass  
  - [ ] Define `ToolCall` dataclass
  - [ ] Define `ModelCapabilities` dataclass
  - [ ] Define `UsageStats` dataclass
  - [ ] Define OpenHands exception hierarchy

- [ ] **Create native types tests** (`tests/sdk/llm/test_native_types.py`)
  - [ ] Test `CompletionResult` serialization/deserialization
  - [ ] Test `ToolSpec` validation and conversion
  - [ ] Test `ToolCall` structure and validation
  - [ ] Test `ModelCapabilities` detection logic
  - [ ] Test `UsageStats` aggregation and calculation
  - [ ] Test exception hierarchy and error propagation

#### Phase 1.2: LLMService

- [ ] **Create LLMService** (`openhands/sdk/llm/service.py`)
  - [ ] Implement `LLMService` class with LiteLLM backend
  - [ ] Implement `complete()` method
  - [ ] Implement `count_tokens()` method
  - [ ] Implement `get_capabilities()` method
  - [ ] Add comprehensive error handling and exception mapping

- [ ] **Create LLMService tests** (`tests/sdk/llm/test_llm_service.py`)
  - [ ] Mock LiteLLM completion at service boundary
  - [ ] Test successful completion flow with various models
  - [ ] Test error handling and retry logic
  - [ ] Test token counting accuracy
  - [ ] Test capability detection and caching
  - [ ] Test timeout and rate limiting scenarios
  - [ ] Test concurrent request handling

#### Phase 1.3: Message Converter

- [ ] **Create MessageConverter** (`openhands/sdk/llm/converters/message.py`)
  - [ ] Implement `to_llm_format()` method
  - [ ] Implement `from_llm_response()` method
  - [ ] Implement `serialize_message()` method
  - [ ] Handle all message content types (text, image, tool calls)

- [ ] **Create MessageConverter tests**
  (`tests/sdk/llm/test_message_converter.py`)
  - [ ] Test bidirectional conversion fidelity
  - [ ] Test all message content types (text, image, tool calls)
  - [ ] Test edge cases and malformed inputs
  - [ ] Property-based testing for conversion consistency
  - [ ] Test cache control and metadata preservation

#### Phase 1.4: Tool Converter

- [ ] **Create ToolConverter** (`openhands/sdk/llm/converters/tool.py`)
  - [ ] Implement `to_llm_tools()` method
  - [ ] Implement `from_llm_tool_calls()` method
  - [ ] Implement `validate_tool_spec()` method
  - [ ] Handle tool parameter schema conversion

- [ ] **Create ToolConverter tests** (`tests/sdk/llm/test_tool_converter.py`)
  - [ ] Test tool specification conversion accuracy
  - [ ] Test tool call conversion and parameter handling
  - [ ] Test schema validation and error cases
  - [ ] Test complex nested parameter structures
  - [ ] Property-based testing for tool parameter edge cases

### Phase 2: Supporting Services

#### Phase 2.1: Model Capability Service

- [ ] **Create ModelCapabilityService** (`openhands/sdk/llm/capability.py`)
  - [ ] Implement capability detection logic
  - [ ] Add caching mechanism for capabilities
  - [ ] Implement `supports_feature()` method
  - [ ] Handle model name variations and aliases

- [ ] **Create ModelCapabilityService tests**
  (`tests/sdk/llm/test_model_capability_service.py`)
  - [ ] Test capability detection for different model families
  - [ ] Test caching behavior and cache invalidation
  - [ ] Test fallback mechanisms for unknown models
  - [ ] Test model alias resolution

#### Phase 2.2: Telemetry Service

- [ ] **Create TelemetryService** (`openhands/sdk/llm/telemetry.py`)
  - [ ] Implement cost calculation with native types
  - [ ] Implement metrics tracking
  - [ ] Implement completion logging
  - [ ] Migrate existing telemetry logic

- [ ] **Create TelemetryService tests**
  (`tests/sdk/llm/test_telemetry_service.py`)
  - [ ] Test usage tracking accuracy across different models
  - [ ] Test cost calculation with various pricing models
  - [ ] Test metrics aggregation and reporting
  - [ ] Test integration with existing telemetry systems

#### Phase 2.3: LLM Class Integration

- [ ] **Update LLM class** (`openhands/sdk/llm/llm.py`)
  - [ ] Integrate `LLMService` into existing `LLM` class
  - [ ] Maintain backward compatibility during transition
  - [ ] Update method signatures to use native types
  - [ ] Add deprecation warnings for old methods

- [ ] **Create LLM integration tests** (`tests/sdk/llm/test_llm_integration.py`)
  - [ ] Test LLMService integration with updated LLM class
  - [ ] Test backward compatibility of existing LLM API
  - [ ] Test telemetry integration end-to-end
  - [ ] Test capability service integration

### Phase 3: Consumer Migration

#### Phase 3.1: Agent System Migration

- [ ] **Update Agent** (`openhands/sdk/agent/agent.py`)
  - [ ] Replace LiteLLM imports with service usage
  - [ ] Update completion logic to use `CompletionResult`
  - [ ] Update message handling to use native types
  - [ ] Remove direct LiteLLM type usage

- [ ] **Create Agent migration tests**
  (`tests/sdk/agent/test_agent_migration.py`)
  - [ ] Test that existing Agent workflows continue to function
  - [ ] Test completion logic with new `CompletionResult` type
  - [ ] Test message handling with native types
  - [ ] Test backward compatibility of Agent API

#### Phase 3.2: Tool System Migration

- [ ] **Update Tool System** (`openhands/sdk/tool/tool.py`)
  - [ ] Replace `ChatCompletionToolParam` with `ToolSpec`
  - [ ] Update tool conversion methods
  - [ ] Update tool validation logic
  - [ ] Remove LiteLLM imports

- [ ] **Create Tool migration tests** (`tests/sdk/tool/test_tool_migration.py`)
  - [ ] Test that existing Tool system remains compatible
  - [ ] Test tool conversion with new `ToolSpec` format
  - [ ] Test tool validation logic
  - [ ] Test MCP integration with new types

#### Phase 3.3: Event System Migration

- [ ] **Update Event System** (`openhands/sdk/event/llm_convertible.py`)
  - [ ] Replace LiteLLM types with native types
  - [ ] Update event serialization
  - [ ] Update tool call handling
  - [ ] Remove LiteLLM imports

- [ ] **Update MCP Integration** (`openhands/sdk/mcp/tool.py`)
  - [ ] Replace `ChatCompletionToolParam` with `ToolSpec`
  - [ ] Update MCP tool conversion
  - [ ] Remove LiteLLM imports

- [ ] **Create Event system migration tests**
  (`tests/sdk/event/test_event_migration.py`)
  - [ ] Test that Event system serialization is preserved
  - [ ] Test tool call handling with native types
  - [ ] Test MCP integration compatibility

#### Phase 3.4: Utility Migration and Integration Testing

- [ ] **Update Utility Files**
  - [ ] Update `openhands/sdk/utils/json.py`
  - [ ] Update `openhands/sdk/llm/mixins/` files
  - [ ] Remove LiteLLM imports from utility functions

- [ ] **Create comprehensive migration tests**
  - [ ] **Backward compatibility tests**
    (`tests/sdk/llm/test_backward_compatibility.py`)
    - [ ] Test that existing LLM API still works after migration
    - [ ] Test all existing public interfaces remain functional
    - [ ] Test deprecation warnings are properly shown
  - [ ] **Migration parity tests** (`tests/sdk/llm/test_migration_parity.py`)
    - [ ] Compare old vs new completion results for identical inputs
    - [ ] Verify tool call conversion produces same outputs
    - [ ] Verify message conversion maintains fidelity
    - [ ] Test performance parity between old and new systems

- [ ] **Create cross-component integration tests**
  (`tests/cross/test_llm_service_integration.py`)
  - [ ] Test Agent + LLMService + Tools integration
  - [ ] Test Event system with new LLM types
  - [ ] Test MCP integration with new tool specifications
  - [ ] Test end-to-end conversation flows

### Phase 4: Documentation and Cleanup

#### Phase 4.1: Documentation

- [ ] **Create comprehensive documentation**
  - [ ] Update API documentation for new types
  - [ ] Create migration guide for external users
  - [ ] Document service layer architecture
  - [ ] Add examples using new native types

- [ ] **Documentation validation tests** (`tests/sdk/llm/test_documentation.py`)
  - [ ] Test all code examples in documentation
  - [ ] Validate migration guide steps work correctly
  - [ ] Test API documentation accuracy
  - [ ] Verify example scripts run without errors

#### Phase 4.2: Code Cleanup

- [ ] **Clean up codebase**
  - [ ] Remove unused LiteLLM imports
  - [ ] Clean up deprecated methods
  - [ ] Consolidate error handling
  - [ ] Optimize import statements

- [ ] **Code quality validation**
  - [ ] Run linting and formatting tools
  - [ ] Ensure all type hints are correct
  - [ ] Validate import organization
  - [ ] Check for unused code

#### Phase 4.3: Final Validation

- [ ] **Comprehensive testing**
  - [ ] Run complete test suite with no failures
  - [ ] Execute integration tests with multiple LLM providers
  - [ ] Validate all examples and documentation code
  - [ ] Performance regression testing

- [ ] **Final verification**
  - [ ] Validate no regression in functionality
  - [ ] Confirm LiteLLM usage reduced to target files
  - [ ] Performance validation against benchmarks
  - [ ] Security and compatibility review

### Success Metrics

- **Reduced LiteLLM touchpoints**: From 12 files to 4 files
- **Maintained functionality**: All existing features work unchanged
- **Clean abstractions**: Native types are intuitive and well-documented
- **Performance**: No significant performance regression
- **Testability**: Improved unit test coverage through better abstractions

## 5. Testing Strategy Summary

### Integrated Testing Approach

This implementation plan integrates testing into each phase rather than
deferring it to the end. This approach provides:

1. **Continuous Validation**: Each component is tested as it's built
2. **Early Issue Detection**: Problems are caught before they compound
3. **Backward Compatibility Assurance**: Existing functionality is preserved
   throughout
4. **Integration Confidence**: Cross-component interactions are validated
   continuously

### Test Categories

#### Unit Tests

- **Native Types**: Serialization, validation, edge cases
- **Service Classes**: LLMService, ModelCapabilityService, TelemetryService
- **Converters**: Message and tool conversion fidelity
- **Utilities**: Helper functions and error handling

#### Integration Tests

- **Cross-Component**: Service integration with existing components
- **End-to-End**: Complete workflow testing
- **Backward Compatibility**: Existing API preservation
- **Migration Parity**: Old vs new behavior comparison

#### Performance Tests

- **Latency**: Completion time benchmarking
- **Memory**: Usage patterns and leak detection
- **Concurrency**: Multi-request handling
- **Regression**: Performance comparison with baseline

#### Documentation Tests

- **Example Validation**: All documentation code works
- **Migration Guide**: Step-by-step validation
- **API Accuracy**: Documentation matches implementation

### Testing Tools and Patterns

- **Mocking Strategy**: Mock LiteLLM at service boundary, not throughout
  codebase
- **Fixtures**: Reusable test data and mock objects in conftest.py
- **Property-Based Testing**: Use hypothesis for conversion edge cases
- **Real Integration**: Test with actual tools but mocked LLM responses
- **Continuous Testing**: All existing tests must pass throughout migration

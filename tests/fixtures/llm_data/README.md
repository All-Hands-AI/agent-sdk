# LLM Test Data Fixtures

This directory contains real LLM completion data collected from `examples/hello_world.py` for comprehensive testing of the LLM class and related components.

## Structure

```
tests/fixtures/llm_data/
├── README.md                      # This file
├── fncall-llm-message.json       # Function calling conversation messages
├── nonfncall-llm-message.json    # Non-function calling conversation messages
├── llm-logs/                     # Raw function calling completion logs
│   └── *.json                    # Individual completion log files
└── nonfncall-llm-logs/           # Raw non-function calling completion logs
    └── *.json                    # Individual completion log files
```

## Data Sources

### Function Calling Data
- **Model**: `litellm_proxy/anthropic/claude-sonnet-4-20250514`
- **Features**: Native function calling support
- **Files**: `fncall-llm-message.json`, `llm-logs/*.json`

### Non-Function Calling Data
- **Model**: `litellm_proxy/deepseek/deepseek-chat`
- **Features**: Prompt-based function calling mocking
- **Files**: `nonfncall-llm-message.json`, `nonfncall-llm-logs/*.json`

## File Formats

### Message Files (`*-llm-message.json`)
Contains conversation messages in OpenHands format:
```json
[
  {
    "role": "system",
    "content": "System prompt..."
  },
  {
    "role": "user", 
    "content": "User message..."
  },
  {
    "role": "assistant",
    "content": "Assistant response...",
    "tool_calls": [...]  // Only in function calling data
  },
  {
    "role": "tool",
    "content": "Tool result...",
    "tool_call_id": "..."  // Only in function calling data
  }
]
```

### Raw Log Files (`*/logs/*.json`)
Contains complete LiteLLM completion logs:
```json
{
  "messages": [...],           // Request messages
  "tools": [...],             // Tool definitions (if any)
  "kwargs": {...},            // Request parameters
  "context_window": 200000,   // Model context window
  "response": {               // LiteLLM response
    "id": "...",
    "model": "...",
    "choices": [...],
    "usage": {...}
  },
  "cost": 0.016626,          // API cost
  "timestamp": 1757003287.33, // Unix timestamp
  "latency_sec": 3.305       // Response latency
}
```

## Usage in Tests

### Unit Tests (`tests/sdk/llm/test_llm_real_data.py`)
- Tests LLM class methods with real completion data
- Validates message serialization/deserialization
- Tests function calling vs non-function calling behavior
- Validates cost and latency tracking
- Tests error handling with real message formats

### Integration Tests (`tests/integration/test_llm_integration_real_data.py`)
- End-to-end conversation replay using real data
- Tests Agent and Conversation classes with real LLM responses
- Validates telemetry and logging integration
- Tests tool execution patterns
- Compares function calling vs prompt mocking approaches

## Regenerating Test Data

Use the test data generator utility to create new test fixtures:

```bash
# Generate new test data
python tests/utils/test_data_generator.py --api-key YOUR_API_KEY

# Validate existing test data
python tests/utils/test_data_generator.py --api-key YOUR_API_KEY --validate-only

# Custom models and messages
python tests/utils/test_data_generator.py \
  --api-key YOUR_API_KEY \
  --fncall-model "litellm_proxy/anthropic/claude-sonnet-4-20250514" \
  --nonfncall-model "litellm_proxy/deepseek/deepseek-chat" \
  --user-message "Create a Python script that calculates fibonacci numbers"
```

## Test Coverage

The real data enables testing of:

1. **LLM Core Functionality**
   - Message formatting and serialization
   - Function calling detection and handling
   - Prompt-based function calling mocking
   - Response parsing and validation

2. **Telemetry and Logging**
   - Cost calculation and tracking
   - Latency measurement
   - Request/response logging
   - Metadata capture

3. **Error Handling**
   - Retry logic with real error patterns
   - Timeout handling
   - Rate limit responses

4. **Integration Scenarios**
   - Agent-LLM interaction
   - Tool execution workflows
   - Conversation state management
   - End-to-end message flow

## Data Validation

The test data is validated to ensure:
- Message structure consistency
- Required fields presence
- Tool schema validity
- Cost and latency data integrity
- Log file completeness

Run validation with:
```bash
python tests/utils/test_data_generator.py --validate-only
```

## Maintenance

- **Update Frequency**: Regenerate when LLM implementation changes significantly
- **Model Updates**: Update when new models are added or existing models change behavior
- **Schema Changes**: Regenerate if message or log schemas are modified
- **Version Control**: All test data is committed to ensure reproducible tests
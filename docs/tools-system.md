# OpenHands Tools System

## What it is

A type-safe tool execution framework with Pydantic schema validation and MCP compatibility. Tools wrap executors with input/output validation and provide standardized interfaces for LLM function calling.

## Architecture Overview

```mermaid
graph TB
    subgraph "Core Framework (openhands/sdk/tool)"
        Tool[Tool]
        ActionBase[ActionBase]
        ObservationBase[ObservationBase]
        ToolExecutor[ToolExecutor]
    end
    
    subgraph "Built-in Tools (openhands/sdk/tool/builtins)"
        FinishTool[FinishTool]
        ThinkTool[ThinkTool]
    end
    
    subgraph "Runtime Tools (openhands/tools)"
        BashTool[BashTool]
        FileEditorTool[FileEditorTool]
        TaskTrackerTool[TaskTrackerTool]
    end
    
    Tool --> FinishTool
    Tool --> ThinkTool
    Tool --> BashTool
    Tool --> FileEditorTool
    Tool --> TaskTrackerTool
    
    ActionBase --> ExecuteBashAction
    ActionBase --> StrReplaceEditorAction
    ActionBase --> TaskTrackerAction
    
    ObservationBase --> ExecuteBashObservation
    ObservationBase --> StrReplaceEditorObservation
    ObservationBase --> TaskTrackerObservation
```

## Core Components

### Schema Base Classes

**Schema** - Base for all input/output schemas ([source](https://github.com/All-Hands-AI/agent-sdk/blob/main/openhands/sdk/tool/schema.py))
- Converts Pydantic models to MCP-compatible JSON schemas
- Handles schema normalization and validation
- Supports dynamic model creation from JSON schemas

**ActionBase** - Input schema for tool actions ([source](https://github.com/All-Hands-AI/agent-sdk/blob/main/openhands/sdk/tool/schema.py))
- Inherits from Schema
- Includes security_risk field for LLM safety assessment
- Moves ActionBase fields to end of schema for better LLM ordering

**ObservationBase** - Output schema for tool results ([source](https://github.com/All-Hands-AI/agent-sdk/blob/main/openhands/sdk/tool/schema.py))
- Inherits from Schema
- Requires agent_observation property for LLM consumption
- Allows extra fields for flexibility

### Tool Framework

**Tool** - Generic tool wrapper with validation ([source](https://github.com/All-Hands-AI/agent-sdk/blob/main/openhands/sdk/tool/tool.py))
- Type parameters: `Tool[ActionT, ObservationT]`
- Validates inputs before execution
- Coerces outputs to expected types
- Exports MCP and OpenAI tool descriptions

**ToolExecutor** - Callable interface for tool logic ([source](https://github.com/All-Hands-AI/agent-sdk/blob/main/openhands/sdk/tool/tool.py))
- Generic type: `ToolExecutor[ActionT, ObservationT]`
- Implements `__call__(action: ActionT) -> ObservationT`

**ToolAnnotations** - MCP-compatible tool metadata ([source](https://github.com/All-Hands-AI/agent-sdk/blob/main/openhands/sdk/tool/tool.py))
- readOnlyHint: Tool doesn't modify environment
- destructiveHint: Tool may perform destructive updates
- idempotentHint: Repeated calls have no additional effect
- openWorldHint: Tool interacts with external entities

## Usage Patterns

### Simplified Pattern (Recommended)

```python
from openhands.tools import BashTool, FileEditorTool, TaskTrackerTool

tools = [
    BashTool.create(working_dir="/workspace"),
    FileEditorTool.create(),
    TaskTrackerTool.create(save_dir="/workspace"),
]
```

### Advanced Pattern (Custom Tools)

```python
from openhands.tools import BashExecutor, execute_bash_tool

# Explicit executor for reuse
executor = BashExecutor(working_dir="/workspace")
tool = execute_bash_tool.set_executor(executor)
```

### Creating Custom Tools

```python
from openhands.sdk.tool import Tool, ActionBase, ObservationBase, ToolExecutor
from pydantic import Field

class MyAction(ActionBase):
    input_text: str = Field(description="Text to process")

class MyObservation(ObservationBase):
    result: str = Field(description="Processed result")
    
    @property
    def agent_observation(self):
        return [TextContent(text=self.result)]

class MyExecutor(ToolExecutor):
    def __call__(self, action: MyAction) -> MyObservation:
        return MyObservation(result=f"Processed: {action.input_text}")

my_tool = Tool(
    name="my_tool",
    description="Processes text input",
    action_type=MyAction,
    observation_type=MyObservation,
    executor=MyExecutor()
)
```

## Available Runtime Tools

### BashTool
Execute bash commands in a persistent shell session.
```python
BashTool.create(working_dir="/workspace")
```
**Source**: [`openhands/tools/execute_bash/definition.py`](https://github.com/All-Hands-AI/agent-sdk/blob/main/openhands/tools/execute_bash/definition.py)

### FileEditorTool  
Edit files using string replacement, creation, and viewing operations.
```python
FileEditorTool.create(workspace_root="/workspace")
```
**Source**: [`openhands/tools/str_replace_editor/definition.py`](https://github.com/All-Hands-AI/agent-sdk/blob/main/openhands/tools/str_replace_editor/definition.py)

### TaskTrackerTool
Manage development tasks with structured tracking and persistence.
```python
TaskTrackerTool.create(save_dir="/workspace")  # Saves to TASKS.json
```
**Source**: [`openhands/tools/task_tracker/definition.py`](https://github.com/All-Hands-AI/agent-sdk/blob/main/openhands/tools/task_tracker/definition.py)

## Schema Class Inheritance

```mermaid
classDiagram
    class ActionBase {
        +security_risk: SECURITY_RISK_LITERAL
        +to_mcp_schema() dict
    }
    
    class ObservationBase {
        +agent_observation: list[TextContent|ImageContent]
        +model_config: extra="allow"
    }
    
    class ExecuteBashAction {
        +command: str
        +is_input: bool
        +timeout: float|None
    }
    
    class StrReplaceEditorAction {
        +command: CommandLiteral
        +path: str
        +file_text: str|None
        +old_str: str|None
        +new_str: str|None
        +insert_line: int|None
        +view_range: list[int]|None
    }
    
    class TaskTrackerAction {
        +command: Literal["view", "plan"]
        +task_list: list[TaskItem]
    }
    
    class ExecuteBashObservation {
        +output: str
        +command: str|None
        +exit_code: int|None
        +error: bool
        +timeout: bool
        +metadata: CmdOutputMetadata
        +agent_observation
    }
    
    class StrReplaceEditorObservation {
        +output: str
        +path: str|None
        +prev_exist: bool
        +old_content: str|None
        +new_content: str|None
        +error: str|None
        +agent_observation
    }
    
    class TaskTrackerObservation {
        +content: str
        +command: str
        +task_list: list[TaskItem]
        +agent_observation
    }
    
    ActionBase <|-- ExecuteBashAction
    ActionBase <|-- StrReplaceEditorAction
    ActionBase <|-- TaskTrackerAction
    ObservationBase <|-- ExecuteBashObservation
    ObservationBase <|-- StrReplaceEditorObservation
    ObservationBase <|-- TaskTrackerObservation
```

## Tool Execution Flow

```mermaid
sequenceDiagram
    participant LLM
    participant Tool
    participant Executor
    participant Environment
    
    LLM->>Tool: call(action_data)
    Tool->>Tool: validate input schema
    Tool->>Executor: __call__(validated_action)
    Executor->>Environment: perform operation
    Environment-->>Executor: raw result
    Executor-->>Tool: observation
    Tool->>Tool: validate/coerce output
    Tool-->>LLM: validated observation
```

## Built-in vs Runtime Tools

**Built-in Tools** ([`openhands/sdk/tool/builtins`](https://github.com/All-Hands-AI/agent-sdk/tree/main/openhands/sdk/tool/builtins))
- Essential tools required for agent operation
- No environment interaction
- Examples: [FinishTool](https://github.com/All-Hands-AI/agent-sdk/blob/main/openhands/sdk/tool/builtins/finish.py), [ThinkTool](https://github.com/All-Hands-AI/agent-sdk/blob/main/openhands/sdk/tool/builtins/think.py)

**Runtime Tools** ([`openhands/tools`](https://github.com/All-Hands-AI/agent-sdk/tree/main/openhands/tools))
- Environment-interactive tools
- Separate package for modularity
- Examples: [BashTool](https://github.com/All-Hands-AI/agent-sdk/blob/main/openhands/tools/execute_bash/definition.py), [FileEditorTool](https://github.com/All-Hands-AI/agent-sdk/blob/main/openhands/tools/str_replace_editor/definition.py), [TaskTrackerTool](https://github.com/All-Hands-AI/agent-sdk/blob/main/openhands/tools/task_tracker/definition.py)

## Security Integration

All ActionBase schemas include security_risk assessment:
- LOW: Read-only operations
- MEDIUM: Container-scoped modifications  
- HIGH: Data exfiltration or privilege escalation
- UNKNOWN: Default for weaker LLMs

## MCP Compatibility

Tools export MCP-compatible schemas via:
- `to_mcp_tool()`: Full MCP tool description
- `to_openai_tool()`: OpenAI function calling format
- Schema normalization removes Pydantic-specific constructs

## Key Design Principles

1. **Type Safety**: Generic Tool[ActionT, ObservationT] ensures compile-time correctness
2. **Schema Flexibility**: Support both Pydantic classes and raw JSON schemas
3. **Validation**: Input validation before execution, output coercion after
4. **Separation**: Core framework separate from environment-specific tools
5. **Standards**: MCP compatibility for interoperability

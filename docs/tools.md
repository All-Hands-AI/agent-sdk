# Tools

Two usage patterns are supported.

Simplified pattern
```python
from openhands.tools import BashTool, FileEditorTool

tools = [
    BashTool(working_dir=os.getcwd()),
    FileEditorTool(),
]
```

Advanced pattern
```python
from openhands.tools import BashExecutor, execute_bash_tool

bash_executor = BashExecutor(working_dir=os.getcwd())
bash_tool = execute_bash_tool.set_executor(executor=bash_executor)
```

Custom tools
- Define Action/Observation schemas (pydantic models)
- Implement a ToolExecutor that accepts Action and returns Observation
- Wrap in Tool(name, description, input_schema, output_schema, executor)

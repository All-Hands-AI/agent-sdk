# Repomix Tool

The Repomix tool provides codebase packaging and analysis capabilities for OpenHands agents. It wraps the [repomix](https://repomix.com/) MCP server to enable AI agents to analyze and package codebases into consolidated XML files optimized for AI analysis.

## Overview

Repomix is a powerful tool that analyzes codebase structure, extracts relevant code content, and generates comprehensive reports including metrics, file trees, and formatted code content. This tool integrates repomix's `pack_codebase` functionality into the OpenHands ecosystem.

## Features

- **Codebase Analysis**: Analyzes directory structure and extracts code content
- **Compression**: Optional Tree-sitter compression to reduce token usage by ~70%
- **Pattern Filtering**: Include/exclude files using fast-glob patterns
- **Metrics**: Provides file size metrics and codebase statistics
- **AI-Optimized**: Generates output specifically formatted for AI analysis

## Usage

### Basic Usage

```python
from openhands.tools import RepomixTool

# Create the tool
repomix_tool = RepomixTool.create()

# Pack a codebase
action = PackCodebaseAction(directory="/path/to/your/project")
result = repomix_tool.execute(action)

print(result.output)  # Contains the packed codebase XML
```

### Advanced Usage with Options

```python
from openhands.tools.repomix import PackCodebaseAction, RepomixTool

# Create tool
repomix_tool = RepomixTool.create()

# Pack with compression and filtering
action = PackCodebaseAction(
    directory="/path/to/your/project",
    compress=True,  # Enable compression to reduce token usage
    include_patterns="src/**/*.py,**/*.md",  # Only include Python and Markdown files
    ignore_patterns="test/**,*.log,__pycache__/**",  # Exclude test files and logs
    top_files_length=15  # Show top 15 largest files in metrics
)

result = repomix_tool.execute(action)

if not result.error:
    print(f"Successfully packed {result.directory}")
    print(f"Output size: {len(result.output)} characters")
else:
    print(f"Error: {result.error_message}")
```

### Integration with OpenHands Agent

```python
from openhands.sdk import Agent, LLM
from openhands.tools import BashTool, FileEditorTool, RepomixTool

# Create tools including repomix
tools = [
    BashTool.create(working_dir="/workspace"),
    FileEditorTool.create(),
    RepomixTool.create(),
]

# Create agent with tools
agent = Agent(llm=llm, tools=tools)

# The agent can now use repomix to analyze codebases
```

## Parameters

### PackCodebaseAction

- **directory** (required): Absolute path to the directory to pack
- **compress** (optional, default: False): Enable Tree-sitter compression to extract essential code signatures and structure while removing implementation details
- **include_patterns** (optional): Comma-separated fast-glob patterns for files to include (e.g., `"**/*.{js,ts}"`, `"src/**,docs/**"`)
- **ignore_patterns** (optional): Comma-separated fast-glob patterns for files to exclude (e.g., `"test/**,*.spec.js"`, `"node_modules/**,dist/**"`)
- **top_files_length** (optional, default: 10): Number of largest files by size to display in the metrics summary

## Requirements

This tool requires repomix to be available via npx. The tool automatically handles installation using `npx -y repomix` when needed.

### System Requirements

- Node.js and npm/npx installed
- Internet connection for initial repomix installation

## Output Format

The tool returns a `PackCodebaseObservation` containing:

- **output**: The packed codebase content in XML format
- **directory**: The directory that was packed
- **output_id**: Optional ID for future reference (if supported by repomix version)
- **error**: Boolean indicating if there was an error
- **error_message**: Error details if an error occurred

## Error Handling

The tool handles various error conditions:

- Directory not found
- Permission issues
- MCP server connection problems
- Repomix execution errors

All errors are captured in the observation's `error` and `error_message` fields.

## Source and Attribution

This tool is based on the repomix MCP server implementation:

- **Repomix Website**: https://repomix.com/
- **Repomix Repository**: https://github.com/yamadashy/repomix
- **MCP Server Guide**: https://repomix.com/guide/mcp-server

## License

This tool wrapper is part of the OpenHands project. The underlying repomix tool has its own license terms - please refer to the [repomix repository](https://github.com/yamadashy/repomix) for details.
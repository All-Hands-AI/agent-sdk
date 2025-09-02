"""Convert function calling messages to non-function calling messages and vice versa.  # noqa

This will inject prompts so that models that doesn't support function calling
can still be used with function calling agents.

We follow format from: https://docs.litellm.ai/docs/completion/function_call
"""  # noqa

# noqa
import copy  # noqa
import json  # noqa
import re  # noqa
import sys  # noqa
from typing import Iterable, Literal, NotRequired, TypedDict, cast  # noqa

# noqa
from litellm import ChatCompletionToolParam, ChatCompletionToolParamFunctionChunk  # noqa

# noqa
from openhands.core.llm.exceptions import (  # noqa
    FunctionCallConversionError,
    FunctionCallValidationError,
)


# noqa
# noqa
class CacheControl(TypedDict):
    type: Literal["ephemeral"]


# noqa
# noqa
class TextPart(TypedDict):
    type: Literal["text"]
    text: str
    cache_control: NotRequired[CacheControl]


# noqa
# noqa
Content = str | list[TextPart]  # noqa
# noqa
EXECUTE_BASH_TOOL_NAME = "execute_bash"  # noqa
STR_REPLACE_EDITOR_TOOL_NAME = "str_replace_editor"  # noqa
BROWSER_TOOL_NAME = "browser"  # noqa
FINISH_TOOL_NAME = "finish"  # noqa
LLM_BASED_EDIT_TOOL_NAME = "edit_file"  # noqa
TASK_TRACKER_TOOL_NAME = "task_tracker"  # noqa
# noqa
# Inspired by: https://docs.together.ai/docs/llama-3-function-calling#function-calling-w-llama-31-70b # noqa  # noqa
SYSTEM_PROMPT_SUFFIX_TEMPLATE = """  # noqa
You have access to the following functions:

{description}

If you choose to call a function ONLY reply in the following format with NO suffix:

<function=example_function_name>
<parameter=example_parameter_1>value_1</parameter>
<parameter=example_parameter_2>
This is the value for the second parameter
that can span
multiple lines
</parameter>
</function>

<IMPORTANT>
Reminder:
- Function calls MUST follow the specified format, start with <function= and end with </function>  # noqa
- Required parameters MUST be specified
- Only call one function at a time
- You may provide optional reasoning for your function call in natural language BEFORE the function call, but NOT after.
- If there is no function call available, answer the question like normal with your current knowledge and do not tell the user about function calls
</IMPORTANT>
"""  # noqa
# noqa
STOP_WORDS = ["</function"]  # noqa


# noqa
# noqa
def refine_prompt(prompt: str) -> str:  # noqa
    if sys.platform == "win32":  # noqa
        return prompt.replace("bash", "powershell")  # noqa
    return prompt  # noqa


# noqa
# noqa
# NOTE: we need to make sure these examples are always in-sync with the tool interface designed in openhands/agenthub/codeact_agent/function_calling.py # noqa  # noqa
# noqa
# Example snippets for each tool  # noqa
TOOL_EXAMPLES = {  # noqa
    "execute_bash": {
        "check_dir": """
ASSISTANT: Sure! Let me first check the current directory:
<function=execute_bash>
<parameter=command>
pwd && ls
</parameter>
</function>

USER: EXECUTION RESULT of [execute_bash]:
/workspace
openhands@runtime:~/workspace$
""",  # noqa
        "run_server": """
ASSISTANT:
Let me run the Python file for you:
<function=execute_bash>
<parameter=command>
python3 app.py > server.log 2>&1 &
</parameter>
</function>

USER: EXECUTION RESULT of [execute_bash]:
[1] 121
[1]+  Exit 1                  python3 app.py > server.log 2>&1

ASSISTANT:
Looks like the server was running with PID 121 then crashed. Let me check the server log:
<function=execute_bash>
<parameter=command>
cat server.log
</parameter>
</function>

USER: EXECUTION RESULT of [execute_bash]:
Traceback (most recent call last):
  File "/workspace/app.py", line 2, in <module>
    from flask import Flask
ModuleNotFoundError: No module named 'flask'

ASSISTANT:
Looks like the server crashed because the `flask` module is not installed. Let me install the `flask` module for you:
<function=execute_bash>
<parameter=command>
pip3 install flask
</parameter>
</function>

USER: EXECUTION RESULT of [execute_bash]:
Defaulting to user installation because normal site-packages is not writeable
Collecting flask
  Using cached flask-3.0.3-py3-none-any.whl (101 kB)
Collecting blinker>=1.6.2
  Using cached blinker-1.7.0-py3-none-any.whl (13 kB)
Collecting Werkzeug>=3.0.0
  Using cached werkzeug-3.0.2-py3-none-any.whl (226 kB)
Collecting click>=8.1.3
  Using cached click-8.1.7-py3-none-any.whl (97 kB)
Collecting itsdangerous>=2.1.2
  Using cached itsdangerous-2.2.0-py3-none-any.whl (16 kB)
Requirement already satisfied: Jinja2>=3.1.2 in /home/openhands/.local/lib/python3.10/site-packages (from flask) (3.1.3)  # noqa
Requirement already satisfied: MarkupSafe>=2.0 in /home/openhands/.local/lib/python3.10/site-packages (from Jinja2>=3.1.2->flask) (2.1.5)  # noqa
Installing collected packages: Werkzeug, itsdangerous, click, blinker, flask
Successfully installed Werkzeug-3.0.2 blinker-1.7.0 click-8.1.7 flask-3.0.3 itsdangerous-2.2.0

ASSISTANT:
The `flask` module is installed successfully. Let me run the Python file again:
<function=execute_bash>
<parameter=command>
python3 app.py > server.log 2>&1 &
</parameter>
</function>

USER: EXECUTION RESULT of [execute_bash]:
[1] 124

ASSISTANT:
Let me check the server log again:
<function=execute_bash>
<parameter=command>
cat server.log
</parameter>
</function>

USER: EXECUTION RESULT of [execute_bash]:
* Serving Flask app 'app'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit

ASSISTANT:
The server is running on port 5000 with PID 124. You can access the list of numbers by visiting http://127.0.0.1:5000. If you have any further questions, feel free to ask!
""",  # noqa
        "kill_server": """
USER: Now kill the server, make it display the numbers in a table format.

ASSISTANT:
Sure! Let me stop the server first:
<function=execute_bash>
<parameter=command>
kill 124
</parameter>
</function>

USER: EXECUTION RESULT of [execute_bash]:
[1]+  Terminated              python3 app.py > server.log 2>&1
""",  # noqa
        "run_server_again": """
ASSISTANT:
Running the updated file:
<function=execute_bash>
<parameter=command>
python3 app.py > server.log 2>&1 &
</parameter>
</function>

USER: EXECUTION RESULT of [execute_bash]:
[1] 126

ASSISTANT:
The server is running on port 5000 with PID 126. You can access the list of numbers in a table format by visiting http://127.0.0.1:5000.
""",  # noqa
    },
    "str_replace_editor": {
        "create_file": """
ASSISTANT:
There is no `app.py` file in the current directory. Let me create a Python file `app.py`:
<function=str_replace_editor>
<parameter=command>create</parameter>
<parameter=path>/workspace/app.py</parameter>
<parameter=file_text>
from flask import Flask
app = Flask(__name__)

@app.route('/')
def index():
    numbers = list(range(1, 11))
    return str(numbers)

if __name__ == '__main__':
    app.run(port=5000)
</parameter>
</function>

USER: EXECUTION RESULT of [str_replace_editor]:
File created successfully at: /workspace/app.py
""",  # noqa
        "edit_file": """
ASSISTANT:
Now let me display the numbers in a table format:
<function=str_replace_editor>
<parameter=command>str_replace</parameter>
<parameter=path>/workspace/app.py</parameter>
<parameter=old_str>return str(numbers)</parameter>
<parameter=new_str>return '<table>' + ''.join([f'<tr><td>{i}</td></tr>' for i in numbers]) + '</table>'</parameter>  # noqa
</function>

USER: EXECUTION RESULT of [str_replace_editor]:
The file /workspace/app.py has been edited. Here's the result of running `cat -n` on a snippet of /workspace/app.py:
     3
     4  @app.route('/')
     5  def index():
     6      numbers = list(range(1, 11))
     7      return '<table>' + ''.join([f'<tr><td>{i}</td></tr>' for i in numbers]) + '</table>'  # noqa
     8
     9  if __name__ == '__main__':
    10      app.run(port=5000)
Review the changes and make sure they are as expected. Edit the file again if necessary.

""",  # noqa
    },
    "browser": {
        "view_page": """
ASSISTANT:
Let me check how the page looks in the browser:
<function=browser>
<parameter=code>
goto('http://127.0.0.1:5000')
noop(1000)  # Wait for page to load
</parameter>
</function>

USER: EXECUTION RESULT of [browser]:
[Browser shows the numbers in a table format]
"""  # noqa
    },
    "edit_file": {
        "create_file": """
ASSISTANT: There is no `app.py` file in the current directory. Let me create a Python file `app.py`:
<function=edit_file>
<parameter=path>/workspace/app.py</parameter>
<parameter=start>1</parameter>
<parameter=end>-1</parameter>
<parameter=content>
from flask import Flask
app = Flask(__name__)

@app.route('/')
def index():
    numbers = list(range(1, 11))
    return str(numbers)

if __name__ == '__main__':
    app.run(port=5000)
</parameter>
</function>

USER: EXECUTION RESULT of [edit_file]:
File created successfully at: /workspace/app.py
""",  # noqa
        "edit_file": """
ASSISTANT:
Now let me display the numbers in a table format:
<function=edit_file>
<parameter=path>/workspace/app.py</parameter>
<parameter=start>6</parameter>
<parameter=end>9</parameter>
<parameter=content>
    numbers = list(range(1, 11))
    return '<table>' + ''.join([f'<tr><td>{i}</td></tr>' for i in numbers]) + '</table>'
    # ... existing code ...
if __name__ == '__main__':
</parameter>
</function>

USER: EXECUTION RESULT of [edit_file]:
The file /workspace/app.py has been edited. Here's the result of running `cat -n` on a snippet of /workspace/app.py:
     3
     4  @app.route('/')
     5  def index():
     6      numbers = list(range(1, 11))
     7      return '<table>' + ''.join([f'<tr><td>{i}</td></tr>' for i in numbers]) + '</table>'  # noqa
     8
     9  if __name__ == '__main__':
    10      app.run(port=5000)
Review the changes and make sure they are as expected. Edit the file again if necessary.
""",  # noqa
    },
    "finish": {
        "example": """
ASSISTANT:
The server is running on port 5000 with PID 126. You can access the list of numbers in a table format by visiting http://127.0.0.1:5000. Let me know if you have any further requests!  # noqa
<function=finish>
<parameter=message>The task has been completed. The web server is running and displaying numbers 1-10 in a table format at http://127.0.0.1:5000.</parameter>  # noqa
</function>
"""  # noqa
    },
}


# noqa
# noqa
def get_example_for_tools(tools: list[ChatCompletionToolParam]) -> str:  # noqa
    """Generate an in-context learning example based on available tools."""  # noqa
    available_tools = set()
    for tool in tools:
        if tool["type"] == "function":
            name = tool["function"]["name"]
            if name == EXECUTE_BASH_TOOL_NAME:
                available_tools.add("execute_bash")
            elif name == STR_REPLACE_EDITOR_TOOL_NAME:
                available_tools.add("str_replace_editor")
            elif name == BROWSER_TOOL_NAME:
                available_tools.add("browser")
            elif name == FINISH_TOOL_NAME:
                available_tools.add("finish")
            elif name == LLM_BASED_EDIT_TOOL_NAME:
                available_tools.add("edit_file")

    if not available_tools:
        return ""

    example = """Here's a running example of how to perform a task with the provided tools. # noqa  # noqa
  # noqa
--------------------- START OF EXAMPLE ---------------------
  # noqa
USER: Create a list of numbers from 1 to 10, and display them in a web page at port 5000.
  # noqa
"""  # noqa

    # Build example based on available tools
    if "execute_bash" in available_tools:
        example += TOOL_EXAMPLES["execute_bash"]["check_dir"]

    if "str_replace_editor" in available_tools:
        example += TOOL_EXAMPLES["str_replace_editor"]["create_file"]
    elif "edit_file" in available_tools:
        example += TOOL_EXAMPLES["edit_file"]["create_file"]

    if "execute_bash" in available_tools:
        example += TOOL_EXAMPLES["execute_bash"]["run_server"]

    if "browser" in available_tools:
        example += TOOL_EXAMPLES["browser"]["view_page"]

    if "execute_bash" in available_tools:
        example += TOOL_EXAMPLES["execute_bash"]["kill_server"]

    if "str_replace_editor" in available_tools:
        example += TOOL_EXAMPLES["str_replace_editor"]["edit_file"]
    elif "edit_file" in available_tools:
        example += TOOL_EXAMPLES["edit_file"]["edit_file"]

    if "execute_bash" in available_tools:
        example += TOOL_EXAMPLES["execute_bash"]["run_server_again"]

    if "finish" in available_tools:
        example += TOOL_EXAMPLES["finish"]["example"]

    example += """  # noqa
--------------------- END OF EXAMPLE ---------------------
  # noqa
Do NOT assume the environment is the same as in the example above.
  # noqa
--------------------- NEW TASK DESCRIPTION ---------------------
"""  # noqa
    example = example.lstrip()

    return refine_prompt(example)


IN_CONTEXT_LEARNING_EXAMPLE_PREFIX = get_example_for_tools

IN_CONTEXT_LEARNING_EXAMPLE_SUFFIX = """  # noqa
--------------------- END OF NEW TASK DESCRIPTION ---------------------
  # noqa
PLEASE follow the format strictly! PLEASE EMIT ONE AND ONLY ONE FUNCTION CALL PER MESSAGE.
"""  # noqa

# Regex patterns for function call parsing
FN_REGEX_PATTERN = r"<function=([^>]+)>\n(.*?)</function>"
FN_PARAM_REGEX_PATTERN = r"<parameter=([^>]+)>(.*?)</parameter>"

# Add new regex pattern for tool execution results
TOOL_RESULT_REGEX_PATTERN = r"EXECUTION RESULT of \[(.*?)\]:\n(.*)"


def convert_tool_call_to_string(tool_call: dict) -> str:
    """Convert tool call to content in string format."""  # noqa
    if "function" not in tool_call:  # noqa
        raise FunctionCallConversionError("Tool call must contain 'function' key.")  # noqa
    if "id" not in tool_call:  # noqa
        raise FunctionCallConversionError("Tool call must contain 'id' key.")  # noqa
    if "type" not in tool_call:  # noqa
        raise FunctionCallConversionError("Tool call must contain 'type' key.")  # noqa
    if tool_call["type"] != "function":  # noqa
        raise FunctionCallConversionError("Tool call type must be 'function'.")  # noqa
    # noqa
    ret = f"<function={tool_call['function']['name']}>\n"  # noqa
    try:
        args = json.loads(tool_call["function"]["arguments"])  # noqa
    except json.JSONDecodeError as e:
        raise FunctionCallConversionError(  # noqa
            f"Failed to parse arguments as JSON. Arguments: {tool_call['function']['arguments']}"  # noqa  # noqa
        ) from e
    for param_name, param_value in args.items():
        is_multiline = isinstance(param_value, str) and "\n" in param_value  # noqa
        ret += f"<parameter={param_name}>"  # noqa
        if is_multiline:  # noqa
            ret += "\n"  # noqa
        if isinstance(param_value, list) or isinstance(param_value, dict):  # noqa
            ret += json.dumps(param_value)  # noqa
        else:
            ret += f"{param_value}"  # noqa
        if is_multiline:  # noqa
            ret += "\n"  # noqa
        ret += "</parameter>\n"  # noqa
    ret += "</function>"  # noqa
    return ret  # noqa


# noqa
# noqa
def convert_tools_to_description(tools: list[ChatCompletionToolParam]) -> str:  # noqa
    ret = ""  # noqa
    for i, tool in enumerate(tools):
        assert tool["type"] == "function"  # noqa
        fn = tool["function"]  # noqa
        if i > 0:  # noqa
            ret += "\n"  # noqa
        ret += f"---- BEGIN FUNCTION #{i + 1}: {fn['name']} ----\n"  # noqa
        if "description" in fn:  # noqa
            ret += f"Description: {fn['description']}\n"  # noqa
        # noqa
        if "parameters" in fn:  # noqa
            ret += "Parameters:\n"  # noqa
            properties = fn["parameters"].get("properties", {})  # noqa
            required_params = set(fn["parameters"].get("required", []))  # noqa
            # noqa
            for j, (param_name, param_info) in enumerate(properties.items()):
                # Indicate required/optional in parentheses with type  # noqa
                is_required = param_name in required_params  # noqa
                param_status = "required" if is_required else "optional"  # noqa
                param_type = param_info.get("type", "string")  # noqa
                # noqa
                # Get parameter description  # noqa
                desc = param_info.get("description", "No description provided")  # noqa
                # noqa
                # Handle enum values if present  # noqa
                if "enum" in param_info:  # noqa
                    enum_values = ", ".join(f"`{v}`" for v in param_info["enum"])  # noqa
                    desc += f"\nAllowed values: [{enum_values}]"  # noqa
                # noqa
                ret += (  # noqa
                    f"  ({j + 1}) {param_name} ({param_type}, {param_status}): {desc}\n"  # noqa
                )
        else:
            ret += "No parameters are required for this function.\n"  # noqa
        # noqa
        ret += f"---- END FUNCTION #{i + 1} ----\n"  # noqa
    return ret  # noqa


# noqa
# noqa
def convert_fncall_messages_to_non_fncall_messages(  # noqa
    messages: list[dict],
    tools: list[ChatCompletionToolParam],
    add_in_context_learning_example: bool = True,  # noqa
) -> list[dict]:
    """Convert function calling messages to non-function calling messages."""  # noqa
    messages = copy.deepcopy(messages)

    formatted_tools = convert_tools_to_description(tools)
    system_prompt_suffix = SYSTEM_PROMPT_SUFFIX_TEMPLATE.format(
        description=formatted_tools
    )

    converted_messages = []
    first_user_message_encountered = False
    for message in messages:
        role = message["role"]
        content: Content = message["content"]

        # 1. SYSTEM MESSAGES
        # append system prompt suffix to content
        if role == "system":
            if isinstance(content, str):
                content += system_prompt_suffix
            elif isinstance(content, list):
                if content and content[-1]["type"] == "text":
                    content[-1]["text"] += system_prompt_suffix
                else:
                    content.append({"type": "text", "text": system_prompt_suffix})
            else:
                raise FunctionCallConversionError(
                    f"Unexpected content type {type(content)}. Expected str or list. Content: {content}"  # noqa
                )
            converted_messages.append({"role": "system", "content": content})

        # 2. USER MESSAGES (no change)
        elif role == "user":
            # Add in-context learning example for the first user message
            if not first_user_message_encountered and add_in_context_learning_example:
                first_user_message_encountered = True

                # Generate example based on available tools
                example = IN_CONTEXT_LEARNING_EXAMPLE_PREFIX(tools)

                # Add example if we have any tools
                if example:
                    # add in-context learning example
                    if isinstance(content, str):
                        content = example + content + IN_CONTEXT_LEARNING_EXAMPLE_SUFFIX
                    elif isinstance(content, list):
                        if content and content[0]["type"] == "text":
                            content[0]["text"] = (
                                example
                                + content[0]["text"]
                                + IN_CONTEXT_LEARNING_EXAMPLE_SUFFIX
                            )
                        else:
                            content = (
                                [
                                    cast(
                                        TextPart,
                                        {
                                            "type": "text",
                                            "text": example,
                                        },
                                    )
                                ]
                                + content
                                + [
                                    cast(
                                        TextPart,
                                        {
                                            "type": "text",
                                            "text": IN_CONTEXT_LEARNING_EXAMPLE_SUFFIX,
                                        },
                                    )
                                ]
                            )
                    else:
                        raise FunctionCallConversionError(
                            f"Unexpected content type {type(content)}. Expected str or list. Content: {content}"  # noqa
                        )
            converted_messages.append(
                {
                    "role": "user",
                    "content": content,
                }
            )

        # 3. ASSISTANT MESSAGES
        # - 3.1 no change if no function call
        # - 3.2 change if function call
        elif role == "assistant":
            if "tool_calls" in message and message["tool_calls"] is not None:
                if len(message["tool_calls"]) != 1:
                    raise FunctionCallConversionError(
                        f"Expected exactly one tool call in the message. More than one tool call is not supported. But got {len(message['tool_calls'])} tool calls. Content: {content}"  # noqa
                    )
                try:
                    tool_content = convert_tool_call_to_string(message["tool_calls"][0])
                except FunctionCallConversionError as e:
                    raise FunctionCallConversionError(
                        f"Failed to convert tool call to string.\nCurrent tool call: {message['tool_calls'][0]}.\nRaw messages: {json.dumps(messages, indent=2)}"  # noqa
                    ) from e
                if isinstance(content, str):
                    content += "\n\n" + tool_content
                    content = content.lstrip()
                elif isinstance(content, list):
                    if content and content[-1]["type"] == "text":
                        content[-1]["text"] += "\n\n" + tool_content
                        content[-1]["text"] = content[-1]["text"].lstrip()
                    else:
                        content.append({"type": "text", "text": tool_content})
                else:
                    raise FunctionCallConversionError(
                        f"Unexpected content type {type(content)}. Expected str or list. Content: {content}"  # noqa
                    )
            converted_messages.append({"role": "assistant", "content": content})

        # 4. TOOL MESSAGES (tool outputs)
        elif role == "tool":
            # Convert tool result as user message
            tool_name = message.get("name", "function")
            prefix = f"EXECUTION RESULT of [{tool_name}]:\n"
            # and omit "tool_call_id" AND "name"
            if isinstance(content, str):
                content = prefix + content
            elif isinstance(content, list):
                if content and (
                    first_text_content := next(
                        (c for c in content if c["type"] == "text"), None
                    )
                ):
                    first_text_content["text"] = prefix + first_text_content["text"]
                else:
                    content = [
                        cast(TextPart, {"type": "text", "text": prefix})
                    ] + content

                if "cache_control" in message:
                    content[-1]["cache_control"] = cast(
                        CacheControl, {"type": "ephemeral"}
                    )
            else:
                raise FunctionCallConversionError(
                    f"Unexpected content type {type(content)}. Expected str or list. Content: {content}"  # noqa
                )

            converted_messages.append({"role": "user", "content": content})
        else:
            raise FunctionCallConversionError(
                f"Unexpected role {role}. Expected system, user, assistant or tool."
            )
    return converted_messages


def _extract_and_validate_params(
    matching_tool: ChatCompletionToolParamFunctionChunk,
    param_matches: Iterable[re.Match],
    fn_name: str,
) -> dict:
    params = {}
    # Parse and validate parameters
    required_params = set()
    if "parameters" in matching_tool and "required" in matching_tool["parameters"]:
        required_params = set(matching_tool["parameters"].get("required", []))

    allowed_params = set()
    if "parameters" in matching_tool and "properties" in matching_tool["parameters"]:
        allowed_params = set(matching_tool["parameters"]["properties"].keys())

    param_name_to_type = {}
    if "parameters" in matching_tool and "properties" in matching_tool["parameters"]:
        param_name_to_type = {
            name: val.get("type", "string")
            for name, val in matching_tool["parameters"]["properties"].items()
        }

    # Collect parameters
    found_params = set()
    for param_match in param_matches:
        param_name = param_match.group(1)
        param_value = param_match.group(2)

        # Validate parameter is allowed
        if allowed_params and param_name not in allowed_params:
            raise FunctionCallValidationError(
                f"Parameter '{param_name}' is not allowed for function '{fn_name}'. Allowed parameters: {allowed_params}"  # noqa
            )

        # Validate and convert parameter type
        # supported: string, integer, array
        if param_name in param_name_to_type:
            if param_name_to_type[param_name] == "integer":
                try:
                    param_value = int(param_value)
                except ValueError:
                    raise FunctionCallValidationError(
                        f"Parameter '{param_name}' is expected to be an integer."
                    )
            elif param_name_to_type[param_name] == "array":
                try:
                    param_value = json.loads(param_value)
                except json.JSONDecodeError:
                    raise FunctionCallValidationError(
                        f"Parameter '{param_name}' is expected to be an array."
                    )
            else:
                # string
                pass

        # Enum check
        if (
            "parameters" in matching_tool
            and "enum" in matching_tool["parameters"]["properties"][param_name]
        ):
            if (
                param_value
                not in matching_tool["parameters"]["properties"][param_name]["enum"]
            ):
                raise FunctionCallValidationError(
                    f"Parameter '{param_name}' is expected to be one of {matching_tool['parameters']['properties'][param_name]['enum']}."  # noqa
                )

        params[param_name] = param_value
        found_params.add(param_name)

    # Check all required parameters are present
    missing_params = required_params - found_params
    if missing_params:
        raise FunctionCallValidationError(
            f"Missing required parameters for function '{fn_name}': {missing_params}"
        )
    return params


def _fix_stopword(content: str) -> str:
    """Fix the issue when some LLM would NOT return the stopword."""  # noqa
    if "<function=" in content and content.count("<function=") == 1:  # noqa
        if content.endswith("</"):  # noqa
            content = content.rstrip() + "function>"  # noqa
        else:
            content = content + "\n</function>"  # noqa
    return content  # noqa


# noqa
# noqa
def _normalize_parameter_tags(fn_body: str) -> str:  # noqa
    """Normalize malformed parameter tags to the canonical format.  # noqa

    Some models occasionally emit malformed parameter tags like:
        <parameter=command=str_replace</parameter>
    instead of the correct:
        <parameter=command>str_replace</parameter>

    This function rewrites the malformed form into the correct one to allow
    downstream parsing to succeed.
    """  # noqa
    # Replace '<parameter=name=value</parameter>' with '<parameter=name>value</parameter>' # noqa  # noqa
    return re.sub(  # noqa
        r"<parameter=([a-zA-Z0-9_]+)=([^<]*)</parameter>",  # noqa
        r"<parameter=\1>\2</parameter>",  # noqa
        fn_body,
    )


# noqa
# noqa
def convert_non_fncall_messages_to_fncall_messages(  # noqa
    messages: list[dict],
    tools: list[ChatCompletionToolParam],
) -> list[dict]:
    """Convert non-function calling messages back to function calling messages."""  # noqa
    messages = copy.deepcopy(messages)
    formatted_tools = convert_tools_to_description(tools)
    system_prompt_suffix = SYSTEM_PROMPT_SUFFIX_TEMPLATE.format(
        description=formatted_tools
    )

    converted_messages = []
    tool_call_counter = 1  # Counter for tool calls

    first_user_message_encountered = False
    for message in messages:
        role, content = message["role"], message["content"]
        content = content or ""  # handle cases where content is None
        # For system messages, remove the added suffix
        if role == "system":
            if isinstance(content, str):
                # Remove the suffix if present
                content = content.split(system_prompt_suffix)[0]
            elif isinstance(content, list):
                if content and content[-1]["type"] == "text":
                    # Remove the suffix from the last text item
                    content[-1]["text"] = content[-1]["text"].split(
                        system_prompt_suffix
                    )[0]
            converted_messages.append({"role": "system", "content": content})
        # Skip user messages (no conversion needed)
        elif role == "user":
            # Check & replace in-context learning example
            if not first_user_message_encountered:
                first_user_message_encountered = True
                if isinstance(content, str):
                    # Remove any existing example
                    if content.startswith(IN_CONTEXT_LEARNING_EXAMPLE_PREFIX(tools)):
                        content = content.replace(
                            IN_CONTEXT_LEARNING_EXAMPLE_PREFIX(tools), "", 1
                        )
                    if content.endswith(IN_CONTEXT_LEARNING_EXAMPLE_SUFFIX):
                        content = content.replace(
                            IN_CONTEXT_LEARNING_EXAMPLE_SUFFIX, "", 1
                        )
                elif isinstance(content, list):
                    for item in content:
                        if item["type"] == "text":
                            # Remove any existing example
                            example = IN_CONTEXT_LEARNING_EXAMPLE_PREFIX(tools)
                            if item["text"].startswith(example):
                                item["text"] = item["text"].replace(example, "", 1)
                            if item["text"].endswith(
                                IN_CONTEXT_LEARNING_EXAMPLE_SUFFIX
                            ):
                                item["text"] = item["text"].replace(
                                    IN_CONTEXT_LEARNING_EXAMPLE_SUFFIX, "", 1
                                )
                else:
                    raise FunctionCallConversionError(
                        f"Unexpected content type {type(content)}. Expected str or list. Content: {content}"  # noqa
                    )

            # Check for tool execution result pattern
            if isinstance(content, str):
                tool_result_match = re.search(
                    TOOL_RESULT_REGEX_PATTERN, content, re.DOTALL
                )
            elif isinstance(content, list):
                tool_result_match = next(
                    (
                        _match
                        for item in content
                        if item.get("type") == "text"
                        and (
                            _match := re.search(
                                TOOL_RESULT_REGEX_PATTERN, item["text"], re.DOTALL
                            )
                        )
                    ),
                    None,
                )
            else:
                raise FunctionCallConversionError(
                    f"Unexpected content type {type(content)}. Expected str or list. Content: {content}"  # noqa
                )

            if tool_result_match:
                if isinstance(content, list):
                    text_content_items = [
                        item for item in content if item.get("type") == "text"
                    ]
                    if not text_content_items:
                        raise FunctionCallConversionError(
                            f"Could not find text content in message with tool result. Content: {content}"  # noqa
                        )
                elif not isinstance(content, str):
                    raise FunctionCallConversionError(
                        f"Unexpected content type {type(content)}. Expected str or list. Content: {content}"  # noqa
                    )

                tool_name = tool_result_match.group(1)
                tool_result = tool_result_match.group(2).strip()

                # Convert to tool message format
                converted_messages.append(
                    {
                        "role": "tool",
                        "name": tool_name,
                        "content": [{"type": "text", "text": tool_result}]
                        if isinstance(content, list)
                        else tool_result,
                        "tool_call_id": f"toolu_{tool_call_counter - 1:02d}",  # Use last generated ID  # noqa
                    }
                )
            else:
                converted_messages.append({"role": "user", "content": content})

        # Handle assistant messages
        elif role == "assistant":
            if isinstance(content, str):
                content = _fix_stopword(content)
                fn_match = re.search(FN_REGEX_PATTERN, content, re.DOTALL)
            elif isinstance(content, list):
                if content and content[-1]["type"] == "text":
                    content[-1]["text"] = _fix_stopword(content[-1]["text"])
                    fn_match = re.search(
                        FN_REGEX_PATTERN, content[-1]["text"], re.DOTALL
                    )
                else:
                    fn_match = None
                fn_match_exists = any(
                    item.get("type") == "text"
                    and re.search(FN_REGEX_PATTERN, item["text"], re.DOTALL)
                    for item in content
                )
                if fn_match_exists and not fn_match:
                    raise FunctionCallConversionError(
                        f"Expecting function call in the LAST index of content list. But got content={content}"  # noqa
                    )
            else:
                raise FunctionCallConversionError(
                    f"Unexpected content type {type(content)}. Expected str or list. Content: {content}"  # noqa
                )

            if fn_match:
                fn_name = fn_match.group(1)
                fn_body = _normalize_parameter_tags(fn_match.group(2))
                matching_tool: ChatCompletionToolParamFunctionChunk | None = next(
                    (
                        tool["function"]
                        for tool in tools
                        if tool["type"] == "function"
                        and tool["function"]["name"] == fn_name
                    ),
                    None,
                )
                # Validate function exists in tools
                if not matching_tool:
                    raise FunctionCallValidationError(
                        f"Function '{fn_name}' not found in available tools: {[tool['function']['name'] for tool in tools if tool['type'] == 'function']}"  # noqa
                    )

                # Parse parameters
                param_matches = re.finditer(FN_PARAM_REGEX_PATTERN, fn_body, re.DOTALL)
                params = _extract_and_validate_params(
                    matching_tool, param_matches, fn_name
                )

                # Create tool call with unique ID
                tool_call_id = f"toolu_{tool_call_counter:02d}"
                tool_call = {
                    "index": 1,  # always 1 because we only support **one tool call per message**  # noqa
                    "id": tool_call_id,
                    "type": "function",
                    "function": {"name": fn_name, "arguments": json.dumps(params)},
                }
                tool_call_counter += 1  # Increment counter

                # Remove the function call part from content
                if isinstance(content, list):
                    assert content and content[-1]["type"] == "text"
                    content[-1]["text"] = (
                        content[-1]["text"].split("<function=")[0].strip()
                    )
                elif isinstance(content, str):
                    content = content.split("<function=")[0].strip()
                else:
                    raise FunctionCallConversionError(
                        f"Unexpected content type {type(content)}. Expected str or list. Content: {content}"  # noqa
                    )

                converted_messages.append(
                    {"role": "assistant", "content": content, "tool_calls": [tool_call]}
                )
            else:
                # No function call, keep message as is
                converted_messages.append(message)

        else:
            raise FunctionCallConversionError(
                f"Unexpected role {role}. Expected system, user, or assistant in non-function calling messages."  # noqa
            )
    return converted_messages


def convert_from_multiple_tool_calls_to_single_tool_call_messages(
    messages: list[dict],
    ignore_final_tool_result: bool = False,
) -> list[dict]:
    """Break one message with multiple tool calls into multiple messages."""  # noqa
    converted_messages = []  # noqa
    # noqa
    pending_tool_calls: dict[str, dict] = {}  # noqa
    for message in messages:
        role: str
        content: Content
        role, content = message["role"], message["content"]  # noqa
        if role == "assistant":  # noqa
            if message.get("tool_calls") and len(message["tool_calls"]) > 1:  # noqa
                # handle multiple tool calls by breaking them into multiple messages  # noqa
                for i, tool_call in enumerate(message["tool_calls"]):
                    pending_tool_calls[tool_call["id"]] = {  # noqa
                        "role": "assistant",
                        "content": content if i == 0 else "",  # noqa
                        "tool_calls": [tool_call],
                    }
            else:
                converted_messages.append(message)
        elif role == "tool":  # noqa
            if message["tool_call_id"] in pending_tool_calls:  # noqa
                # remove the tool call from the pending list  # noqa
                _tool_call_message = pending_tool_calls.pop(message["tool_call_id"])  # noqa
                converted_messages.append(_tool_call_message)
                # add the tool result  # noqa
                converted_messages.append(message)
            else:
                assert len(pending_tool_calls) == 0, (  # noqa
                    f"Found pending tool calls but not found in pending list: {pending_tool_calls=}"  # noqa  # noqa
                )
                converted_messages.append(message)
        else:
            assert len(pending_tool_calls) == 0, (  # noqa
                f"Found pending tool calls but not expect to handle it with role {role}: {pending_tool_calls=}, {message=}"  # noqa  # noqa
            )
            converted_messages.append(message)
    # noqa
    if not ignore_final_tool_result and len(pending_tool_calls) > 0:  # noqa
        raise FunctionCallConversionError(  # noqa
            f"Found pending tool calls but no tool result: {pending_tool_calls=}"  # noqa
        )
    return converted_messages  # noqa

# Pause Conversation Examples

This directory contains examples demonstrating the pause/resume functionality of the OpenHands agent-sdk conversation system.

## Examples

### 1. `simple_pause_example.py`
A minimal example that closely follows the user's sample script pattern:
- Runs an agent in a background thread
- Sends periodic encouraging messages
- Handles Ctrl+C to pause the conversation
- Allows resuming after pause

### 2. `pause_conversation_example.py`
A more comprehensive example that demonstrates:
- Complete pause/resume workflow
- Proper signal handling
- User interaction for resume/exit choice
- Event callback handling
- Error handling and cleanup

## Usage

1. Set up your environment:
   ```bash
   export LITELLM_API_KEY="your-api-key-here"
   ```

2. Run an example:
   ```bash
   # Simple example
   uv run python examples/simple_pause_example.py
   
   # Comprehensive example
   uv run python examples/pause_conversation_example.py
   ```

3. Interact with the example:
   - Let the agent run normally
   - Press **Ctrl+C** at any time to pause
   - Follow the prompts to resume or exit

## Key Features Demonstrated

- **Thread-safe pause control**: The `conversation.pause()` method can be called from any thread
- **Graceful interruption**: The agent pauses between steps, not during LLM completion
- **Resume capability**: Call `conversation.run()` again to resume from where it left off
- **Signal handling**: Proper Ctrl+C handling using Python's signal module
- **State management**: Using conversation state to track execution status

## How It Works

1. **Background Thread**: The agent runs in a separate thread using `threading.Thread(target=conversation.run)`
2. **Signal Handler**: A signal handler catches Ctrl+C and calls `conversation.pause()`
3. **Pause Flag**: The conversation checks `state.agent_paused` between agent steps
4. **Resume**: Calling `conversation.run()` again resumes execution

## Code Pattern

```python
import signal
import threading

# Set up signal handler
def signal_handler(signum, frame):
    conversation.pause()

signal.signal(signal.SIGINT, signal_handler)

# Run agent in background
thread = threading.Thread(target=conversation.run, daemon=True)
thread.start()

# Monitor and interact
while thread.is_alive():
    # Your monitoring logic here
    time.sleep(1)

# Resume if paused
if paused:
    conversation.run()  # Resume execution
```

This pattern allows CLI applications to provide responsive pause/resume functionality while maintaining thread safety and proper resource management.
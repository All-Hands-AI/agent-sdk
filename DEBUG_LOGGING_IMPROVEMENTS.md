# Debug Logging Improvements for Agent Server

## Summary

Fixed the issue where `DEBUG=1 uv run agent-server --port 9000` wasn't properly showing internal stack traces in logs when errors occurred.

## Changes Made

### 1. Enhanced Exception Handling (`openhands/agent_server/api.py`)
- Added DEBUG mode detection
- Modified exception handlers to include stack traces in responses when DEBUG=1
- Unhandled exceptions now return detailed error information including:
  - Full stack trace
  - Exception message
  - Original error details

### 2. Custom Logging Configuration (`openhands/agent_server/logging_config.py`)
- Created a custom logging configuration for uvicorn
- Ensures proper propagation of log messages
- Sets appropriate log levels based on DEBUG environment variable
- Preserves stack traces in error logs

### 3. Updated Server Entry Point (`openhands/agent_server/__main__.py`)
- Integrated custom logging configuration
- Added visual indicator for DEBUG mode status on startup
- Properly configures uvicorn with debug-aware logging

## Usage

To run the server with debug logging enabled:

```bash
DEBUG=1 uv run agent-server --port 9000
```

When DEBUG=1 is set:
- Server will show "🐛 DEBUG mode: ENABLED" on startup
- All internal errors will include full stack traces in logs
- API error responses will include traceback information (useful for development)

## Benefits

1. **Better Error Visibility**: Full stack traces are now properly logged when errors occur
2. **Development-Friendly**: Error responses include traceback information in DEBUG mode
3. **Production-Safe**: In production (without DEBUG=1), sensitive error details are not exposed
4. **Consistent Logging**: Both application and uvicorn logs follow the same configuration

## Testing

To test that errors are properly logged:

1. Start the server with `DEBUG=1`
2. Make a request that causes an error
3. Check the console output for full stack traces
4. Check the API response for traceback information
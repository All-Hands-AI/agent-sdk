# Web Chat App Example Guide

This guide explains how to run the OpenHands Web Chat App example using the provided scripts.

## Overview

The Web Chat App is a complete web-based interface for interacting with OpenHands agents. It provides:

- **Conversation Management**: Create, manage, and switch between multiple conversations
- **Real-time Chat**: WebSocket-based real-time communication with agents
- **Agent Controls**: Pause, resume, and delete conversations
- **Modern UI**: Clean, responsive web interface with conversation history

## Quick Start

### Prerequisites

1. Make sure you have the development environment set up:
   ```bash
   make build
   ```

2. Ensure you have the required environment variables set (like `OPENAI_API_KEY` or other LLM provider keys).

### Running the Web Chat App

You can run the web chat app using either of the provided scripts:

#### Option 1: Python Script (Recommended)
```bash
python run_web_chat_app.py
# or with uv
uv run python run_web_chat_app.py
```

#### Option 2: Shell Script
```bash
./run_web_chat_app.sh
```

Both scripts will:
- Set up the correct configuration
- Start the OpenHands agent server
- Serve the web interface
- Enable auto-reload for development

### Accessing the Application

Once the server starts, you can access:

- **Web Chat Interface**: http://localhost:8000/static/
- **API Documentation**: http://localhost:8000/docs
- **API Base URL**: http://localhost:8000

## Configuration

The web chat app uses the configuration file located at:
```
examples/server_sdk/webhook/web_chat_app/agent_server_config.json
```

Current configuration:
```json
{
  "static_files_path": "web"
}
```

This tells the server to serve static files from the `web` directory, which contains:
- `index.html` - Main web interface
- `app.js` - JavaScript application logic
- `styles.css` - Styling
- `index-dev.html` & `app-dev.js` - Development versions

## Features

### Conversation Management
- **New Conversation**: Click "New Chat" to start a fresh conversation
- **Conversation List**: View and switch between existing conversations
- **Conversation Controls**: Pause, resume, or delete conversations

### Chat Interface
- **Message Input**: Type messages and press Ctrl+Enter to send
- **Real-time Updates**: See agent responses in real-time via WebSocket
- **Status Indicators**: Connection status and typing indicators
- **Agent Thinking**: Visual feedback when the agent is processing

### Agent Configuration
- **Max Iterations**: Configure how many iterations the agent can perform
- **Initial Message**: Optionally provide a starting message when creating conversations

## Development

### File Structure
```
examples/server_sdk/webhook/web_chat_app/
├── agent_server_config.json    # Server configuration
└── web/                        # Static web files
    ├── index.html              # Main HTML interface
    ├── app.js                  # JavaScript application
    ├── styles.css              # CSS styling
    ├── index-dev.html          # Development HTML
    └── app-dev.js              # Development JavaScript
```

### Customization

To customize the web chat app:

1. **Modify the UI**: Edit files in the `web/` directory
2. **Change Configuration**: Update `agent_server_config.json`
3. **Add Features**: Extend the JavaScript in `app.js`

The server runs with auto-reload enabled, so changes to Python code will automatically restart the server.

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   - The server runs on port 8000 by default
   - Make sure no other services are using this port
   - You can modify the port in the run scripts if needed

2. **Config File Not Found**
   - Make sure you're running the script from the agent-sdk root directory
   - Verify the file exists at `examples/server_sdk/webhook/web_chat_app/agent_server_config.json`

3. **Static Files Not Loading**
   - Check that the `web/` directory exists and contains the HTML/JS/CSS files
   - Verify the `static_files_path` in the config points to the correct directory

4. **WebSocket Connection Issues**
   - Ensure your browser supports WebSockets
   - Check browser console for connection errors
   - Verify the server is running and accessible

### Logs and Debugging

- Server logs will appear in the terminal where you ran the script
- Browser console (F12) shows client-side errors and WebSocket messages
- Use the development versions (`index-dev.html`, `app-dev.js`) for additional debugging

## API Integration

The web chat app communicates with the OpenHands agent server via:

- **REST API**: For conversation management (create, list, delete)
- **WebSocket**: For real-time message exchange
- **Static Files**: Served at `/static/` endpoint

See the API documentation at http://localhost:8000/docs for detailed endpoint information.
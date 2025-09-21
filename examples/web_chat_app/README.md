# OpenHands Web Chat Application

A complete web-based chat interface for the OpenHands agent server, featuring real-time conversation management, WebSocket communication, and a modern HTML5 interface.

## Features

### 🚀 Core Functionality
- **Real-time Chat Interface**: Modern, responsive web UI for chatting with OpenHands agents
- **Conversation Management**: Create, pause, resume, and delete conversations
- **Live Event Streaming**: Real-time updates via WebSocket connections
- **Multi-conversation Support**: Switch between multiple active conversations
- **Agent Status Monitoring**: Visual indicators for agent state (idle, running, paused, error)

### 🎨 User Interface
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Dark Sidebar**: Clean conversation list with status indicators
- **Chat-style Messages**: Familiar messaging interface with timestamps
- **System Event Display**: Visual representation of tool calls, results, and errors
- **Loading States**: Smooth loading indicators and connection status
- **Modal Dialogs**: Intuitive forms for creating new conversations

### 🔧 Technical Features
- **WebSocket Integration**: Real-time bidirectional communication
- **RESTful API**: Full integration with OpenHands agent server API
- **Docker Deployment**: Complete containerized setup
- **CORS Support**: Proper cross-origin resource sharing configuration
- **Error Handling**: Comprehensive error display and recovery
- **Auto-reconnection**: Automatic WebSocket reconnection on connection loss

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Frontend  │    │  Nginx Proxy    │    │  Agent Server   │
│   (HTML/JS/CSS) │◄──►│   (Port 80)     │◄──►│   (Port 8000)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
    Static Files            API Proxy              WebSocket Events
    User Interface         CORS Headers           Conversation Data
```

## Quick Start

### Prerequisites
- Docker and Docker Compose
- LiteLLM API key (for agent LLM access)

### 1. Clone and Setup
```bash
cd examples/web_chat_app
cp .env.example .env
# Edit .env and set your LITELLM_API_KEY
```

### 2. Start the Application
```bash
./start.sh
```

### 3. Access the Interface
- Web Interface: http://localhost:8080
- Agent Server API: http://localhost:8000

## Configuration

### Environment Variables
Create a `.env` file with the following variables:

```bash
# Required: Your LiteLLM API key
LITELLM_API_KEY=your-api-key-here

# Optional: Web interface port (default: 8080)
WEB_PORT=8080

# Optional: Agent server configuration
AGENT_SERVER_HOST=0.0.0.0
AGENT_SERVER_PORT=8000
```

### Agent Server Configuration
The agent server configuration is located in `config/agent_server_config.json`:

```json
{
  "allow_cors_origins": ["http://localhost:8080", "http://127.0.0.1:8080"],
  "conversations_path": "/app/workspace/conversations",
  "workspace_path": "/app/workspace/project",
  "webhooks": []
}
```

## Usage Guide

### Creating a New Conversation
1. Click the "New Chat" button in the sidebar
2. Optionally enter an initial message
3. Set the maximum iterations (default: 500)
4. Click "Create" to start the conversation

### Chatting with the Agent
1. Select a conversation from the sidebar
2. Type your message in the input field
3. Press Ctrl+Enter or click the send button
4. Watch real-time responses and tool executions

### Managing Conversations
- **Pause**: Temporarily stop agent execution
- **Resume**: Continue a paused conversation
- **Delete**: Permanently remove a conversation
- **Refresh**: Reload the conversation list

### Understanding Agent Events
The interface displays different types of events:
- **User Messages**: Your input messages
- **Assistant Messages**: Agent responses
- **Tool Calls**: When the agent uses tools (bash, file editor, etc.)
- **Tool Results**: Output from tool executions
- **System Events**: Agent start/stop, errors, and status changes

## Development

### Running in Development Mode
For development without Docker:

1. Start the agent server:
```bash
cd ../../
python -m openhands.agent_server --host 0.0.0.0 --port 8000
```

2. Serve the web interface:
```bash
cd examples/web_chat_app/web
python -m http.server 8080
```

3. Open http://localhost:8080/index-dev.html

### File Structure
```
web_chat_app/
├── web/                    # Frontend files
│   ├── index.html         # Main HTML (production)
│   ├── index-dev.html     # Development HTML
│   ├── styles.css         # CSS styles
│   ├── app.js            # Main JavaScript (production)
│   └── app-dev.js        # Development JavaScript
├── config/                # Configuration files
│   └── agent_server_config.json
├── workspace/             # Agent workspace
├── docker-compose.yml     # Docker orchestration
├── Dockerfile.frontend    # Frontend container
├── nginx.conf            # Nginx configuration
├── docker-entrypoint.sh  # Frontend startup script
├── start.sh              # Application startup script
└── .env.example          # Environment template
```

### API Integration
The frontend integrates with these agent server endpoints:

- `GET /conversations/search` - List conversations
- `POST /conversations` - Create new conversation
- `GET /conversations/{id}/events/search` - Get conversation history
- `POST /conversations/{id}/events` - Send message
- `POST /conversations/{id}/pause` - Pause conversation
- `POST /conversations/{id}/resume` - Resume conversation
- `DELETE /conversations/{id}` - Delete conversation
- `WebSocket /conversations/{id}/events/socket` - Real-time events

## Troubleshooting

### Common Issues

**Connection Failed**
- Ensure the agent server is running on port 8000
- Check that your LITELLM_API_KEY is valid
- Verify CORS configuration allows your frontend origin

**WebSocket Disconnections**
- Check network connectivity
- Ensure no firewall blocking WebSocket connections
- The interface will automatically attempt to reconnect

**Agent Not Responding**
- Verify your LiteLLM API key has sufficient credits
- Check agent server logs for errors
- Ensure the agent configuration includes necessary tools

**Docker Issues**
- Run `docker-compose down` and `docker-compose up --build` to rebuild
- Check Docker logs: `docker-compose logs agent-server`
- Ensure ports 8000 and 8080 are not in use by other applications

### Logs and Debugging
- Agent server logs: `docker-compose logs agent-server`
- Web server logs: `docker-compose logs web-frontend`
- Browser console: Open developer tools for JavaScript errors
- Network tab: Check API requests and WebSocket connections

## Customization

### Styling
Modify `web/styles.css` to customize the appearance:
- Color scheme variables at the top of the file
- Component-specific styles for layout changes
- Responsive breakpoints for mobile optimization

### Functionality
Extend `web/app.js` to add features:
- Additional message types and formatting
- Custom tool result displays
- Enhanced error handling
- User preferences and settings

### Agent Configuration
Modify the agent configuration in `createNewConversation()`:
- Change LLM model and parameters
- Add or remove tools
- Adjust conversation settings

## Security Considerations

### Production Deployment
- **HTTPS**: Always use HTTPS in production
- **API Keys**: Store API keys securely using environment variables
- **CORS**: Configure CORS origins restrictively
- **Rate Limiting**: Implement rate limiting for API endpoints
- **Authentication**: Add user authentication for multi-user deployments

### Development vs Production
- Development mode connects directly to agent server
- Production mode uses nginx proxy for better security and performance
- Environment-specific configurations are handled automatically

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with both development and Docker setups
5. Submit a pull request

### Development Guidelines
- Follow the existing code style and structure
- Test both Docker and development modes
- Update documentation for new features
- Ensure responsive design works on all screen sizes

## License

This example application is part of the OpenHands project and follows the same license terms.
# OpenHands Web Chat Application - Deployment Guide

This document provides detailed deployment instructions for the OpenHands Web Chat Application.

## Quick Deployment

### 1. Prerequisites
- Docker and Docker Compose installed
- LiteLLM API key

### 2. Setup
```bash
cd examples/web_chat_app
cp .env.example .env
# Edit .env and set your LITELLM_API_KEY
```

### 3. Deploy
```bash
./start.sh
```

### 4. Access
- Web Interface: http://localhost:8080
- Agent Server API: http://localhost:8000

## Deployment Options

### Option 1: Quick Start (Recommended)
Use the provided startup script:
```bash
./start.sh
```

### Option 2: Manual Docker Compose
```bash
# Set environment variables
export LITELLM_API_KEY="your-api-key-here"

# Start services
docker-compose up --build -d

# View logs
docker-compose logs -f
```

### Option 3: Development Mode
For development without Docker:
```bash
# Terminal 1: Start agent server
cd ../../
python -m openhands.agent_server --host 0.0.0.0 --port 8000

# Terminal 2: Serve web interface
cd examples/web_chat_app/web
python -m http.server 8080

# Open http://localhost:8080/index-dev.html
```

## Configuration

### Environment Variables (.env file)
```bash
# Required
LITELLM_API_KEY=your-api-key-here

# Optional
WEB_PORT=8080
AGENT_SERVER_HOST=0.0.0.0
AGENT_SERVER_PORT=8000
```

### Agent Server Configuration
Edit `config/agent_server_config.json`:
```json
{
  "allow_cors_origins": ["http://localhost:8080"],
  "conversations_path": "/agent-server/workspace/conversations",
  "workspace_path": "/agent-server/workspace/project",
  "webhooks": []
}
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Frontend  │    │  Nginx Proxy    │    │  Agent Server   │
│   (HTML/JS/CSS) │◄──►│   (Port 80)     │◄──►│   (Port 8000)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
    Static Files            API Proxy              WebSocket Events
    User Interface         CORS Headers           Conversation Data
```

## Services

### Agent Server
- **Image**: Built from `openhands/agent_server/docker/Dockerfile`
- **Port**: 8000
- **Purpose**: REST API and WebSocket server for agent interactions
- **Health Check**: `curl -f http://localhost:8000/docs`

### Web Frontend
- **Image**: Built from `Dockerfile.frontend` (nginx + static files)
- **Port**: 8080 (configurable via WEB_PORT)
- **Purpose**: Serves HTML5 interface and proxies API calls
- **Features**: Static file serving, API proxying, CORS handling

## Networking

### Port Configuration
- **8000**: Agent Server API (internal and external)
- **8080**: Web Interface (external, configurable)
- **80**: Nginx inside web-frontend container (internal)

### API Routing
- Frontend requests to `/api/*` are proxied to agent server
- WebSocket connections are upgraded and proxied
- Static files served directly by nginx

## Storage

### Volumes
- `./config:/agent-server/config:ro` - Agent server configuration (read-only)
- `./workspace:/agent-server/workspace` - Agent workspace and conversations

### Data Persistence
- Conversations stored in `./workspace/conversations/`
- Agent workspace in `./workspace/project/`
- Configuration in `./config/`

## Monitoring

### Health Checks
```bash
# Agent Server
curl http://localhost:8000/docs

# Web Frontend
curl http://localhost:8080/health
```

### Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f agent-server
docker-compose logs -f web-frontend
```

### Service Status
```bash
docker-compose ps
```

## Troubleshooting

### Common Issues

**Services won't start**
```bash
# Check if ports are in use
netstat -tulpn | grep :8000
netstat -tulpn | grep :8080

# Check Docker logs
docker-compose logs
```

**API Key Issues**
```bash
# Verify environment variable is set
docker-compose exec agent-server env | grep LITELLM_API_KEY

# Test API key manually
curl -H "Authorization: Bearer $LITELLM_API_KEY" https://api.openai.com/v1/models
```

**CORS Errors**
- Check `config/agent_server_config.json` has correct origins
- Verify web interface URL matches CORS configuration
- Clear browser cache and cookies

**WebSocket Connection Issues**
- Check browser console for WebSocket errors
- Verify agent server is running and accessible
- Test WebSocket connection manually

### Debug Commands
```bash
# Rebuild and restart
docker-compose down
docker-compose up --build

# Shell into containers
docker-compose exec agent-server bash
docker-compose exec web-frontend sh

# Check container networking
docker-compose exec web-frontend ping agent-server
```

## Production Deployment

### Security Considerations
- Use HTTPS in production
- Configure restrictive CORS origins
- Set up proper authentication
- Use environment-specific API keys
- Enable rate limiting

### Performance Optimization
- Use nginx caching for static assets
- Configure connection pooling
- Set up load balancing for multiple instances
- Monitor resource usage

### Scaling
- Use Docker Swarm or Kubernetes for orchestration
- Scale web-frontend horizontally
- Use external database for conversation storage
- Implement session affinity for WebSocket connections

## Testing

### Basic Tests
```bash
python test_basic.py
```

### Manual Testing
1. Open web interface
2. Create new conversation
3. Send test message
4. Verify real-time updates
5. Test pause/resume functionality
6. Check conversation persistence

### Integration Testing
```bash
# Test API endpoints
curl http://localhost:8000/conversations/search
curl -X POST http://localhost:8000/conversations -H "Content-Type: application/json" -d '{...}'

# Test WebSocket
# Use browser developer tools or WebSocket testing tools
```

## Maintenance

### Updates
```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose up --build -d
```

### Backup
```bash
# Backup conversations and workspace
tar -czf backup-$(date +%Y%m%d).tar.gz workspace/

# Backup configuration
cp -r config/ config-backup-$(date +%Y%m%d)/
```

### Cleanup
```bash
# Remove old containers and images
docker-compose down --rmi all --volumes --remove-orphans
docker system prune -a
```

## Support

### Documentation
- Main README: `README.md`
- Agent Server docs: `../../openhands/agent_server/README.md`
- API Documentation: http://localhost:8000/docs (when running)

### Logs Location
- Docker logs: `docker-compose logs`
- Application logs: Check container stdout/stderr
- Nginx logs: Inside web-frontend container at `/var/log/nginx/`

### Getting Help
1. Check this deployment guide
2. Review application logs
3. Test with development mode
4. Check GitHub issues and documentation
5. Create detailed bug reports with logs and configuration
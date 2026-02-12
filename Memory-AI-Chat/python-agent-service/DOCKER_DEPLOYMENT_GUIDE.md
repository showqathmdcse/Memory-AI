# Docker Deployment Guide

## ✅ Current Status - Running in Docker!

Your Python Agent Service is now running successfully in Docker with NATS streaming enabled!

```
✅ Python Agent Service - Port 8000 (running in Docker)
✅ NATS Server - Ports 4222, 8222, 6222 (running in Docker)
✅ Spring Boot Service - Port 8081 (your existing service)
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Network                          │
│                                                               │
│  ┌──────────────┐         ┌──────────────────────┐         │
│  │     NATS     │◄────────┤  Python Agent        │         │
│  │  JetStream   │         │  Service             │         │
│  │              │         │  Port: 6080 (8000)   │         │
│  │  Subjects:   │         └──────────────────────┘         │
│  │  - agent.    │                    │                      │
│  │    messages  │                    │                      │
│  │  - agent.code│                    │                      │
│  └──────────────┘                    │                      │
│         │                            │                      │
└─────────│────────────────────────────│──────────────────────┘
          │                            │
          │ (Both accessible from host)│
          ▼                            ▼
    Port 4222, 8222              Port 8000 (API)
          │                            │
          │                            │
          └────────────┬───────────────┘
                       │
                       ▼
          ┌────────────────────────┐
          │  Spring Boot Gateway   │
          │  Port 8081             │
          │  (Your existing)       │
          │                        │
          │  - Static UI           │
          │  - VS Code Extension   │
          │  - NATS Consumer       │
          └────────────────────────┘
```

## Services Information

### 1. Python Agent Service
- **Container**: `python-agent-service`
- **Image**: `agent_image:latest`
- **Host Port**: 8000 → Container Port: 6080
- **API Endpoint**: http://localhost:8000/chat
- **Health Check**: http://localhost:8000/health
- **NATS Connection**: `nats://nats:4222` (within Docker network)
- **MCP Server**: Points to `http://localhost:8081/mcp` (currently disabled)

### 2. NATS Server
- **Container**: `nats-streaming`
- **Image**: `nats:latest`
- **Ports**:
  - 4222: Client connections (NATS protocol)
  - 8222: HTTP monitoring dashboard
  - 6222: Cluster/routing connections
- **JetStream**: Enabled
- **Stream Name**: AGENT_STREAM
- **Subjects**:
  - `agent.messages.<user_id>.<chat_id>` - Chat messages and responses
  - `agent.code.<user_id>.<chat_id>` - Code changes and operations

### 3. Spring Boot Gateway (Your Service)
- **Port**: 8081
- **Role**: 
  - Serves static UI
  - Handles VS Code extension requests
  - Can subscribe to NATS streams
  - Provides MCP endpoints (when enabled)

## Quick Commands

### Start/Stop Services

```bash
# Start everything
docker-compose up -d

# Stop everything
docker-compose down

# Restart specific service
docker-compose restart agent-service
docker-compose restart nats

# Rebuild and restart
docker-compose up -d --build agent-service
```

### View Logs

```bash
# All services
docker-compose logs -f

# Python agent only
docker-compose logs -f agent-service

# NATS only
docker-compose logs -f nats

# Last 50 lines
docker-compose logs --tail=50 agent-service
```

### Check Status

```bash
# See running containers
docker-compose ps

# Check health
curl http://localhost:8000/health

# Check NATS monitoring
curl http://localhost:8222/varz
open http://localhost:8222
```

## Testing the Setup

### 1. Test Python Agent API

```bash
# Simple test
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "chat_id": "test_chat",
    "message": "Hello, are you working?"
  }'

# Should return:
# {"reply":"Yes, I'm here and ready to assist! How can I help you today?"}
```

### 2. Test NATS Streaming

Open 2 terminals:

**Terminal 1 - Subscribe to NATS stream:**
```bash
docker run --rm -it --network host natsio/nats-box:latest \
  nats sub 'agent.messages.>'
```

**Terminal 2 - Send a chat message:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "chat_id": "test_chat",
    "message": "What is 2+2?"
  }'
```

You'll see messages in Terminal 1:
```
[#1] Received on "agent.messages.test_user.test_chat"
{"type":"start","user_id":"test_user","chat_id":"test_chat",...}

[#2] Received on "agent.messages.test_user.test_chat"
{"type":"response","content":"...", ...}

[#3] Received on "agent.messages.test_user.test_chat"
{"type":"end","user_id":"test_user",...}
```

### 3. Test from Spring Boot

Your Spring Boot service can subscribe to NATS at `nats://localhost:4222`:

```java
// In your Spring Boot application
@Configuration
public class NatsConfig {
    
    @Bean
    public Connection natsConnection() throws IOException, InterruptedException {
        Options options = new Options.Builder()
            .server("nats://localhost:4222")
            .build();
        return Nats.connect(options);
    }
    
    @Bean
    public JetStream jetStream(Connection connection) throws IOException {
        return connection.jetStream();
    }
}

@Service
public class NatsConsumerService {
    
    @Autowired
    private JetStream jetStream;
    
    @PostConstruct
    public void subscribeToAgentMessages() {
        // Subscribe to all agent messages
        PushSubscribeOptions options = PushSubscribeOptions.builder()
            .stream("AGENT_STREAM")
            .build();
            
        jetStream.subscribe("agent.messages.>", (msg) -> {
            String data = new String(msg.getData());
            System.out.println("Received from NATS: " + data);
            
            // Forward to WebSocket clients in your static UI
            webSocketHandler.broadcast(data);
            
            msg.ack();
        }, false, options);
    }
}
```

## Integration with Spring Boot on Port 8081

### 1. Spring Dependencies

Add to your `pom.xml`:
```xml
<dependency>
    <groupId>io.nats</groupId>
    <artifactId>jnats</artifactId>
    <version>2.17.0</version>
</dependency>
```

### 2. NATS Configuration

`application.yml`:
```yaml
nats:
  url: nats://localhost:4222
  stream-name: AGENT_STREAM
  
server:
  port: 8081
```

### 3. Sample Consumer Service

```java
@Service
@Slf4j
public class AgentMessageConsumer {
    
    private final JetStream jetStream;
    private final SimpMessagingTemplate messagingTemplate; // For WebSocket
    
    @PostConstruct
    public void initialize() {
        subscribeToMessages();
        subscribeToCodeChanges();
    }
    
    private void subscribeToMessages() {
        try {
            PushSubscribeOptions options = PushSubscribeOptions.builder()
                .stream("AGENT_STREAM")
                .build();
                
            jetStream.subscribe("agent.messages.>", msg -> {
                String subject = msg.getSubject();
                String data = new String(msg.getData());
                
                log.info("Received message on {}: {}", subject, data);
                
                // Parse and forward to WebSocket clients
                AgentMessage agentMsg = objectMapper.readValue(data, AgentMessage.class);
                messagingTemplate.convertAndSend("/topic/agent-updates", agentMsg);
                
                msg.ack();
            }, false, options);
            
            log.info("Subscribed to agent.messages.>");
        } catch (Exception e) {
            log.error("Failed to subscribe to NATS", e);
        }
    }
    
    private void subscribeToCodeChanges() {
        try {
            PushSubscribeOptions options = PushSubscribeOptions.builder()
                .stream("AGENT_STREAM")
                .build();
                
            jetStream.subscribe("agent.code.>", msg -> {
                String data = new String(msg.getData());
                log.info("Code change received: {}", data);
                
                // Handle code changes
                CodeChange change = objectMapper.readValue(data, CodeChange.class);
                messagingTemplate.convertAndSend("/topic/code-changes", change);
                
                msg.ack();
            }, false, options);
            
            log.info("Subscribed to agent.code.>");
        } catch (Exception e) {
            log.error("Failed to subscribe to code changes", e);
        }
    }
}
```

### 4. WebSocket Configuration for Static UI

```java
@Configuration
@EnableWebSocketMessageBroker
public class WebSocketConfig implements WebSocketMessageBrokerConfigurer {
    
    @Override
    public void configureMessageBroker(MessageBrokerRegistry config) {
        config.enableSimpleBroker("/topic");
        config.setApplicationDestinationPrefixes("/app");
    }
    
    @Override
    public void registerStompEndpoints(StompEndpointRegistry registry) {
        registry.addEndpoint("/ws")
            .setAllowedOrigins("*")
            .withSockJS();
    }
}
```

### 5. Frontend JavaScript (in your Static UI)

```javascript
// Connect to WebSocket
const socket = new SockJS('http://localhost:8081/ws');
const stompClient = Stomp.over(socket);

stompClient.connect({}, function(frame) {
    console.log('Connected: ' + frame);
    
    // Subscribe to agent updates
    stompClient.subscribe('/topic/agent-updates', function(message) {
        const agentMessage = JSON.parse(message.body);
        console.log('Agent message:', agentMessage);
        
        // Update UI based on message type
        if (agentMessage.type === 'start') {
            showLoadingIndicator();
        } else if (agentMessage.type === 'response') {
            displayResponse(agentMessage.content);
        } else if (agentMessage.type === 'end') {
            hideLoadingIndicator();
        }
    });
    
    // Subscribe to code changes
    stompClient.subscribe('/topic/code-changes', function(message) {
        const codeChange = JSON.parse(message.body);
        console.log('Code change:', codeChange);
        updateCodeEditor(codeChange);
    });
});

// Send chat message
function sendChatMessage(message) {
    fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            user_id: 'ui_user',
            chat_id: 'ui_chat_' + Date.now(),
            message: message
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Direct response:', data);
        // You'll also get real-time updates via WebSocket
    });
}
```

## VS Code Extension Integration

Your VS Code extension can also subscribe to NATS for real-time updates:

```typescript
import { connect, StringCodec } from 'nats';

async function connectToNATS() {
    const nc = await connect({ servers: 'nats://localhost:4222' });
    const sc = StringCodec();
    
    // Subscribe to messages for this VS Code session
    const userId = 'vscode_user';
    const chatId = 'vscode_session_' + Date.now();
    
    const sub = nc.subscribe(`agent.messages.${userId}.${chatId}`);
    
    (async () => {
        for await (const msg of sub) {
            const data = JSON.parse(sc.decode(msg.data));
            console.log('Received from agent:', data);
            
            // Update VS Code UI
            if (data.type === 'response') {
                vscode.window.showInformationMessage(data.content);
            } else if (data.type === 'code') {
                // Apply code changes
                applyCodeChange(data);
            }
        }
    })();
    
    return { connection: nc, userId, chatId };
}
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs agent-service

# Restart everything
docker-compose down
docker-compose up -d --build

# Check Docker resources
docker system df
docker system prune -f  # Clean up if needed
```

### NATS Connection Issues

```bash
# Check NATS is running
docker-compose ps nats

# Test NATS connection
docker run --rm --network host natsio/nats-box:latest nats-box -s localhost:4222 server info

# Check NATS logs
docker-compose logs nats
```

### API Returns 500 Error

```bash
# Check application logs
docker-compose logs --tail=100 agent-service

# Check environment variables are loaded
docker-compose exec agent-service env | grep AZURE

# Verify .env file
cat .env
```

### Spring Can't Connect to NATS

```bash
# Verify NATS is accessible from host
telnet localhost 4222

# Check NATS connection from Spring logs
# Make sure using localhost:4222, not nats:4222
```

## Logs Location

### Docker Logs
```bash
# Via docker-compose
docker-compose logs -f agent-service

# Via docker directly
docker logs -f python-agent-service
```

### Application Logs (Mounted)
```bash
# The server.log is mounted to host
tail -f server.log

# Location in container
docker-compose exec agent-service cat /app/server.log
```

## Environment Variables

All configured in `.env` file:

```bash
# Python Agent Service (Port 8000)
HOST=0.0.0.0
PORT=8000  # Exposed as 8000 on host, runs as 6080 in container
LOG_LEVEL=DEBUG

# NATS Streaming
NATS_STREAMING_ENABLED=true
NATS_URL=nats://localhost:4222  # For local Spring service
# (In container it uses nats://nats:4222)

# MCP Configuration
MCP_ENABLED=false
MCP_SERVER_URL=http://localhost:8081/mcp  # Your Spring service
```

## Production Considerations

### 1. Remove Debug Logging
```bash
# In .env
LOG_LEVEL=INFO
```

### 2. Add Resource Limits

Update `docker-compose.yml`:
```yaml
agent-service:
  # ... other config ...
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '1'
        memory: 1G
```

### 3. Persist NATS Data
Already configured with volume:
```yaml
volumes:
  nats-data:/data
```

### 4. Enable MCP
When ready to use MCP tools:
```bash
# In .env
MCP_ENABLED=true
MCP_SERVER_URL=http://host.docker.internal:8081/mcp  # For Docker
# or
MCP_SERVER_URL=http://localhost:8081/mcp  # For local
```

## Summary

✅ **Python Agent Service** runs on port 8000 with NATS streaming enabled
✅ **NATS Server** handles real-time message streaming
✅ **Spring Boot Service** on port 8081 can subscribe to NATS streams
✅ **Static UI** gets real-time updates via WebSocket from Spring
✅ **VS Code Extension** can also subscribe to NATS

All services can communicate through NATS for real-time agent updates! 🚀
